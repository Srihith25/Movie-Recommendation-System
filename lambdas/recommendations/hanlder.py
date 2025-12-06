# lambdas/recommendations/handler.py
import json
import boto3
import numpy as np
from typing import List, Dict, Tuple
from decimal import Decimal
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def get_recommendations(event, context):
    """Main recommendation endpoint"""
    
    # Get user ID from path parameters
    user_id = event['pathParameters']['userId']
    
    # Check cache first (using DynamoDB TTL)
    cache_table = dynamodb.Table('movie-rec-cache')
    
    try:
        cached = cache_table.get_item(Key={'cacheKey': f'rec_{user_id}'})
        if 'Item' in cached:
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': cached['Item']['recommendations']
            }
    except:
        pass  # Cache miss, generate recommendations
    
    # Get user profile
    users_table = dynamodb.Table('movie-rec-users')
    user_response = users_table.get_item(Key={'userId': user_id})
    
    if 'Item' not in user_response:
        return {
            'statusCode': 404,
            'body': json.dumps({'error': 'User not found'})
        }
    
    user_profile = user_response['Item']
    
    # Get collaborative filtering recommendations
    cf_recommendations = get_cf_recommendations(user_id, user_profile)
    
    # Get content-based recommendations using embeddings
    cb_recommendations = get_content_recommendations(user_profile)
    
    # Hybrid ranking
    hybrid_recommendations = hybrid_rank(cf_recommendations, cb_recommendations)
    
    # Generate explanations for top 10
    final_recommendations = []
    
    for movie_id, score in hybrid_recommendations[:10]:
        # Get movie details
        movies_table = dynamodb.Table('movie-rec-movies')
        movie = movies_table.get_item(Key={'movieId': movie_id})['Item']
        
        # Generate explanation asynchronously
        explanation = generate_explanation_async(user_id, movie_id, user_profile, movie)
        
        final_recommendations.append({
            'movieId': movie_id,
            'title': movie['title'],
            'genres': movie.get('genres', []),
            'score': float(score),
            'explanation': explanation
        })
    
    # Cache results (1 hour TTL)
    cache_response = json.dumps(final_recommendations, cls=DecimalEncoder)
    
    try:
        cache_table.put_item(Item={
            'cacheKey': f'rec_{user_id}',
            'recommendations': cache_response,
            'ttl': int(datetime.utcnow().timestamp()) + 3600
        })
    except:
        pass  # Cache write failure shouldn't affect response
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': cache_response
    }

def get_cf_recommendations(user_id: str, user_profile: Dict) -> List[Tuple[str, float]]:
    """Get collaborative filtering recommendations"""
    
    # Load CF model from S3
    response = s3_client.get_object(Bucket='movie-rec-models', Key='cf_model.json')
    model_data = json.loads(response['Body'].read())
    
    # Get user index
    user_id_map = model_data['user_id_map']
    if user_id not in user_id_map:
        return []
    
    user_idx = user_id_map[user_id]
    movie_id_map = model_data['movie_id_map']
    predicted_ratings = np.array(model_data['predicted_ratings'])
    
    # Get predictions for this user
    user_predictions = predicted_ratings[user_idx]
    
    # Filter out already watched movies
    watched_movies = set(user_profile.get('movieIds', []))
    
    recommendations = []
    reverse_movie_map = {v: k for k, v in movie_id_map.items()}
    
    for movie_idx, rating in enumerate(user_predictions):
        movie_id = reverse_movie_map.get(movie_idx)
        if movie_id and movie_id not in watched_movies:
            recommendations.append((movie_id, float(rating)))
    
    # Sort by predicted rating
    recommendations.sort(key=lambda x: x[1], reverse=True)
    
    return recommendations[:100]  # Top 100 candidates

def get_content_recommendations(user_profile: Dict) -> List[Tuple[str, float]]:
    """Get content-based recommendations using embeddings"""
    
    embeddings_table = dynamodb.Table('movie-rec-embeddings')
    
    # Calculate user preference embedding (average of highly rated movies)
    watched_movies = user_profile.get('movieIds', [])
    ratings = user_profile.get('ratings', [])
    
    if not watched_movies:
        return []
    
    # Get embeddings for highly rated movies
    high_rated = []
    for movie_id, rating in zip(watched_movies, ratings):
        if float(rating) >= 4.0:
            try:
                response = embeddings_table.get_item(Key={'movieId': movie_id})
                if 'Item' in response:
                    high_rated.append(np.array(response['Item']['embedding']))
            except:
                continue
    
    if not high_rated:
        return []
    
    # Calculate average preference embedding
    user_embedding = np.mean(high_rated, axis=0)
    user_embedding = user_embedding / np.linalg.norm(user_embedding)
    
    # Scan all movies and calculate similarities (in production, use vector DB)
    response = embeddings_table.scan()
    all_embeddings = response['Items']
    
    similarities = []
    watched_set = set(watched_movies)
    
    for item in all_embeddings:
        movie_id = item['movieId']
        if movie_id not in watched_set:
            movie_embedding = np.array(item['embedding'])
            similarity = np.dot(user_embedding, movie_embedding)
            similarities.append((movie_id, float(similarity)))
    
    # Sort by similarity
    similarities.sort(key=lambda x: x[1], reverse=True)
    
    return similarities[:100]

def hybrid_rank(cf_recs: List[Tuple[str, float]], 
                cb_recs: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
    """Combine CF and CB recommendations"""
    
    # Normalize scores
    cf_dict = {movie_id: score for movie_id, score in cf_recs}
    cb_dict = {movie_id: score for movie_id, score in cb_recs}
    
    all_movies = set(cf_dict.keys()) | set(cb_dict.keys())
    
    hybrid_scores = []
    cf_weight = 0.6
    cb_weight = 0.4
    
    for movie_id in all_movies:
        cf_score = cf_dict.get(movie_id, 0)
        cb_score = cb_dict.get(movie_id, 0)
        
        # Normalize scores to [0, 1]
        cf_norm = cf_score / 5.0 if cf_score > 0 else 0
        cb_norm = (cb_score + 1) / 2.0  # Cosine similarity is [-1, 1]
        
        hybrid_score = cf_weight * cf_norm + cb_weight * cb_norm
        hybrid_scores.append((movie_id, hybrid_score))
    
    hybrid_scores.sort(key=lambda x: x[1], reverse=True)
    
    return hybrid_scores

def generate_explanation_async(user_id: str, movie_id: str, 
                              user_profile: Dict, movie: Dict) -> str:
    """Invoke explanation Lambda asynchronously"""
    
    try:
        response = lambda_client.invoke(
            FunctionName='movie-rec-llm-explainer',
            InvocationType='RequestResponse',  # Synchronous for now
            Payload=json.dumps({
                'body': json.dumps({
                    'userId': user_id,
                    'movieId': movie_id
                })
            })
        )
        
        result = json.loads(response['Payload'].read())
        body = json.loads(result['body'])
        return body.get('explanation', 'Recommended based on your preferences.')
        
    except Exception as e:
        print(f"Explanation generation failed: {e}")
        # Fallback explanation
        genres = movie.get('genres', [])
        return f"Recommended because you enjoy {genres[0].lower() if genres else 'similar'} films."