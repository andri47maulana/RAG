from flask import send_from_directory
from dotenv import load_dotenv
import os as _os

# Ensure environment loaded even if blueprint imported
try:
    # Do not override already-set environment variables
    load_dotenv(_os.path.join(_os.path.dirname(__file__), '..', '.env'), override=False)
except Exception:
    pass

import pickle
from flask import Blueprint, request, jsonify, Response
import os
from werkzeug.utils import secure_filename
import time
import threading

from utils.text_utils import extract_text, chunk_text
from services.embedding_service import get_embedding
from services.faiss_service import create_or_update_index
from services.llm_service import ask_llm_with_faiss
import numpy as np
import requests

bp = Blueprint('index', __name__)

@bp.after_request
def add_cors_headers(response):
    try:
        allowed = {
            "http://localhost:5002", "http://127.0.0.1:5002",
            "http://localhost:8001", "http://127.0.0.1:8001",
            "http://localhost:8000", "http://127.0.0.1:8000"
        }
        origin = request.headers.get("Origin")
        if origin in allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    except Exception:
        pass
    return response

@bp.route('/upload', methods=['OPTIONS'])
def upload_options():
    return Response(status=204)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'docs')
ALLOWED_EXTENSIONS = {'pdf', 'txt'}
import uuid
progress_messages = {}
progress_lock = threading.Lock()

@bp.route('/docs/<kategori>/<filename>')
def serve_file(kategori, filename):
    docs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'docs', kategori))
    return send_from_directory(docs_dir, filename)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def send_progress(msg, progress_id):
    with progress_lock:
        if progress_id not in progress_messages:
            progress_messages[progress_id] = []
        progress_messages[progress_id].append(msg)

@bp.route('/progress-stream')
def progress_stream():
    import sys
    progress_id = request.args.get('id')
    print(f"[SSE] progress_stream called for id={progress_id}", file=sys.stderr)
    if not progress_id:
        print("[SSE] Missing progress id", file=sys.stderr)
        return Response("Missing progress id", status=400)
    def event_stream():
        last_index = 0
        while True:
            with progress_lock:
                msgs = progress_messages.get(progress_id, [])
                new_msgs = msgs[last_index:]
                last_index = len(msgs)
            for msg in new_msgs:
                print(f"[SSE] Sending progress: {msg}", file=sys.stderr)
                yield f"data: {msg}\n\n"
            time.sleep(0.5)
    return Response(event_stream(), mimetype="text/event-stream")

@bp.route('/progress-stream', methods=['OPTIONS'])
def progress_stream_options():
    return Response(status=204)

@bp.route('/health', methods=['GET'])
def health():
    try:
        key_present = bool(os.getenv('OPENAI_API_KEY'))
        return jsonify({'ok': True, 'OPENAI_API_KEY_present': key_present, 'cwd': os.getcwd()})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@bp.route('/upload', methods=['POST'])
