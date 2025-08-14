import sys, json, pickle, os
import faiss
import numpy as np

if len(sys.argv) >= 3:
    INDEX_FILE = sys.argv[1]
    META_FILE = sys.argv[2]
else:
    INDEX_FILE = 'company_index.faiss'
    META_FILE = 'company_meta.pkl'

def remove_file_from_index(filename):
    # Baca metadata dan index lama
    if not os.path.exists(INDEX_FILE) or not os.path.exists(META_FILE):
        print('Index atau metadata tidak ditemukan')
        return
    with open(META_FILE, 'rb') as f:
        metadatas = pickle.load(f)
    index = faiss.read_index(INDEX_FILE)
    # Filter metadata dan vektor yang tidak terkait file yang dihapus
    keep_indices = [i for i, m in enumerate(metadatas) if m.get('source') != filename]
    if not keep_indices:
        # Jika semua data dihapus, buat index kosong
        index = faiss.IndexFlatL2(1)
        faiss.write_index(index, INDEX_FILE)
        with open(META_FILE, 'wb') as f:
            pickle.dump([], f)
        print('Index kosong disimpan')
        return
    # Rekonstruksi vektor yang ingin disimpan
    dim = index.d
    vectors = [index.reconstruct(i) for i in keep_indices]
    new_index = faiss.IndexFlatL2(dim)
    new_index.add(np.array(vectors).astype('float32'))
    faiss.write_index(new_index, INDEX_FILE)
    # Simpan metadata baru
    new_metadatas = [metadatas[i] for i in keep_indices]
    with open(META_FILE, 'wb') as f:
        pickle.dump(new_metadatas, f)
    print(f'Index dan metadata untuk {filename} dihapus')

if __name__ == '__main__':
    # Input: { "filename": "namafile.pdf" }
    data = json.loads(sys.stdin.read())
    filename = data['filename']
    remove_file_from_index(filename)
