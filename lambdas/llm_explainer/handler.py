# lambdas/llm_explainer/handler.py
import json
import boto3
import os
import requests
from typing import List, Dict

dynamodb = boto3.resource('dynamodb')
bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')

class LLMExplainer:
    def __init__(self):
        # Option 1: Amazon Bedrock (if available in free tier/trial)
        self.use_bedrock = os.environ.get('USE_BEDROCK', 'false').lower() == 'true'
        
        # Option 2: External free APIs
        self.hf_token = os.environ.get('HF_API_TOKEN', '')
        self.cohere_key = os.environ.get('COHERE_API_KEY', '')
        
    def generate_explanation(self, user_profile: Dict, 
                            movie: Dict, 
                            similar_movies: List[Dict]) -> str:
        """Generate personalized explanation for recommendation"""
        
        prompt = self._build_prompt(user_profile, movie, similar_movies)
        
        if self.use_bedrock:
            return self._bedrock_explanation(prompt, user_profile, movie)
        elif self.hf_token:
            return self._huggingface_explanation(prompt, user_profile, movie)
        elif self.cohere_key:
            return self._cohere_explanation(prompt, user_profile, movie)
        else:
            return self._rule_based_explanation(user_profile, movie)
    
    def _bedrock_explanation(self, prompt: str, user_profile: Dict, movie: Dict) -> str:
        """Use Amazon Bedrock Claude Instant"""
        try:
            response = bedrock_runtime.invoke_model(
                modelId='anthropic.claude-instant-v1',
                contentType='application/json',
                accept='application/json',
                body=json.dumps({
                    'prompt': f"\n\nHuman: {prompt}\n\nAssistant:",
                    'max_tokens_to_sample': 150,
                    'temperature': 0.7,
                    'top_p': 0.9
                })
            )
            
            response_body = json.loads(response['body'].read())
            return response_body.get('completion', '').strip()
            
        except Exception as e:
            print(f"Bedrock error: {e}")
            return self._rule_based_explanation(user_profile, movie)
    
    def _huggingface_explanation(self, prompt: str, user_profile: Dict, movie: Dict) -> str:
        """Use Hugging Face Inference API (free tier)"""
        
        headers = {"Authorization": f"Bearer {self.hf_token}"}
        
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 150,
                "temperature": 0.7,
                "do_sample": True,
                "top_p": 0.9
            }
        }
        
        # Use smaller model for better free tier performance
        model = "google/flan-t5-base"
        try:
            response = requests.post(
                f"https://api-inference.huggingface.co/models/{model}",
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                return result[0]['generated_text'] if isinstance(result, list) else result.get('generated_text', '')
        except Exception as e:
            print(f"HuggingFace error: {e}")
        
        return self._rule_based_explanation(user_profile, movie)
    
    def _cohere_explanation(self, prompt: str, user_profile: Dict, movie: Dict) -> str:
        """Use Cohere API (1000 free calls/month)"""
        
        headers = {
            "Authorization": f"Bearer {self.cohere_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "command-nightly",
            "prompt": prompt,
            "max_tokens": 150,
            "temperature": 0.7,
            "p": 0.9
        }
        
        try:
            response = requests.post(
                "https://api.cohere.ai/v1/generate",
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()['generations'][0]['text']
        except Exception as e:
            print(f"Cohere error: {e}")
        
        return self._rule_based_explanation(user_profile, movie)
    
    def _build_prompt(self, user_profile: Dict, movie: Dict, similar_movies: List[Dict]) -> str:
        """Build prompt for LLM"""
        
        avg_rating = float(user_profile.get('avgRating', 3.5))
        genres = ', '.join(movie.get('genres', ['Drama']))
        similar_titles = ', '.join([m['title'] for m in similar_movies[:3]]) if similar_movies else 'various films'
        
        prompt = f"""Generate a brief, personalized movie recommendation explanation.

User preferences:
- Average rating: {avg_rating:.1f}/5
- Number of movies rated: {user_profile.get('totalRatings', 0)}
- Similar movies watched: {similar_titles}

Recommended movie: {movie['title']}
Genres: {genres}

Write 2-3 sentences explaining why this specific movie matches the user's taste, referencing their viewing history.

Explanation:"""
        
        return prompt
    
    def _rule_based_explanation(self, user_profile: Dict, movie: Dict) -> str:
        """Fallback rule-based explanation"""
        genres = movie.get('genres', [])
        genre_text = genres[0].lower() if genres else 'this type of'
        avg_rating = float(user_profile.get('avgRating', 3.5))
        
        if avg_rating >= 4:
            preference = "highly rated"
        elif avg_rating >= 3:
            preference = "enjoyed"
        else:
            preference = "watched"
        
        return f"Based on your viewing history, you've {preference} {genre_text} films. "\
               f"{movie['title']} combines elements from movies you've rated highly, "\
               f"making it an excellent match for your preferences."

def find_similar_watched_movies(user_profile: Dict, movie_id: str) -> List[Dict]:
    """Find similar movies the user has watched"""
    # Placeholder implementation - you can enhance this later
    # For now, return empty list or basic logic
    watched_movies = user_profile.get('watchedMovies', [])
    
    # Return up to 3 movies from user's history
    similar = []
    for movie_data in watched_movies[:3]:
        if isinstance(movie_data, dict):
            similar.append(movie_data)
    
    return similar

def generate_recommendation_explanation(event, context):
    """Lambda handler for generating explanations"""
    
    body = json.loads(event['body'])
    user_id = body['userId']
    movie_id = body['movieId']
    
    # Fetch user profile
    users_table = dynamodb.Table('movie-rec-users')
    user_response = users_table.get_item(Key={'userId': user_id})
    
    if 'Item' not in user_response:
        return {
            'statusCode': 404,
            'body': json.dumps({'error': 'User not found'})
        }
    
    user_profile = user_response['Item']
    
    # Fetch movie details
    movies_table = dynamodb.Table('movie-rec-movies')
    movie_response = movies_table.get_item(Key={'movieId': movie_id})
    
    if 'Item' not in movie_response:
        return {
            'statusCode': 404,
            'body': json.dumps({'error': 'Movie not found'})
        }
    
    movie = movie_response['Item']
    
    # Find similar movies the user has watched
    similar_movies = find_similar_watched_movies(user_profile, movie_id)
    
    # Generate explanation
    explainer = LLMExplainer()
    explanation = explainer.generate_explanation(user_profile, movie, similar_movies)
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'movieId': movie_id,
            'explanation': explanation
        })
    }