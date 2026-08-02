"""Pipeline - Step-by-step like Hermes"""
from .ai import AI
from .tools import Tools
from ..core.config import Config
from ..core.memory import Memory


class Pipeline:
    """Step-by-step CMS pipeline"""

    def __init__(self, config=None):
        self.config = config or Config()
        self.ai = AI(self.config)
        self.tools = Tools(self.config.output_dir)
        self.memory = Memory()

    def process(self, message):
        """Process user message step by step"""
        role = self.config.data.get("role", "developer")
        if role == "admin":
            return {"response": "Admin mode.", "files": [], "status": "admin"}

        self.memory.save_message("user", message)
        history = self.memory.get_history(limit=10)

        # Classify
        action = self.ai.classify(message)

        if action == "chat":
            response = self.ai.chat(message, history)
            self.memory.save_message("assistant", response)
            return {"response": response, "files": [], "status": "chat"}

        if action == "edit":
            return self._handle_edit(message)

        # BUILD
        return self._handle_build(message)

    def _handle_build(self, message):
        """Build website step by step"""
        # Step 1: Plan
        steps = self.ai.plan(message)
        files_created = []
        previous_code = ""

        for step in steps:
            name = step.get("name", "index.html")
            desc = step.get("description", message)

            # Generate
            code = self.ai.generate_component(
                step, previous_code, message
            )
            html = self.tools.extract_html(code)

            if not html:
                continue

            # Validate
            self.tools.file_write(name, html)
            validation = self.tools.html_validate(name)

            if validation != "VALID":
                # Fix
                fixed = self.ai.fix_component(html, validation)
                fixed_html = self.tools.extract_html(fixed)
                if fixed_html:
                    self.tools.file_write(name, fixed_html)
                    html = fixed_html

            files_created.append({"name": name, "size": len(html)})
            previous_code = html

        if files_created:
            response = f"Built {len(files_created)} files:\n"
            for f in files_created:
                response += f"- {f['name']} ({f['size']} bytes)\n"
            response += f"\nPreview: /preview/{files_created[-1]['name']}"
        else:
            response = "Could not build anything."

        self.memory.save_message("assistant", response)
        return {"response": response, "files": files_created, "status": "done"}

    def _handle_edit(self, message):
        """Edit existing site"""
        current_path = self.config.output_dir / "index.html"
        if not current_path.exists():
            return {"response": "No site exists yet.", "files": [], "status": "error"}

        current_code = current_path.read_text("utf-8")
        result = self.ai.edit(current_code, message)
        new_html = self.tools.extract_html(result)

        if new_html:
            current_path.write_text(new_html, encoding="utf-8")
            return {"response": "Edited! /preview/index.html", "files": [{"name": "index.html", "size": len(new_html)}], "status": "done"}

        return {"response": "Edit failed.", "files": [], "status": "error"}
