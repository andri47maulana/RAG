module.exports = {
  apps: [
    {
      name: 'rag-backend',
      cwd: './backend/v1/app',
      // TIP (server): Prefer using absolute path to your venv's gunicorn to avoid PATH issues.
      // Example:
      //   script: '/var/www/staging/stg-ai/RAG/venv/bin/gunicorn',
      //   args: 'main:app -b 127.0.0.1:5001 -k gthread -w 2',
      //   interpreter: 'none',
      // Generic approach (requires /bin/bash and gunicorn on PATH):
      script: '/bin/bash',
      args: ['-lc', 'gunicorn -w 2 -k gthread -b 127.0.0.1:5001 main:app'],
      interpreter: 'none',
      exec_mode: 'fork',
      autorestart: true,
      watch: false,
      env: {
        NODE_ENV: 'production',
        PYTHONUNBUFFERED: '1'
      },
      out_file: './logs/backend_out.log',
      error_file: './logs/backend_err.log',
      time: true,
      max_memory_restart: '256M'
    },
    {
      name: 'rag-frontend',
      cwd: './frontend',
      // Run via npm start to avoid direct path issues for server.js
      script: '/bin/bash',
      args: ['-lc', 'npm start'],
      interpreter: 'none',
      exec_mode: 'fork',
      autorestart: true,
      watch: false,
      env: {
        NODE_ENV: 'production',
        PORT: 5002
      },
      out_file: './logs/frontend_out.log',
      error_file: './logs/frontend_err.log',
      time: true,
      max_memory_restart: '256M'
    }
  ]
};
