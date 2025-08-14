import faiss
import numpy as np
import os

INDEX_FILE = os.path.join(os.path.dirname(__file__), 'company_index.faiss')

index = faiss.read_index(INDEX_FILE)
print('Dimensi index:', index.d)
