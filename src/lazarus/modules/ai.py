"""AI - Professional prompts for step-by-step web development"""
import requests
import json
import re
from pathlib import Path


class AI:
    """Professional AI with step-by-step capabilities"""

    def __init__(self, config):
        self.config = config
        self.api_url = config.data["api"]["url"]
        self.api_key = config.data["api"]["key"]
        self.model = config.data["api"]["model"]

    def _call(self, messages, max_tokens=4096):
        """Single API call with error handling"""
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

    def load_skills(self):
        for path in [
            Path(__file__).parent.parent / "skills.md",
            Path.home() / ".lazarus" / "skills.md",
        ]:
            if path.exists():
                return path.read_text("utf-8")
        return ""

    # ===== CLASSIFICATION =====

    def classify(self, message):
        """Classify user request: chat, build, or edit"""
        msg = message.lower().strip()

        # Chat words
        chat_words = ["سلام", "hi", "hello", "hey", "خوبی", "حالت", "چطوری",
                       "ممنون", "thanks", "ok", "باشه", "بله", "نه"]
        if msg in chat_words or len(msg.split()) <= 2:
            return "chat"

        # Edit words (requires existing site)
        edit_words = ["ادیت", "تغییر", "عوض کن", "ترمیم", "ویرایش",
                       "edit", "change", "update", "modify", "رنگ", "فونت"]
        has_existing = (Path.home() / ".lazarus" / "output" / "index.html").exists()
        if has_existing and any(kw in msg for kw in edit_words):
            return "edit"

        # Build words
        build_words = ["بساز", "درست کن", "بنویس", "طراحی کن", "ایجاد کن",
                        "ساخت", "سایت", "صفحه", "وبلاگ", "فروشگاه", "بلاگ",
                        "html", "css", "build", "create", "make", "design",
                        "website", "page", "site", "blog", "template", "کد"]
        if any(kw in msg for kw in build_words):
            return "build"

        # Default: chat
        return "chat"

    # ===== PLANNING =====

    def plan(self, message):
        """Break request into small steps"""
        prompt = f"""You are a web developer planning a project.

TASK: {message}

Break this into 2-3 SMALL steps. Each step produces ONE HTML file.
Maximum 50 lines of code per step.
ALL files must be .html (no separate .css or .js files).

Reply in JSON format:
[{{"step": 1, "name": "page.html", "description": "what to build", "lines": 50}}]

Rules:
- Maximum 3 steps
- Each step is ONE complete HTML file
- Keep it simple"""
        result = self._call([{"role": "user", "content": prompt}], max_tokens=500)
        try:
            match = re.search(r"\[.*\]", result, re.DOTALL)
            if match:
                return json.loads(match.group())
        except (json.JSONDecodeError, TypeError):
            pass
        return [{"step": 1, "name": "index.html", "description": message, "lines": 50}]

    # ===== CODE GENERATION =====

    def generate_component(self, step, previous_code="", original_request=""):
        """Generate ONE small component"""
        prompt = f"""You are a web developer. Write ONE HTML component.

TASK: {step['description']}
FILE: {step['name']}
ORIGINAL REQUEST: {original_request}

RULES:
1. Maximum 50 lines of code
2. Inline CSS only
3. RTL support (dir=rtl, lang=fa)
4. Responsive design
5. Vazirmatn font

OUTPUT: ONLY the code in a ```html block. No explanations.

{f"PREVIOUS CODE (for context):\\n{previous_code[:300]}" if previous_code else ""}"""
        return self._call([{"role": "user", "content": prompt}], max_tokens=2000)

    def fix_component(self, code, issues):
        """Fix issues in a component"""
        prompt = f"""Fix these issues in the HTML code:

ISSUES: {issues}

CODE:
```html
{code}
```

Reply with ONLY the fixed code in a ```html block. No explanations."""
        return self._call([{"role": "user", "content": prompt}], max_tokens=2000)

    # ===== CHAT =====

    def chat(self, message, history):
        """Simple chat"""
        messages = [{"role": "system", "content": "You are Lazarus, a friendly AI assistant. Reply concisely in the same language as the user."}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        return self._call(messages)

    # ===== EDIT =====

    def edit(self, current_code, instruction):
        """Edit existing code"""
        prompt = f"""Edit this HTML code:

INSTRUCTION: {instruction}

CURRENT CODE:
```html
{current_code}
```

Reply with ONLY the edited code in a ```html block. No explanations."""
        return self._call([{"role": "user", "content": prompt}], max_tokens=4000)

    # ===== REVIEW =====

    def review(self, code):
        """Review code and list issues"""
        prompt = f"""Review this HTML code. List any issues.

CODE:
```html
{code}
```

Reply with:
1. Issues found (if any)
2. Quality rating (1-10)
3. Suggestions

Be concise."""
        return self._call([{"role": "user", "content": prompt}], max_tokens=500)
