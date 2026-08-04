"""AI - talks to an OpenAI-compatible chat completions endpoint."""
import json
import re

import requests


class AIError(Exception):
    """Raised when the model call fails, so callers can report a real reason."""


# Short conversational messages that should never trigger a site build.
_CHAT_PATTERNS = (
    "سلام", "سلم", "درود", "خوبی", "چطوری", "حالت", "ممنون", "مرسی",
    "باشه", "بله", "نه", "خدافظ", "خداحافظ", "شبت", "hi", "hello", "hey",
    "thanks", "thank you", "ok", "okay", "bye", "good", "yes", "no",
)

# Words that mean "change what already exists" rather than "build from scratch".
_EDIT_PATTERNS = (
    "عوض کن", "تغییر بده", "تغییرش", "اضافه کن", "حذف کن", "پاک کن",
    "بزرگتر", "کوچکتر", "رنگ", "جابجا", "ویرایش", "اصلاح", "درستش کن",
    "بهترش", "برش دار", "کمش کن", "زیادش کن",
    "change", "edit", "update", "add ", "remove", "delete", "fix",
    "make it", "replace", "rename", "resize", "recolor",
)

# Words that clearly mean "build something new".
_BUILD_PATTERNS = (
    "بساز", "درست کن", "ایجاد کن", "طراحی کن", "بنویس", "سایت", "صفحه",
    "وبسایت", "وب سایت", "لندینگ", "فروشگاه", "پورتفولیو", "وبلاگ",
    "build", "create", "make me", "design", "generate", "website",
    "landing", "portfolio", "blog", "shop", "page",
)


