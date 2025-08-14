// ...existing code...
const express = require('express');
const router = express.Router();

// Progress SSE
let clients = [];
router.get('/progress-stream', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();
  clients.push(res);
  req.on('close', () => {
    clients = clients.filter(c => c !== res);
  });
});
const fs = require('fs');
const path = require('path');
const multer = require('multer');
const { extractText, chunkText } = require('../docs/docUtils');
const { spawn } = require('child_process');
const OpenAI = require('openai');
const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
const docsDir = path.join(__dirname, '..', 'docs');
const upload = multer({ dest: path.join(__dirname, 'uploads') });

// Upload dokumen
router.post('/upload', upload.single('file'), async (req, res) => {
  try {
  let kategori = req.body.kategori || req.query.kategori || (req.body && req.body.get && req.body.get('kategori'));
  if (Array.isArray(kategori)) kategori = kategori[0];
  if (!kategori || typeof kategori !== 'string') return res.status(400).json({ ok: false, error: 'Kategori wajib diisi' });
    const tmp = req.file.path;
    const originalName = req.file.originalname;
    // Simpan file ke folder kategori
    const kategoriDir = path.join(docsDir, kategori);
    if (!fs.existsSync(kategoriDir)) fs.mkdirSync(kategoriDir, { recursive: true });
    const destPath = path.join(kategoriDir, originalName);
    fs.renameSync(tmp, destPath);
    const text = await extractText(destPath);
    const chunks = chunkText(text, 500);
    const vectors = [];
    const metadatas = [];
    for (let i = 0; i < chunks.length; i++) {
      const chunk = chunks[i];
      const embRes = await openai.embeddings.create({ model: 'text-embedding-3-small', input: chunk });
      const emb = embRes.data[0].embedding;
      vectors.push(emb);
      metadatas.push({ source: originalName, chunk_index: i, text: chunk, kategori });
    }
    // Buat nama index dan meta sesuai kategori
    const indexFile = `index_${kategori}.faiss`;
    const metaFile = `meta_${kategori}.pkl`;
    const py = spawn(
      process.env.PYTHON_PATH,
      ['-u', path.join(__dirname, '..', 'vector', 'faiss_index.py'), indexFile, metaFile],
      {
        cwd: path.join(__dirname, '..', 'vector'),
        stdio: ['pipe', 'pipe', 'inherit'],
        env: { ...process.env, PYTHONUNBUFFERED: '1' }
      }
    );
    py.stdin.write(JSON.stringify({ vectors, metadatas }));
    py.stdin.end();
    py.stdout.on('data', d => {
      const lines = d.toString().split(/\r?\n/);
      for (const line of lines) {
        if (line.trim().startsWith('Progress:')) {
          for (const client of clients) {
            client.write(`data: ${line.trim()}\n\n`);
          }
        }
      }
      process.stdout.write(d);
    });
    py.on('close', code => console.log('faiss indexer exited', code));
    res.json({ ok: true, message: 'File uploaded and indexing started' });
  } catch (e) {
    console.error(e);
    res.status(500).json({ ok: false, error: e.toString() });
  }
}); 

// Daftar dokumen
router.get('/docs', (req, res) => {
  try {
    let kategori = req.query.kategori;
    if (Array.isArray(kategori)) kategori = kategori[0];
    kategori = (typeof kategori === 'string' && kategori.trim() !== '') ? kategori : '';
    const allowedKategori = ['keuangan', 'sdm', 'operasional', 'teknologi', 'hukum'];
    let dir = docsDir;
    if (kategori) {
      if (!allowedKategori.includes(kategori)) {
        return res.status(400).json({ ok: false, error: 'Kategori tidak valid' });
      }
      dir = path.join(docsDir, kategori);
    }
    if (!fs.existsSync(dir)) return res.json({ ok: true, files: [] });
    const files = fs.readdirSync(dir).filter(f => f.endsWith('.pdf') || f.endsWith('.txt'));
    const filesWithKategori = files.map(f => ({ nama: f, kategori }));
    res.json({ ok: true, files: filesWithKategori });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.toString() });
  }
});

