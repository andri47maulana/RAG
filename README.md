my-rag-bot-with-uploader — FAISS + OpenAI RAG + Admin Uploader
=============================================================

What's included
----------------
- python/faiss_index.py      : saves FAISS index from stdin vectors+metadata
- python/faiss_search.py     : searches FAISS index given a vector from stdin
- uploader/                  : small Express app to upload files and index via OpenAI embeddings
  - uploader/server.js
  - uploader/static/upload.html
  - uploader/package.json
- actions/ragAction.js       : Botpress action to query FAISS and call OpenAI Chat
- hooks/after_server_start/initUploader.js : example hook to show how to start uploader (optional)
- README with setup steps

Quick setup
-----------
1. Extract this package into a folder (e.g., /var/www/company_rag).
2. Install Python deps for FAISS:
     python3 -m pip install faiss-cpu numpy
   (If you prefer sentence-transformers, install it too; but here embeddings are created using OpenAI.)
3. Install uploader Node deps:
     cd uploader
     npm install
4. Set OPENAI_API_KEY environment variable in the environment where uploader and Botpress run.
5. Start the uploader (or run with pm2):
     cd uploader
     node server.js
   The uploader will run on http://localhost:3005 by default.
6. Upload PDF/TXT via the uploader UI (or embed the uploader page into Botpress admin using an iframe).
   When you upload, the server will:
     - extract text
     - chunk text into 500-char pieces
     - call OpenAI Embeddings API to create vectors
     - call python/faiss_index.py to save company_index.faiss and company_meta.pkl in python/ directory
7. Copy actions/ragAction.js into your Botpress bot actions folder:
     data/bots/<your_bot>/actions/ragAction.js
8. In Botpress flow, call action 'ragAction' in a node to enable RAG responses.
9. Ensure Botpress process has access to OPENAI_API_KEY and has python3 in PATH.

Notes
-----
- The uploader currently supports PDF and TXT. Add DOCX support by using 'docx' python package or a Node converter.
- For better results, add chunk overlap, deduplication, and metadata fields (title, page, offsets).
- For production deploy, run uploader as a separate service (pm2/systemd) and secure the upload endpoint (auth).
- To embed uploader in Botpress admin: open Botpress admin and add an iframe pointing to the uploader URL (http://<host>:3005/).

