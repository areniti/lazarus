"""Web Application - Flask UI"""
import time
from pathlib import PurePath

import requests
from flask import (Flask, jsonify, redirect, render_template, request, session,
                   url_for)

from .. import __version__
from ..core.config import Config
from ..modules.pipeline import Pipeline

# Extensions the static catch-all is allowed to serve out of the output dir.
ALLOWED_EXT = {".css", ".js", ".html", ".png", ".jpg", ".jpeg", ".svg",
               ".ico", ".gif", ".webp", ".woff", ".woff2", ".json", ".txt"}

CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}

TEXT_EXT = {".css", ".js", ".html", ".json", ".txt", ".svg"}

# Simple in-memory brute-force guard for the login form.
LOGIN_MAX_ATTEMPTS = 8
LOGIN_WINDOW = 300  # seconds


class LoginGuard:
    """Per-app failed-login tracker. Instance state, not a module global,
    so separate apps (and separate tests) never share a counter."""

    def __init__(self, max_attempts=LOGIN_MAX_ATTEMPTS, window=LOGIN_WINDOW):
        self.max_attempts = max_attempts
        self.window = window
        self._attempts = {}

    def is_limited(self, ip):
        now = time.time()
        recent = [t for t in self._attempts.get(ip, []) if now - t < self.window]
        self._attempts[ip] = recent
        return len(recent) >= self.max_attempts

    def record(self, ip):
        self._attempts.setdefault(ip, []).append(time.time())

    def reset(self, ip):
        self._attempts.pop(ip, None)


