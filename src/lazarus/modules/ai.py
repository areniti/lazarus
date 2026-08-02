"""AI - Multi-page CMS with verification"""
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
            return result["choices"][0]["message"]["content"] or "No response"
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
        """Break request into independent pages with descriptions"""
        prompt = f"""You are a web architect. Decompose this request into independent pages.

REQUEST: {message}

Create a project plan as JSON. Each page is independent.

Reply ONLY in JSON:
{{
  "project_name": "name",
  "pages": [
    {{
      "filename": "index.html",
      "title": "Home",
      "description": "Main page with hero section, navigation bar at top, featured content, and footer. Shows the main message of the site.",
      "inputs": ["none"],
      "outputs": ["HTML page"]
    }},
    {{
      "filename": "about.html",
      "title": "About",
      "description": "About page with personal info, skills list, experience timeline, and contact form.",
      "inputs": ["none"],
      "outputs": ["HTML page"]
    }}
  ]
}}

RULES:
- 3-5 pages maximum
- Each page is COMPLETE and independent
- All pages share navigation bar
- First page is always index.html
- Include inputs/outputs for each page
- RTL, dark theme, Vazirmatn font"""
        result = self._call([{"role": "user", "content": prompt}], max_tokens=1500)
        try:
            match = re.search(r"\{.*\}", result, re.DOTALL)
            if match:
                return json.loads(match.group())
        except (json.JSONDecodeError, TypeError):
            pass
        return {"project_name": "website", "pages": [
            {"filename": "index.html", "title": "Home", "description": message,
             "inputs": ["none"], "outputs": ["HTML page"]}
        ]}

    # ===== STEP 2: GENERATE PROJECT.MD =====

    def generate_project_md(self, plan):
        """Generate project.md description file"""
        lines = [f"# {plan['project_name']}\n"]
        lines.append(f"Generated: {plan.get('project_name', 'website')}\n")
        lines.append("---\n")
        for i, page in enumerate(plan["pages"], 1):
            lines.append(f"## {i}. {page['filename']} - {page['title']}\n")
            lines.append(f"**Description:** {page['description']}\n")
            lines.append(f"**Inputs:** {', '.join(page.get('inputs', ['none']))}\n")
            lines.append(f"**Outputs:** {', '.join(page.get('outputs', ['HTML page']))}\n")
            lines.append(f"**Status:** pending\n")
            lines.append("---\n")
        return "\n".join(lines)

    # ===== STEP 3: GENERATE EACH PAGE =====

    def generate_page(self, page, plan, original_request):
        """Generate ONE page based on its description"""
        all_pages = "\n".join([
            f"- {p['filename']}: {p['description']}" for p in plan["pages"]
        ])

        prompt = f"""You are building page "{page['filename']}" for a website.

ORIGINAL REQUEST: {original_request}
THIS PAGE: {page['description']}
ALL PAGES:
{all_pages}

STYLE: Dark theme, gradient header (#667eea to #764ba2), Vazirmatn font, responsive, RTL

RULES:
1. Write ONLY this one page
2. Maximum 100 lines
3. Include navigation bar linking to ALL other pages
4. Include header, main content, and footer
5. Navigation: <a href="filename.html">Title</a>
6. This page must be COMPLETE
7. Inline CSS only

OUTPUT: ONLY the HTML code in a ```html block."""
        return self._call([{"role": "user", "content": prompt}], max_tokens=2000)

    # ===== STEP 4: VERIFY =====

    def verify_page(self, page, code):
        """Ask AI if the generated code matches the description"""
        prompt = f"""You are a code reviewer. Check if this HTML matches the requirements.

REQUIREMENTS: {page['description']}
PAGE NAME: {page['filename']}

CODE:
```html
{code}
```

Does this code match the requirements?
Reply with ONLY:
- "APPROVED" if it matches
- "REJECTED: [reason]" if it doesn't match"""
        return self._call([{"role": "user", "content": prompt}], max_tokens=200)

    # ===== STEP 5: EDIT =====

    def edit(self, current_code, instruction):
        prompt = f"""Edit this HTML:

INSTRUCTION: {instruction}

CODE:
```html
{current_code}
```

Reply with ONLY the edited code in a ```html block."""
        return self._call([{"role": "user", "content": prompt}], max_tokens=4000)

    # ===== CHAT =====

    def chat(self, message, history):
        messages = [{"role": "system", "content": "You are Lazarus, a friendly AI assistant. Reply concisely in the same language as the user."}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        return self._call(messages)