def upload_file():
    progress_id = request.form.get('progress_id') or str(uuid.uuid4())
    kategori = request.form.get('kategori') or request.args.get('kategori')
    regional = request.form.get('regional') or request.args.get('regional') or 'regional-unknown'
    if 'file' not in request.files:
        return jsonify({'ok': False, 'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'ok': False, 'error': 'No selected file'}), 400
    import sys
    if file and allowed_file(file.filename):
        print(f"[UPLOAD] Mulai upload file: {file.filename}, kategori: {kategori}, progress_id: {progress_id}", file=sys.stderr)
        filename = secure_filename(file.filename)
        kategori_dir = os.path.join(UPLOAD_FOLDER, kategori)
        os.makedirs(kategori_dir, exist_ok=True)
        file_path = os.path.join(kategori_dir, filename)
        file.save(file_path)
        send_progress("Upload started", progress_id)
        text = extract_text(file_path)
        if not text.strip():
            print("[UPLOAD] File tidak berisi teks.", file=sys.stderr)
            return jsonify({'ok': False, 'error': 'File tidak berisi teks.'}), 400
        send_progress("Text extracted", progress_id)
        chunks = chunk_text(text, 500)
        if not chunks:
            print("[UPLOAD] Tidak ada chunk yang dihasilkan.", file=sys.stderr)
            return jsonify({'ok': False, 'error': 'Tidak ada chunk yang dihasilkan.'}), 400
        send_progress(f"Text chunked: {len(chunks)} chunks", progress_id)
        vectors = []
        metadatas = []
        for i, chunk in enumerate(chunks):
            print(f"[UPLOAD] Mulai embedding chunk {i+1}/{len(chunks)}", file=sys.stderr)
            emb = get_embedding(chunk)
            print(f"[UPLOAD] Selesai embedding chunk {i+1}/{len(chunks)}", file=sys.stderr)
            if not emb:
                print(f"[UPLOAD] Gagal membuat embedding untuk chunk {i+1}.", file=sys.stderr)
                return jsonify({'ok': False, 'error': f'Gagal membuat embedding pada chunk {i+1}'}), 400
            vectors.append(emb)
            metadatas.append({'source': filename, 'chunk_index': i, 'text': chunk, 'kategori': kategori, 'regional': regional})
            send_progress(f"Embedding {i+1}/{len(chunks)}", progress_id)
        if not vectors:
            print("[UPLOAD] Tidak ada embedding yang berhasil dibuat.", file=sys.stderr)
            return jsonify({'ok': False, 'error': 'Gagal membuat embedding.'}), 400
        vector_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../vector'))
        os.makedirs(vector_dir, exist_ok=True)
        index_file = os.path.join(vector_dir, f'index_{kategori}.faiss')
        meta_file = os.path.join(vector_dir, f'meta_{kategori}.pkl')
        send_progress("Indexing started", progress_id)
        create_or_update_index(vectors, metadatas, index_file, meta_file)
        send_progress("Done", progress_id)
        try:
            portal_api = os.environ.get('PORTAL_API_URL')
            if portal_api:
                size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                requests.post(f"{portal_api}/documents", json={'filename': filename,'kategori': kategori,'regional': regional,'size': size,'uploaded_by': request.form.get('uploaded_by') or request.args.get('uploaded_by') or 'system'}, timeout=3)
        except Exception:
            pass
        print(f"[UPLOAD] Selesai upload dan indexing file: {file.filename}, progress_id: {progress_id}", file=sys.stderr)
        def delayed_cleanup(pid):
            import time
            time.sleep(10)
            with progress_lock:
                progress_messages.pop(pid, None)
            print(f"[UPLOAD] progress_messages untuk {pid} dihapus setelah delay", file=sys.stderr)
        threading.Thread(target=delayed_cleanup, args=(progress_id,), daemon=True).start()
        return jsonify({'ok': True, 'message': 'File uploaded and indexing started (Python backend)', 'progress_id': progress_id}), 200
    else:
        print(f"[UPLOAD] File type not allowed: {file.filename}", file=sys.stderr)
        return jsonify({'ok': False, 'error': 'File type not allowed'}), 400

@bp.route('/vector/list', methods=['GET'])
def vector_list():
    try:
        kategori = (request.args.get('kategori') or '').strip()
        if not kategori:
            return jsonify({"ok": False, "error": "kategori wajib"}), 400
        vector_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../vector'))
        meta_file = os.path.join(vector_dir, f'meta_{kategori}.pkl')
        if not os.path.exists(meta_file):
            return jsonify({"ok": True, "kategori": kategori, "sources": []})
        with open(meta_file, 'rb') as f:
            metas = pickle.load(f)
        sources = sorted(list({(m.get('source') or '') for m in (metas or []) if isinstance(m, dict)}))
        return jsonify({"ok": True, "kategori": kategori, "sources": sources})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@bp.route('/answer', methods=['POST'])
def answer():
    data = request.get_json()
    question = data.get('question')
    kategori = data.get('kategori')
    regional = data.get('regional')
    user_id = data.get('user_id', 'default')
    thread_id = data.get('thread_id', 'default')
    top_k = data.get('top_k', 5)
    security_api_key = data.get('security_api_key') or data.get('security_key')
    if not question or not kategori:
        return jsonify({'ok': False, 'error': 'Pertanyaan dan kategori wajib diisi'}), 400
    result = ask_llm_with_faiss(question, kategori, user_id=user_id, thread_id=thread_id, top_k=top_k, security_api_key=security_api_key, regional=regional)
    if not result:
        return jsonify({'ok': False, 'error': 'Internal error: no result from LLM'}), 500
    if result.get('error'):
        return jsonify({'ok': False, 'error': result.get('error')}), 200
    return jsonify({'ok': True,'answer': result.get('llm_answer'),'results': result.get('results'),'error': result.get('error'),'prompt': result.get('prompt')})

from flask import send_from_directory
from dotenv import load_dotenv
import os as _os
# Ensure environment loaded even if blueprint imported without main.py context
try:
    load_dotenv(_os.path.join(_os.path.dirname(__file__), '..', '.env'))
except Exception:
    pass

try:
    import faiss  # optional: used for delete/reindex operations
except Exception:
    faiss = None
import pickle
from flask import Blueprint, request, jsonify, Response
import os
from werkzeug.utils import secure_filename
import time
import threading
from utils.text_utils import extract_text, chunk_text
from services.embedding_service import get_embedding
from services.faiss_service import create_or_update_index, load_faiss_index, load_metadata
from services.llm_service import ask_llm_with_faiss
import numpy as np
import requests

bp = Blueprint('index', __name__)
@bp.after_request
def add_cors_headers(response):
    try:
        allowed = {
            "http://localhost:5002", "http://127.0.0.1:5002",
            "http://localhost:8001", "http://127.0.0.1:8001",
            "http://localhost:8000", "http://127.0.0.1:8000"
        }
        origin = request.headers.get("Origin")
        if origin in allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    except Exception:
        pass
    return response

@bp.route('/upload', methods=['OPTIONS'])
def upload_options():
    return Response(status=204)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'docs')
ALLOWED_EXTENSIONS = {'pdf', 'txt'}
import uuid
progress_messages = {}  # key: progress_id, value: list of messages
progress_lock = threading.Lock()
@bp.route('/docs/<kategori>/<filename>')

def serve_file(kategori, filename):
    docs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'docs', kategori))
    return send_from_directory(docs_dir, filename)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def send_progress(msg, progress_id):
    with progress_lock:
        if progress_id not in progress_messages:
            progress_messages[progress_id] = []
        progress_messages[progress_id].append(msg)

