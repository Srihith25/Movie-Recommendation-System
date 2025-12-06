import json
import boto3
import random
from decimal import Decimal

dynamodb = boto3.resource('dynamodb', region_name='us-east-2')

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)

def lambda_handler(event, context):
    """Simple recommendation endpoint for testing"""
    
    # Get userId from path
    user_id = event.get('pathParameters', {}).get('userId', '1')
    
    # Get movies from database
    movies_table = dynamodb.Table('movie-rec-movies')
    response = movies_table.scan(Limit=10)
    movies = response.get('Items', [])
    
    # Create mock recommendations
    recommendations = []
    for movie in movies[:10]:
        recommendations.append({
            'movieId': movie.get('movieId', '0'),
            'title': movie.get('title', 'Unknown Movie'),
            'genres': movie.get('genres', ['Drama']),
            'score': random.uniform(0.7, 0.95),
            'explanation': f"Recommended because you enjoy {movie.get('genres', ['Drama'])[0].lower()} films with compelling narratives."
        })
    
    # Sort by score
    recommendations.sort(key=lambda x: x['score'], reverse=True)
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(recommendations, cls=DecimalEncoder)
    }