"""Tools - File operations"""
import os
import re
from pathlib import Path


class Tools:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def file_read(self, filename):
        path = self.output_dir / filename
        if not path.exists():
            return f"ERROR: File not found: {filename}"
        return path.read_text("utf-8")

    def file_write(self, filename, content):
        path = self.output_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"OK: Wrote {len(content)} bytes to {filename}"

    def html_validate(self, filename):
        content = self.file_read(filename)
        if content.startswith("ERROR"):
            return content
        issues = []
        if "<!DOCTYPE" not in content and "<!doctype" not in content:
            issues.append("Missing <!DOCTYPE>")
        if "<html" not in content:
            issues.append("Missing <html> tag")
        if "</html>" not in content:
            issues.append("Missing </html>")
        if "<body" not in content:
            issues.append("Missing <body>")
        return "VALID" if not issues else f"ISSUES: {'; '.join(issues)}"

    def extract_css(self, response):
        """Extract CSS from AI response"""
        if not response:
            return None
        # Try ```css ... ```
        match = re.search(r"```css\n(.*?)\n```", response, re.DOTALL)
        if match:
            return match.group(1).strip()
        # Try ```css without closing
        if "```css" in response:
            idx = response.index("```css") + 6
            css = response[idx:].strip()
            # Remove trailing ```
            if css.endswith("```"):
                css = css[:-3].strip()
            elif css.endswith("\n```"):
                css = css[:-4].strip()
            if css and len(css) > 10:
                return css
        # Try <style> tag
        match = re.search(r"<style[^>]*>(.*?)</style>", response, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None

    def extract_js(self, response):
        """Extract JS from AI response"""
        if not response:
            return None
        match = re.search(r"```javascript\n(.*?)\n```", response, re.DOTALL)
        if match:
            return match.group(1).strip()
        match = re.search(r"```js\n(.*?)\n```", response, re.DOTALL)
        if match:
            return match.group(1).strip()
        # Without closing
        if "```javascript" in response:
            idx = response.index("```javascript") + 13
            js = response[idx:].strip()
            if js.endswith("```"):
                js = js[:-3].strip()
            if js and len(js) > 10:
                return js
        if "```js" in response:
            idx = response.index("```js") + 5
            js = response[idx:].strip()
            if js.endswith("```"):
                js = js[:-3].strip()
            if js and len(js) > 10:
                return js
        return None

    def extract_html(self, response):
        """Extract HTML from AI response"""
        if not response:
            return None
        # Strategy 1: ```html ... ```
        match = re.search(r"```html\n(.*?)\n```", response, re.DOTALL)
        if match:
            code = match.group(1).strip()
            if "<!DOCTYPE" in code or "<html" in code:
                return code
        # Strategy 2: ```html without closing
        if "```html" in response:
            idx = response.index("```html") + 7
            code = response[idx:].strip()
            if code.endswith("```"):
                code = code[:-3].strip()
            elif code.endswith("\n```"):
                code = code[:-4].strip()
            end = code.find("</html>")
            if end >= 0:
                code = code[: end + 7]
            if "<!DOCTYPE" in code or "<html" in code:
                return code.strip()
        # Strategy 3: response IS html
        if "<!DOCTYPE" in response or "<html" in response:
            return response.strip()
        return None
