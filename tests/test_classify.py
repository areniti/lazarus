"""Intent classification tests — the old logic sent short requests to chat."""
import pytest

from lazarus.modules.ai import AI


class DummyConfig:
    data = {"api": {"url": "http://x/v1", "key": "k", "model": "m"}}


@pytest.fixture
def ai():
    return AI(DummyConfig())


@pytest.mark.parametrize("msg", [
    "سلام", "سلام!", "خوبی", "چطوری", "ممنون", "مرسی", "باشه",
    "hi", "hello", "thanks", "ok", "bye",
])
def test_greetings_are_chat(ai, msg):
    assert ai.classify(msg) == "chat"


@pytest.mark.parametrize("msg", [
    "یه سایت فروشگاهی بساز",
    "سایت بساز",
    "یه فروشگاه",
    "برام یه پورتفولیو درست کن",
    "build me a landing page",
    "create a blog website",
    "یه صفحه لندینگ برای کافه طراحی کن",
])
def test_build_requests_are_build(ai, msg):
    assert ai.classify(msg) == "build"


@pytest.mark.parametrize("msg", [
    "رنگ رو عوض کن",
    "هدر رو بزرگتر کن",
    "این بخش رو حذف کن",
    "یه دکمه اضافه کن",
    "change the color to blue",
    "remove the footer",
    "fix the navbar",
])
def test_edit_requests_are_edit(ai, msg):
    assert ai.classify(msg) == "edit"


def test_build_wins_over_edit_when_both_present(ai):
    # "یه سایت جدید بساز و رنگش رو عوض کن" is a build, not an edit.
    assert ai.classify("یه سایت جدید بساز و رنگش رو عوض کن") == "build"


def test_short_build_request_not_swallowed_as_chat(ai):
    """Regression: len(split()) <= 2 used to force everything into chat."""
    assert ai.classify("سایت بساز") == "build"
    assert ai.classify("یه فروشگاه") == "build"