@bp.route('/progress-stream')
def progress_stream():
    import sys
    progress_id = request.args.get('id')
    print(f"[SSE] progress_stream called for id={progress_id}", file=sys.stderr)
    if not progress_id:
        print("[SSE] Missing progress id", file=sys.stderr)
        return Response("Missing progress id", status=400)
    def event_stream():
        last_index = 0
        while True:
            with progress_lock:
                msgs = progress_messages.get(progress_id, [])
                new_msgs = msgs[last_index:]
                last_index = len(msgs)
            for msg in new_msgs:
                print(f"[SSE] Sending progress: {msg}", file=sys.stderr)
                yield f"data: {msg}\n\n"
            time.sleep(0.5)
    return Response(event_stream(), mimetype="text/event-stream")

@bp.route('/progress-stream', methods=['OPTIONS'])
def progress_stream_options():
    return Response(status=204)

@bp.route('/health', methods=['GET'])
def health():
    try:
        import os
        key_present = bool(os.getenv('OPENAI_API_KEY'))
        return jsonify({
            'ok': True,
            'OPENAI_API_KEY_present': key_present,
            'cwd': os.getcwd(),
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@bp.route('/upload', methods=['POST'])
def upload_file():
    progress_id = request.form.get('progress_id') or str(uuid.uuid4())
    kategori = request.form.get('kategori') or request.args.get('kategori')
    regional = request.form.get('regional') or request.args.get('regional') or 'regional-unknown'
    if 'file' not in request.files:
        return jsonify({'ok': False, 'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'ok': False, 'error': 'No selected file'}), 400
    import sys
    if file and allowed_file(file.filename):
        print(f"[UPLOAD] Mulai upload file: {file.filename}, kategori: {kategori}, progress_id: {progress_id}", file=sys.stderr)
        filename = secure_filename(file.filename)
        kategori_dir = os.path.join(UPLOAD_FOLDER, kategori)
        os.makedirs(kategori_dir, exist_ok=True)
        file_path = os.path.join(kategori_dir, filename)
        file.save(file_path)
        send_progress("Upload started", progress_id)
        text = extract_text(file_path)
        if not text.strip():
            print("[UPLOAD] File tidak berisi teks.", file=sys.stderr)
            return jsonify({'ok': False, 'error': 'File tidak berisi teks.'}), 400
        send_progress("Text extracted", progress_id)
        chunks = chunk_text(text, 500)
        if not chunks:
            print("[UPLOAD] Tidak ada chunk yang dihasilkan.", file=sys.stderr)
            return jsonify({'ok': False, 'error': 'Tidak ada chunk yang dihasilkan.'}), 400
        send_progress(f"Text chunked: {len(chunks)} chunks", progress_id)
        vectors = []
        metadatas = []
        for i, chunk in enumerate(chunks):
            print(f"[UPLOAD] Mulai embedding chunk {i+1}/{len(chunks)}", file=sys.stderr)
            emb = get_embedding(chunk)
            print(f"[UPLOAD] Selesai embedding chunk {i+1}/{len(chunks)}", file=sys.stderr)
            if not emb:
                print(f"[UPLOAD] Gagal membuat embedding untuk chunk {i+1}.", file=sys.stderr)
                return jsonify({'ok': False, 'error': f'Gagal membuat embedding pada chunk {i+1}'}), 400
            vectors.append(emb)
            metadatas.append({
                'source': filename,
                'chunk_index': i,
                'text': chunk,
                'kategori': kategori,
                'regional': regional
            })
            send_progress(f"Embedding {i+1}/{len(chunks)}", progress_id)
        if not vectors:
            print("[UPLOAD] Tidak ada embedding yang berhasil dibuat.", file=sys.stderr)
            return jsonify({'ok': False, 'error': 'Gagal membuat embedding.'}), 400
        # Pastikan folder vector ada
        vector_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../vector'))
        os.makedirs(vector_dir, exist_ok=True)
        index_file = os.path.join(vector_dir, f'index_{kategori}.faiss')
        meta_file = os.path.join(vector_dir, f'meta_{kategori}.pkl')
        send_progress("Indexing started", progress_id)
        create_or_update_index(vectors, metadatas, index_file, meta_file)
        send_progress("Done", progress_id)
        # Notify portal about the document for regional aggregation (best-effort)
        try:
            portal_api = os.environ.get('PORTAL_API_URL')
            if portal_api:
                size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                requests.post(f"{portal_api}/documents", json={
                    'filename': filename,
                    'kategori': kategori,
                    'regional': regional,
                    'size': size,
                    'uploaded_by': request.form.get('uploaded_by') or request.args.get('uploaded_by') or 'system'
                }, timeout=3)
        except Exception:
            pass
        print(f"[UPLOAD] Selesai upload dan indexing file: {file.filename}, progress_id: {progress_id}", file=sys.stderr)
        # Hapus progress_messages dengan delay agar SSE client sempat menerima semua pesan
        def delayed_cleanup(pid):
            import time
            time.sleep(10)
            with progress_lock:
                progress_messages.pop(pid, None)
            print(f"[UPLOAD] progress_messages untuk {pid} dihapus setelah delay", file=sys.stderr)
        threading.Thread(target=delayed_cleanup, args=(progress_id,), daemon=True).start()
        return jsonify({'ok': True, 'message': 'File uploaded and indexing started (Python backend)', 'progress_id': progress_id}), 200
    else:
        print(f"[UPLOAD] File type not allowed: {file.filename}", file=sys.stderr)
        return jsonify({'ok': False, 'error': 'File type not allowed'}), 400

@bp.route('/docs', methods=['GET'])
def list_docs():
    try:
        kategori = request.args.get('kategori', '')
        if isinstance(kategori, list):
            kategori = kategori[0]
        kategori = kategori.strip() if isinstance(kategori, str) else ''
        dir_path = UPLOAD_FOLDER
        if kategori:
            dir_path = os.path.join(UPLOAD_FOLDER, kategori)
        if not os.path.exists(dir_path):
            return jsonify({"ok": True, "files": []})
        files = [f for f in os.listdir(dir_path) if f.endswith('.pdf') or f.endswith('.txt')]
        files_with_kategori = [{"nama": f, "kategori": kategori} for f in files]
        return jsonify({"ok": True, "files": files_with_kategori})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@bp.route('/vector/list', methods=['GET'])
def vector_list():
    try:
        kategori = (request.args.get('kategori') or '').strip()
        if not kategori:
            return jsonify({"ok": False, "error": "kategori wajib"}), 400
        vector_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../vector'))
        meta_file = os.path.join(vector_dir, f'meta_{kategori}.pkl')
        if not os.path.exists(meta_file):
            return jsonify({"ok": True, "kategori": kategori, "sources": []})
        with open(meta_file, 'rb') as f:
            metas = pickle.load(f)
        sources = sorted(list({(m.get('source') or '') for m in (metas or []) if isinstance(m, dict)}))
        return jsonify({"ok": True, "kategori": kategori, "sources": sources})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@bp.route('/answer', methods=['POST'])
def answer():
    data = request.get_json()
    question = data.get('question')
    kategori = data.get('kategori')
    regional = data.get('regional')
    user_id = data.get('user_id', 'default')
    thread_id = data.get('thread_id', 'default')
    top_k = data.get('top_k', 5)
    # Terima baik security_key maupun security_api_key dari frontend
    security_api_key = data.get('security_api_key') or data.get('security_key')
    if not question or not kategori:
        return jsonify({'ok': False, 'error': 'Pertanyaan dan kategori wajib diisi'}), 400
    result = ask_llm_with_faiss(question, kategori, user_id=user_id, thread_id=thread_id, top_k=top_k, security_api_key=security_api_key, regional=regional)
    if not result:
        return jsonify({'ok': False, 'error': 'Internal error: no result from LLM'}), 500
    if result.get('error'):
        return jsonify({'ok': False, 'error': result.get('error')}), 200
    return jsonify({
        'ok': True,
        'answer': result.get('llm_answer'),
        'results': result.get('results'),
        'error': result.get('error'),
        'prompt': result.get('prompt')
    })

# Endpoint hapus file dan reindex
@bp.route('/delete', methods=['POST'])
def delete_file():
    import sys
    data = request.get_json()
    filename = data.get('filename')
    kategori = data.get('kategori')
    if not filename or not kategori:
        return jsonify({'ok': False, 'error': 'filename dan kategori wajib'}), 400
    kategori_dir = os.path.join(UPLOAD_FOLDER, kategori)
    file_path = os.path.join(kategori_dir, filename)
    if not os.path.exists(file_path):
        return jsonify({'ok': False, 'error': 'File tidak ditemukan'}), 404
    try:
        os.remove(file_path)
        print(f"[DELETE] File dihapus: {file_path}", file=sys.stderr)
        # Update metadata dan reindex (tanpa re-embedding, hanya filter & reconstruct)
        vector_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../vector'))
        index_file = os.path.join(vector_dir, f'index_{kategori}.faiss')
        meta_file = os.path.join(vector_dir, f'meta_{kategori}.pkl')
        if not os.path.exists(index_file) or not os.path.exists(meta_file):
            print('[DELETE] Index atau metadata tidak ditemukan', file=sys.stderr)
            return jsonify({'ok': True, 'message': 'File dihapus, index/metadata tidak ditemukan'}), 200
        with open(meta_file, 'rb') as f:
            metadatas = pickle.load(f)
        if faiss is None:
            return jsonify({'ok': False, 'error': 'FAISS tidak tersedia di server'}), 500
        index = faiss.read_index(index_file)
        keep_indices = [i for i, m in enumerate(metadatas) if m.get('source') != filename]
        if not keep_indices:
            # Jika semua data dihapus, buat index kosong
            index = faiss.IndexFlatL2(1)
            faiss.write_index(index, index_file)
            with open(meta_file, 'wb') as f:
                pickle.dump([], f)
            print('[DELETE] Index kosong disimpan', file=sys.stderr)
            return jsonify({'ok': True, 'message': 'File dihapus, index dikosongkan'}), 200
        dim = index.d
        vectors = [index.reconstruct(i) for i in keep_indices]
        new_index = faiss.IndexFlatL2(dim)
        new_index.add(np.array(vectors).astype('float32'))
        faiss.write_index(new_index, index_file)
        new_metadatas = [metadatas[i] for i in keep_indices]
        with open(meta_file, 'wb') as f:
            pickle.dump(new_metadatas, f)
        print(f'[DELETE] Index dan metadata untuk {filename} dihapus', file=sys.stderr)
        return jsonify({'ok': True, 'message': f'File dihapus dan index diupdate (tanpa re-embedding)'}), 200
    except Exception as e:
        print(f"[DELETE] Error: {e}", file=sys.stderr)
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/roles', methods=['GET'])
def get_roles():
    #roles diambil dari endpoint portal ai
    try:
        #resp = requests.get('https://stg-ai.ptpn1.co.id/api/roles', timeout=10)
        resp = requests.get('http://127.0.0.1:8000/api/roles', timeout=10)
        data = resp.json()
        #dalam format {"ok": True, "roles": [...]}
        return jsonify(data)
    except Exception as e:
        return jsonify({"ok": False, "roles": [], "error": str(e)})