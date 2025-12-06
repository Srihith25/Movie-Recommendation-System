# lambdas/embeddings/handler.py
import json
import boto3
import numpy as np
from typing import List, Dict
from datetime import datetime
import torch

# For Lambda layer - use smaller model for free tier
from transformers import AutoTokenizer, AutoModel

dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')

# Initialize model (load once during cold start)
model_name = 'sentence-transformers/all-MiniLM-L6-v2'
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModel.from_pretrained(model_name)

def generate_embeddings(event, context):
    """Generate embeddings for movies using lightweight model"""
    
    movies_table = dynamodb.Table('movie-rec-movies')
    embeddings_table = dynamodb.Table('movie-rec-embeddings')
    
    # Scan movies (paginate for large datasets)
    response = movies_table.scan()
    movies = response['Items']
    
    batch_size = 25  # Process in batches to avoid timeout
    
    with embeddings_table.batch_writer() as batch:
        for i in range(0, len(movies), batch_size):
            movie_batch = movies[i:i+batch_size]
            
            for movie in movie_batch:
                # Create text representation
                text = f"{movie['title']} {' '.join(movie.get('genres', []))}"
                
                # Generate embedding
                embedding = generate_embedding(text)
                
                # Store as binary to save space (DynamoDB free tier is 25GB)
                batch.put_item(Item={
                    'movieId': movie['movieId'],
                    'embedding': embedding.tolist(),  # Convert to list for JSON
                    'embeddingDim': len(embedding),
                    'model': model_name,
                    'timestamp': datetime.utcnow().isoformat()
                })
    
    return {
        'statusCode': 200,
        'body': json.dumps(f'Generated embeddings for {len(movies)} movies')
    }

def generate_embedding(text: str) -> np.ndarray:
    """Generate embedding for text using transformer model"""
    
    # Tokenize
    inputs = tokenizer(text, padding=True, truncation=True, return_tensors='pt')
    
    # Generate embedding
    with torch.no_grad():
        outputs = model(**inputs)
        embedding = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()
    
    # Normalize
    embedding = embedding / np.linalg.norm(embedding)
    
    return embedding