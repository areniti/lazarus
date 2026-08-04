"""Tools - file operations and code extraction from model responses."""
import re
from pathlib import Path

CSS_LINK = '<link rel="stylesheet" href="style.css">'
JS_TAG = '<script src="main.js"></script>'
FONT_LINK = ('<link href="https://fonts.googleapis.com/css2?'
             'family=Vazirmatn:wght@300;400;500;700;900&display=swap" '
             'rel="stylesheet">')


class Tools:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ===== file ops =====

    def file_read(self, filename):
        path = self._resolve(filename)
        if path is None or not path.is_file():
            return f"ERROR: File not found: {filename}"
        return path.read_text("utf-8")

    def file_write(self, filename, content):
        path = self._resolve(filename)
        if path is None:
            return f"ERROR: Refused unsafe path: {filename}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"OK: Wrote {len(content)} bytes to {filename}"

    def _resolve(self, filename):
        """Keep every write inside output_dir."""
        base = self.output_dir.resolve()
        try:
            target = (base / filename).resolve()
        except (OSError, RuntimeError):
            return None
        if base != target and base not in target.parents:
            return None
        return target

    # ===== validation =====

    def html_validate(self, filename):
        content = self.file_read(filename)
        if content.startswith("ERROR"):
            return content
        return self.html_validate_text(content)

    @staticmethod
    def html_validate_text(html):
        issues = []
        low = html.lower()
        if "<!doctype" not in low:
            issues.append("Missing <!DOCTYPE>")
        if "<html" not in low:
            issues.append("Missing <html>")
        if "</html>" not in low:
            issues.append("Missing </html>")
        if "<body" not in low:
            issues.append("Missing <body>")
        if len(html) < 200:
            issues.append(f"Too short ({len(html)} bytes)")
        return "VALID" if not issues else f"ISSUES: {'; '.join(issues)}"

    @staticmethod
    def ensure_assets(html):
        """Guarantee the page links style.css, main.js, the font, and closes."""
        low = html.lower()

        if "style.css" not in low:
            if "</head>" in low:
                idx = low.index("</head>")
                html = html[:idx] + f"    {CSS_LINK}\n" + html[idx:]
            elif "<head>" in low:
                idx = low.index("<head>") + len("<head>")
                html = html[:idx] + f"\n    {CSS_LINK}" + html[idx:]

        low = html.lower()
        if "fonts.googleapis.com" not in low and "</head>" in low:
            idx = low.index("</head>")
            html = html[:idx] + f"    {FONT_LINK}\n" + html[idx:]

        low = html.lower()
        if "main.js" not in low:
            if "</body>" in low:
                idx = low.index("</body>")
                html = html[:idx] + f"    {JS_TAG}\n" + html[idx:]
            else:
                html = html.rstrip() + f"\n{JS_TAG}\n"

        low = html.lower()
        if "</body>" not in low:
            html = html.rstrip() + "\n</body>"
        if "</html>" not in html.lower():
            html = html.rstrip() + "\n</html>"
        return html

    # ===== extraction =====

    @staticmethod
    def _from_fence(response, langs):
        """Pull code out of a ```lang fenced block, closed or not."""
        for lang in langs:
            match = re.search(rf"```{lang}\s*\n(.*?)\n\s*```", response,
                              re.DOTALL | re.IGNORECASE)
            if match:
                code = match.group(1).strip()
                if code:
                    return code
        for lang in langs:
            match = re.search(rf"```{lang}\s*\n(.*)", response,
                              re.DOTALL | re.IGNORECASE)
            if match:
                code = re.sub(r"```\s*$", "", match.group(1)).strip()
                if code:
                    return code
        return None

    def extract_css(self, response):
        if not response:
            return None
        code = self._from_fence(response, ["css"])
        if code and len(code) > 10:
            return code
        match = re.search(r"<style[^>]*>(.*?)</style>", response, re.DOTALL)
        if match and len(match.group(1).strip()) > 10:
            return match.group(1).strip()
        # Bare CSS with no fence: looks like selectors and braces.
        stripped = response.strip()
        if stripped and "{" in stripped and "}" in stripped and "<" not in stripped[:50]:
            return stripped
        return None

    def extract_js(self, response):
        if not response:
            return None
        code = self._from_fence(response, ["javascript", "js"])
        if code and len(code) > 10:
            return code
        match = re.search(r"<script[^>]*>(.*?)</script>", response, re.DOTALL)
        if match and len(match.group(1).strip()) > 10:
            return match.group(1).strip()
        return None

    def extract_html(self, response):
        if not response:
            return None
        code = self._from_fence(response, ["html"])
        if code:
            code = self._trim_html(code)
            if self._looks_like_html(code):
                return code
        if self._looks_like_html(response):
            return self._trim_html(response.strip())
        return None

    @staticmethod
    def _looks_like_html(text):
        low = text.lower()
        return "<!doctype" in low or "<html" in low

    @staticmethod
    def _trim_html(code):
        """Drop any prose before <!DOCTYPE / <html and after </html>."""
        low = code.lower()
        start = low.find("<!doctype")
        if start < 0:
            start = low.find("<html")
        if start > 0:
            code = code[start:]
            low = code.lower()
        end = low.rfind("</html>")
        if end >= 0:
            code = code[:end + len("</html>")]
        return code.strip()
