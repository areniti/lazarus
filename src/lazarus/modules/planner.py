"""Planner - breaks projects into sub-projects with file specs"""
import json
import re


class Planner:
    """
    Planner - like CPU instruction decoder.
    Breaks a big project into small independent sub-projects.
    Each has: name, description, file spec, input, output.
    """

    def __init__(self, ai):
        self.ai = ai

    def decompose(self, message):
        """Break project into sub-projects with file specs"""
        # Simple keyword-based decomposition (no API call = fast)
        tasks = self._simple_decompose(message)
        
        # If too few tasks, ask AI
        if len(tasks) <= 1:
            raw = self.ai.decompose(message)
            tasks = self._parse_tasks(raw) or tasks

        if not tasks:
            tasks = [{"name": "main", "description": message}]

        # Add file specs to each task
        for task in tasks:
            if "file" not in task:
                task["file"] = self._make_file_spec(task)

        return tasks

    def _parse_tasks(self, raw):
        """Parse AI response into list of tasks"""
        if isinstance(raw, list):
            return raw
        try:
            match = re.search(r"\[.*\]", str(raw), re.DOTALL)
            if match:
                return json.loads(match.group())
        except (json.JSONDecodeError, TypeError):
            pass
        return []

    def _simple_decompose(self, message):
        """Fast local decomposition without API"""
        msg = message.lower()
        tasks = []
        
        # Always create: HTML structure
        tasks.append({
            "name": "html_structure",
            "description": f"Create complete HTML page: {message}",
            "input": message,
            "output": "Complete HTML page with CSS"
        })
        
        return tasks

    def _make_file_spec(self, task):
        """Create file specification for a task"""
        name = task.get("name", "output")
        desc = task.get("description", "").lower()

        # Determine format
        if any(kw in desc for kw in ["css", "style", "استایل"]):
            fmt = "css"
            ext = "css"
        elif any(kw in desc for kw in ["js", "javascript", "اسکریپت"]):
            fmt = "javascript"
            ext = "js"
        elif any(kw in desc for kw in ["json", "داده", "data"]):
            fmt = "json"
            ext = "json"
        else:
            fmt = "html"
            ext = "html"

        return {
            "name": f"{name}.{ext}",
            "format": fmt,
            "css": "inline" if fmt == "html" else None,
        }
