"""Executor - runs sub-projects with state transitions + circuit breaker"""
import re
from pathlib import Path


class Executor:
    """
    Executor - like CPU execution unit.
    Each sub-project: create file → generate → write → verify
    With state transitions and circuit breaker.
    """

    MAX_RETRIES = 1
    CIRCUIT_BREAK_THRESHOLD = 3  # Break after 3 consecutive failures

    def __init__(self, ai, state, output_dir):
        self.ai = ai
        self.state = state
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.consecutive_failures = 0

    def run_all(self):
        """Run all sub-projects one by one (FCFS)"""
        projects = self.state.state["sub_projects"]
        last_output = ""

        for i, project in enumerate(projects):
            # Circuit breaker check
            if self.consecutive_failures >= self.CIRCUIT_BREAK_THRESHOLD:
                print(f"\n⚡ Circuit Breaker: {self.consecutive_failures} consecutive failures. Stopping.")
                self.state.fail_step(i, "Circuit breaker triggered")
                return False

            print(f"\n🔨 Step {i+1}/{len(projects)}: {project['name']}")

            # Get file spec
            file_spec = project.get("file", {})
            filename = file_spec.get("name", f"{project['name']}.html")
            filepath = self.output_dir / filename

            # 1. Create file FIRST (empty)
            filepath.write_text(f"<!-- {project['description']} -->", encoding="utf-8")
            print(f"  📄 Created: {filename}")

            # 2-4. Generate + Write + Verify
            success = False
            for attempt in range(1, self.MAX_RETRIES + 1):
                print(f"  Attempt {attempt}/{self.MAX_RETRIES}...")

                # State: → EXECUTING
                self.state.start_step(i)

                # Generate
                code = self.ai.generate_code(project, last_output)
                html = self._extract_html(code)

                if not html:
                    print(f"  ❌ No HTML extracted")
                    self.state.retry_step(i)
                    continue

                # State: → VERIFYING
                self.state.verify_step(i)

                # Validate
                ok, error = self._validate(html)
                if not ok:
                    print(f"  ❌ Validation: {error}")
                    self.state.retry_step(i)
                    if attempt < self.MAX_RETRIES:
                        fixed = self.ai.fix_code(html, error, project["description"])
                        html = self._extract_html(fixed) or html
                    continue

                # 3. Write to file
                filepath.write_text(html, encoding="utf-8")
                print(f"  ✅ Written: {filename} ({len(html)} bytes)")

                last_output = html
                self.consecutive_failures = 0  # Reset on success
                success = True
                break

            if success:
                self.state.complete_step(i, {"path": filename, "name": project["name"]})
            else:
                self.consecutive_failures += 1
                self.state.fail_step(i, f"Failed after {self.MAX_RETRIES} attempts")
                return False

        return True

    def _extract_html(self, response):
        """Extract HTML from AI response"""
        if not response:
            return None

        # Strategy 1: ```html ... ```
        match = re.search(r"```html\s*(.*?)```", response, re.DOTALL)
        if match:
            code = match.group(1).strip()
            if "<!DOCTYPE" in code or "<html" in code:
                return code

        # Strategy 2: ```html without closing ```
        match = re.search(r"```html\s*(.*)", response, re.DOTALL)
        if match:
            code = match.group(1)
            code = re.sub(r"```\s*$", "", code).strip()
            end = code.find("</html>")
            if end >= 0:
                code = code[: end + 7]
            else:
                code = code.rstrip()
                code += "\n</body>\n</html>"
            if "<!DOCTYPE" in code or "<html" in code:
                return code.strip()

        # Strategy 3: response IS html
        if "<!DOCTYPE" in response or "<html" in response:
            return response.strip()

        return None

    def _validate(self, html):
        """Local validation (no API needed)"""
        errors = []
        if len(html) < 200:
            errors.append(f"Too short ({len(html)} bytes)")
        if "<!DOCTYPE" not in html and "<!doctype" not in html:
            errors.append("Missing <!DOCTYPE>")
        if "<html" not in html:
            errors.append("Missing <html>")
        if "</html>" not in html:
            errors.append("Missing </html>")
        if "<body" not in html:
            errors.append("Missing <body>")
        if errors:
            return False, "; ".join(errors)
        return True, None
