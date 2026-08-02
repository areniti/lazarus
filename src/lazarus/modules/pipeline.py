"""Pipeline - Multi-page CMS with verification"""
import json
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
        """Build multi-page website with verification"""
        log = []

        # ===== STEP 1: DECOMPOSE =====
        log.append("📋 در حال تحلیل پروژه...")
        plan = self.ai.decompose(message)
        pages = plan.get("pages", [])
        if not pages:
            return {"response": "❌ Could not decompose project.", "files": [], "status": "error"}

        log.append(f"✅ {len(pages)} صفحه پیدا شد")
        for p in pages:
            log.append(f"  📄 {p['filename']}: {p['title']}")

        # ===== STEP 2: WRITE PROJECT.MD =====
        log.append("\n📝 نوشتن project.md...")
        md_content = self.ai.generate_project_md(plan)
        self.tools.file_write("project.md", md_content)
        log.append("✅ project.md نوشته شد")

        # ===== STEP 3-5: GENERATE + VERIFY EACH PAGE =====
        files_created = []
        max_attempts = 3

        for page in pages:
            filename = page["filename"]
            log.append(f"\n🔧 ساخت {filename}...")

            attempt = 0
            success = False

            while attempt < max_attempts and not success:
                attempt += 1
                log.append(f"  🔄 تلاش {attempt}/{max_attempts}...")

                # Generate
                code = self.ai.generate_page(page, plan, message)
                html = self.tools.extract_html(code)

                if not html:
                    log.append(f"  ❌ کد خالی برگشت")
                    continue

                # Verify
                log.append(f"  🔍 تأیید...")
                verdict = self.ai.verify_page(page, html)

                if "APPROVED" in verdict.upper():
                    # Save
                    self.tools.file_write(filename, html)
                    files_created.append({"name": filename, "size": len(html)})
                    log.append(f"  ✅ {filename} تأیید شد ({len(html)} bytes)")
                    success = True
                else:
                    reason = verdict.replace("REJECTED:", "").strip()[:100]
                    log.append(f"  ❌ رد شد: {reason}")

            if not success:
                log.append(f"  ⚠️ {filename} بعد از {max_attempts} تلاش آماده نشد")

        # ===== SUMMARY =====
        response = "\n".join(log)
        if files_created:
            response += f"\n\n🌐 /preview/{files_created[0]['name']}"
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
