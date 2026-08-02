"""Web Application - Flask UI"""
import requests
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from ..core.config import Config
from ..modules.pipeline import Pipeline


def create_app():
    app = Flask(__name__)
    app.secret_key = "lazarus-secret-key-change-me"
    config = Config()
    pipeline = Pipeline(config)

    @app.route("/")
    def index():
        sites = []
        if config.output_dir.exists():
            sites = [{"name": f.stem, "file": f.name} for f in config.output_dir.glob("*.html")]
        return render_template("index.html", sites=sites)

    @app.route("/admin/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            if config.login(request.form.get("username", ""), request.form.get("password", "")):
                session["logged_in"] = True
                return redirect(url_for("admin"))
            return render_template("login.html", error="Wrong credentials")
        return render_template("login.html", error=None)

    @app.route("/admin")
    def admin():
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        sites = []
        if config.output_dir.exists():
            sites = [{"name": f.stem, "file": f.name, "size": f.stat().st_size}
                     for f in config.output_dir.glob("*.html")]
        return render_template("admin.html", sites=sites, config=config.data)

    @app.route("/admin/save-config", methods=["POST"])
    def admin_save_config():
        if not session.get("logged_in"):
            return jsonify({"error": "login"})
        data = request.get_json()
        if data.get("api_url"): config.data["api"]["url"] = data["api_url"]
        if data.get("api_key"): config.data["api"]["key"] = data["api_key"]
        if data.get("api_model"): config.data["api"]["model"] = data["api_model"]
        if data.get("username"): config.data["username"] = data["username"]
        if data.get("password"): config.data["password"] = data["password"]
        config.save()
        return jsonify({"ok": True})

    @app.route("/api/chat", methods=["POST"])
    def api_chat():
        if not session.get("logged_in"):
            return jsonify({"error": "login"})
        msg = request.json.get("message", "")
        if not msg:
            return jsonify({"error": "empty"})
        try:
            result = pipeline.process(msg)
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": str(e), "status": "error"})

    @app.route("/preview/<filename>")
    def preview(filename):
        path = config.output_dir / filename
        if path.exists():
            return path.read_text("utf-8"), 200, {"Content-Type": "text/html"}
        return "Not found", 404

    @app.route("/user")
    def user_page():
        sites = []
        if config.output_dir.exists():
            sites = [{"name": f.stem, "file": f.name} for f in config.output_dir.glob("*.html")]
        return render_template("index.html", sites=sites)

    return app
