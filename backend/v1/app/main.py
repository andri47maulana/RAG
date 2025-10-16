from dotenv import load_dotenv
import os
from flask import Flask, request
from flask_cors import CORS
from api import index

# Load .env from this app directory (do not commit .env)
_ENV_PATH = os.path.join(os.path.dirname(__file__), '.env')
try:
    # Do not override already-set environment variables (e.g., from PowerShell)
    load_dotenv(_ENV_PATH, override=False)
except Exception:
    # If loading fails, continue; missing keys will be reported by services
    pass

def create_app():
    app = Flask(__name__)
    # Allow local frontend origins during dev
    CORS(
        app,
        resources={r"/*": {"origins": [
            "http://localhost:5002", "http://127.0.0.1:5002",
            "http://localhost:8000", "http://127.0.0.1:8000",
            "http://localhost:8001", "http://127.0.0.1:8001"
        ]}},
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization"],
    )

    @app.after_request
    def add_cors_headers(response):
        allowed = {
            "http://localhost:5002", "http://127.0.0.1:5002",
            "http://localhost:8000", "http://127.0.0.1:8000",
            "http://localhost:8001", "http://127.0.0.1:8001"
        }
        origin = request.headers.get("Origin")
        if origin in allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    app.register_blueprint(index.bp)
    return app


app = create_app()

if __name__ == "__main__":
    # Print routes once
    print("[ROUTES] Daftar route Flask:")
    for rule in app.url_map.iter_rules():
        print(f"[ROUTE] {rule}")
    # Avoid Windows socket fromfd issue by disabling reloader on Windows
    use_reloader = False if os.name == 'nt' else True
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5001"))
    app.run(debug=True, host=host, port=port, use_reloader=use_reloader)
