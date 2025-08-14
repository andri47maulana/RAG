require('dotenv').config();

const express = require('express');
require('dotenv').config();
const app = express();
const path = require('path');
const port = process.env.UPLOADER_PORT || process.env.SERVER_PORT || 3005;

app.use(express.static(path.join(__dirname, 'static')));
app.use(express.json());

// Routing dokumen
const documentRoutes = require('./routes/document');
app.use('/', documentRoutes);

// Routing database
const databaseRoutes = require('./routes/database');
app.use('/', databaseRoutes);

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'static', 'upload.html'));
});

app.listen(port, () => {
  console.log('Uploader running on port', port);
  console.log('Open http://localhost:' + port + ' to upload documents (or embed via iframe in Botpress admin).');
});
