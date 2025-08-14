
import sys, json, pickle, os
import faiss
import numpy as np
import requests
from dotenv import load_dotenv

# Use absolute path based on script location
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
THREADS_DIR = os.path.join(BASE_DIR, 'threads')
os.makedirs(THREADS_DIR, exist_ok=True)



def get_index_and_meta_file(category: str = 'teknologi'):
    # Map kategori ke nama file
    index_file = os.path.join(BASE_DIR, '..', 'uploader', 'vector', f'index_{category}.faiss')
    meta_file = os.path.join(BASE_DIR, '..', 'uploader', 'vector', f'meta_{category}.pkl')
    return index_file, meta_file

def search(vector, top_k=3, category='teknologi'):
    index_file, meta_file = get_index_and_meta_file(category)
    index = faiss.read_index(index_file)
    with open(meta_file, 'rb') as f:
        metas = pickle.load(f)
    # Debug: print dimensi vector dan index
    import sys
    print(f"VECTOR DIM: {len(vector)} INDEX DIM: {index.d}", file=sys.stderr)
    print(f"index_file: {index_file}, meta_file: {meta_file}", file=sys.stderr)
    D, I = index.search(np.array([vector]).astype('float32'), top_k)
    res = []
    for idx in I[0]:
        if idx < len(metas):
            res.append(metas[idx])
    return res

def load_thread(user_id, thread_id):
    path = os.path.join(THREADS_DIR, f'{user_id}_{thread_id}.json')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_thread(user_id, thread_id, memory):
    path = os.path.join(THREADS_DIR, f'{user_id}_{thread_id}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)



if __name__ == '__main__':
    # Load .env dari folder uploader
    load_dotenv(os.path.join(BASE_DIR, '..', 'uploader', '.env'))
    data = json.load(sys.stdin)
    vector = data.get('vector', None)
    top_k = data.get('top_k', 3)
    user_id = data.get('user_id', 'default')
    thread_id = data.get('thread_id', 'default')
    question = data.get('question', None)
    category = data.get('category', 'teknologi')

    # Load memory thread
    memory = load_thread(user_id, thread_id)

    # --- BEST PRACTICE: DETEKSI PERTANYAAN LANJUTAN ---
    is_followup = False
    prev_llm_answer = None
    if question and len(memory) > 0:
        prev_entry = memory[-1]
        prev_llm_answer = prev_entry.get('a')
        is_followup = True

    # --- BEST PRACTICE: REPHRASE PERTANYAAN LANJUTAN (jika ada API key) ---
    rephrased_question = question
    openai_api_key = os.environ.get('OPENAI_API_KEY')
    if is_followup and prev_llm_answer and openai_api_key:
        headers = {
            'Authorization': f'Bearer {openai_api_key}',
            'Content-Type': 'application/json'
        }
        rephrase_prompt = f"Buat ulang pertanyaan berikut agar lebih spesifik berdasarkan jawaban sebelumnya.\n\nJawaban sebelumnya: {prev_llm_answer}\n\nPertanyaan baru: {question}\n\nPertanyaan spesifik:"
        chat_payload = {
            'model': 'gpt-4',
            'messages': [
                {"role": "system", "content": "Anda adalah asisten AI yang membantu membuat ulang pertanyaan agar lebih spesifik berdasarkan jawaban sebelumnya."},
                {"role": "user", "content": rephrase_prompt}
            ],
            'max_tokens': 128,
            'temperature': 0.2
        }
        resp = requests.post('https://api.openai.com/v1/chat/completions', headers=headers, json=chat_payload)
        if resp.status_code == 200:
            rephrased_question = resp.json()['choices'][0]['message']['content'].strip()
        else:
            rephrased_question = question + " (catatan: gagal rephrase)"

    # --- EMBEDDING ---
    if vector is None and rephrased_question:
        if not openai_api_key:
            print(json.dumps({'error': 'OPENAI_API_KEY environment variable not set'}))
            sys.exit(1)
        headers = {
            'Authorization': f'Bearer {openai_api_key}',
            'Content-Type': 'application/json'
        }
        embed_payload = {
            'input': rephrased_question,
            'model': 'text-embedding-3-small'
        }
        resp = requests.post('https://api.openai.com/v1/embeddings', headers=headers, json=embed_payload)
        if resp.status_code != 200:
            print(json.dumps({'error': 'OpenAI API error', 'details': resp.text}))
            sys.exit(1)
        vector = resp.json()['data'][0]['embedding']

    # Simpan pertanyaan (dan rephrase jika follow-up) ke memory
    if question:
        mem_entry = {'q': question}
        if is_followup:
            mem_entry['rephrased'] = rephrased_question
        memory.append(mem_entry)

    # --- FAISS SEARCH ---
    try:
        results = search(vector, top_k, category=category)
        error = ""
    except Exception as e:
        results = []
        error = str(e)

    # --- CONTEXT DARI FAISS ---
    if results and isinstance(results[0], dict) and 'text' in results[0]:
        context = '\n\n---\n\n'.join([r['text'] for r in results if 'text' in r])
    else:
        context = '\n\n---\n\n'.join([str(r) for r in results])

    # --- LLM NARASI (jika ada API key) ---
    llm_answer = None
    if rephrased_question and openai_api_key:
        prompt = f"Jawablah pertanyaan berikut hanya berdasarkan context di bawah ini. Jika tidak ada jawaban di context, jawab 'Maaf, tidak ditemukan jawaban yang relevan.'\n\nContext:\n{context}\n\nPertanyaan:\n{rephrased_question}\n\nJawaban:"
        headers = {
            'Authorization': f'Bearer {openai_api_key}',
            'Content-Type': 'application/json'
        }
        chat_payload = {
            'model': 'gpt-4',
            'messages': [
                {"role": "system", "content": "Anda adalah asisten AI yang hanya boleh menjawab berdasarkan context yang diberikan."},
                {"role": "user", "content": prompt}
            ],
            'max_tokens': 512,
            'temperature': 0.2
        }
        resp = requests.post('https://api.openai.com/v1/chat/completions', headers=headers, json=chat_payload)
        if resp.status_code == 200:
            llm_answer = resp.json()['choices'][0]['message']['content'].strip()
        else:
            llm_answer = f"[OpenAI API error: {resp.text}]"

        # Simpan jawaban LLM ke memory
        memory[-1]['a'] = llm_answer
        memory[-1]['context'] = context
        save_thread(user_id, thread_id, memory)
    else:
        # Simpan context dan jawaban FAISS saja jika tidak ada LLM
        if question:
            memory[-1]['a'] = context
            memory[-1]['context'] = context
            save_thread(user_id, thread_id, memory)

    print(json.dumps({
        'results': results,
        'context': context,
        'llm_answer': llm_answer,
        'memory': memory,
        'error': error
    }))
