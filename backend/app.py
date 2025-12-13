import os
from pathlib import Path

from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from routes import api
from config import config


def _dist_dir():
    """Resolve frontend/dist relative to backend folder."""
    return (Path(__file__).resolve().parent.parent / "frontend" / "dist").resolve()


def create_app():
    # Load backend/.env so service credentials and feature flags are available when running locally.
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")
    dist_dir = _dist_dir()
    app = Flask(__name__, static_folder=str(dist_dir), static_url_path="/")
    CORS(app)
    app.register_blueprint(api)

    # Serve built frontend if present; otherwise show a friendly message.
    if dist_dir.exists():
        @app.route("/", defaults={"path": ""})
        @app.route("/<path:path>")
        def serve_spa(path):
            target = dist_dir / path
            if path and target.exists():
                return send_from_directory(dist_dir, path)
            return send_from_directory(dist_dir, "index.html")
    else:
        @app.route("/", defaults={"path": ""})
        @app.route("/<path:path>")
        def frontend_missing(path):
            return (
                "Frontend build not found. Please run 'npm install && npm run build' in the frontend directory.",
                503,
            )

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=config.DEBUG)
