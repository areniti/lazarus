"""Lazarus Pipeline - CPU-like architecture for code generation

Flows like a real CPU:
1. FETCH: understand request + check skills
2. DECODE: decompose into sub-projects
3. EXECUTE: for each sub-project (ONE BY ONE, each with own API calls):
   a. Create file
   b. Generate code
   c. Verify with API
   d. If fails: retry
4. WRITEBACK: save to disk + update state

Each sub-project = multiple API calls.
A site with 4 sub-projects = 8+ API calls minimum.
"""
from .ai import AI
from .planner import Planner
from .state import StateRegister
from .executor import Executor
from ..core.config import Config
from ..core.memory import Memory


class Pipeline:
    """Main pipeline - heavy API usage, quality over speed."""

    def __init__(self, config=None):
        self.config = config or Config()
        self.ai = AI(self.config)
        self.planner = Planner(self.ai)
        self.state = StateRegister(self.config.output_dir)
        self.executor = Executor(self.ai, self.state, self.config.output_dir)
        self.memory = Memory()

    def process(self, message, history=None):
        """Full pipeline - many API calls, one by one"""
        role = self.config.data.get("role", "developer")
        if role == "admin":
            return {"response": "Admin mode. Use /admin.", "files": [], "status": "admin"}

        # Save to memory
        self.memory.save_message("user", message)
        memory_history = self.memory.get_history(limit=10)

        # Chat or Build?
        if not self.ai.needs_code(message):
            response = self.ai.chat(message, memory_history)
            self.memory.save_message("assistant", response)
            return {"response": response, "files": [], "status": "chat"}

        # === BUILD PIPELINE (heavy API usage) ===
        logs = []

        # STEP 1: Ask which skills are needed
        print("\n📋 Step 1: Checking skills...")
        skills = self.ai.load_skills()
        needed_skills = self.ai.ask_skills(message, skills)
        logs.append(f"Skills: {needed_skills}")
        print(f"   Skills needed: {needed_skills}")

        # STEP 2: Decompose into sub-projects
        print("\n📋 Step 2: Decomposing...")
        sub_projects = self.ai.decompose_with_skills(message, needed_skills)
        logs.append(f"Sub-projects: {len(sub_projects)}")
        print(f"   {len(sub_projects)} sub-projects:")
        for sp in sub_projects:
            print(f"   - {sp['name']}: {sp.get('description', '')[:60]}")

        self.state.start_new_project(message, sub_projects)

        # STEP 3: Execute each sub-project (ONE BY ONE)
        files_created = []
        last_output = ""

        for i, project in enumerate(sub_projects):
            file_spec = project.get("file", {})
            filename = file_spec.get("name", f"{project['name']}.html")
            filepath = self.config.output_dir / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)

            print(f"\n🔨 Step 3.{i+1}: {project['name']}")

            # Create file FIRST
            filepath.write_text(f"<!-- {project.get('description', '')} -->", encoding="utf-8")
            print(f"   📄 File created: {filename}")

            self.state.start_step(i)

            # API call 1: Generate code
            print(f"   🤖 Generating code...")
            code = self.ai.generate_code(
                project.get("description", message),
                skills=needed_skills,
                previous_output=last_output,
            )
            html = self.executor._extract_html(code)

            if not html:
                self.state.fail_step(i, "No HTML generated")
                print(f"   ❌ No HTML extracted")
                continue

            # API call 2: Verify with API
            print(f"   🔍 Verifying with API...")
            verify_ok = self.ai.verify_code(html, project.get("description", message))

            if not verify_ok:
                # API call 3: Fix issues
                print(f"   🔧 Fixing issues...")
                fixed = self.ai.fix_code(html, project.get("description", message))
                html = self.executor._extract_html(fixed) or html

            # Local validation
            ok, error = self.executor._validate(html)
            if not ok:
                # API call 4: Try fixing again
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
                print(f"   ❌ {error}")

        self.state.finish()

        # Response
        if files_created:
            names = ", ".join(f["name"] for f in files_created)
            response = f"✅ ساخته شد! ({len(files_created)} فایل: {names})"
            for f in files_created:
                response += f"\n🔗 /preview/{f['path']}"
        else:
            response = "❌ نتونستم بسازم."

        self.memory.save_message("assistant", response)
        return {
            "response": response,
            "files": files_created,
            "status": "done" if files_created else "error",
            "logs": logs,
        }
