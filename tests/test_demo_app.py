"""The deliberately vulnerable demo app behaves as documented."""
import uuid

import pytest

import app as demo


@pytest.fixture()
def client():
    demo.app.config["TESTING"] = True
    with demo.app.test_client() as c:
        yield c


def _login(client, version, username):
    return client.post(f"/login/{version}", json={"username": username, "password": "wrongpass"})


def test_v1_same_body_for_known_and_unknown_user(client):
    a, b = _login(client, "v1", "alice"), _login(client, "v1", "notauser")
    assert a.status_code == b.status_code == 401
    assert a.data == b.data  # v1 leaks through timing only


def test_v2_body_is_longer_for_known_user(client):
    a, b = _login(client, "v2", "alice"), _login(client, "v2", "notauser")
    assert len(a.data) - len(b.data) == 158


def test_v3_is_byte_identical(client):
    assert _login(client, "v3", "alice").data == _login(client, "v3", "notauser").data


def test_signup_differs_for_registered_email(client):
    taken = client.post("/signup", json={"email": "alice@example.com", "password": "x"})
    fresh = client.post("/signup", json={"email": f"test+{uuid.uuid4().hex}@example.com", "password": "x"})
    assert taken.status_code == 409 and fresh.status_code == 201


def test_health_serves_json_to_scripts_and_html_to_browsers(client):
    j = client.get("/health", headers={"Accept": "*/*"})
    assert j.is_json and j.get_json()["status"] == "ok"
    assert j.headers["Access-Control-Allow-Origin"] == "*"
    h = client.get("/health", headers={"Accept": "text/html,application/xhtml+xml"})
    assert h.mimetype == "text/html"
