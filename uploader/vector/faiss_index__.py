import sys, json, pickle
import faiss
import numpy as np
import os

if len(sys.argv) >= 3:
    INDEX_FILE = sys.argv[1]
    META_FILE = sys.argv[2]
else:
    INDEX_FILE = 'company_index.faiss'
    META_FILE = 'company_meta.pkl'

def save_index(vectors, metadatas):
    # Cek apakah index dan metadata lama ada
    try:
        index = None
        old_vectors = []
        old_metadatas = []
        if os.path.exists(INDEX_FILE) and os.path.exists(META_FILE):
            # Baca index lama
            index = faiss.read_index(INDEX_FILE)
            with open(META_FILE, 'rb') as f:
                old_metadatas = pickle.load(f)
            # Gabungkan vektor lama dan baru
            old_vectors = index.reconstruct_n(0, index.ntotal).tolist() if index.ntotal > 0 else []
        else:
            index = None
        # Gabungkan semua vektor dan metadata
        all_vectors = old_vectors + vectors
        all_metadatas = old_metadatas + metadatas
        if not all_vectors:
            index = faiss.IndexFlatL2(1)
            faiss.write_index(index, INDEX_FILE)
            with open(META_FILE, 'wb') as f:
                pickle.dump([], f)
            print("Index kosong disimpan")
            return
        dim = len(all_vectors[0])
        index = faiss.IndexFlatL2(dim)
        index.add(np.array(all_vectors).astype('float32'))
        faiss.write_index(index, INDEX_FILE)
        with open(META_FILE, 'wb') as f:
            pickle.dump(all_metadatas, f)
    except Exception as e:
        print(f"Gagal update index: {e}")

if __name__ == '__main__':
    data = json.loads(sys.stdin.read())
    vectors = data['vectors']
    metadatas = data['metadatas']
    save_index(vectors, metadatas)
    print("Index saved")
