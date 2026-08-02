"""AI - Professional CMS with multi-page support"""
import requests
import json
import re
from pathlib import Path


class AI:
    def __init__(self, config):
        self.config = config
        self.api_url = config.data["api"]["url"]
        self.api_key = config.data["api"]["key"]
        self.model = config.data["api"]["model"]

    def _call(self, messages, max_tokens=4096):
        url = self.api_url.rstrip("/")
        if not url.endswith("/chat/completions"):
            url += "/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        data = {"model": self.model, "messages": messages, "max_tokens": max_tokens}
        try:
            r = requests.post(url, headers=headers, json=data, timeout=180)
            if r.status_code != 200:
                return f"ERROR: HTTP {r.status_code}"
            result = r.json()
            if "choices" not in result:
                return f"ERROR: {json.dumps(result)[:200]}"
            content = result["choices"][0]["message"]["content"]
            return content if content else "No response"
        except requests.Timeout:
            return "ERROR: Timeout"
        except Exception as e:
            return f"ERROR: {str(e)}"

    def classify(self, message):
        msg = message.lower().strip()
        chat_words = ["سلام", "hi", "hello", "hey", "خوبی", "حالت", "چطوری",
                       "ممنون", "thanks", "ok", "باشه", "بله", "نه"]
        if msg in chat_words or len(msg.split()) <= 2:
            return "chat"
        has_existing = (Path.home() / ".lazarus" / "output" / "index.html").exists()
        edit_words = ["ادیت", "تغییر", "عوض کن", "ترمیم", "ویرایش",
                       "edit", "change", "update", "modify", "رنگ", "فونت"]
        if has_existing and any(kw in msg for kw in edit_words):
            return "edit"
        return "build"

    def plan_pages(self, message):
        """AI decides which pages to create"""
        prompt = f"""You are a web developer planning a website.

USER REQUEST: {message}

Create a list of HTML pages for this website.
Each page must be a SEPARATE .html file.
Maximum 5 pages. Maximum 80 lines per page.

Reply ONLY in JSON:
[{{"name": "index.html", "description": "Main page with hero section and navigation", "is_main": true}}, {{"name": "about.html", "description": "About me page with skills and experience", "is_main": false}}]

RULES:
- First page is always the main page (index.html)
- Each page is COMPLETE on its own (has header, nav, footer, CSS)
- ALL pages share the same color scheme and font
- Navigation links between pages must be REAL (href="about.html")
- Use inline CSS, no external files
- RTL (dir=rtl, lang=fa), Vazirmatn font
- Responsive design
- Modern dark theme"""
        result = self._call([{"role": "user", "content": prompt}], max_tokens=1000)
        try:
            match = re.search(r"\[.*\]", result, re.DOTALL)
            if match:
                pages = json.loads(match.group())
                return pages
        except (json.JSONDecodeError, TypeError):
            pass
        return [{"name": "index.html", "description": message, "is_main": True}]

    def generate_page(self, page, all_pages, original_request):
        """Generate ONE complete page"""
        nav_links = ""
        for p in all_pages:
            nav_links += f"- {p['name']}: {p['description']}\n"

        prompt = f"""You are building page "{page['name']}" for a website.

ORIGINAL REQUEST: {original_request}
THIS PAGE: {page['description']}
ALL PAGES IN THIS SITE:
{nav_links}
STYLE: Dark theme, gradient header (#667eea to #764ba2), Vazirmatn font, responsive

RULES:
1. Write ONLY this one page
2. Maximum 80 lines of HTML
3. Include navigation bar that links to ALL other pages
4. Include header, main content, and footer
5. Use inline CSS
6. Navigation: <a href="pagename.html">link text</a>
7. This page must be COMPLETE and self-contained
8. RTL support (dir=rtl, lang="fa")

OUTPUT: ONLY the HTML code in a ```html block. No explanations."""
        return self._call([{"role": "user", "content": prompt}], max_tokens=2000)

    def generate_theme(self, original_request):
        """Generate a shared CSS theme"""
        prompt = f"""You are creating a CSS theme for a website.

REQUEST: {original_request}

Create a SHORT CSS theme (max 30 lines).
Include: colors, fonts, spacing, responsive breakpoints.
Dark theme, gradient header, Vazirmatn font.

OUTPUT: ONLY CSS in a ```css block."""
        return self._call([{"role": "user", "content": prompt}], max_tokens=800)

    def chat(self, message, history):
        messages = [{"role": "system", "content": "You are Lazarus, a friendly AI assistant. Reply concisely in the same language as the user."}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        return self._call(messages)

    def edit(self, current_code, instruction):
        prompt = f"""Edit this HTML:

INSTRUCTION: {instruction}

CODE:
```html
{current_code}
```

Reply with ONLY the edited code in a ```html block."""
        return self._call([{"role": "user", "content": prompt}], max_tokens=4000)
