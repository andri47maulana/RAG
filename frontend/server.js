require('dotenv').config();

const express = require('express');
const app = express();
const path = require('path');
const port = process.env.NODE_PORT;



app.use(express.static(path.join(__dirname, 'pages')));
app.use(express.json());

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'pages', 'upload.html'));
});

app.listen(port, () => {
  console.log('Uploader running on port', port);
  console.log('Open http://localhost:' + port );
});

