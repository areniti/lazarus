"""Planner - breaks projects into sub-projects with file specs"""
import json
import re


class Planner:
    """Breaks projects into sub-projects with file specs."""

    def __init__(self, ai):
        self.ai = ai

    def decompose(self, message):
        """Break project into sub-projects"""
        # Ask AI to decompose
        raw = self.ai.decompose(message)
        tasks = self._parse_tasks(raw)

        if not tasks:
            # Fallback: single task
            tasks = [{"name": "main", "description": message, "input": message, "output": "HTML page"}]

        # Add file specs
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

    def _make_file_spec(self, task):
        """Create file specification for a task"""
        name = task.get("name", "output")
        desc = task.get("description", "").lower()

        if any(kw in desc for kw in ["css", "style", "استایل"]):
            fmt, ext = "css", "css"
        elif any(kw in desc for kw in ["js", "javascript", "اسکریپت"]):
            fmt, ext = "javascript", "js"
        elif any(kw in desc for kw in ["json", "داده", "data"]):
            fmt, ext = "json", "json"
        else:
            fmt, ext = "html", "html"

        return {"name": f"{name}.{ext}", "format": fmt}