// Hapus dokumen
router.post('/delete', express.json(), async (req, res) => {
  try {
    const { filename, kategori } = req.body;
    if (!filename) return res.status(400).json({ ok: false, error: 'No filename provided' });
    let filePath = docsDir;
    if (kategori && typeof kategori === 'string' && kategori.trim() !== '') {
      filePath = path.join(filePath, kategori);
    }
    filePath = path.join(filePath, filename);
    if (!fs.existsSync(filePath)) return res.status(404).json({ ok: false, error: 'File not found' });
    fs.unlinkSync(filePath);
    // Update index dan metadata FAISS setelah file dihapus
    // Tentukan index dan meta file sesuai kategori
    const allowedKategori = ['keuangan', 'sdm', 'operasional', 'teknologi', 'hukum'];
    let indexFile = 'company_index.faiss';
    let metaFile = 'company_meta.pkl';
    if (kategori && allowedKategori.includes(kategori)) {
      indexFile = `index_${kategori}.faiss`;
      metaFile = `meta_${kategori}.pkl`;
    }
    const py = spawn(
      process.env.PYTHON_PATH,
      [path.join(__dirname, '..', 'vector', 'faiss_remove_file.py'), indexFile, metaFile],
      { cwd: path.join(__dirname, '..', 'vector') }
    );
    py.stdin.write(JSON.stringify({ filename }));
    py.stdin.end();
    py.stdout.on('data', d => console.log('[PY-REMOVE]', d.toString()));
    py.stderr.on('data', d => console.error('[PY-REMOVE-ERR]', d.toString()));
    py.on('close', code => {
      res.json({ ok: true, message: 'File deleted and index updated' });
    });
  } catch (e) {
    console.error(e);
    res.status(500).json({ ok: false, error: e.toString() });
  }
});

// Pencarian RAG
router.post('/search', express.json(), async (req, res) => {
  try {
    const question = req.body.question;
    let kategori = req.body.kategori;
    if (Array.isArray(kategori)) kategori = kategori[0];
    kategori = (typeof kategori === 'string' && kategori.trim() !== '') ? kategori : '';
    const allowedKategori = ['keuangan', 'sdm', 'operasional', 'teknologi', 'hukum'];
    if (!question) return res.status(400).json({ ok: false, error: 'No question provided' });
    if (!kategori || !allowedKategori.includes(kategori)) return res.status(400).json({ ok: false, error: 'Kategori '+kategori+' tidak valid' });
    const embRes = await openai.embeddings.create({ model: 'text-embedding-3-small', input: question });
    const vector = embRes.data[0].embedding;
    // Gunakan index dan meta file sesuai kategori
    const indexFile = `index_${kategori}.faiss`;
    const metaFile = `meta_${kategori}.pkl`;
    const py = spawn(
      process.env.PYTHON_PATH,
      [path.join(__dirname, '..', 'vector', 'faiss_search.py'), indexFile, metaFile],
      { cwd: path.join(__dirname, '..', 'vector') }
    );
    py.stdin.write(JSON.stringify({ vector, top_k: 5 }));
    py.stdin.end();
    let out = '';
    py.stdout.on('data', d => { out += d.toString(); });
    py.stderr.on('data', d => console.error('[PY-ERR]', d.toString()));
    py.on('close', async code => {
      let results = [];
      try { results = JSON.parse(out); } catch (e) { console.error('FAISS parse error:', e); }
      const contexts = results.map(r => r.text).join('\n\n---\n\n');
      const systemPrompt = "Kamu adalah asisten perusahaan. Jawab pertanyaan user menggunakan hanya konteks berikut (jika perlu, jawaban boleh singkat):\n" + contexts+ "\n\n, sebutkan sumber referensi atas jawaban kamu.";
      let answer = '';
      try {
        const chat = await openai.chat.completions.create({
          model: 'gpt-4o',
          messages: [
            { role: 'system', content: systemPrompt },
            { role: 'user', content: question }
          ],
          max_tokens: 800
        });
        answer = (chat.choices && chat.choices[0] && chat.choices[0].message && chat.choices[0].message.content) || 'Maaf, gagal mendapatkan jawaban.';
      } catch (e) {
        answer = 'Maaf, gagal mendapatkan jawaban dari LLM.';
      }
      res.json({ ok: true, results, answer });
    });
  } catch (e) {
    console.error(e);
    res.status(500).json({ ok: false, error: e.toString() });
  }
});

module.exports = router;
