"""Lazarus Pipeline - CPU-like architecture for code generation"""
from .ai import AI
from .state import StateRegister
from .executor import Executor
from ..core.config import Config


class Pipeline:
    """
    Main pipeline - like a CPU instruction cycle:
    Fetch -> Decode -> Execute -> Writeback
    """

    def __init__(self, config=None):
        self.config = config or Config()
        self.ai = AI(self.config)
        self.state = StateRegister(self.config.output_dir)
        self.executor = Executor(self.ai, self.state, self.config.output_dir)

    def process(self, message, history=None):
        """
        Full pipeline for a user message.
        Returns: {response, files, progress, status}
        """
        history = history or []

        # Step 1: Detect role
        role = self.ai.detect_role(message)

        if role == "admin":
            return self._admin_flow(message)

        # Step 2: Needs code?
        needs_code = self.ai.needs_code(message)

        if not needs_code:
            response = self.ai.chat(message, history)
            return {"response": response, "files": [], "status": "chat"}

        # Step 3: Info complete?
        complete = self.ai.info_complete(message)

        if not complete:
            response = self.ai.ask_clarification(message)
            return {"response": response, "files": [], "status": "need_info"}

        # Step 4: Decompose
        sub_projects = self.ai.decompose(message)
        self.state.start_new_project(message, sub_projects)

        # Step 5: Execute all
        success = self.executor.run_all()

        if not success:
            return {
                "response": f"❌ Error at step {self.state.state['current_step']}",
                "files": [],
                "status": "error",
            }

        # Step 6: Done
        self.state.finish()
        progress = self.state.get_progress()
        files = [r for r in progress["results"] if r.get("status") == "done"]

        return {
            "response": f"✅ Project complete! {progress['done']} sub-projects built.",
            "files": files,
            "status": "done",
            "progress": progress,
        }

    def _admin_flow(self, message):
        """Handle admin messages"""
        if "show config" in message.lower():
            return {"response": str(self.config.data), "files": [], "status": "config"}
        if "progress" in message.lower():
            progress = self.state.get_progress()
            return {"response": str(progress), "files": [], "status": "progress"}
        return {"response": "Admin panel available at /admin", "files": [], "status": "admin"}
