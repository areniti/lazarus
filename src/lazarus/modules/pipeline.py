"""Lazarus Pipeline - CPU-like architecture for code generation"""
from .ai import AI
from .planner import Planner
from .state import StateRegister
from .executor import Executor
from ..core.config import Config
from ..core.memory import Memory


class Pipeline:
    """Main pipeline with memory, skills, decompose, verify, retry."""

    def __init__(self, config=None):
        self.config = config or Config()
        self.ai = AI(self.config)
        self.planner = Planner(self.ai)
        self.state = StateRegister(self.config.output_dir)
        self.executor = Executor(self.ai, self.state, self.config.output_dir)
        self.memory = Memory()

    def process(self, message, history=None):
        """Full pipeline for a user message"""
        role = self.config.data.get("role", "developer")

        if role == "admin":
            return {"response": "Admin mode. Use /admin for settings.", "files": [], "status": "admin"}

        # Save to memory
        self.memory.save_message("user", message)
        memory_history = self.memory.get_history(limit=20)

        # Chat or Build?
        is_build_request = self.ai.needs_code(message)

        if not is_build_request:
            response = self.ai.chat(message, memory_history)
            self.memory.save_message("assistant", response)
            return {"response": response, "files": [], "status": "chat"}

        # === BUILD PIPELINE ===
        print(f"\n🔨 Building: {message[:50]}...")

        # Step 1: Decompose
        sub_projects = self.planner.decompose(message)
        print(f"   {len(sub_projects)} sub-projects:")
        for sp in sub_projects:
            print(f"   - {sp['name']}: {sp.get('description', '')[:50]}")

        self.state.start_new_project(message, sub_projects)

        # Step 2: Execute each one
        files_created = []
        last_output = ""

        for i, project in enumerate(sub_projects):
            file_spec = project.get("file", {})
            filename = file_spec.get("name", f"{project['name']}.html")
            filepath = self.config.output_dir / filename

            # Create file FIRST (empty)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(f"<!-- {project.get('description', '')} -->", encoding="utf-8")
            print(f"   📄 Created: {filename}")

            self.state.start_step(i)

            # Generate
            code = self.ai.generate_code(project.get("description", message))
            html = self.executor._extract_html(code)

            if not html:
                self.state.fail_step(i, "No HTML generated")
                continue

            # Verify
            ok, error = self.executor._validate(html)

            if not ok:
                # Try to fix
                print(f"   🔧 Fixing: {error}")
                fixed = self.ai.fix_code(html, error, project.get("description", ""))
                html = self.executor._extract_html(fixed) or html
                ok, error = self.executor._validate(html)

            if ok:
                filepath.write_text(html, encoding="utf-8")
                self.state.complete_step(i, {"path": filename, "name": project["name"]})
                files_created.append({"path": filename, "name": project["name"], "size": len(html)})
                last_output = html
                print(f"   ✅ {filename} ({len(html)} bytes)")
            else:
                self.state.fail_step(i, error)
                print(f"   ❌ {filename}: {error}")

        self.state.finish()

        # Response
        if files_created:
            names = ", ".join(f["name"] for f in files_created)
            response = f"✅ ساخته شد! ({len(files_created)} فایل: {names})\n🔗 /preview/{files_created[0]['path']}"
        else:
            response = "❌ نتونستم بسازم."

        self.memory.save_message("assistant", response)
        return {
            "response": response,
            "files": files_created,
            "status": "done" if files_created else "error",
        }
