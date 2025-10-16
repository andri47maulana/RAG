import os
import pickle

def create_or_update_index(vectors, metadatas, index_file, meta_file):
    """
    Minimal implementation that only persists metadata for vector/list and simple search.
    'vectors' are ignored here to avoid faiss dependency; you can extend to real FAISS later.
    """
    os.makedirs(os.path.dirname(meta_file), exist_ok=True)
    existing = []
    if os.path.exists(meta_file):
        try:
            with open(meta_file, 'rb') as f:
                existing = pickle.load(f) or []
        except Exception:
            existing = []
    combined = (existing or []) + (metadatas or [])
    with open(meta_file, 'wb') as f:
        pickle.dump(combined, f)
    # Touch index_file as a placeholder to signal an index exists
    try:
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        with open(index_file, 'ab') as _:
            pass
    except Exception:
        pass


# --- Minimal thread memory storage (JSON file per user-thread) ---
import json

def _thread_file(user_id: str, thread_id: str):
    safe_user = str(user_id).replace('/', '_')
    safe_thread = str(thread_id).replace('/', '_')
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'threads'))
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, f"{safe_user}_{safe_thread}.json")

def load_thread(user_id: str, thread_id: str):
    try:
        p = _thread_file(user_id, thread_id)
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return []

def save_thread(user_id: str, thread_id: str, memory):
    try:
        p = _thread_file(user_id, thread_id)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(memory or [], f, ensure_ascii=False)
    except Exception:
        pass

def search(vector, top_k=3, category=None):
    """Minimal search stub: returns empty results.
    Replace with a real vector search reading meta_{category}.pkl when needed.
    """
    return []

import os
import sys
import json
import pickle
import faiss
import numpy as np




# Absolute path for backend/v1 root
V1_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
VECTOR_DIR = os.path.join(V1_DIR, 'vector')
THREADS_DIR = os.path.join(V1_DIR, 'threads')
os.makedirs(VECTOR_DIR, exist_ok=True)
os.makedirs(THREADS_DIR, exist_ok=True)



def get_index_and_meta_file(category: str = 'teknologi'):
    """Return absolute paths for index and metadata files for a given category."""
    index_file = os.path.join(VECTOR_DIR, f'index_{category}.faiss')
    meta_file = os.path.join(VECTOR_DIR, f'meta_{category}.pkl')
    return index_file, meta_file

def search(vector, top_k=3, category='teknologi'):
    """Search the FAISS index for the top_k most similar vectors in the given category."""
    index_file, meta_file = get_index_and_meta_file(category)
    try:
        if not os.path.exists(index_file):
            #raise FileNotFoundError(f"Index file not found: {index_file}")
            raise FileNotFoundError(f"Data tidak ditemukan!.")
        if not os.path.exists(meta_file):
            # raise FileNotFoundError(f"Meta file not found: {meta_file}")
            raise FileNotFoundError(f"Data tidak ditemukan!.")
        index = faiss.read_index(index_file)
        with open(meta_file, 'rb') as f:
            metas = pickle.load(f)
        print(f"VECTOR DIM: {len(vector)} INDEX DIM: {index.d}", file=sys.stderr)
        print(f"index_file: {index_file}, meta_file: {meta_file}", file=sys.stderr)
        if len(vector) != index.d:
            #raise ValueError(f"Dimensi vector ({len(vector)}) tidak cocok dengan index ({index.d})")
            raise ValueError(f"Kesalahan pada data, silakan coba lagi atau hubungi admin.")
        D, I = index.search(np.array([vector]).astype('float32'), top_k)
        res = [metas[idx] for idx in I[0] if idx < len(metas)]
        return res
    except Exception as e:
        print(f"[FAISS SEARCH ERROR] {e}", file=sys.stderr)
        raise

def load_thread(user_id, thread_id):
    """Load a user's thread memory from file."""
    path = os.path.join(THREADS_DIR, f'{user_id}_{thread_id}.json')
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return []
                return json.loads(content)
        except Exception as e:
            print(f"[THREAD] Gagal mengingat percapakapan. {path}: {e}", file=sys.stderr)
            return []
    return []

def save_thread(user_id, thread_id, memory):
    """Save a user's thread memory to file."""
    path = os.path.join(THREADS_DIR, f'{user_id}_{thread_id}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)


# def save_faiss_index(index, file_path):
#     """Save a FAISS index to file."""
#     faiss.write_index(index, file_path)

def load_faiss_index(file_path):
    """Load a FAISS index from file."""
    return faiss.read_index(file_path)

def save_metadata(meta, file_path):
    """Save metadata to file using pickle."""
    with open(file_path, 'wb') as f:
        pickle.dump(meta, f)

def load_metadata(file_path):
    """Load metadata from file using pickle."""
    with open(file_path, 'rb') as f:
        return pickle.load(f)



def create_or_update_index(vectors, metadatas, index_file, meta_file):
    """Create a new FAISS index or update an existing one with new vectors and metadata."""
    try:
        index = None
        old_vectors = []
        old_metadatas = []
        # Backup sebelum overwrite
        if os.path.exists(index_file):
            os.rename(index_file, index_file + ".bak")
        if os.path.exists(meta_file):
            os.rename(meta_file, meta_file + ".bak")

        # Load data lama
        if os.path.exists(index_file + ".bak") and os.path.exists(meta_file + ".bak"):
            try:
                index = faiss.read_index(index_file + ".bak")
                old_metadatas = load_metadata(meta_file + ".bak")
                old_vectors = index.reconstruct_n(0, index.ntotal).tolist() if index.ntotal > 0 else []
            except Exception as e:
                print(f"[BACKUP LOAD ERROR] {e}")
                old_vectors = []
                old_metadatas = []
        all_vectors = old_vectors + vectors
        all_metadatas = old_metadatas + metadatas
        if not all_vectors:
            index = faiss.IndexFlatL2(1)
            faiss.write_index(index, index_file)
            with open(meta_file, 'wb') as f:
                pickle.dump([], f)
            print("Index kosong disimpan")
            return
        dim = len(all_vectors[0])
        total = len(all_vectors)
        index = faiss.IndexFlatL2(dim)
        last_percent = -1
        for i in range(total):
            index.add(np.array([all_vectors[i]]).astype('float32'))
            percent = int(((i + 1) / total) * 100)
            if percent != last_percent:
                print(f"Progress: {percent}% ({i + 1}/{total})", flush=True)
                last_percent = percent
        faiss.write_index(index, index_file)
        with open(meta_file, 'wb') as f:
            pickle.dump(all_metadatas, f)
        # Hapus backup jika sukses
        if os.path.exists(index_file + ".bak"):
            os.remove(index_file + ".bak")
        if os.path.exists(meta_file + ".bak"):
            os.remove(meta_file + ".bak")
    except Exception as e:
        print(f"Gagal update index: {e}")
        # Restore backup jika gagal
        if os.path.exists(index_file + ".bak"):
            os.rename(index_file + ".bak", index_file)
        if os.path.exists(meta_file + ".bak"):
            os.rename(meta_file + ".bak", meta_file)
