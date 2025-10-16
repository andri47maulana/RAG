import os

def extract_text(file_path: str) -> str:
    # Minimal placeholder: read .txt files; for .pdf, return empty to be handled upstream or extend with real PDF extraction.
    _, ext = os.path.splitext(file_path.lower())
    if ext == '.txt':
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception:
            return ''
    # TODO: integrate a real PDF text extractor (e.g., pypdf)
    return ''

def chunk_text(text: str, chunk_size: int = 500):
    text = (text or '').strip()
    if not text:
        return []
    chunks = []
    for i in range(0, len(text), chunk_size):
        chunks.append(text[i:i+chunk_size])
    return chunks
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
        # Hybrid: Try PyMuPDF (fitz) first, fallback to pdfplumber if needed
        try:
            import fitz  # PyMuPDF
            text = ''
            doc = fitz.open(file_path)
            for page in doc:
                page_text = page.get_text()
                if page_text:
                    text += page_text + '\n'
            if text.strip():
                return text
        except Exception as e:
            import traceback
            print(f"[extract_text] Error extracting PDF with PyMuPDF: {file_path}\n{e}")
            traceback.print_exc()
        # Fallback to pdfplumber
        try:
            import pdfplumber
            text = ''
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + '\n'
            return text
        except Exception as e:
            print(f"[extract_text] Error extracting PDF with pdfplumber: {file_path}\n{e}")
            traceback.print_exc()
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
