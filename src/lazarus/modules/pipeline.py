"""Pipeline - orchestrates a build: plan → css → js → html."""
import shutil
import tempfile
from pathlib import Path

from ..core.config import Config
from ..core.memory import Memory
from .ai import AI, AIError
from .tools import Tools


class Pipeline:
    def __init__(self, config=None):
        self.config = config or Config()
        self.ai = AI(self.config)
        self.tools = Tools(self.config.output_dir)
        self.memory = Memory()

    # ===== entry point =====

    def process(self, message):
        self.memory.save_message("user", message)
        action = self.ai.classify(message)

        try:
            if action == "chat":
                history = self.memory.get_history(limit=10)
                response = self.ai.chat(message, history)
                self.memory.save_message("assistant", response)
                return {"response": response, "files": [], "status": "chat"}
            if action == "edit":
                return self._handle_edit(message)
            return self._handle_build(message)
        except AIError as e:
            response = f"❌ {e}"
            self.memory.save_message("assistant", response)
            return {"response": response, "files": [], "status": "error"}

    # ===== build =====

    def _handle_build(self, message):
        log = []
        output = Path(self.config.output_dir)

        # Build into a temp dir first, so a failure never destroys the live site.
        staging = Path(tempfile.mkdtemp(prefix="lazarus-build-"))
        try:
            log.append("📋 تحلیل پروژه...")
            plan = self.ai.decompose(message)
            sections = plan.get("sections", [])
            log.append(f"✅ {plan.get('project_name', 'پروژه')} — "
                       f"{len(sections)} بخش:")
            for s in sections:
                log.append(f"  • {s.get('title')} (#{s.get('id')})")

            log.append("\n🎨 ساخت style.css...")
            css = self.tools.extract_css(self.ai.generate_css(plan))
            if not css:
                raise AIError("مدل CSS معتبری تولید نکرد.")
            (staging / "style.css").write_text(css, encoding="utf-8")
            log.append(f"✅ style.css ({len(css)} bytes)")

            log.append("\n⚡ ساخت main.js...")
            js = self.tools.extract_js(self.ai.generate_js(plan))
            if not js:
                raise AIError("مدل JavaScript معتبری تولید نکرد.")
            (staging / "main.js").write_text(js, encoding="utf-8")
            log.append(f"✅ main.js ({len(js)} bytes)")

            log.append("\n🔧 ساخت index.html...")
            html = self.tools.extract_html(self.ai.generate_homepage(message, plan))
            if not html:
                raise AIError("مدل HTML معتبری تولید نکرد.")
            html = self.tools.ensure_assets(html)
            (staging / "index.html").write_text(html, encoding="utf-8")
            log.append(f"✅ index.html ({len(html)} bytes)")

            verdict = self.tools.html_validate_text(html)
            if verdict != "VALID":
                log.append(f"⚠️ {verdict}")

            # Everything succeeded — swap staging into place atomically-ish.
            self._promote(staging, output)
            log.append("\n🌐 آماده است: /preview/index.html")
            response = "\n".join(log)
            self.memory.save_message("assistant", response)
            return {
                "response": response,
                "files": [{"name": f.name, "size": f.stat().st_size}
                          for f in sorted(output.iterdir()) if f.is_file()],
                "status": "done",
            }
        except AIError as e:
            log.append(f"\n❌ {e}")
            log.append("سایت قبلی دست‌نخورده باقی ماند.")
            response = "\n".join(log)
            self.memory.save_message("assistant", response)
            return {"response": response, "files": [], "status": "error"}
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    @staticmethod
    def _promote(staging, output):
        """Replace output with staging contents, keeping a rollback copy."""
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        backup = output.with_name(output.name + ".prev")
        shutil.rmtree(backup, ignore_errors=True)
        if output.exists():
            output.rename(backup)
        try:
            shutil.copytree(staging, output)
        except Exception:
            shutil.rmtree(output, ignore_errors=True)
            if backup.exists():
                backup.rename(output)
            raise
        shutil.rmtree(backup, ignore_errors=True)

    # ===== edit =====

    def _handle_edit(self, message):
        current_path = Path(self.config.output_dir) / "index.html"
        if not current_path.is_file():
            response = "سایتی وجود نداره که ادیت بشه. اول یکی بساز."
            self.memory.save_message("assistant", response)
            return {"response": response, "files": [], "status": "error"}

        current_code = current_path.read_text("utf-8")
        new_html = self.tools.extract_html(self.ai.edit(current_code, message))
        if not new_html:
            response = "❌ ادیت انجام نشد — مدل HTML معتبری برنگرداند."
            self.memory.save_message("assistant", response)
            return {"response": response, "files": [], "status": "error"}

        new_html = self.tools.ensure_assets(new_html)
        current_path.write_text(new_html, encoding="utf-8")
        response = "✅ ادیت شد!\n\n🌐 /preview/index.html"
        self.memory.save_message("assistant", response)
        return {"response": response,
                "files": [{"name": "index.html", "size": len(new_html)}],
                "status": "done"}
