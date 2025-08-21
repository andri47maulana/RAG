import os
import requests

def ask_llm_with_faiss(question, category, user_id="default", thread_id="default", top_k=3, security_api_key=None):
    # --- SECURITY API KEY CHECK (opsional) ---
    SECURITY_API_KEY = os.environ.get('SECURITY_API_KEY')
    if SECURITY_API_KEY and security_api_key != SECURITY_API_KEY:
        return {'error': 'Unauthorized: Invalid security_api_key'}

    from . import faiss_service

    # Load memory thread
    memory = faiss_service.load_thread(user_id, thread_id)
    is_followup = False
    prev_llm_answer = None
    if question and len(memory) > 0:
        prev_entry = memory[-1]
        prev_llm_answer = prev_entry.get('a')
        is_followup = True

    # --- REPHRASE ---
    rephrased_question = question
    if is_followup and prev_llm_answer:
        openai_api_key = os.environ.get('OPENAI_API_KEY')
        headers = {
            'Authorization': f'Bearer {openai_api_key}',
            'Content-Type': 'application/json'
        }
        rephrase_prompt = (
            "Tentukan apakah pertanyaan berikut ini merupakan lanjutan (follow-up) dari pertanyaan sebelumnya atau merupakan pertanyaan baru yang tidak berkaitan. "
            "Jika follow-up, buat ulang pertanyaan agar lebih spesifik berdasarkan jawaban sebelumnya. "
            "Jika pertanyaan baru, jawab dengan: 'PERTANYAAN BARU'.\n\n"
            f"Jawaban sebelumnya: {prev_llm_answer}\n\nPertanyaan baru: {question}\n\nOutput:"
        )
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
            rephrase_result = resp.json()['choices'][0]['message']['content'].strip()
            if rephrase_result.strip().upper() == 'PERTANYAAN BARU':
                is_followup = False
                rephrased_question = question
            else:
                is_followup = True
                rephrased_question = rephrase_result
        else:
            rephrased_question = question + " (catatan: gagal rephrase)"

    # --- EMBEDDING ---
    openai_api_key = os.environ.get('OPENAI_API_KEY')
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
        return {'error': f'OpenAI API error: {resp.text}'}
    vector = resp.json()['data'][0]['embedding']

    # Simpan pertanyaan ke memory
    if question:
        mem_entry = {'q': question}
        if is_followup:
            mem_entry['rephrased'] = rephrased_question
        memory.append(mem_entry)

    # --- FAISS SEARCH ---
    import sys
    try:
        results = faiss_service.search(vector, top_k, category=category)
        error = ""
    except Exception as e:
        print(f"[LLM_SERVICE][FAISS_SEARCH_ERROR] {e}", file=sys.stderr)
        results = []
        error = str(e)

    # --- CONTEXT DARI FAISS ---
    if results and isinstance(results, list) and len(results) > 0 and isinstance(results[0], dict) and 'text' in results[0]:
        context = '\n\n---\n\n'.join([r['text'] for r in results if 'text' in r])
    else:
        context = ''

    # --- LLM NARASI ---
    llm_answer = None
    if rephrased_question:
        prompt = f"Jawablah pertanyaan berikut hanya berdasarkan context di bawah ini. Jika tidak ada jawaban di context, jawab 'Maaf, tidak ditemukan jawaban yang relevan.'\n\nContext:\n{context}\n\nPertanyaan:\n{rephrased_question}\n\nJawaban:"
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
    # Simpan jawaban LLM ke memory jika ada entry
    if memory:
        memory[-1]['a'] = llm_answer
        faiss_service.save_thread(user_id, thread_id, memory)

    return {
        'llm_answer': llm_answer,
        'results': results,
        'error': error,
        'prompt':prompt
    }
