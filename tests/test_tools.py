"""Tools tests: extraction, asset injection, path safety."""
import pytest

from lazarus.modules.tools import Tools


@pytest.fixture
def tools(tmp_path):
    return Tools(tmp_path / "output")


# ===== HTML extraction =====

def test_extract_html_fenced(tools):
    resp = "Here you go:\n```html\n<!DOCTYPE html><html><body>hi</body></html>\n```\nDone!"
    code = tools.extract_html(resp)
    assert code.startswith("<!DOCTYPE html>")
    assert code.endswith("</html>")
    assert "Here you go" not in code
    assert "Done!" not in code


def test_extract_html_unclosed_fence(tools):
    resp = "```html\n<!DOCTYPE html><html><body>x</body></html>"
    assert tools.extract_html(resp).endswith("</html>")


def test_extract_html_bare(tools):
    resp = "<!DOCTYPE html>\n<html><body>bare</body></html>"
    assert tools.extract_html(resp) == resp


def test_extract_html_strips_prose_before_doctype(tools):
    resp = "Sure! Here is the page.\n<!DOCTYPE html><html><body>y</body></html>"
    assert tools.extract_html(resp).startswith("<!DOCTYPE")


def test_extract_html_rejects_non_html(tools):
    assert tools.extract_html("I cannot help with that.") is None
    assert tools.extract_html("") is None
    assert tools.extract_html(None) is None


# ===== CSS / JS extraction =====

def test_extract_css_fenced(tools):
    assert "color: red" in tools.extract_css("```css\nbody { color: red; }\n```")


def test_extract_css_from_style_tag(tools):
    assert "margin: 0" in tools.extract_css("<style>body { margin: 0; padding: 2px; }</style>")


def test_extract_css_rejects_junk(tools):
    assert tools.extract_css("no css at all here") is None


def test_extract_js_fenced(tools):
    assert "hello" in tools.extract_js("```javascript\nconsole.log('hello world');\n```")


def test_extract_js_short_lang_tag(tools):
    assert "hello" in tools.extract_js("```js\nconsole.log('hello world');\n```")


def test_extract_js_rejects_junk(tools):
    assert tools.extract_js("nothing") is None


# ===== asset injection =====

def test_ensure_assets_injects_everything(tools):
    html = "<!DOCTYPE html><html><head><title>t</title></head><body>x</body></html>"
    out = tools.ensure_assets(html)
    assert 'href="style.css"' in out
    assert 'src="main.js"' in out
    assert "fonts.googleapis.com" in out


def test_ensure_assets_is_idempotent(tools):
    html = ('<!DOCTYPE html><html><head><link rel="stylesheet" href="style.css">'
            '</head><body><script src="main.js"></script></body></html>')
    once = tools.ensure_assets(html)
    twice = tools.ensure_assets(once)
    assert once == twice
    assert once.count("style.css") == 1
    assert once.count("main.js") == 1


def test_ensure_assets_closes_tags(tools):
    out = tools.ensure_assets("<!DOCTYPE html><html><head></head><body>x")
    assert out.rstrip().endswith("</html>")
    assert "</body>" in out


# ===== validation =====

def test_html_validate_text(tools):
    good = "<!DOCTYPE html><html><body>" + "x" * 300 + "</body></html>"
    assert tools.html_validate_text(good) == "VALID"
    assert "Missing <!DOCTYPE>" in tools.html_validate_text("<html><body>x</body></html>")


# ===== path safety =====

def test_file_write_and_read_roundtrip(tools):
    assert tools.file_write("a/b.html", "content").startswith("OK")
    assert tools.file_read("a/b.html") == "content"


def test_file_write_refuses_traversal(tools):
    assert tools.file_write("../../escaped.html", "bad").startswith("ERROR")


def test_file_read_missing(tools):
    assert tools.file_read("nope.html").startswith("ERROR")
