import re
import os

def extract_text(file_path):
    if not os.path.exists(file_path):
        return ''
    if file_path.lower().endswith('.txt'):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception:
            return ''
    elif file_path.lower().endswith('.pdf'):
        try:
            import pdfplumber
            text = ''
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + '\n'
            return text
        except Exception:
            return ''
    return ''

def chunk_text(text, chunk_size=500):
    # Potong teks per chunk_size karakter, tanpa memotong kata
    words = text.split()
    chunks = []
    chunk = []
    total = 0
    for word in words:
        if total + len(word) + 1 > chunk_size:
            chunks.append(' '.join(chunk))
            chunk = []
            total = 0
        chunk.append(word)
        total += len(word) + 1
    if chunk:
        chunks.append(' '.join(chunk))
    return chunks
