module.exports = {
  apps: [
    {
      name: "backend-api",
      script: "./venv/bin/gunicorn",
      args: "api.index:app -b 0.0.0.0:5001 -k uvicorn.workers.UvicornWorker --timeout 300 --workers 2",
      cwd: "/var/www/staging/stg-ai/RAG/backend/v1/app",
      interpreter: "none", // penting: biar PM2 pakai binary langsung, bukan node/python
      env: {
        NODE_ENV: "production",
        PYTHONUNBUFFERED: "1"
      }
    }
  ]
}
