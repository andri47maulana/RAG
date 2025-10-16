import os
from dotenv import load_dotenv
import requests

# Ensure .env is loaded from app directory to make OPENAI_API_KEY available
try:
    _ENV_PATH = os.path.join(os.path.dirname(__file__), '..', '.env')
    load_dotenv(_ENV_PATH, override=False)
except Exception:
    pass

def ask_llm_with_faiss(question, category, user_id="default", thread_id="default", top_k=3, security_api_key=None, regional=None):
    import sys
    try:
        # --- SECURITY API KEY CHECK (opsional) ---
        # SECURITY_API_KEY =1245
        # if SECURITY_API_KEY and security_api_key != SECURITY_API_KEY:
        #     return {'error': 'Unauthorized: Invalid security_api_key' }

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
            if not openai_api_key:
                return {'error': 'OPENAI_API_KEY is not set in environment'}
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
                # capture usage for rephrase call (small)
                try:
                    usage = resp.json().get('usage') or {}
                    total_tokens = usage.get('total_tokens') or 0
                    model = resp.json().get('model') or 'gpt-4'
                    portal_url = os.environ.get('PORTAL_API_URL')  # e.g. http://127.0.0.1:8000/api
                    if portal_url and total_tokens:
                        requests.post(f"{portal_url}/tokens/usage", json={
                            'model': model,
                            'tokens': int(total_tokens),
                            'user_id': user_id,
                            'thread_id': thread_id,
                            'meta': {'type': 'rephrase-detection'}
                        }, timeout=3)
                except Exception:
                    pass
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
        if not openai_api_key:
            return {'error': 'OPENAI_API_KEY is not set in environment'}
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
        try:
            results = faiss_service.search(vector, top_k, category=category)
            # Optional regional filter – if provided, filter results where metadata.regional matches (case-insensitive contains)
            if regional:
                rlow = str(regional).lower()
                results = [r for r in (results or []) if str(r.get('regional','')).lower().find(rlow) >= 0]
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
                # capture usage for main answer
                try:
                    usage = resp.json().get('usage') or {}
                    total_tokens = usage.get('total_tokens') or 0
                    model = resp.json().get('model') or 'gpt-4'
                    portal_url = os.environ.get('PORTAL_API_URL')  # e.g. http://127.0.0.1:8000/api
                    if portal_url and total_tokens:
                        requests.post(f"{portal_url}/tokens/usage", json={
                            'model': model,
                            'tokens': int(total_tokens),
                            'user_id': user_id,
                            'thread_id': thread_id,
                            'meta': {'type': 'answer', 'top_k': top_k, 'category': category}
                        }, timeout=3)
                except Exception:
                    pass
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
    except Exception as e:
        import traceback
        print(f"[LLM_SERVICE][FATAL_ERROR] {e}\n{traceback.format_exc()}", file=sys.stderr)
        return {'error': f'LLM Service Fatal Error: {e}'}
