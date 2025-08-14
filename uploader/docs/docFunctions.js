// Fungsi-fungsi terkait dokumen (PDF/TXT)
const fs = require('fs');
const path = require('path');
const pdfParse = require('pdf-parse');

function extractText(filePath) {
  if (filePath.endsWith('.pdf')) {
    const data = fs.readFileSync(filePath);
    return pdfParse(data).then(res => res.text);
  } else {
    return Promise.resolve(fs.readFileSync(filePath, 'utf8'));
  }
}

function chunkText(text, size = 500) {
  text = text.replace(/\r\n/g, '\n');
  const chunks = [];
  for (let i = 0; i < text.length; i += size) {
    const chunk = text.slice(i, i + size).trim();
    if (chunk) chunks.push(chunk);
  }
  return chunks;
}

module.exports = { extractText, chunkText };
