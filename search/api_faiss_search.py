from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import faiss_search_v2

app = FastAPI()


class SearchRequest(BaseModel):
    question: Optional[str] = None
    vector: Optional[list] = None
    top_k: Optional[int] = 3
    user_id: Optional[str] = "default"
    thread_id: Optional[str] = "default"
    category: Optional[str] = "teknologi"
    security_api_key: Optional[str] = None


@app.post("/search")
def search_endpoint(request: SearchRequest):
    import os
    # --- SECURITY API KEY CHECK ---
    SECURITY_API_KEY = os.environ.get('SECURITY_API_KEY')
    if SECURITY_API_KEY:
        if request.security_api_key != SECURITY_API_KEY:
            from fastapi import status
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": "Unauthorized: Invalid security_api_key"})
    # Log seluruh request body dan parameter penting
    print("[LOG] Incoming request:")
    try:
        import json as _json
        print(_json.dumps(request.dict(), indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"[LOG] Gagal print request body: {e}")
    import os
    import requests
    import json
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'uploader', '.env'))


    vector = request.vector
    top_k = request.top_k or 3
    user_id = request.user_id or "default"
    thread_id = request.thread_id or "default"
    question = request.question
    category = request.category or "teknologi"

    # Load memory thread
    memory = faiss_search_v2.load_thread(user_id, thread_id)

    # --- BEST PRACTICE: DETEKSI PERTANYAAN LANJUTAN ---
    is_followup = False
    prev_llm_answer = None
    if question and len(memory) > 0:
        # Deteksi sederhana: jika ada pertanyaan sebelumnya, anggap follow-up
        prev_entry = memory[-1]
        prev_llm_answer = prev_entry.get('a')
        is_followup = True

    # --- BEST PRACTICE: REPHRASE PERTANYAAN LANJUTAN ---
    rephrased_question = question
    if is_followup and prev_llm_answer:
        openai_api_key = os.environ.get('OPENAI_API_KEY')
        if not openai_api_key:
            raise HTTPException(status_code=500, detail='OPENAI_API_KEY environment variable not set')
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
        openai_api_key = os.environ.get('OPENAI_API_KEY')
        if not openai_api_key:
            raise HTTPException(status_code=500, detail='OPENAI_API_KEY environment variable not set')
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
            raise HTTPException(status_code=500, detail=f'OpenAI API error: {resp.text}')
        vector = resp.json()['data'][0]['embedding']

    # Simpan pertanyaan (dan rephrase jika follow-up) ke memory
    if question:
        mem_entry = {'q': question}
        if is_followup:
            mem_entry['rephrased'] = rephrased_question
        memory.append(mem_entry)

    # --- FAISS SEARCH ---
    try:
        results = faiss_search_v2.search(vector, top_k, category=category)
        error = ""
    except Exception as e:
        results = []
        error = str(e)

    # --- CONTEXT DARI FAISS ---
    if results and isinstance(results[0], dict) and 'text' in results[0]:
        context = '\n\n---\n\n'.join([r['text'] for r in results if 'text' in r])
    else:
        context = '\n\n---\n\n'.join([str(r) for r in results])

    # --- LLM NARASI ---
    llm_answer = None
    if rephrased_question:
        prompt = f"Jawablah pertanyaan berikut hanya berdasarkan context di bawah ini.Jika pertanyaan terkait lokasi maka lampirkan link https://www.google.com/maps?q= dengan q isi lokasi yang ditanyakan. Jika tidak ada jawaban di context, jawab 'Maaf, tidak ditemukan jawaban yang relevan.'\n\nContext:\n{context}\n\nPertanyaan:\n{rephrased_question}\n\nJawaban:"
        openai_api_key = os.environ.get('OPENAI_API_KEY')
        if not openai_api_key:
            raise HTTPException(status_code=500, detail='OPENAI_API_KEY environment variable not set')
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
        faiss_search_v2.save_thread(user_id, thread_id, memory)

    return {
        #'results': results,
        'llm_answer': llm_answer,
        #'memory': memory,
        'error': error
    }

# Contoh body JSON untuk request:
# {
#   "question": "contoh pertanyaan",
#   "top_k": 5,
#   "user_id": "user1",
#   "thread_id": "thread1"
#   "category": "teknologi",
# }
