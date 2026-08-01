"""Lazarus Pipeline - AI-Powered CMS"""
import re
from .ai import AI
from .planner import Planner
from .state import StateRegister
from .executor import Executor
from ..core.config import Config
from ..core.memory import Memory


class Pipeline:
    """CMS Pipeline - builds complete websites from descriptions."""

    def __init__(self, config=None):
        self.config = config or Config()
        self.ai = AI(self.config)
        self.planner = Planner(self.ai)
        self.state = StateRegister(self.config.output_dir)
        self.executor = Executor(self.ai, self.state, self.config.output_dir)
        self.memory = Memory()

    def process(self, message, history=None):
        role = self.config.data.get("role", "developer")
        if role == "admin":
            return {"response": "Admin mode.", "files": [], "status": "admin"}

        self.memory.save_message("user", message)
        memory_history = self.memory.get_history(limit=10)

        if self.ai.needs_edit(message):
            return self._handle_edit(message)

        if not self.ai.needs_code(message):
            response = self.ai.chat(message, memory_history)
            self.memory.save_message("assistant", response)
            return {"response": response, "files": [], "status": "chat"}

        # BUILD
        skills = self.ai.load_skills()
        needed_skills = self.ai.ask_skills(message, skills)
        sections = self.ai.decompose_with_skills(message, needed_skills)
        self.state.start_new_project(message, sections)

        css_parts = []
        html_parts = []

        for i, section in enumerate(sections):
            self.state.start_step(i)
            code = self.ai.generate_code(
                section.get("description", message),
                original_request=message,
                skills=needed_skills,
                previous_output="\n".join(html_parts[-1:]) if html_parts else "",
            )
            html = self.executor._extract_html(code)
            if not html:
                self.state.fail_step(i, "No HTML")
                continue

            style_m = re.search(r"<style[^>]*>(.*?)</style>", html, re.DOTALL)
            if style_m:
                css_parts.append(style_m.group(1).strip())
            body_m = re.search(r"<body[^>]*>(.*?)</body>", html, re.DOTALL)
            if body_m:
                html_parts.append(body_m.group(1).strip())
            else:
                html_parts.append(html)

            self.state.complete_step(i, {"path": f"section_{i}.html", "name": section["name"]})

        final_html = self._merge_all(css_parts, html_parts, message)
        filepath = self.config.output_dir / "index.html"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(final_html, encoding="utf-8")
        self.state.finish()

        response = "Done! /preview/index.html"
        self.memory.save_message("assistant", response)
        return {"response": response, "files": [{"path": "index.html", "name": "index", "size": len(final_html)}], "status": "done"}

    def _handle_edit(self, message):
        current_path = self.config.output_dir / "index.html"
        if not current_path.exists():
            return {"response": "No site exists yet.", "files": [], "status": "error"}
        current_html = current_path.read_text("utf-8")
        result = self.ai.edit_section(current_html, message)
        new_html = self.executor._extract_html(result)
        if new_html:
            current_path.write_text(new_html, encoding="utf-8")
            return {"response": "Edited! /preview/index.html", "files": [{"path": "index.html", "name": "index", "size": len(new_html)}], "status": "done"}
        return {"response": "Edit failed.", "files": [], "status": "error"}

    def _merge_all(self, css_parts, html_parts, original_request):
        all_css = "\n\n".join(css_parts)
        all_body = "\n\n".join(html_parts)
        merged = self.ai.merge_files(all_css, all_body, original_request)
        html = self.executor._extract_html(merged)
        if html:
            return html
        return f'<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>{original_request[:50]}</title><link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;700;900&display=swap" rel="stylesheet"><style>*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:"Vazirmatn",sans-serif}}{all_css}</style></head><body>{all_body}</body></html>'
