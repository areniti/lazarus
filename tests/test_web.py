"""Web tests: preview route, auth gating, path traversal, rate limit."""
import pytest

from lazarus.core.config import Config


@pytest.fixture
def app_ctx(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    cfg = Config()
    password = cfg.generated_password
    cfg.complete_setup("ali", "testpass123")

    out = cfg.output_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(
        "<!DOCTYPE html><html><body>GENERATED SITE</body></html>", "utf-8")
    (out / "style.css").write_text("body{color:red}", "utf-8")

    # A secret sitting outside the output dir — traversal must not reach it.
    (tmp_path / "secret.html").write_text("TOP SECRET", "utf-8")

    from lazarus.web.app import create_app
    app = create_app()
    app.config.update(TESTING=True)
    return app, cfg, password


@pytest.fixture
def client(app_ctx):
    app, _, _ = app_ctx
    return app.test_client()


@pytest.fixture
def auth_client(app_ctx):
    app, _, _ = app_ctx
    c = app.test_client()
    r = c.post("/admin/login", data={"username": "ali", "password": "testpass123"})
    assert r.status_code == 302
    return c


# ===== the reported bug =====

def test_preview_route_exists(client):
    """Regression: admin linked to /preview/... which had no route -> Not found."""
    r = client.get("/preview/index.html")
    assert r.status_code == 200
    assert b"GENERATED SITE" in r.data


def test_admin_view_link_actually_resolves(auth_client):
    page = auth_client.get("/admin").get_data(as_text=True)
    assert "/preview/index.html" in page
    assert auth_client.get("/preview/index.html").status_code == 200


def test_preview_serves_css_with_right_type(client):
    r = client.get("/preview/style.css")
    assert r.status_code == 200
    assert "text/css" in r.headers["Content-Type"]


def test_preview_missing_file_404(client):
    assert client.get("/preview/nope.html").status_code == 404


# ===== path traversal =====

@pytest.mark.parametrize("attack", [
    "../secret.html",
    "../../secret.html",
    "..%2f..%2fsecret.html",
    "foo/../../secret.html",
])
def test_traversal_blocked(client, attack):
    for prefix in ("/preview/", "/"):
        r = client.get(prefix + attack)
        assert r.status_code == 404, f"{prefix}{attack} leaked"
        assert b"TOP SECRET" not in r.data


def test_disallowed_extension_blocked(client):
    assert client.get("/../.lazarus/config.json").status_code == 404
    assert client.get("/preview/anything.exe").status_code == 404


# ===== auth =====

@pytest.mark.parametrize("path", [
    "/admin", "/admin/chat", "/admin/settings", "/admin/settings/api",
])
def test_admin_pages_require_login(client, path):
    r = client.get(path)
    assert r.status_code == 302
    assert "/admin/login" in r.headers["Location"]


@pytest.mark.parametrize("path", [
    "/api/chat", "/api/save-password", "/api/save-api", "/api/add-model",
])
def test_api_post_requires_login(client, path):
    assert client.post(path, json={}).status_code == 401


def test_api_get_requires_login(client):
    assert client.get("/api/chat-history").status_code == 401
    assert client.get("/api/models-list").status_code == 401


def test_login_with_wrong_password_fails(client):
    r = client.get("/admin")
    assert r.status_code == 302
    r = client.post("/admin/login", data={"username": "ali", "password": "nope"})
    assert r.status_code == 200
    assert client.get("/admin").status_code == 302


def test_logout_clears_session(auth_client):
    assert auth_client.get("/admin").status_code == 200
    auth_client.get("/logout")
    assert auth_client.get("/admin").status_code == 302


def test_login_rate_limited(client):
    codes = [client.post("/admin/login",
                         data={"username": "ali", "password": "bad"}).status_code
             for _ in range(12)]
    assert 429 in codes


# ===== secret leakage =====

def test_admin_page_leaks_no_secrets(auth_client, app_ctx):
    _, cfg, _ = app_ctx
    cfg.data["api"]["key"] = "sk-super-secret-key"
    cfg.save()
    for path in ("/admin", "/admin/settings", "/admin/chat"):
        body = auth_client.get(path).get_data(as_text=True)
        assert cfg.data["password_hash"] not in body
        assert cfg.data["secret_key"] not in body


def test_secret_key_not_hardcoded(app_ctx):
    app, cfg, _ = app_ctx
    assert app.secret_key == cfg.data["secret_key"]
    assert app.secret_key != "42f161997178fe6461f6c1f9adff5571"


# ===== chat guard =====

def test_chat_without_api_configured_returns_message(auth_client):
    r = auth_client.post("/api/chat", json={"message": "یه سایت بساز"})
    assert r.status_code == 200
    assert r.get_json()["status"] == "error"


def test_chat_empty_message(auth_client):
    assert auth_client.post("/api/chat", json={"message": "  "}).status_code == 400


# ===== public site =====

def test_root_serves_generated_site(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"GENERATED SITE" in r.data
