# lambdas/matrix_factorization/handler.py
import json
import boto3
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import svds
import pickle
import base64

s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

def train_collaborative_filtering(event, context):
    """Train matrix factorization model"""
    
    users_table = dynamodb.Table('movie-rec-users')
    
    # Build user-item matrix
    response = users_table.scan()
    users_data = response['Items']
    
    # Create ratings matrix
    user_ids = []
    movie_ids = []
    ratings = []
    
    user_id_map = {}
    movie_id_map = {}
    
    for user in users_data:
        user_idx = user_id_map.setdefault(user['userId'], len(user_id_map))
        
        for movie_id, rating in zip(user['movieIds'], user['ratings']):
            movie_idx = movie_id_map.setdefault(movie_id, len(movie_id_map))
            
            user_ids.append(user_idx)
            movie_ids.append(movie_idx)
            ratings.append(rating)
    
    # Create sparse matrix
    n_users = len(user_id_map)
    n_movies = len(movie_id_map)
    
    ratings_matrix = csr_matrix(
        (ratings, (user_ids, movie_ids)),
        shape=(n_users, n_movies)
    )
    
    # Perform SVD
    k = min(50, min(n_users, n_movies) - 1)  # Latent factors
    U, sigma, Vt = svds(ratings_matrix, k=k)
    
    # Diagonal matrix of singular values
    sigma = np.diag(sigma)
    
    # Calculate predicted ratings
    predicted_ratings = np.dot(np.dot(U, sigma), Vt)
    
    # Save model to S3
    model_data = {
        'U': U.tolist(),
        'sigma': sigma.tolist(),
        'Vt': Vt.tolist(),
        'user_id_map': user_id_map,
        'movie_id_map': movie_id_map,
        'predicted_ratings': predicted_ratings.tolist()
    }
    
    # Compress to stay within Lambda limits
    model_json = json.dumps(model_data)
    model_bytes = model_json.encode('utf-8')
    
    s3_client.put_object(
        Bucket='movie-rec-models',
        Key='cf_model.json',
        Body=model_bytes,
        ContentType='application/json'
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps(f'Model trained: {n_users} users, {n_movies} movies')
    }