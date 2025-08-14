const express = require('express');
const router = express.Router();
const { fetchDocuments } = require('../db/dbUtils');
const { chunkText } = require('../docs/docUtils');
const { spawn } = require('child_process');
const path = require('path');
const OpenAI = require('openai');
const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

// Indexing dari MySQL
router.post('/index-mysql', express.json(), async (req, res) => {
  try {
    const rows = await fetchDocuments();
    let vectors = [];
    let metadatas = [];
    for (const row of rows) {
      const text = `${row.judul}\n${row.isi}`;
      const chunks = chunkText(text, 500);
      for (let i = 0; i < chunks.length; i++) {
        const chunk = chunks[i];
        const embRes = await openai.embeddings.create({ model: 'text-embedding-3-small', input: chunk });
        const emb = embRes.data[0].embedding;
        vectors.push(emb);
        metadatas.push({ source: 'mysql', id: row.id, judul: row.judul, chunk_index: i, text: chunk });
      }
    }
  const py = spawn(process.env.PYTHON_PATH, [path.join(__dirname, 'vector', 'faiss_index.py')], { cwd: path.join(__dirname, 'vector') });
    py.stdin.write(JSON.stringify({ vectors, metadatas }));
    py.stdin.end();
    py.stdout.on('data', d => console.log('[PY]', d.toString()));
    py.stderr.on('data', d => console.error('[PY-ERR]', d.toString()));
    py.on('close', code => res.json({ ok: true, message: 'Index dari MySQL selesai' }));
  } catch (e) {
    console.error(e);
    res.status(500).json({ ok: false, error: e.toString() });
  }
});

// Event-driven indexing
router.post('/db-event', express.json(), async (req, res) => {
  try {
    const { action, data } = req.body;
    // ...implementasi event-driven indexing sesuai kebutuhan...
    res.json({ ok: true, message: 'Event-driven indexing processed' });
  } catch (e) {
    console.error(e);
    res.status(500).json({ ok: false, error: e.toString() });
  }
});

module.exports = router;
