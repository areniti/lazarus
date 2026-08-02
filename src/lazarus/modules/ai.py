"""AI - Professional multi-file CMS"""
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
            r = requests.post(url, headers=headers, json=data, timeout=300)
            if r.status_code != 200:
                return f"ERROR: HTTP {r.status_code}"
            result = r.json()
            if "choices" not in result:
                return f"ERROR: {json.dumps(result)[:200]}"
            msg = result["choices"][0]["message"]
            content = msg.get("content") or msg.get("reasoning") or "No response"
            return content
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
        return "build"

    # ===== STEP 1: DECOMPOSE =====

    def decompose(self, message):
        """Break into independent pages + assets"""
        prompt = f"""You are a web architect. Create a project structure.

REQUEST: {message}

Create a COMPLETE project structure as JSON:

{{
  "project_name": "my-project",
  "description": "short description",
  "theme": {{
    "primary_color": "#667eea",
    "secondary_color": "#764ba2",
    "bg_color": "#0d1117",
    "text_color": "#e6edf3",
    "font": "Vazirmatn"
  }},
  "files": [
    {{
      "path": "css/style.css",
      "type": "css",
      "description": "Main stylesheet with variables, responsive grid, dark theme"
    }},
    {{
      "path": "js/main.js",
      "type": "js",
      "description": "Navigation toggle, smooth scroll, form validation"
    }},
    {{
      "path": "index.html",
      "type": "html",
      "page_title": "Home",
      "description": "Hero section with main message, features section, call to action",
      "sections": ["hero", "features", "cta"],
      "links_to": ["pages/about.html", "pages/blog.html", "pages/contact.html"]
    }},
    {{
      "path": "pages/about.html",
      "type": "html",
      "page_title": "About",
      "description": "About me section, skills grid, experience timeline",
      "sections": ["intro", "skills", "experience"],
      "links_to": ["../index.html", "blog.html", "contact.html"]
    }},
    {{
      "path": "pages/blog.html",
      "type": "html",
      "page_title": "Blog",
      "description": "Blog post list with cards, categories filter, read more links",
      "sections": ["filter", "posts"],
      "links_to": ["../index.html", "about.html", "contact.html"]
    }},
    {{
      "path": "pages/contact.html",
      "type": "html",
      "page_title": "Contact",
      "description": "Contact form with validation, map placeholder, social links",
      "sections": ["form", "info"],
      "links_to": ["../index.html", "about.html", "blog.html"]
    }}
  ]
}}

RULES:
- Always include css/style.css and js/main.js
- Always include index.html + pages/*.html
- 2-3 HTML pages total
- All HTML pages link to shared CSS and JS
- Pages in pages/ use relative paths (../css/style.css)
- Navigation bar on every page linking to all pages"""
        result = self._call([{"role": "user", "content": prompt}], max_tokens=2000)
        try:
            match = re.search(r"\{.*\}", result, re.DOTALL)
            if match:
                return json.loads(match.group())
        except (json.JSONDecodeError, TypeError):
            pass
        # Fallback: create basic structure
        return {
            "project_name": "my-website",
            "theme": {"primary_color": "#667eea", "secondary_color": "#764ba2", "bg_color": "#0d1117", "text_color": "#e6edf3", "font": "Vazirmatn"},
            "files": [
                {"path": "css/style.css", "type": "css", "description": "Dark theme stylesheet with gradient colors, responsive grid, Vazirmatn font"},
                {"path": "js/main.js", "type": "js", "description": "Navigation toggle, smooth scroll, form validation"},
                {"path": "index.html", "type": "html", "page_title": "Home", "description": "Main page with hero section and navigation", "sections": ["hero", "nav"], "links_to": ["pages/about.html"]},
                {"path": "pages/about.html", "type": "html", "page_title": "About", "description": "About page with skills and info", "sections": ["intro", "skills"], "links_to": ["../index.html"]}
            ]
        }

    # ===== STEP 2: GENERATE PROJECT.MD =====

    def generate_project_md(self, plan):
        lines = [f"# {plan['project_name']}\n"]
        lines.append(f"{plan.get('description', '')}\n\n")
        lines.append("## Theme\n")
        theme = plan.get("theme", {})
        for k, v in theme.items():
            lines.append(f"- {k}: `{v}`\n")
        lines.append("\n## Files\n")
        for f in plan.get("files", []):
            lines.append(f"### {f['path']}\n")
            lines.append(f"- **Type:** {f['type']}\n")
            lines.append(f"- **Description:** {f['description']}\n")
            if f.get("sections"):
                lines.append(f"- **Sections:** {', '.join(f['sections'])}\n")
            if f.get("links_to"):
                lines.append(f"- **Links to:** {', '.join(f['links_to'])}\n")
            lines.append(f"- **Status:** pending\n\n")
        return "".join(lines)

    # ===== STEP 3: GENERATE CSS =====

    def generate_css(self, plan):
        theme = plan.get("theme", {})
        prompt = f"""Create a complete CSS stylesheet.

THEME: {json.dumps(theme)}

Include:
- CSS variables for colors
- Base styles (body, typography, links)
- Navbar (sticky, flex, responsive)
- Cards grid (responsive)
- Hero section (gradient background)
- Footer (flex, centered)
- Form styles (inputs, buttons)
- Responsive breakpoints (mobile-first)
- Animations (fade-in, hover effects)
- Dark theme

OUTPUT: ONLY CSS in a ```css block. Minimum 100 lines."""
        return self._call([{"role": "user", "content": prompt}], max_tokens=4096)

    # ===== STEP 4: GENERATE JS =====

    def generate_js(self, plan):
        prompt = """Create JavaScript for a website.

Include:
- Navigation toggle for mobile
- Smooth scroll for anchor links
- Contact form validation
- Scroll animations (fade in on scroll)
- Back to top button
- Active nav link highlight

OUTPUT: ONLY JavaScript in a ```javascript block."""
        return self._call([{"role": "user", "content": prompt}], max_tokens=4096)

    # ===== STEP 5: GENERATE EACH HTML PAGE =====

    def generate_page(self, file_info, plan):
        """Generate ONE HTML page"""
        theme = plan.get("theme", {})
        is_root = not file_info["path"].startswith("pages/")
        css_path = "css/style.css" if is_root else "../css/style.css"
        js_path = "js/main.js" if is_root else "../js/main.js"

        nav_links = []
        for f in plan.get("files", []):
            if f["type"] == "html":
                if is_root:
                    nav_links.append(f'"{f["path"]}": "{f["page_title"]}"')
                else:
                    if f["path"].startswith("pages/"):
                        nav_links.append(f'"{f["path"].split("/")[-1]}": "{f["page_title"]}"')
                    else:
                        nav_links.append(f'"../{f["path"]}": "{f["page_title"]}"')

        prompt = f"""Create page "{file_info['path']}" for a website.

PAGE: {file_info['description']}
SECTIONS: {file_info.get('sections', [])}
ALL PAGES: {', '.join(nav_links)}

STYLE:
- Link to: <link rel="stylesheet" href="{css_path}">
- Script: <script src="{js_path}"></script>
- Theme: {json.dumps(theme)}

NAVIGATION BAR:
{"<nav><a href='../index.html'>Home</a>" if not is_root else "<nav><a href='index.html'>Home</a>"}
Must link to ALL pages.

RULES:
1. Maximum 120 lines
2. Use CSS classes from style.css
3. Include proper HTML5 structure
4. RTL (dir=rtl, lang="fa")
5. Include meta viewport tag
6. Every section must have real content (not lorem ipsum)

OUTPUT: ONLY HTML in a ```html block."""
        return self._call([{"role": "user", "content": prompt}], max_tokens=4096)

    # ===== GENERATE HOMEPAGE =====

    def generate_homepage(self, original_request, plan):
        """Generate ONE complete homepage with all sections"""
        theme = plan.get("theme", {})
        nav = []
        for f in plan.get("files", []):
            if f["type"] == "html" and f["path"] != "index.html":
                nav.append(f["{f['path']}": "{f.get('page_title', f['path'].replace('.html',''))}"])

        prompt = f"""Create a COMPLETE homepage for a website.

ORIGINAL REQUEST: {original_request}
STYLE: Dark theme, gradient header (#667eea to #764ba2), Vazirmatn font, responsive, RTL

INCLUDE ALL THESE SECTIONS IN ONE PAGE:
1. Navigation bar with links to: {', '.join([f["path"] for f in plan.get('files', []) if f['type'] == 'html'])}
2. Hero section with main title and description
3. About section with info and skills
4. Blog/Content section with post cards
5. Contact section with form or info
6. Footer

RULES:
1. ONE complete HTML file with ALL sections
2. Maximum 200 lines
3. Inline CSS (use variables from style.css)
4. RTL (dir=rtl, lang="fa")
5. Link to: <link rel="stylesheet" href="style.css">
6. Script: <script src="main.js"></script>
7. Every section must have REAL content (not lorem ipsum)
8. Modern dark design

OUTPUT: ONLY HTML in a ```html block."""

    # ===== VERIFY =====

    def verify_page(self, file_info, code):
        prompt = f"""Check if this HTML matches requirements.

REQUIREMENTS: {file_info['description']}
SECTIONS: {file_info.get('sections', [])}
FILE: {file_info['path']}

CODE:
```html
{code}
```

Does it match? Reply ONLY:
- "APPROVED" if OK
- "REJECTED: reason" if not"""
        return self._call([{"role": "user", "content": prompt}], max_tokens=200)

    # ===== CHAT =====

    def chat(self, message, history):
        messages = [{"role": "system", "content": "You are Lazarus, a friendly AI assistant. Reply concisely."}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        return self._call(messages)

    def edit(self, current_code, instruction):
        prompt = f"""Edit: {instruction}\n\nCode:\n```html\n{current_code}\n```\n\nReply ONLY edited code in ```html block."""
        return self._call([{"role": "user", "content": prompt}], max_tokens=4000)
