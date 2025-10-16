import os
import requests

# Fungsi untuk mendapatkan embedding dari OpenAI tanpa SDK (pakai HTTP langsung)
def get_embedding(text, model="text-embedding-3-small"):
    # Ambil API key dari environment untuk menghindari kebocoran rahasia di repo
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY belum diset di environment.")

    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com")
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': model,
        'input': text
    }
    resp = requests.post(f'{base_url}/v1/embeddings', headers=headers, json=payload, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"OpenAI Embedding API error: {resp.text}")
    data = resp.json()
    return data['data'][0]['embedding']
