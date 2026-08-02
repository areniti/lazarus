"""Tools - File operations like Hermes"""
import os
import re
from pathlib import Path


class Tools:
    """File operations for the CMS"""

    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def file_read(self, filename):
        """Read a file"""
        path = self.output_dir / filename
        if not path.exists():
            return f"ERROR: File not found: {filename}"
        return path.read_text("utf-8")

    def file_write(self, filename, content):
        """Write content to a file"""
        path = self.output_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"OK: Wrote {len(content)} bytes to {filename}"

    def file_list(self):
        """List all files"""
        files = []
        for f in self.output_dir.glob("*"):
            if f.is_file() and not f.name.startswith("."):
                files.append({"name": f.name, "size": f.stat().st_size})
        return files

    def html_validate(self, filename):
        """Validate HTML structure"""
        content = self.file_read(filename)
        if content.startswith("ERROR"):
            return content

        issues = []
        if "<!DOCTYPE" not in content and "<!doctype" not in content:
            issues.append("Missing <!DOCTYPE>")
        if "<html" not in content:
            issues.append("Missing <html> tag")
        if "</html>" not in content:
            issues.append("Missing </html> closing tag")
        if "<body" not in content:
            issues.append("Missing <body> tag")
        if "</body>" not in content:
            issues.append("Missing </body> closing tag")
        if "<head" not in content:
            issues.append("Missing <head> tag")
        if "charset" not in content:
            issues.append("Missing charset declaration")
        if "viewport" not in content:
            issues.append("Missing viewport meta tag")

        if issues:
            return f"ISSUES: {'; '.join(issues)}"
        return "VALID"

    def search_replace(self, filename, search, replace):
        """Find and replace in file"""
        content = self.file_read(filename)
        if content.startswith("ERROR"):
            return content

        if search not in content:
            return f"NOT FOUND: '{search}'"

        new_content = content.replace(search, replace)
        self.file_write(filename, new_content)
        count = content.count(search)
        return f"OK: Replaced {count} occurrences"

    def extract_html(self, response):
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
