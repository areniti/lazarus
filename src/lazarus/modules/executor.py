"""Executor - runs each sub-project"""
import re
import time
from pathlib import Path


class Executor:
    """Executes sub-projects one by one"""

    def __init__(self, ai, state, output_dir):
        self.ai = ai
        self.state = state
        self.output_dir = Path(output_dir)

    def run_all(self):
        """Run all sub-projects in sequence"""
        projects = self.state.state["sub_projects"]
        last_output = ""

        for i, project in enumerate(projects):
            print(f"\n🔨 Step {i+1}/{len(projects)}: {project['name']}")

            # Start
            self.state.start_step(i)

            # Generate
            code = self.ai.generate_code(project, last_output)

            # Extract HTML
            html = self._extract_html(code)
            if not html:
                self.state.fail_step(i, "No valid HTML generated")
                return False

            # Save
            filename = f"{project['name']}.html"
            path = self.output_dir / filename
            path.write_text(html, encoding="utf-8")

            self.state.complete_step(i, {"path": filename, "name": project["name"]})
            last_output = html
            print(f"  ✅ Saved: {filename} ({len(html)} bytes)")

        return True

    def _extract_html(self, response):
        """Extract HTML from AI response"""
        # Strategy 1: ```html ... ```
        match = re.search(r"```html\s*(.*?)```", response, re.DOTALL)
        if match:
            code = match.group(1).strip()
            if "<!DOCTYPE" in code or "<html" in code:
                return code

        # Strategy 2: ```html without closing ```
        match = re.search(r"```html\s*(.*)", response, re.DOTALL)
        if match:
            code = match.group(1)
            end = code.find("</html>")
            if end >= 0:
                code = code[: end + 7]
            if "<!DOCTYPE" in code or "<html" in code:
                return code.strip()

        # Strategy 3: response IS html
        if "<!DOCTYPE" in response or "<html" in response:
            return response.strip()

        return None
