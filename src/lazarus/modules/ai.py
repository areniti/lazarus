"""AI - Control Unit"""
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
        r = requests.post(url, headers=headers, json=data, timeout=180)
        if r.status_code != 200:
            return f"ERROR: HTTP {r.status_code}"
        result = r.json()
        if "choices" not in result:
            return f"ERROR: {json.dumps(result)[:200]}"
        content = result["choices"][0]["message"]["content"]
        return content if content else "No response"

    def load_skills(self):
        for path in [
            Path(__file__).parent.parent / "skills.md",
            Path(__file__).parent.parent / "docs" / "skills.md",
            Path.home() / ".lazarus" / "skills.md",
        ]:
            if path.exists():
                return path.read_text("utf-8")
        return ""

    def needs_edit(self, message):
        msg = message.lower().strip()
        edit_keywords = [
            "ادیت", "تغییر", "عوض کن", "ترمیم", "ویرایش",
            "edit", "change", "update", "modify",
            "رنگ", "color", "فونت", "font", "سایز", "size",
            "بیشتر", "کمتر", "بزرگتر", "کوچکتر",
        ]
        has_existing = (Path.home() / ".lazarus" / "output" / "index.html").exists()
        has_keyword = any(kw in msg for kw in edit_keywords)
        return has_existing and has_keyword

    def needs_code(self, message):
        msg = message.lower().strip()
        code_keywords = [
            "بساز", "بسازید", "درست کن", " بنویس", "طراحی کن", "ایجاد کن",
            "ساخت", "سایت", "صفحه", "وبلاگ", "فروشگاه", "رستوران", "بلاگ", "قالب",
            "html", "css", "build", "create", "make", "design", "generate", "code",
            "website", "page", "site", "blog", "template", "کد",
        ]
        return any(kw in msg for kw in code_keywords)

    def ask_skills(self, message, skills):
        prompt = (
            "You are a project planner.\n"
            "Which skills are needed for this request?\n"
            "Reply with ONLY a comma-separated list.\n"
            "If none, reply: none\n\n"
            f"Skills:\n{skills[:1500]}\n\n"
            f"Request: {message}"
        )
        return self._call([{"role": "user", "content": prompt}], max_tokens=100).strip()

    def decompose_with_skills(self, message, needed_skills):
        prompt = (
            "You are a website architect.\n"
            "Break this into 3-5 sections, each is ONE part of the page.\n"
            "Reply in JSON:\n"
            '[{"name":"header", "description":"Build header with nav", "file":{"name":"header.html"}}]\n\n'
            f"Skills: {needed_skills}\n"
            f"Request: {message}"
        )
        result = self._call([{"role": "user", "content": prompt}], max_tokens=2000)
        try:
            match = re.search(r"\[.*\]", result, re.DOTALL)
            if match:
                return json.loads(match.group())
        except (json.JSONDecodeError, TypeError):
            pass
        return [{"name": "main", "description": message, "file": {"name": "main.html"}}]

    def generate_code(self, description, skills="", previous_output=""):
        prompt = (
            "You are Lazarus, a professional website builder.\n"
            "Generate a COMPLETE, WORKING HTML page.\n\n"
            "SKILLS:\n" + (skills[:1000] if skills else self.load_skills()[:1000]) + "\n\n"
            "RULES:\n"
            "- Start with <!DOCTYPE html>\n"
            "- Include ALL CSS inside <style> tag\n"
            "- RTL (dir=rtl, lang=fa)\n"
            "- Modern, professional design\n"
            "- Responsive\n"
            "- Google Font: Vazirmatn\n"
            "- One single HTML file\n"
            "- NO explanations, ONLY ```html code block\n\n"
        )
        if previous_output:
            prompt += f"Previous section:\n{previous_output[:500]}\n\n"
        prompt += f"BUILD: {description}"
        return self._call([{"role": "user", "content": prompt}], max_tokens=8000)

    def verify_code(self, html, description):
        prompt = (
            "Reply ONLY True or False.\n"
            "Is this valid, complete HTML?\n"
            f"Code: {html[:400]}\n"
        )
        result = self._call([{"role": "user", "content": prompt}], max_tokens=100)
        return "true" in result.lower()

    def edit_section(self, section_html, instruction):
        prompt = (
            "Edit this HTML. Make ONLY the requested change.\n"
            "Reply with ONLY the ```html code block.\n\n"
            f"INSTRUCTION: {instruction}\n"
            f"CODE:\n{section_html[:3000]}\n"
        )
        return self._call([{"role": "user", "content": prompt}], max_tokens=8000)

    def merge_files(self, all_css, all_body, original_request):
        prompt = (
            "Merge these parts into ONE complete HTML page.\n"
            "Combine CSS into one <style> tag.\n"
            "Combine body in order (header first, footer last).\n"
            "RTL, responsive, Vazirmatn.\n"
            "Reply with ONLY ```html code block.\n\n"
            f"Request: {original_request}\n"
            f"CSS:\n{all_css[:2000]}\n"
            f"Body:\n{all_body[:3000]}\n"
        )
        return self._call([{"role": "user", "content": prompt}], max_tokens=8000)

    def fix_code(self, html, error, task=""):
        prompt = (
            "Fix this HTML.\n"
            f"Problem: {error}\n"
            f"Task: {task}\n"
            "Reply with ONLY fixed ```html code block.\n\n"
            f"Code:\n{html[:3000]}\n"
        )
        return self._call([{"role": "user", "content": prompt}], max_tokens=8000)

    def chat(self, message, history):
        messages = [{"role": "system", "content": "You are Lazarus, a friendly AI assistant. Reply in the same language as the user. Keep responses short."}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        return self._call(messages)
