"""Pipeline - Professional multi-file CMS"""
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
        role = self.config.data.get("role", "developer")
        if role == "admin":
            return {"response": "Admin mode.", "files": [], "status": "admin"}

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
        """Build multi-file project"""
        log = []

        # ===== STEP 1: DECOMPOSE =====
        log.append("📋 تحلیل پروژه...")
        plan = self.ai.decompose(message)
        files = plan.get("files", [])
        if not files:
            return {"response": "❌ نتوانستم پروژه را تحلیل کنم.", "files": [], "status": "error"}

        log.append(f"✅ ساختار پروژه:")
        log.append(f"📁 {plan.get('project_name', 'site')}/")
        for f in files:
            log.append(f"  📄 {f['path']}")

        # ===== STEP 2: CREATE DIRECTORY STRUCTURE =====
        log.append("\n📁 ایجاد دایرکتوری‌ها...")
        base = self.config.output_dir / plan.get("project_name", "site")
        for d in ["css", "js", "pages", "images"]:
            (base / d).mkdir(parents=True, exist_ok=True)
        log.append("✅ دایرکتوری‌ها ساخته شد")

        # ===== STEP 3: WRITE PROJECT.MD =====
        log.append("\n📝 نوشتن project.md...")
        md = self.ai.generate_project_md(plan)
        (base / "project.md").write_text(md, encoding="utf-8")
        log.append("✅ project.md")

        # ===== STEP 4: GENERATE CSS =====
        log.append("\n🎨 ساخت style.css...")
        css_code = self.ai.generate_css(plan)
        css = self.tools.extract_css(css_code)
        if css:
            (base / "css" / "style.css").write_text(css, encoding="utf-8")
            log.append(f"✅ style.css ({len(css)} bytes)")
        else:
            log.append("❌ style.css ساخته نشد")

        # ===== STEP 5: GENERATE JS =====
        log.append("\n⚡ ساخت main.js...")
        js_code = self.ai.generate_js(plan)
        js = self.tools.extract_js(js_code)
        if js:
            (base / "js" / "main.js").write_text(js, encoding="utf-8")
            log.append(f"✅ main.js ({len(js)} bytes)")
        else:
            log.append("❌ main.js ساخته نشد")

        # ===== STEP 6: GENERATE EACH HTML =====
        files_created = []
        max_attempts = 3

        for file_info in files:
            if file_info["type"] != "html":
                continue

            path = file_info["path"]
            log.append(f"\n🔧 ساخت {path}...")

            attempt = 0
            success = False

            while attempt < max_attempts and not success:
                attempt += 1

                code = self.ai.generate_page(file_info, plan)
                html = self.tools.extract_html(code)

                if not html:
                    log.append(f"  ❌ تلاش {attempt}: کد خالی")
                    continue

                # Save directly (no verify - model can't do it reliably)
                full_path = base / path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(html, encoding="utf-8")
                files_created.append({"name": path, "size": len(html)})
                log.append(f"  ✅ {path} ({len(html)} bytes)")
                success = True

            if not success:
                log.append(f"  ⚠️ {path} آماده نشد")

        # ===== SUMMARY =====
        response = "\n".join(log)
        if files_created:
            main = next((f for f in files_created if "index.html" in f["name"]), files_created[0])
            response += f"\n\n🌐 /preview/{plan.get('project_name', 'site')}/{main['name']}"
        self.memory.save_message("assistant", response)
        return {"response": response, "files": files_created, "status": "done"}

    def _handle_edit(self, message):
        current_path = self.config.output_dir / "index.html"
        if not current_path.exists():
            return {"response": "No site exists yet.", "files": [], "status": "error"}
        current_code = current_path.read_text("utf-8")
        result = self.ai.edit(current_code, message)
        new_html = self.tools.extract_html(result)
        if new_html:
            current_path.write_text(new_html, encoding="utf-8")
            return {"response": "✅ Edited!", "files": [{"name": "index.html", "size": len(new_html)}], "status": "done"}
        return {"response": "❌ Edit failed.", "files": [], "status": "error"}
