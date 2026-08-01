"""Lazarus Pipeline - CPU-like architecture for code generation"""
from .ai import AI
from .state import StateRegister
from .executor import Executor
from ..core.config import Config


class Pipeline:
    """
    Main pipeline.
    Developer mode: chat for normal messages, build for requests.
    Admin mode: settings only.
    """

    def __init__(self, config=None):
        self.config = config or Config()
        self.ai = AI(self.config)
        self.state = StateRegister(self.config.output_dir)
        self.executor = Executor(self.ai, self.state, self.config.output_dir)

    def process(self, message, history=None):
        """Full pipeline for a user message"""
        history = history or []
        role = self.config.data.get("role", "developer")

        if role == "admin":
            return {"response": "Admin mode. Use /admin for settings.", "files": [], "status": "admin"}

        # Check if user wants to BUILD something
        is_build_request = self.ai.needs_code(message)

        if not is_build_request:
            # It's just chat
            response = self.ai.chat(message, history)
            return {"response": response, "files": [], "status": "chat"}

        # Build request - generate code
        print(f"\n🔨 Building: {message[:50]}...")
        self.state.start_new_project(message, [{"name": "main", "description": message}])
        self.state.start_step(0)

        code = self.ai.generate_code(message)
        html = self.executor._extract_html(code)

        if not html:
            self.state.fail_step(0, "No HTML generated")
            return {"response": f"❌ نتونستم کد بسازم.\n\n{code[:300]}", "files": [], "status": "error"}

        ok, error = self.executor._validate(html)
        if not ok:
            self.state.fail_step(0, error)
            return {"response": f"❌ خطا: {error}", "files": [], "status": "error"}

        filepath = self.config.output_dir / "main.html"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(html, encoding="utf-8")

        self.state.complete_step(0, {"path": "main.html", "name": "main"})
        self.state.finish()

        return {
            "response": f"✅ سایت ساخته شد! ({len(html)} bytes)\n🔗 /preview/main.html",
            "files": [{"path": "main.html", "name": "main", "size": len(html)}],
            "status": "done",
        }
