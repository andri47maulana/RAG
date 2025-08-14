
import sys, json, pickle, os
import faiss
import numpy as np

# Use absolute path based on script location
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if len(sys.argv) >= 3:
    INDEX_FILE = os.path.join(BASE_DIR, sys.argv[1])
    META_FILE = os.path.join(BASE_DIR, sys.argv[2])
else:
    INDEX_FILE = os.path.join(BASE_DIR, 'company_index.faiss')
    META_FILE = os.path.join(BASE_DIR, 'company_meta.pkl')

def search(vector, top_k=3):
    index = faiss.read_index(INDEX_FILE)
    with open(META_FILE, 'rb') as f:
        metas = pickle.load(f)
    D, I = index.search(np.array([vector]).astype('float32'), top_k)
    res = []
    for idx in I[0]:
        if idx < len(metas):
            res.append(metas[idx])
    return res

if __name__ == '__main__':
    data = json.load(sys.stdin)
    vector = data['vector']
    top_k = data.get('top_k', 3)
    results = search(vector, top_k)
    print(json.dumps(results))
