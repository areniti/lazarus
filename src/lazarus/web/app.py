"""Web Application - Flask UI"""
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
        return render_template("index.html")

    @app.route("/admin/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            if config.login(username, password):
                session["logged_in"] = True
                return redirect(url_for("admin"))
            return render_template("login.html", error="Wrong username/password")
        return render_template("login.html", error=None)

    @app.route("/admin")
    def admin():
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        progress = pipeline.state.get_progress()
        sites = list(config.output_dir.glob("*.html")) if config.output_dir.exists() else []
        return render_template("admin.html", progress=progress, sites=sites, config=config.data)

    @app.route("/api/chat", methods=["POST"])
    def api_chat():
        if not session.get("logged_in"):
            return jsonify({"error": "login required"})
        msg = request.json.get("message", "")
        if not msg:
            return jsonify({"error": "empty message"})
        result = pipeline.process(msg)
        return jsonify(result)

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
        return render_template("user.html", sites=sites)

    return app
