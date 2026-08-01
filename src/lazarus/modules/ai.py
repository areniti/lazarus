"""AI - Control Unit: handles all API calls and decision making"""
import requests
import json
import re
from pathlib import Path


class AI:
    """Control Unit - routes all AI decisions"""

    def __init__(self, config):
        self.config = config
        self.api_url = config.data["api"]["url"]
        self.api_key = config.data["api"]["key"]
        self.model = config.data["api"]["model"]

    def _call(self, messages, max_tokens=4096):
        """Raw API call - ALU operation"""
        url = self.api_url.rstrip("/")
        if not url.endswith("/chat/completions"):
            url += "/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        data = {"model": self.model, "messages": messages, "max_tokens": max_tokens}
        r = requests.post(url, headers=headers, json=data, timeout=180)
        if r.status_code != 200:
            return f"ERROR: HTTP {r.status_code}"
        result = r.json()
        if "choices" not in result:
            return f"ERROR: {json.dumps(result)[:200]}"
        content = result["choices"][0]["message"]["content"]
        return content if content else "No response"

    def load_skills(self):
        """Load skills from skills.md"""
        for path in [
            Path(__file__).parent.parent / "skills.md",
            Path(__file__).parent.parent / "docs" / "skills.md",
            Path.home() / ".lazarus" / "skills.md",
        ]:
            if path.exists():
                return path.read_text("utf-8")
        return ""

    def needs_code(self, message):
        """Does user want code? Only keyword check"""
        msg = message.lower().strip()
        code_keywords = [
            "بساز", "بسازید", "درست کن", " بنویس", "طراحی کن", "ایجاد کن",
            "ساخت", "سایت", "صفحه", "وبلاگ", "فروشگاه", "رستوران", "بلاگ", "قالب",
            "html", "css", "build", "create", "make", "design", "generate", "code",
            "website", "page", "site", "blog", "template", "کد",
        ]
        return any(kw in msg for kw in code_keywords)

    def ask_skills(self, message, skills):
        """Ask which skills are needed"""
        prompt = (
            "You are a project planner.\n"
            "Given the user request and available skills, which skills are needed?\n"
            "Reply with ONLY a comma-separated list of skill names.\n"
            "If none needed, reply: none\n\n"
            f"Available skills:\n{skills[:1500]}\n\n"
            f"User request: {message}"
        )
        result = self._call([{"role": "user", "content": prompt}], max_tokens=100)
        return result.strip()

    def decompose_with_skills(self, message, needed_skills):
        """Decompose project using skills"""
        prompt = (
            "You are a website architect.\n"
            "Break this into 3-5 sub-projects, each is ONE HTML file.\n"
            "Each sub-project: name, description, file name.\n"
            "Use the skills reference for design patterns.\n\n"
            f"Skills needed: {needed_skills}\n\n"
            "Reply in JSON:\n"
            '[{"name":"header", "description":"Build site header with navigation", "file":{"name":"header.html"}}]\n\n'
            f"User request: {message}"
        )
        result = self._call([{"role": "user", "content": prompt}], max_tokens=2000)
        try:
            match = re.search(r"\[.*\]", result, re.DOTALL)
            if match:
                return json.loads(match.group())
        except (json.JSONDecodeError, TypeError):
            pass
        return [{"name": "main", "description": message, "file": {"name": "main.html"}}]

    def decompose(self, message):
        """Simple decompose"""
        return self.decompose_with_skills(message, "none")

    def generate_code(self, description, skills="", previous_output=""):
        """Generate HTML code"""
        prompt = (
            "You are Lazarus, a professional website builder.\n"
            "Generate a COMPLETE, WORKING HTML page.\n\n"
            "SKILLS:\n" + (skills[:1000] if skills else self.load_skills()[:1000]) + "\n\n"
            "RULES:\n"
            "- Start with <!DOCTYPE html>\n"
            "- Include ALL CSS inside <style> tag\n"
            "- RTL (dir=rtl, lang=fa)\n"
            "- Modern, professional design\n"
            "- Responsive (mobile + desktop)\n"
            "- Google Font: Vazirmatn\n"
            "- One single HTML file\n"
            "- NO explanations, NO questions\n"
            "- ONLY the ```html code block\n\n"
        )
        if previous_output:
            prompt += f"Previous section (for consistency):\n{previous_output[:500]}\n\n"
        prompt += f"BUILD: {description}"
        return self._call([{"role": "user", "content": prompt}], max_tokens=8000)

    def verify_code(self, html, description):
        """Verify code with API"""
        prompt = (
            "Reply ONLY True or False.\n"
            "Is this valid, complete, professional HTML?\n"
            "Check: DOCTYPE, html tag, head, body, content, CSS.\n"
            f"Description: {description}\n"
            f"Code preview: {html[:400]}\n"
        )
        result = self._call([{"role": "user", "content": prompt}], max_tokens=100)
        return "true" in result.lower()

    def fix_code(self, html, error_or_description, task=""):
        """Fix broken code"""
        prompt = (
            "Fix this HTML code.\n"
            f"Problem: {error_or_description}\n"
            f"Task: {task}\n"
            "Reply with ONLY the fixed ```html code block.\n\n"
            f"Code:\n{html[:3000]}\n"
        )
        return self._call([{"role": "user", "content": prompt}], max_tokens=8000)

    def chat(self, message, history):
        """General chat with memory"""
        skills = self.load_skills()
        messages = [{"role": "system", "content": "You are Lazarus, a friendly AI assistant. Reply in the same language as the user. Keep responses short and helpful."}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        return self._call(messages)
