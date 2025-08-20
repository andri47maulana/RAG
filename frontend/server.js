require('dotenv').config();

const express = require('express');
const app = express();
const path = require('path');
const port = process.env.NODE_PORT;




// Serve upload.html with injected env
app.get('/upload.html', (req, res) => {
  const fs = require('fs');
  let html = fs.readFileSync(path.join(__dirname, 'pages', 'upload.html'), 'utf8');
  // Inject window.env script after <body>
  html = html.replace(
    '<body>',
    `<body><script>window.env = { PYTHON_URL: "${process.env.PYTHON_URL}", SECURITY_KEY: "${process.env.SECURITY_API_KEY}" };</script>`
  );
  res.send(html);
});

app.use(express.static(path.join(__dirname, 'pages')));
app.use(express.json()); 

app.get('/', (req, res) => {
  res.redirect('/upload.html');
});

app.listen(port, () => {
  console.log('Uploader running on port', port);
  console.log('Open http://localhost:' + port );
});

