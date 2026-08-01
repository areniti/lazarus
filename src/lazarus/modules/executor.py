"""Executor - validates and extracts HTML"""
import re
from pathlib import Path


class Executor:
    """Validates HTML content."""

    def __init__(self, ai, state, output_dir):
        self.ai = ai
        self.state = state
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _extract_html(self, response):
        """Extract HTML from AI response"""
        if not response:
            return None

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
            code = re.sub(r"```\s*$", "", code).strip()
            end = code.find("</html>")
            if end >= 0:
                code = code[: end + 7]
            else:
                code = code.rstrip()
                code += "\n</body>\n</html>"
            if "<!DOCTYPE" in code or "<html" in code:
                return code.strip()

        # Strategy 3: response IS html
        if "<!DOCTYPE" in response or "<html" in response:
            return response.strip()

        return None

    def _validate(self, html):
        """Local validation"""
        errors = []
        if len(html) < 200:
            errors.append(f"Too short ({len(html)} bytes)")
        if "<!DOCTYPE" not in html and "<!doctype" not in html:
            errors.append("Missing <!DOCTYPE>")
        if "<html" not in html:
            errors.append("Missing <html>")
        if "</html>" not in html:
            errors.append("Missing </html>")
        if "<body" not in html:
            errors.append("Missing <body>")
        if errors:
            return False, "; ".join(errors)
        return True, None
