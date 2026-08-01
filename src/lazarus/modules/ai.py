from pathlib import Path
"""AI - Control Unit: handles all API calls and decision making"""
import requests
import json
import re


class AI:
    """Control Unit - routes all AI decisions"""

    def __init__(self, config):
        self.config = config
        self.api_url = config.data["api"]["url"]
        self.api_key = config.data["api"]["key"]
        self.model = config.data["api"]["model"]

    def _call(self, messages, max_tokens=4096):
        """Raw API call - ALU operation"""
        # Auto-append /chat/completions if missing
        url = self.api_url
        if not url.endswith("/chat/completions"):
            if url.endswith("/"):
                url += "chat/completions"
            else:
                url += "/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        r = requests.post(url, headers=headers, json=data, timeout=120)
        if r.status_code != 200:
            return f"ERROR: HTTP {r.status_code}"
        result = r.json()
        if "choices" not in result:
            return f"ERROR: {json.dumps(result)[:200]}"
        content = result["choices"][0]["message"]["content"]
        return content if content else "No response"

    # ===== CONTROL UNIT DECISIONS =====

    def detect_role(self, message):
        """Step 1: Is this Developer or Admin?"""
        prompt = (
            "Reply with ONLY one word: 'developer' or 'admin'.\n"
            "Developer = wants to build/create code, websites, projects\n"
            "Admin = wants to manage, configure, view settings\n"
            f"User said: {message}"
        )
        result = self._call([{"role": "user", "content": prompt}], max_tokens=100)
        return "admin" if "admin" in result.lower() else "developer"

    def needs_code(self, message):
        """Does user want code? Only keyword check (no API, no length check)"""
        msg = message.lower().strip()
        
        # MUST have a code keyword to be a build request
        code_keywords = [
            "بساز", "بسازید", "درست کن", " بنویس", "طراحی کن", "ایجاد کن",
            "ساخت", "سایت", "صفحه", "وبلاگ", "فروشگاه", "رستوران", "بلاگ", "قالب",
            "html", "css", "build", "create", "make", "design", "generate", "code",
            "website", "page", "site", "blog", "template", "کد",
        ]
        return any(kw in msg for kw in code_keywords)

    def info_complete(self, message, context=""):
        """Step 3: Is info sufficient?"""
        msg = message.lower()
        if len(message.split()) >= 5:
            return True
        types = ["سایت", "وبلاگ", "صفحه", "فروشگاه", "رستوران", "بلاگ",
                  "site", "blog", "page", "shop", "website", "html"]
        if any(t in msg for t in types):
            return True
        prompt = (
            "Reply ONLY True or False. Is this enough info to build a website?\n"
            f"User: {message}"
        )
        result = self._call([{"role": "user", "content": prompt}], max_tokens=100)
        return "true" in result.lower()

    def ask_clarification(self, message):
        """Step 3b: Ask what's missing"""
        prompt = (
            "You are a helpful assistant. The user's request is unclear or incomplete.\n"
            "Ask them SPECIFIC questions about what's missing.\n"
            "Be concise, in the same language as the user.\n"
            f"User said: {message}"
        )
        return self._call([{"role": "user", "content": prompt}])

    def decompose(self, message, skills=""):
        """Step 4: Break project into sub-projects"""
        prompt = (
            "You are a project planner. Break the user's request into small, independent sub-projects.\n"
            "Each sub-project must have:\n"
            "- name: short name (underscores, no spaces)\n"
            "- description: what to build\n"
            "- input: what it needs\n"
            "- output: what it produces\n\n"
            "Reply in JSON format:\n"
            '[{"name":"...", "description":"...", "input":"...", "output":"..."}]\n\n'
            f"User request: {message}"
        )
        result = self._call([{"role": "user", "content": prompt}], max_tokens=2000)
        try:
            match = re.search(r"\[.*\]", result, re.DOTALL)
            if match:
                return json.loads(match.group())
        except json.JSONDecodeError:
            pass
        return [{"name": "main", "description": result[:200], "input": message, "output": "HTML site"}]

    def is_complex_task(self, description):
        """Check if a sub-project needs further breakdown"""
        prompt = (
            "Reply ONLY True or False.\n"
            "Is this task too complex for a single AI response? "
            "Would it benefit from being split into smaller pieces?\n"
            f"Task: {description}"
        )
        result = self._call([{"role": "user", "content": prompt}], max_tokens=100)
        return "true" in result.lower()

    def generate_code(self, message):
        """Generate HTML code using skills reference"""
        skills = self.load_skills()
        prompt = (
            "You are Lazarus, a professional website builder.\n"
            "Generate a COMPLETE, WORKING HTML page.\n\n"
            "SKILLS REFERENCE:\n" + skills[:2000] + "\n\n"
            "RULES:\n"
            "- Start with <!DOCTYPE html>\n"
            "- Include ALL CSS inside <style> tag\n"
            "- RTL (dir=rtl, lang=fa)\n"
            "- Modern, professional design\n"
            "- Responsive (mobile + desktop)\n"
            "- Google Font: Vazirmatn\n"
            "- One single HTML file\n"
            "- NO explanations, NO questions\n\n"
            "REPLY: ONLY the ```html code block\n\n"
            f"USER REQUEST: {message}"
        )
        return self._call([{"role": "user", "content": prompt}], max_tokens=8000)

    def verify(self, code, task_description):
        """Step 7: Verify code is correct - local checks + AI"""
        # Fast local checks (no API needed)
        has_doctype = "<!DOCTYPE" in code or "<!doctype" in code
        has_html = "<html" in code
        has_close = "</html>" in code
        has_body = "<body" in code
        has_content = len(code) > 500

        # If all basic checks pass, it's probably OK
        if all([has_doctype, has_html, has_close, has_body, has_content]):
            return True

        # If basic checks fail, ask AI
        prompt = (
            "Reply with ONLY True or False. Is this valid complete HTML?\n"
            f"Code preview: {code[:300]}\n"
        )
        result = self._call([{"role": "user", "content": prompt}], max_tokens=100)
        return "true" in result.lower()

    def fix_code(self, code, error_info, task_description):
        """Fix broken code based on error"""
        prompt = (
            "The following HTML code has errors. Fix it.\n"
            "Keep the same design but fix the issues.\n"
            "Reply with ONLY the fixed HTML in a ```html block.\n\n"
            f"Error: {error_info}\n"
            f"Task: {task_description}\n"
            f"Code:\n{code[:2000]}\n"
        )
        return self._call([{"role": "user", "content": prompt}], max_tokens=8000)

    def load_skills(self):
        """Load skills from skills.md"""
        # Try multiple locations
        for path in [
            Path(__file__).parent.parent / "skills.md",
            Path(__file__).parent.parent / "docs" / "skills.md",
            Path.home() / ".lazarus" / "skills.md",
        ]:
            if path.exists():
                return path.read_text("utf-8")
        return ""

    def decompose(self, message):
        """Break project into sub-projects"""
        skills = self.load_skills()
        prompt = (
            "You are a project planner.\n"
            "Break this request into 2-4 small sub-projects.\n"
            "Each sub-project: name, description, input, output.\n\n"
            "SKILLS:\n" + skills[:1000] + "\n\n"
            "Reply in JSON:\n"
            '[{"name":"...", "description":"...", "input":"...", "output":"..."}]\n\n'
            f"REQUEST: {message}"
        )
        return self._call([{"role": "user", "content": prompt}], max_tokens=2000)

    def chat(self, message, history):
        """General chat with memory"""
        skills = self.load_skills()
        messages = [{"role": "system", "content": "You are Lazarus, a friendly AI assistant. Reply in the same language as the user. Keep responses short and helpful." + "\n\nSkills:\n" + skills[:500]}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        return self._call(messages)
