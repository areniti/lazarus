"""Plan-JSON extraction from reasoning-model responses."""
import pytest

from lazarus.modules.ai import AI


class DummyConfig:
    data = {"api": {"url": "http://x/v1", "key": "k", "model": "m"}}


@pytest.fixture
def ai():
    return AI(DummyConfig())


PLAN = ('{"project_name": "cafe", "sections": ['
        '{"id": "hero", "title": "Hero", "description": "d"},'
        '{"id": "menu", "title": "Menu", "description": "d"}]}')


def test_plain_json(ai):
    assert ai._parse_json(PLAN)["project_name"] == "cafe"


def test_fenced_json(ai):
    assert ai._parse_json(f"```json\n{PLAN}\n```")["project_name"] == "cafe"


def test_json_after_reasoning_prose(ai):
    """Regression: reasoning text contains braces, so grabbing the first '{'
    picked up a fragment instead of the real plan."""
    raw = ('First, the user asked in Persian. I should use {curly braces} in '
           'my notes and maybe a shape like {"foo": 1}. Now the answer:\n\n'
           + PLAN)
    parsed = ai._parse_json(raw)
    assert parsed is not None
    assert parsed["project_name"] == "cafe"
    assert len(parsed["sections"]) == 2


def test_prefers_object_with_sections(ai):
    raw = '{"unrelated": {"a": 1}}\n' + PLAN
    assert ai._parse_json(raw)["project_name"] == "cafe"


def test_truncated_json_returns_none_not_garbage(ai):
    raw = 'reasoning...\n{"project_name": "cafe", "sections": [{"id": "'
    assert ai._parse_json(raw) is None


def test_no_json_at_all(ai):
    assert ai._parse_json("I cannot do that.") is None
    assert ai._parse_json("") is None
    assert ai._parse_json(None) is None


def test_trailing_prose_after_json(ai):
    assert ai._parse_json(PLAN + "\n\nHope that helps!")["project_name"] == "cafe"


# ===== section cleaning =====

def test_clean_sections_generates_missing_ids(ai):
    out = ai._clean_sections([{"title": "A", "description": "d"}])
    assert out[0]["id"] == "section1"


def test_clean_sections_sanitizes_ids(ai):
    out = ai._clean_sections([{"id": "my section!", "title": "A", "description": "d"}])
    assert out[0]["id"] == "mysection"


def test_clean_sections_dedupes_ids(ai):
    out = ai._clean_sections([
        {"id": "hero", "title": "A", "description": "d"},
        {"id": "hero", "title": "B", "description": "d"},
    ])
    assert out[0]["id"] != out[1]["id"]


def test_clean_sections_drops_empty(ai):
    out = ai._clean_sections([{"id": "x"}, {"id": "y", "title": "Real"}])
    assert len(out) == 1
    assert out[0]["title"] == "Real"


def test_clean_sections_caps_at_six(ai):
    many = [{"id": f"s{i}", "title": f"T{i}", "description": "d"} for i in range(20)]
    assert len(ai._clean_sections(many)) == 6


def test_clean_sections_handles_junk(ai):
    assert ai._clean_sections("not a list") == []
    assert ai._clean_sections([None, "x", 5]) == []
