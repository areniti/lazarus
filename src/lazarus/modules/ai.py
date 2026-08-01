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
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        r = requests.post(self.api_url, headers=headers, json=data, timeout=120)
        if r.status_code != 200:
            return f"ERROR: HTTP {r.status_code}"
        result = r.json()
        if "choices" not in result:
            return f"ERROR: {json.dumps(result)[:200]}"
        return result["choices"][0]["message"]["content"]

    # ===== CONTROL UNIT DECISIONS =====

    def detect_role(self, message):
        """Step 1: Is this Developer or Admin?"""
        prompt = (
            "Reply with ONLY one word: 'developer' or 'admin'.\n"
            "Developer = wants to build/create code, websites, projects\n"
            "Admin = wants to manage, configure, view settings\n"
            f"User said: {message}"
        )
        result = self._call([{"role": "user", "content": prompt}], max_tokens=10)
        return "admin" if "admin" in result.lower() else "developer"

    def needs_code(self, message):
        """Step 2: Does user want code? True/False"""
        prompt = (
            "Reply with ONLY 'True' or 'False'.\n"
            "Does this message require generating code, HTML, or a website?\n"
            f"User said: {message}"
        )
        result = self._call([{"role": "user", "content": prompt}], max_tokens=10)
        return "true" in result.lower()

    def info_complete(self, message, context=""):
        """Step 3: Is info sufficient? True/False"""
        prompt = (
            "Reply with ONLY 'True' or 'False'.\n"
            "Does the user provide ENOUGH information to build what they want?\n"
            "If vague or missing details -> False\n"
            f"Context: {context}\n"
            f"User said: {message}"
        )
        result = self._call([{"role": "user", "content": prompt}], max_tokens=10)
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
            "- name: short name\n"
            "- description: what to build\n"
            "- input: what it needs\n"
            "- output: what it produces\n\n"
            "Reply in JSON format:\n"
            '[{"name":"...", "description":"...", "input":"...", "output":"..."}]\n\n'
            f"Skills reference:\n{skills}\n\n"
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

    def generate_code(self, task, previous_output=""):
        """Step 5: Generate code for a sub-project"""
        prompt = (
            "You are an expert web developer.\n"
            "Generate COMPLETE, WORKING HTML code.\n"
            "Include all CSS inline. RTL, responsive, modern design.\n"
            "Reply with ONLY the HTML code in a ```html block.\n\n"
            f"Task: {task['description']}\n"
            f"Input: {task['input']}\n"
            f"Output expected: {task['output']}\n"
        )
        if previous_output:
            prompt += f"Previous sub-project output:\n{previous_output[:500]}\n"
        return self._call([{"role": "user", "content": prompt}], max_tokens=8000)

    def verify(self, code, task_description):
        """Step 7: Verify code is correct"""
        prompt = (
            "Reply with ONLY 'True' or 'False'.\n"
            "Is this code valid, complete, and matches the task description?\n"
            "Check: has <!DOCTYPE>, has <html>, has </html>, has content.\n"
            f"Task: {task_description}\n"
            f"Code starts with: {code[:300]}\n"
        )
        result = self._call([{"role": "user", "content": prompt}], max_tokens=10)
        return "true" in result.lower()

    def chat(self, message, history):
        """General chat"""
        messages = [{"role": "system", "content": "You are Lazarus, a helpful AI web developer."}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        return self._call(messages)
