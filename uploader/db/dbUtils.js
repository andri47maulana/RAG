const mysql = require('mysql2/promise');

async function getConnection() {
  return mysql.createConnection({
    host: process.env.MYSQL_HOST,
    user: process.env.MYSQL_USER,
    password: process.env.MYSQL_PASSWORD,
    database: process.env.MYSQL_DATABASE,
    port: process.env.MYSQL_PORT
  });
}

async function fetchDocuments() {
  const conn = await getConnection();
  const [rows] = await conn.execute('SELECT id, judul, isi FROM dokumen');
  await conn.end();
  return rows;
}

module.exports = { getConnection, fetchDocuments };
