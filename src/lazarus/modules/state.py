"""State Register - tracks progress like CPU registers"""
import json
import time
from pathlib import Path


class StateRegister:
    """
    Like CPU registers - stores current state of the pipeline.
    Tracks: current step, status of each sub-project, results.
    """

    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.output_dir / "state.json"
        self.state = self._load()

    def _load(self):
        if self.state_file.exists():
            return json.loads(self.state_file.read_text("utf-8"))
        return {
            "current_project": None,
            "current_step": 0,
            "total_steps": 0,
            "status": "idle",  # idle | planning | executing | verifying | done | error
            "sub_projects": [],
            "results": [],
            "started_at": None,
            "finished_at": None,
        }

    def save(self):
        self.state_file.write_text(json.dumps(self.state, indent=2, ensure_ascii=False), "utf-8")

    def start_new_project(self, description, sub_projects):
        """Initialize a new project pipeline"""
        self.state = {
            "current_project": description,
            "current_step": 0,
            "total_steps": len(sub_projects),
            "status": "planning",
            "sub_projects": sub_projects,
            "results": [{"status": "pending"} for _ in sub_projects],
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "finished_at": None,
        }
        self.save()

    def start_step(self, index):
        """Begin executing a sub-project"""
        self.state["current_step"] = index
        self.state["status"] = "executing"
        self.state["results"][index]["status"] = "running"
        self.save()

    def complete_step(self, index, result):
        """Mark a sub-project as done"""
        self.state["results"][index] = {
            "status": "done",
            "output_path": result.get("path", ""),
            "output_name": result.get("name", ""),
            "completed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.state["status"] = "verifying"
        self.save()

    def fail_step(self, index, error):
        """Mark a sub-project as failed"""
        self.state["results"][index]["status"] = "failed"
        self.state["results"][index]["error"] = error
        self.state["status"] = "error"
        self.save()

    def all_done(self):
        """Check if all steps completed"""
        return all(r.get("status") == "done" for r in self.state["results"])

    def finish(self):
        """Mark project as complete"""
        self.state["status"] = "done"
        self.state["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.save()

    def get_progress(self):
        """Return progress summary"""
        done = sum(1 for r in self.state["results"] if r.get("status") == "done")
        total = self.state["total_steps"]
        return {
            "project": self.state["current_project"],
            "status": self.state["status"],
            "done": done,
            "total": total,
            "percent": (done / total * 100) if total > 0 else 0,
            "current": self.state["current_step"],
            "results": self.state["results"],
        }

    def get_last_output(self):
        """Get the output of the last completed step (for chaining)"""
        for r in reversed(self.state["results"]):
            if r.get("status") == "done" and r.get("output_path"):
                path = self.output_dir / r["output_path"]
                if path.exists():
                    return path.read_text("utf-8")
        return ""
