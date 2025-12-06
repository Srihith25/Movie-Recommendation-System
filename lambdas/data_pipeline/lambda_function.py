import json
import boto3
import pandas as pd
import numpy as np
from datetime import datetime
import urllib.request
import io

dynamodb = boto3.resource('dynamodb', region_name='us-east-2')

def lambda_handler(event, context):
    """Load MovieLens data into DynamoDB"""
    
    print("Starting data load...")
    
    # Download MovieLens 100k data
    ratings_url = "https://files.grouplens.org/datasets/movielens/ml-100k/u.data"
    movies_url = "https://files.grouplens.org/datasets/movielens/ml-100k/u.item"
    
    # Load ratings
    with urllib.request.urlopen(ratings_url) as response:
        ratings_data = response.read().decode('utf-8')
    
    ratings_df = pd.read_csv(
        io.StringIO(ratings_data),
        sep='\t',
        names=['user_id', 'movie_id', 'rating', 'timestamp'],
        nrows=1000  # Limit for testing
    )
    
    # Load movies
    with urllib.request.urlopen(movies_url) as response:
        movies_data = response.read().decode('latin-1')
    
    movies_df = pd.read_csv(
        io.StringIO(movies_data),
        sep='|',
        names=['movie_id', 'title', 'release_date', 'video_release', 'imdb_url'] + 
               [f'genre_{i}' for i in range(19)],
        nrows=100  # Limit for testing
    )
    
    # Process users
    users_table = dynamodb.Table('movie-rec-users')
    user_data = ratings_df.groupby('user_id').agg({
        'movie_id': list,
        'rating': list
    }).reset_index()
    
    with users_table.batch_writer() as batch:
        for _, user in user_data.head(10).iterrows():  # First 10 users for testing
            batch.put_item(Item={
                'userId': str(user['user_id']),
                'movieIds': [str(m) for m in user['movie_id']],
                'ratings': [float(r) for r in user['rating']],
                'avgRating': float(np.mean(user['rating'])),
                'totalRatings': len(user['rating'])
            })
    
    # Process movies
    movies_table = dynamodb.Table('movie-rec-movies')
    genre_names = ['Action', 'Adventure', 'Animation', 'Children', 'Comedy',
                   'Crime', 'Documentary', 'Drama', 'Fantasy', 'Film-Noir',
                   'Horror', 'Musical', 'Mystery', 'Romance', 'Sci-Fi',
                   'Thriller', 'War', 'Western', 'Unknown']
    
    with movies_table.batch_writer() as batch:
        for _, movie in movies_df.head(20).iterrows():  # First 20 movies for testing
            genres = [genre_names[i] for i in range(19) if movie[f'genre_{i}'] == 1]
            
            batch.put_item(Item={
                'movieId': str(int(movie['movie_id'])),
                'title': movie['title'],
                'genres': genres if genres else ['Unknown']
            })
    
    return {
        'statusCode': 200,
        'body': json.dumps('Data loaded successfully!')
    }