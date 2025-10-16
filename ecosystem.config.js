module.exports = {
  apps: [
    {
      name: 'rag-backend',
      cwd: './backend/v1/app',
      script: 'gunicorn',
      args: '-w 2 -k gthread -b 127.0.0.1:5001 main:app',
      interpreter: 'python3',
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
      max_memory_restart: '512M'
    },
    {
      name: 'rag-frontend',
      cwd: './frontend',
      script: 'server.js',
      interpreter: 'node',
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
