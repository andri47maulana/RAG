import os
import requests

# Fungsi untuk mendapatkan embedding dari OpenAI tanpa SDK (pakai HTTP langsung)
def get_embedding(text, model="text-embedding-3-small"):
    api_key = "REDACTED"
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY belum diset di environment.")

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': model,
        'input': text
    }
    resp = requests.post('https://api.openai.com/v1/embeddings', headers=headers, json=payload, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"OpenAI Embedding API error: {resp.text}")
    data = resp.json()
    return data['data'][0]['embedding']
