from flask import Flask
from api import index
from flask_cors import CORS

def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True, allow_headers=["Content-Type", "Authorization"])  # Aktifkan CORS global
    app.register_blueprint(index.bp)
    return app
app = create_app()

if __name__ == "__main__":
    app = create_app()
    print("[ROUTES] Daftar route Flask:")
    for rule in app.url_map.iter_rules():
        print(f"[ROUTE] {rule}")
    app.run(debug=True, port=5001)
