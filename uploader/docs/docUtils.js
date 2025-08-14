const fs = require('fs');
const pdfParse = require('pdf-parse');

async function extractText(filePath) {
  if (filePath.endsWith('.pdf')) {
    const data = fs.readFileSync(filePath);
    try {
      const res = await pdfParse(data);
      return res.text;
    } catch (e) {
      console.error('PDF parse error', e);
      return '';
    }
  } else {
    return fs.readFileSync(filePath, 'utf8');
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
