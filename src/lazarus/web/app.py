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

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

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

    @app.route("/api/fetch-models", methods=["POST"])
    def api_fetch_models():
        if not session.get("logged_in"):
            return jsonify({"error": "login"})
        data = request.get_json()
        api_url = data.get("api_url", "")
        api_key = data.get("api_key", "")
        if not api_url or not api_key:
            return jsonify({"error": "URL and Key required"})
        try:
            models_url = api_url.rstrip("/") + "/models"
            headers = {"Authorization": f"Bearer {api_key}"}
            r = requests.get(models_url, headers=headers, timeout=15)
            if r.status_code == 200:
                models = [m.get("id", "") for m in r.json().get("data", []) if m.get("id")]
                return jsonify({"models": sorted(models)})
            return jsonify({"error": f"HTTP {r.status_code}", "models": []})
        except Exception as e:
            return jsonify({"error": str(e), "models": []})

    @app.route("/api/test-model", methods=["POST"])
    def api_test_model():
        if not session.get("logged_in"):
            return jsonify({"error": "login"})
        data = request.get_json()
        api_url = data.get("api_url", config.data["api"]["url"])
        api_key = data.get("api_key", config.data["api"]["key"])
        model = data.get("model", config.data["api"]["model"])
        url = api_url.rstrip("/")
        if not url.endswith("/chat/completions"):
            url += "/chat/completions"
        try:
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {"model": model, "messages": [{"role": "user", "content": "say ok"}], "max_tokens": 10}
            r = requests.post(url, headers=headers, json=payload, timeout=15)
            if r.status_code == 200:
                txt = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                return jsonify({"ok": True, "response": txt[:50], "model": model})
            return jsonify({"ok": False, "error": f"HTTP {r.status_code}"})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})

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
