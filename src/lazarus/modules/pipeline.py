"""Pipeline - Professional CMS"""
import shutil
from pathlib import Path
from .ai import AI
from .tools import Tools
from ..core.config import Config
from ..core.memory import Memory


class Pipeline:
    def __init__(self, config=None):
        self.config = config or Config()
        self.ai = AI(self.config)
        self.tools = Tools(self.config.output_dir)
        self.memory = Memory()

    def process(self, message):
        self.memory.save_message("user", message)
        history = self.memory.get_history(limit=10)

        action = self.ai.classify(message)

        if action == "chat":
            response = self.ai.chat(message, history)
            self.memory.save_message("assistant", response)
            return {"response": response, "files": [], "status": "chat"}

        if action == "edit":
            return self._handle_edit(message)

        return self._handle_build(message)

    def _handle_build(self, message):
        log = []
        output = self.config.output_dir

        # STEP 0: پاک کردن output
        if output.exists():
            shutil.rmtree(output)
        output.mkdir(parents=True, exist_ok=True)
        log.append("🧹 پاک کردن پروژه قبلی...")

        # STEP 1: DECOMPOSE
        log.append("📋 تحلیل پروژه...")
        plan = self.ai.decompose(message)
        files = plan.get("files", [])
        if not files:
            return {"response": "❌ نتوانستم پروژه را تحلیل کنم.", "files": [], "status": "error"}

        log.append("✅ ساختار پروژه:")
        for f in files:
            log.append(f"  📄 {f['path']}")

        # STEP 2: CSS
        log.append("\n🎨 ساخت style.css...")
        css_code = self.ai.generate_css(plan)
        css = self.tools.extract_css(css_code)
        if css:
            (output / "style.css").write_text(css, encoding="utf-8")
            log.append(f"✅ style.css ({len(css)} bytes)")
        else:
            log.append("❌ style.css ساخته نشد")

        # STEP 3: JS
        log.append("\n⚡ ساخت main.js...")
        js_code = self.ai.generate_js(plan)
        js = self.tools.extract_js(js_code)
        if js:
            (output / "main.js").write_text(js, encoding="utf-8")
            log.append(f"✅ main.js ({len(js)} bytes)")
        else:
            log.append("❌ main.js ساخته نشد")

        # STEP 4: index.html — صفحه اصلی با همه sections
        log.append("\n🔧 ساخت index.html (صفحه اصلی با همه sections)...")
        html_code = self.ai.generate_homepage(message, plan)
        html = self.tools.extract_html(html_code)
        if html:
            # Ensure CSS link exists
            if 'style.css' not in html:
                html = html.replace('<head>', '<head>\n    <link rel="stylesheet" href="style.css">', 1)
            # Ensure JS link exists
            if 'main.js' not in html:
                html = html.replace('</body>', '    <script src="main.js"></script>\n</body>', 1)
            # Ensure closing tags
            if '</html>' not in html:
                html += '\n</html>'
            (output / "index.html").write_text(html, encoding="utf-8")
            log.append(f"✅ index.html ({len(html)} bytes)")
        else:
            log.append("❌ index.html ساخته نشد")

        # SUMMARY
        response = "\n".join(log)
        html_files = list(output.glob("*.html"))
        if html_files:
            response += f"\n\n🌐 /preview/index.html"
        self.memory.save_message("assistant", response)
        return {"response": response, "files": [{"name": f.name, "size": f.stat().st_size} for f in output.iterdir() if f.is_file()], "status": "done"}

    def _handle_edit(self, message):
        current_path = self.config.output_dir / "index.html"
        if not current_path.exists():
            return {"response": "سایتی وجود نداره.", "files": [], "status": "error"}
        current_code = current_path.read_text("utf-8")
        result = self.ai.edit(current_code, message)
        new_html = self.tools.extract_html(result)
        if new_html:
            current_path.write_text(new_html, encoding="utf-8")
            return {"response": "✅ ادیت شد!", "files": [{"name": "index.html", "size": len(new_html)}], "status": "done"}
        return {"response": "❌ ادیت انجام نشد.", "files": [], "status": "error"}
