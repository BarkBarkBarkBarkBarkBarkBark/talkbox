# Import necessary libraries
import csv
import pandas as pd
from sentence_transformers import SentenceTransformer

# Load the embedding model
model = SentenceTransformer('mixedbread-ai/mxbai-embed-large-v1')

# Function to preprocess CSV and generate embeddings
def process_csv(file_path):
    texts = []
    embeddings = []
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # Pair column headers with their values
            paired_text = ' '.join([f"{header}: {value}" for header, value in row.items()])
            texts.append(paired_text)
            # Generate embedding for the paired text
            embedding = model.encode(paired_text)
            embeddings.append(embedding)
    return texts, embeddings

# Function to save embeddings to a CSV file
def save_embeddings_to_csv(texts, embeddings, output_file):
    # Create a DataFrame with texts and their corresponding embeddings
    df = pd.DataFrame({
        'Text': texts,
        'Embedding': [embedding.tolist() for embedding in embeddings]  # Convert numpy arrays to lists
    })
    # Save the DataFrame to a CSV file
    df.to_csv(output_file, index=False)
    print(f"Embeddings have been saved to {output_file}")

# Example usage
input_file_path = '/Users/marco/Desktop/NOA Purchases Amazon.csv'
output_file_path = '/Users/marco/Desktop/embeddings_output.csv'
texts, embeddings = process_csv(input_file_path)
save_embeddings_to_csv(texts, embeddings, output_file_path)
