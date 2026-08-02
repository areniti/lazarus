"""Pipeline - Multi-page CMS like WordPress"""
import re
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
        """Build multi-page website"""
        # Step 1: Plan pages
        pages = self.ai.plan_pages(message)

        # Step 2: Generate theme
        theme_code = self.ai.generate_theme(message)
        css = self.tools.extract_css(theme_code)

        files_created = []
        previous_pages = []  # track what's been built

        # Step 3: Generate each page
        for page in pages:
            name = page.get("name", "index.html")
            desc = page.get("description", message)

            # Generate this page (knows about all other pages)
            code = self.ai.generate_page(page, pages, message)
            html = self.tools.extract_html(code)

            if not html:
                continue

            # Inject shared theme if page doesn't have one
            if css and "background:" not in html:
                html = html.replace("</head>", f"<style>{css}</style></head>")

            self.tools.file_write(name, html)
            files_created.append({"name": name, "size": len(html)})
            previous_pages.append({"name": name, "description": desc})

        if files_created:
            response = f"✅ Built {len(files_created)} pages:\n"
            for f in files_created:
                response += f"📄 {f['name']} ({f['size']} bytes)\n"
            main = next((f for f in files_created if f["name"] == "index.html"), files_created[0])
            response += f"\n🌐 Preview: /preview/{main['name']}"
        else:
            response = "❌ Could not build anything."

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
