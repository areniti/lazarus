"""State Register - Formal State Machine based on Stallings OS Model"""
import json
import time
from pathlib import Path
from collections import deque
from enum import Enum


class StepState(Enum):
    """Pipeline states mapped from Stallings 5-state model"""
    DECOMPOSED = "decomposed"   # NEW: task defined
    QUEUED = "queued"           # READY: waiting in queue
    EXECUTING = "executing"     # RUNNING: API call in progress
    VERIFYING = "verifying"     # BLOCKED (I/O): checking output
    RETRYING = "retrying"       # BLOCKED: waiting for retry
    COMPLETED = "completed"     # TERMINATED: done
    FAILED = "failed"           # TERMINATED: failed permanently


# Valid state transitions (prevents invalid jumps)
VALID_TRANSITIONS = {
    StepState.DECOMPOSED: [StepState.QUEUED],
    StepState.QUEUED: [StepState.EXECUTING],
    StepState.EXECUTING: [StepState.VERIFYING, StepState.RETRYING, StepState.FAILED],
    StepState.VERIFYING: [StepState.COMPLETED, StepState.RETRYING, StepState.FAILED],
    StepState.RETRYING: [StepState.QUEUED, StepState.FAILED],
    StepState.COMPLETED: [],  # terminal state
    StepState.FAILED: [],     # terminal state
}


class StateRegister:
    """
    State Register - like CPU registers + formal state machine.
    Manages sub-project lifecycle with validated transitions.
    """

    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.output_dir / "state.json"
        self.state = self._load()
        self.task_queue = deque()

    def _load(self):
        if self.state_file.exists():
            return json.loads(self.state_file.read_text("utf-8"))
        return self._empty_state()

    def _empty_state(self):
        return {
            "project": None,
            "status": "idle",
            "current_step": 0,
            "total_steps": 0,
            "sub_projects": [],
            "results": [],
            "started_at": None,
            "finished_at": None,
            "errors": [],
        }

    def save(self):
        self.state_file.write_text(
            json.dumps(self.state, indent=2, ensure_ascii=False), "utf-8"
        )

    def _transition(self, index, new_state):
        """Validate and apply state transition"""
        current = self.state["results"][index].get("status", "decomposed")
        current_enum = StepState(current)
        new_enum = StepState(new_state)

        if new_enum not in VALID_TRANSITIONS.get(current_enum, []):
            print(f"  ⚠️ Invalid transition: {current} → {new_state}")
            return False

        self.state["results"][index]["status"] = new_state
        return True

    def start_new_project(self, description, sub_projects):
        """Initialize project with all sub-projects in DECOMPOSED state"""
        self.task_queue = deque(range(len(sub_projects)))
        self.state = {
            "project": description,
            "status": "planning",
            "current_step": 0,
            "total_steps": len(sub_projects),
            "sub_projects": sub_projects,
            "results": [
                {"status": StepState.DECOMPOSED.value, "name": sp["name"]}
                for sp in sub_projects
            ],
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "finished_at": None,
            "errors": [],
        }
        self.save()

    def start_step(self, index):
        """Transition: DECOMPOSED → QUEUED → EXECUTING"""
        self._transition(index, StepState.QUEUED.value)
        self._transition(index, StepState.EXECUTING.value)
        self.state["current_step"] = index
        self.save()

    def verify_step(self, index):
        """Transition: EXECUTING → VERIFYING"""
        self._transition(index, StepState.VERIFYING.value)
        self.save()

    def complete_step(self, index, result):
        """Transition: VERIFYING → COMPLETED"""
        self._transition(index, StepState.COMPLETED.value)
        self.state["results"][index].update({
            "output_path": result.get("path", ""),
            "output_name": result.get("name", ""),
            "completed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        self.save()

    def retry_step(self, index):
        """Transition: VERIFYING/EXECUTING → RETRYING → QUEUED"""
        self._transition(index, StepState.RETRYING.value)
        self._transition(index, StepState.QUEUED.value)
        self.save()

    def fail_step(self, index, error):
        """Transition: any → FAILED (terminal)"""
        self._transition(index, StepState.FAILED.value)
        self.state["results"][index]["error"] = error
        self.state["errors"].append({
            "step": index,
            "error": error,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        self.save()

    def finish(self):
        """Mark project as done"""
        self.state["status"] = "done"
        self.state["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.save()

    def get_progress(self):
        done = sum(
            1 for r in self.state["results"]
            if r.get("status") == StepState.COMPLETED.value
        )
        total = self.state["total_steps"]
        return {
            "project": self.state["project"],
            "status": self.state["status"],
            "done": done,
            "total": total,
            "percent": (done / total * 100) if total > 0 else 0,
            "current": self.state["current_step"],
            "results": self.state["results"],
            "errors": self.state["errors"],
        }

    def reset(self):
        self.state = self._empty_state()
        self.task_queue.clear()
        self.save()
