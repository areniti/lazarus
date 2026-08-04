"""Pipeline tests: staging build, rollback on failure, error surfacing."""
import tempfile
from pathlib import Path

import pytest

from lazarus.core.config import Config
from lazarus.modules.ai import AIError
from lazarus.modules.pipeline import Pipeline

GOOD_HTML = ("```html\n<!DOCTYPE html><html lang=\"fa\" dir=\"rtl\"><head>"
             "<title>t</title></head><body>" + "content " * 40 +
             "</body></html>\n```")
GOOD_CSS = "```css\nbody { color: red; margin: 0; padding: 0; }\n```"
GOOD_JS = "```javascript\nconsole.log('ready for action');\n```"


class FakeAI:
    """Stands in for the model so tests never hit the network."""

    def __init__(self, config=None, fail_at=None):
        self.fail_at = fail_at
        self.calls = []

    def _maybe_fail(self, step):
        self.calls.append(step)
        if self.fail_at == step:
            raise AIError(f"fake failure at {step}")

    def classify(self, message):
        return "build"

    def decompose(self, message):
        self._maybe_fail("decompose")
        return {"project_name": "p", "theme": {},
                "sections": [{"id": "hero", "title": "H", "description": "d"}]}

    def generate_css(self, plan):
        self._maybe_fail("css")
        return GOOD_CSS

    def generate_js(self, plan):
        self._maybe_fail("js")
        return GOOD_JS

    def generate_homepage(self, message, plan):
        self._maybe_fail("html")
        return GOOD_HTML

    def edit(self, code, instruction):
        self._maybe_fail("edit")
        return GOOD_HTML

    def chat(self, message, history):
        return "hi there"


@pytest.fixture
def pipeline_factory(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    def make(fail_at=None):
        cfg = Config()
        cfg.data["api"] = {"url": "http://x/v1", "key": "k", "model": "m"}
        p = Pipeline(cfg)
        p.ai = FakeAI(fail_at=fail_at)
        return p

    return make


def test_successful_build_writes_all_three_files(pipeline_factory):
    p = pipeline_factory()
    result = p.process("یه سایت فروشگاهی بساز")
    assert result["status"] == "done"
    out = p.config.output_dir
    assert (out / "index.html").is_file()
    assert (out / "style.css").is_file()
    assert (out / "main.js").is_file()


def test_build_response_points_at_working_preview_path(pipeline_factory):
    p = pipeline_factory()
    result = p.process("یه سایت بساز")
    assert "/preview/index.html" in result["response"]


def test_generated_html_has_asset_links(pipeline_factory):
    p = pipeline_factory()
    p.process("یه سایت بساز")
    html = (p.config.output_dir / "index.html").read_text("utf-8")
    assert 'href="style.css"' in html
    assert 'src="main.js"' in html


@pytest.mark.parametrize("fail_at", ["css", "js", "html"])
def test_failed_build_preserves_previous_site(pipeline_factory, fail_at):
    """Regression: rmtree ran before generation, so a failure wiped the site."""
    p = pipeline_factory()
    p.process("یه سایت بساز")
    original = (p.config.output_dir / "index.html").read_text("utf-8")

    p2 = pipeline_factory(fail_at=fail_at)
    result = p2.process("یه سایت دیگه بساز")

    assert result["status"] == "error"
    assert (p2.config.output_dir / "index.html").read_text("utf-8") == original


def test_failure_reports_real_reason(pipeline_factory):
    p = pipeline_factory(fail_at="css")
    result = p.process("یه سایت بساز")
    assert "fake failure at css" in result["response"]


def test_no_leftover_staging_dirs(pipeline_factory, tmp_path):
    p = pipeline_factory(fail_at="html")
    p.process("یه سایت بساز")
    leftovers = list(Path(tempfile.gettempdir()).glob("lazarus-build-*"))
    assert leftovers == []


def test_edit_without_existing_site(pipeline_factory):
    p = pipeline_factory()
    p.ai.classify = lambda m: "edit"
    result = p.process("رنگ رو عوض کن")
    assert result["status"] == "error"


def test_edit_updates_existing_site(pipeline_factory):
    p = pipeline_factory()
    p.process("یه سایت بساز")
    p.ai.classify = lambda m: "edit"
    result = p.process("رنگ رو عوض کن")
    assert result["status"] == "done"
    assert "/preview/index.html" in result["response"]


def test_chat_path_does_not_touch_output(pipeline_factory):
    p = pipeline_factory()
    p.ai.classify = lambda m: "chat"
    result = p.process("سلام")
    assert result["status"] == "chat"
    assert result["files"] == []



