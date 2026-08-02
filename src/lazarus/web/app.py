"""Web Application - Flask UI"""
import requests
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from ..core.config import Config
from ..modules.pipeline import Pipeline


def create_app():
    app = Flask(__name__)
    app.secret_key = "42f161997178fe6461f6c1f9adff5571"
    config = Config()
    pipeline = Pipeline(config)

    def require_login():
        if not session.get("logged_in"):
            return False
        return True

    # ===== PUBLIC =====

    @app.route("/")
    def index():
        sites = []
        if config.output_dir.exists():
            sites = [{"name": f.stem, "file": f.name} for f in config.output_dir.glob("*.html")]
        return render_template("index.html", sites=sites)

    @app.route("/preview/<path:filename>")
    def preview(filename):
        path = config.output_dir / filename
        if path.exists():
            return path.read_text("utf-8"), 200, {"Content-Type": "text/html"}
        return "Not found", 404

    # ===== AUTH =====

    @app.route("/admin/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            if config.login(request.form.get("username", ""), request.form.get("password", "")):
                session["logged_in"] = True
                return redirect(url_for("admin"))
            return render_template("login.html", error="Wrong credentials")
        return render_template("login.html", error=None)

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("index"))

    # ===== ADMIN (3 tabs: Home, Chat, Settings) =====

    @app.route("/admin")
    def admin():
        if not require_login():
            return redirect(url_for("login"))
        sites = []
        if config.output_dir.exists():
            sites = [{"name": f.stem, "file": f.name, "size": f.stat().st_size}
                     for f in config.output_dir.glob("*.html")]
        return render_template("admin.html", sites=sites, config=config.data)

    @app.route("/admin/chat")
    def admin_chat():
        if not require_login():
            return redirect(url_for("login"))
        return render_template("chat.html", config=config.data)

    @app.route("/admin/settings")
    def admin_settings():
        if not require_login():
            return redirect(url_for("login"))
        return render_template("settings.html", config=config.data)

    @app.route("/admin/settings/api")
    def admin_api():
        if not require_login():
            return redirect(url_for("login"))
        return render_template("api_settings.html", config=config.data)

    # ===== API =====

    @app.route("/api/chat", methods=["POST"])
    def api_chat():
        if not require_login():
            return jsonify({"error": "login"})
        msg = request.json.get("message", "")
        if not msg:
            return jsonify({"error": "empty"})
        try:
            result = pipeline.process(msg)
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": str(e), "status": "error"})

    @app.route("/api/fetch-models", methods=["POST"])
    def api_fetch_models():
        if not require_login():
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
        if not require_login():
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
                result = r.json()
                choices = result.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "") or "ok"
                    return jsonify({"ok": True, "response": content[:50], "model": model})
                return jsonify({"ok": True, "response": "ok", "model": model})
            return jsonify({"ok": False, "error": f"HTTP {r.status_code}"})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})

    @app.route("/api/save-password", methods=["POST"])
    def api_save_password():
        if not require_login():
            return jsonify({"error": "login"})
        data = request.get_json()
        old_pass = data.get("old_password", "")
        new_pass = data.get("new_password", "")
        if not config.login(config.data["username"], old_pass):
            return jsonify({"error": "Wrong current password"})
        if not new_pass or len(new_pass) < 4:
            return jsonify({"error": "Password must be at least 4 characters"})
        config.data["password"] = new_pass
        config.save()
        return jsonify({"ok": True})

    @app.route("/api/save-username", methods=["POST"])
    def api_save_username():
        if not require_login():
            return jsonify({"error": "login"})
        data = request.get_json()
        old_pass = data.get("password", "")
        new_user = data.get("new_username", "")
        if not config.login(config.data["username"], old_pass):
            return jsonify({"error": "Wrong password"})
        if not new_user or len(new_user) < 2:
            return jsonify({"error": "Username must be at least 2 characters"})
        config.data["username"] = new_user
        config.save()
        return jsonify({"ok": True})

    @app.route("/api/save-api", methods=["POST"])
    def api_save_api():
        if not require_login():
            return jsonify({"error": "login"})
        data = request.get_json()
        if data.get("api_url"): config.data["api"]["url"] = data["api_url"]
        if data.get("api_key"): config.data["api"]["key"] = data["api_key"]
        if data.get("api_model"): config.data["api"]["model"] = data["api_model"]
        config.save()
        return jsonify({"ok": True})

    @app.route("/api/add-model", methods=["POST"])
    def api_add_model():
        if not require_login():
            return jsonify({"error": "login"})
        data = request.get_json()
        name = data.get("name", "")
        url = data.get("url", "")
        key = data.get("key", "")
        if not name or not url or not key:
            return jsonify({"error": "Name, URL, and Key are required"})
        config.add_model(name, url, key)
        return jsonify({"ok": True})

    @app.route("/api/remove-model", methods=["POST"])
    def api_remove_model():
        if not require_login():
            return jsonify({"error": "login"})
        data = request.get_json()
        index = data.get("index", -1)
        config.remove_model(index)
        return jsonify({"ok": True})

    @app.route("/api/chat-history")
    def api_chat_history():
        if not require_login():
            return jsonify({"error": "login"})
        history = pipeline.memory.get_history(limit=50)
        return jsonify({"history": history})

    @app.route("/api/models-list")
    def api_models_list():
        if not require_login():
            return jsonify({"error": "login"})
        return jsonify({"models": config.data.get("models", [])})

    # ===== USER =====

    @app.route("/user")
    def user_page():
        sites = []
        if config.output_dir.exists():
            sites = [{"name": f.stem, "file": f.name} for f in config.output_dir.glob("*.html")]
        return render_template("index.html", sites=sites)

    return app
