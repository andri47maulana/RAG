import openai
import os

openai.api_key = os.getenv('OPENAI_API_KEY')

# Fungsi untuk mendapatkan embedding dari OpenAI

def get_embedding(text, model="text-embedding-3-small"):
    response = openai.embeddings.create(
        model=model,
        input=text
    )
    return response.data[0].embedding