class AI:
    def __init__(self, config):
        self.config = config
        self.api_url = config.data["api"]["url"]
        self.api_key = config.data["api"]["key"]
        self.model = config.data["api"]["model"]

    # ===== transport =====

    def _call(self, messages, max_tokens=4096):
        if not self.api_url or not self.api_key:
            raise AIError("API URL یا Key تنظیم نشده است.")
        url = self.api_url.rstrip("/")
        if not url.endswith("/chat/completions"):
            url += "/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}",
                   "Content-Type": "application/json"}
        payload = {"model": self.model, "messages": messages,
                   "max_tokens": max_tokens}
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=300)
        except requests.Timeout:
            raise AIError("درخواست به مدل تایم‌اوت شد (۳۰۰ ثانیه).")
        except requests.RequestException as e:
            raise AIError(f"خطای شبکه: {e}")

        if r.status_code != 200:
            raise AIError(f"HTTP {r.status_code} از سرور مدل: {r.text[:200]}")
        try:
            result = r.json()
        except ValueError:
            raise AIError(f"پاسخ نامعتبر (JSON نبود): {r.text[:200]}")
        choices = result.get("choices")
        if not choices:
            raise AIError(f"پاسخ بدون choices: {json.dumps(result)[:200]}")
        msg = choices[0].get("message", {})
        content = msg.get("content") or msg.get("reasoning")
        if not content:
            raise AIError("مدل پاسخ خالی برگرداند.")
        return content

    # ===== intent =====

    def classify(self, message):
        """Return 'chat', 'edit' or 'build' from the user's message."""
        msg = message.lower().strip().rstrip("!?.،؟")

        # Pure greeting / acknowledgement, nothing else in the message.
        if msg in _CHAT_PATTERNS:
            return "chat"
        if len(msg.split()) <= 2 and any(msg.startswith(p) for p in _CHAT_PATTERNS):
            return "chat"

        has_build = any(p in msg for p in _BUILD_PATTERNS)
        has_edit = any(p in msg for p in _EDIT_PATTERNS)

        # "رنگ رو عوض کن" -> edit. "یه سایت جدید بساز" -> build wins.
        if has_edit and not has_build:
            return "edit"
        if has_build:
            return "build"
        if has_edit:
            return "edit"
        # Anything longer than a greeting that asks for something: treat as build.
        if len(msg.split()) >= 3:
            return "build"
        return "chat"

    # ===== planning =====

    def decompose(self, message):
        """Ask the model for a project structure. Falls back to a sane default."""
        prompt = f"""You are a web architect. Plan a small static website.

REQUEST: {message}

Reply with ONLY JSON in this exact shape:

{{
  "project_name": "my-project",
  "description": "one short sentence",
  "theme": {{
    "primary_color": "#667eea",
    "secondary_color": "#764ba2",
    "bg_color": "#0d1117",
    "text_color": "#e6edf3",
    "font": "Vazirmatn"
  }},
  "sections": [
    {{"id": "hero", "title": "...", "description": "what goes in this section"}},
    {{"id": "features", "title": "...", "description": "..."}}
  ]
}}

RULES:
- Sections must match what the user actually asked for. Do NOT invent
  a blog or a portfolio if the request is about something else.
- Between 3 and 6 sections.
- Titles in the same language as the request.
- No markdown, no explanation, JSON only."""
        # Reasoning models emit a long chain of thought before the JSON, so the
        # budget has to cover both or the object arrives truncated.
        raw = self._call([{"role": "user", "content": prompt}], max_tokens=6000)
        plan = self._parse_json(raw)
        if plan and plan.get("sections"):
            plan.setdefault("project_name", "my-website")
            plan.setdefault("theme", self._default_theme())
            plan["sections"] = self._clean_sections(plan["sections"])
            if plan["sections"]:
                return plan
        return self._fallback_plan(message)

    @classmethod
    def _parse_json(cls, raw):
        """Find the JSON plan in a response that may be wrapped in prose."""
        if not raw:
            return None
        for candidate in cls._json_candidates(raw):
            try:
                data = json.loads(candidate)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(data, dict) and "sections" in data:
                return data
        return None

    @staticmethod
    def _json_candidates(raw):
        """Yield plausible JSON objects, richest first.

        Reasoning models write paragraphs containing stray braces before the
        real answer, so scanning for balanced objects and preferring the ones
        that mention "sections" beats grabbing the first '{'.
        """
        candidates = []

        for match in re.finditer(r"```(?:json)?\s*\n(.*?)\n\s*```", raw,
                                 re.DOTALL | re.IGNORECASE):
            candidates.append(match.group(1).strip())

        # Balanced-brace scan over the whole response.
        depth = 0
        start = None
        for i, ch in enumerate(raw):
            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start is not None:
                        candidates.append(raw[start:i + 1])
                        start = None

        # An unterminated object at the end means the reply was truncated.
        if depth > 0 and start is not None:
            candidates.append(raw[start:])

        seen = set()
        ordered = []
        for c in candidates:
            c = c.strip()
            if not c.startswith("{") or c in seen:
                continue
            seen.add(c)
            ordered.append(c)
        # Objects that actually look like a plan first, longest first.
        ordered.sort(key=lambda c: ('"sections"' in c, len(c)), reverse=True)
        return ordered

    @staticmethod
    def _clean_sections(sections):
        """Keep only well-formed sections and give each a usable id."""
        cleaned = []
        used = set()
        if not isinstance(sections, list):
            return cleaned
        for i, s in enumerate(sections):
            if not isinstance(s, dict):
                continue
            title = str(s.get("title") or "").strip()
            desc = str(s.get("description") or "").strip()
            sid = str(s.get("id") or "").strip()
            sid = re.sub(r"[^a-zA-Z0-9_-]", "", sid) or f"section{i + 1}"
            if sid in used:
                sid = f"{sid}{i + 1}"
            used.add(sid)
            if not title and not desc:
                continue
            cleaned.append({"id": sid, "title": title or sid,
                            "description": desc or title})
        return cleaned[:6]

    @staticmethod
    def _default_theme():
        return {"primary_color": "#667eea", "secondary_color": "#764ba2",
                "bg_color": "#0d1117", "text_color": "#e6edf3",
                "font": "Vazirmatn"}

    def _fallback_plan(self, message):
        return {
            "project_name": "my-website",
            "description": message[:120],
            "theme": self._default_theme(),
            "sections": [
                {"id": "hero", "title": "معرفی",
                 "description": f"بخش اصلی بر اساس درخواست: {message[:200]}"},
                {"id": "content", "title": "محتوا",
                 "description": "محتوای اصلی مرتبط با درخواست کاربر"},
                {"id": "contact", "title": "تماس",
                 "description": "راه‌های ارتباطی و فرم تماس"},
            ],
        }

    # ===== generation =====

    def generate_css(self, plan):
        theme = plan.get("theme", self._default_theme())
        sections = ", ".join(s.get("id", "") for s in plan.get("sections", []))
        prompt = f"""Create a complete CSS stylesheet for an RTL Persian website.

THEME: {json.dumps(theme, ensure_ascii=False)}
SECTIONS ON THE PAGE: {sections}

Include:
- :root CSS variables from the theme colors
- Base styles (body, typography, links), RTL aware
- Sticky responsive navbar
- Styles for every section listed above
- Responsive card grid, hero with gradient, footer, form controls
- Mobile-first breakpoints, hover and fade-in animations

OUTPUT: ONLY CSS inside a ```css block. At least 120 lines."""
        return self._call([{"role": "user", "content": prompt}], max_tokens=8000)

    def generate_js(self, plan):
        prompt = """Create vanilla JavaScript for a single-page RTL website.

Include:
- Mobile nav toggle
- Smooth scroll for in-page anchor links
- Contact form validation with inline error messages
- Fade-in on scroll via IntersectionObserver
- Back-to-top button
- Active nav link highlight while scrolling

No frameworks, no external libraries.
OUTPUT: ONLY JavaScript inside a ```javascript block."""
        return self._call([{"role": "user", "content": prompt}], max_tokens=8000)

    def generate_homepage(self, original_request, plan):
        """Generate one complete index.html containing every planned section."""
        theme = plan.get("theme", self._default_theme())
        sections = plan.get("sections", [])
        section_spec = "\n".join(
            f"- id=\"{s.get('id')}\" — {s.get('title')}: {s.get('description')}"
            for s in sections)
        nav_spec = " | ".join(
            f"#{s.get('id')} → {s.get('title')}" for s in sections)

        prompt = f"""Create ONE complete HTML page for this request:

"{original_request}"

PROJECT: {plan.get('project_name')}
THEME: {json.dumps(theme, ensure_ascii=False)}

SECTIONS (every one of these must exist as <section id="...">):
{section_spec}

NAVBAR must link to: {nav_spec}

RULES:
1. Complete file starting with <!DOCTYPE html> and ending with </html>
2. In <head>: <link rel="stylesheet" href="style.css">
3. Before </body>: <script src="main.js"></script>
4. In <head>: <link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;700;900&display=swap" rel="stylesheet">
5. <html lang="fa" dir="rtl"> and a viewport meta tag
6. Real Persian content relevant to the request, NOT lorem ipsum
7. No inline <style> block — all styling comes from style.css
8. Everything interactive must actually work

OUTPUT: ONLY the HTML inside a ```html block."""
        return self._call([{"role": "user", "content": prompt}], max_tokens=16000)

    # ===== verify / edit / chat =====

    def verify_page(self, plan, code):
        section_ids = [s.get("id") for s in plan.get("sections", [])]
        prompt = f"""Check this HTML page.

REQUIRED SECTION IDS: {section_ids}

```html
{code[:6000]}
```

Reply with ONLY:
- "APPROVED" if every required section exists and the page is complete
- "REJECTED: <short reason>" otherwise"""
        return self._call([{"role": "user", "content": prompt}], max_tokens=200)

    def chat(self, message, history):
        messages = [{"role": "system", "content":
                     "You are Lazarus, a friendly Persian-speaking assistant "
                     "for a website builder. Reply concisely in the user's "
                     "language."}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        return self._call(messages, max_tokens=1024)

    def edit(self, current_code, instruction):
        prompt = f"""Apply this change to the page: {instruction}

Keep everything else identical. Keep the style.css link and the main.js script
tag. Keep RTL and the existing section ids unless the instruction says otherwise.

Current page:
```html
{current_code}
```

OUTPUT: ONLY the full edited HTML inside a ```html block."""
        return self._call([{"role": "user", "content": prompt}], max_tokens=16000)