def _safe_output_path(output_dir, filename):
    """Resolve filename inside output_dir, refusing traversal and bad extensions."""
    ext = PurePath(filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        return None
    try:
        base = output_dir.resolve()
        target = (base / filename).resolve()
    except (OSError, RuntimeError):
        return None
    if base != target and base not in target.parents:
        return None
    if not target.is_file():
        return None
    return target


def _serve(path):
    ext = path.suffix.lower()
    ct = CONTENT_TYPES.get(ext, "application/octet-stream")
    if ext in TEXT_EXT:
        return path.read_text("utf-8"), 200, {"Content-Type": ct}
    return path.read_bytes(), 200, {"Content-Type": ct}


def create_app():
    app = Flask(__name__)
    boot_config = Config()
    # Secret key lives in the user's own config, never hardcoded in the package.
    app.secret_key = boot_config.data["secret_key"]
    guard = LoginGuard()
    app.extensions["lazarus_login_guard"] = guard

    def cfg():
        """Fresh config every request so saved settings take effect immediately."""
        return Config()

    def require_login():
        return bool(session.get("logged_in"))

    @app.after_request
    def no_cache(response):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    # ===== PUBLIC =====

    @app.route("/")
    def index():
        config = cfg()
        index_file = config.output_dir / "index.html"
        if index_file.is_file():
            return index_file.read_text("utf-8"), 200, {
                "Content-Type": "text/html; charset=utf-8"}
        return render_template("index.html", sites=[])

    @app.route("/preview/<path:filename>")
    def preview(filename):
        """Serve a generated file from the output dir (used by admin 'view')."""
        path = _safe_output_path(cfg().output_dir, filename)
        if path is None:
            return "Not found", 404
        return _serve(path)

    # ===== FIRST-TIME SETUP =====

    @app.route("/admin/setup", methods=["GET", "POST"])
    def setup():
        config = cfg()
        if not config.data.get("is_first_run", False):
            return redirect(url_for("login"))

        if request.method == "POST":
            gen_user = request.form.get("gen_username", "")
            gen_pass = request.form.get("gen_password", "")
            new_user = request.form.get("new_username", "").strip()
            new_pass = request.form.get("new_password", "").strip()

            if not config.login(gen_user, gen_pass):
                return render_template("setup.html", error="اطلاعات ورود اشتباه است",
                                       success=False)
            if len(new_user) < 2:
                return render_template("setup.html",
                                       error="یوزرنیم حداقل ۲ کاراکتر", success=False)
            if len(new_pass) < 8:
                return render_template("setup.html",
                                       error="پسورد حداقل ۸ کاراکتر", success=False)

            config.complete_setup(new_user, new_pass)
            session["logged_in"] = True
            session["user"] = new_user
            return redirect(url_for("admin"))

        return render_template("setup.html", error=None, success=False)

    # ===== AUTH =====

    @app.route("/admin/login", methods=["GET", "POST"])
    def login():
        config = cfg()
        if config.data.get("is_first_run", False):
            return redirect(url_for("setup"))

        if request.method == "POST":
            ip = request.remote_addr or "unknown"
            if guard.is_limited(ip):
                return render_template(
                    "login.html",
                    error="تلاش زیاد. ۵ دقیقه دیگر امتحان کنید."), 429
            if config.login(request.form.get("username", ""),
                            request.form.get("password", "")):
                guard.reset(ip)
                session["logged_in"] = True
                session["user"] = config.data["username"]
                return redirect(url_for("admin"))
            guard.record(ip)
            return render_template("login.html", error="نام کاربری یا پسورد اشتباه است")
        return render_template("login.html", error=None)

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("index"))

    # ===== ADMIN =====

    @app.route("/admin")
    def admin():
        if not require_login():
            return redirect(url_for("login"))
        config = cfg()
        sites = []
        if config.output_dir.exists():
            for f in sorted(config.output_dir.rglob("*.html")):
                rel = f.relative_to(config.output_dir).as_posix()
                sites.append({"name": f.stem, "file": rel, "size": f.stat().st_size})
        return render_template("admin.html", sites=sites,
                               config=config.public_data(), version=__version__)

    @app.route("/admin/chat")
    def admin_chat():
        if not require_login():
            return redirect(url_for("login"))
        return render_template("chat.html", config=cfg().public_data())

    @app.route("/admin/settings")
    def admin_settings():
        if not require_login():
            return redirect(url_for("login"))
        return render_template("settings.html", config=cfg().public_data())

    @app.route("/admin/settings/api")
    def admin_api():
        if not require_login():
            return redirect(url_for("login"))
        return render_template("api_settings.html", config=cfg().public_data())

    # ===== API =====

    @app.route("/api/chat", methods=["POST"])
    def api_chat():
        if not require_login():
            return jsonify({"error": "login"}), 401
        payload = request.get_json(silent=True) or {}
        msg = (payload.get("message") or "").strip()
        if not msg:
            return jsonify({"error": "پیام خالی است", "status": "error"}), 400
        config = cfg()
        if not config.data["api"].get("url") or not config.data["api"].get("key"):
            return jsonify({
                "response": "❌ اول API را در تنظیمات وارد کنید.",
                "status": "error", "files": []})
        try:
            result = Pipeline(config).process(msg)
            return jsonify(result)
        except Exception as e:
            return jsonify({"response": f"❌ خطا: {e}", "error": str(e),
                            "status": "error", "files": []}), 500

    @app.route("/api/fetch-models", methods=["POST"])
    def api_fetch_models():
        if not require_login():
            return jsonify({"error": "login"}), 401
        data = request.get_json(silent=True) or {}
        api_url = data.get("api_url", "")
        api_key = data.get("api_key", "")
        if not api_url or not api_key:
            return jsonify({"error": "URL و Key الزامی است", "models": []})
        try:
            r = requests.get(api_url.rstrip("/") + "/models",
                             headers={"Authorization": f"Bearer {api_key}"},
                             timeout=15)
            if r.status_code == 200:
                models = [m.get("id", "") for m in r.json().get("data", [])
                          if m.get("id")]
                return jsonify({"models": sorted(models)})
            return jsonify({"error": f"HTTP {r.status_code}", "models": []})
        except Exception as e:
            return jsonify({"error": str(e), "models": []})

    @app.route("/api/test-model", methods=["POST"])
    def api_test_model():
        if not require_login():
            return jsonify({"error": "login"}), 401
        config = cfg()
        data = request.get_json(silent=True) or {}
        api_url = data.get("api_url") or config.data["api"]["url"]
        api_key = data.get("api_key") or config.data["api"]["key"]
        model = data.get("model") or config.data["api"]["model"]
        if not api_url or not api_key:
            return jsonify({"ok": False, "error": "URL و Key الزامی است"})
        url = api_url.rstrip("/")
        if not url.endswith("/chat/completions"):
            url += "/chat/completions"
        try:
            r = requests.post(
                url,
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                json={"model": model,
                      "messages": [{"role": "user", "content": "say ok"}],
                      "max_tokens": 10},
                timeout=20)
            if r.status_code != 200:
                return jsonify({"ok": False, "error": f"HTTP {r.status_code}"})
            choices = r.json().get("choices", [])
            content = "ok"
            if choices:
                content = choices[0].get("message", {}).get("content") or "ok"
            return jsonify({"ok": True, "response": content[:50], "model": model})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})

    @app.route("/api/save-password", methods=["POST"])
    def api_save_password():
        if not require_login():
            return jsonify({"error": "login"}), 401
        config = cfg()
        data = request.get_json(silent=True) or {}
        if not config.verify_password(data.get("old_password", "")):
            return jsonify({"error": "پسورد فعلی اشتباه است"})
        new_pass = data.get("new_password", "")
        if len(new_pass) < 8:
            return jsonify({"error": "پسورد حداقل ۸ کاراکتر"})
        config.set_password(new_pass)
        return jsonify({"ok": True})

    @app.route("/api/save-username", methods=["POST"])
    def api_save_username():
        if not require_login():
            return jsonify({"error": "login"}), 401
        config = cfg()
        data = request.get_json(silent=True) or {}
        if not config.verify_password(data.get("password", "")):
            return jsonify({"error": "پسورد اشتباه است"})
        new_user = data.get("new_username", "").strip()
        if len(new_user) < 2:
            return jsonify({"error": "یوزرنیم حداقل ۲ کاراکتر"})
        config.data["username"] = new_user
        config.save()
        session["user"] = new_user
        return jsonify({"ok": True})

    @app.route("/api/save-api", methods=["POST"])
    def api_save_api():
        if not require_login():
            return jsonify({"error": "login"}), 401
        config = cfg()
        data = request.get_json(silent=True) or {}
        if data.get("api_url"):
            config.data["api"]["url"] = data["api_url"]
        if data.get("api_key"):
            config.data["api"]["key"] = data["api_key"]
        if data.get("api_model"):
            config.data["api"]["model"] = data["api_model"]
        config.save()
        return jsonify({"ok": True})

    @app.route("/api/add-model", methods=["POST"])
    def api_add_model():
        if not require_login():
            return jsonify({"error": "login"}), 401
        data = request.get_json(silent=True) or {}
        name, url, key = data.get("name"), data.get("url"), data.get("key")
        if not name or not url or not key:
            return jsonify({"error": "نام، URL و Key الزامی است"})
        cfg().add_model(name, url, key)
        return jsonify({"ok": True})

    @app.route("/api/remove-model", methods=["POST"])
    def api_remove_model():
        if not require_login():
            return jsonify({"error": "login"}), 401
        data = request.get_json(silent=True) or {}
        cfg().remove_model(int(data.get("index", -1)))
        return jsonify({"ok": True})

    @app.route("/api/chat-history")
    def api_chat_history():
        if not require_login():
            return jsonify({"error": "login"}), 401
        from ..core.memory import Memory
        return jsonify({"history": Memory().get_history(limit=50)})

    @app.route("/api/models-list")
    def api_models_list():
        if not require_login():
            return jsonify({"error": "login"}), 401
        return jsonify({"models": cfg().data.get("models", [])})

    # ===== USER =====

    @app.route("/user")
    def user_page():
        config = cfg()
        sites = []
        if config.output_dir.exists():
            sites = [{"name": f.stem,
                      "file": f.relative_to(config.output_dir).as_posix()}
                     for f in sorted(config.output_dir.rglob("*.html"))]
        return render_template("index.html", sites=sites)

    # ===== STATIC FILES (LAST - catch-all) =====

    @app.route("/<path:filename>")
    def serve_file(filename):
        path = _safe_output_path(cfg().output_dir, filename)
        if path is None:
            return "Not found", 404
        return _serve(path)

    return app
