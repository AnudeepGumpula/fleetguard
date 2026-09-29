import os
import pytest
from fastapi.testclient import TestClient
from conftest import FakeClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    import store
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "t.db"))
    store.init()
    import server
    return TestClient(server.app)


BLOCKY = dict(action_class="destructive", severity=1.0, matches_ticket=0.3, injection=0.97)
ASKY = dict(action_class="bulk_change", severity=0.96, matches_ticket=0.24, injection=0.04)


def post(client, answers, tool="wipe_device", args=None):
    FakeClient.raise_error = None
    FakeClient.answers = answers
    return client.post("/v1/check", json={"tool": tool, "args": args or {"group": "Group 7"},
                                          "ticket": "wipe group 7", "requester_role": "teacher"})


def test_block_is_logged(client):
    r = post(client, BLOCKY).json()
    assert r["decision"] == "block" and r["status"] == "blocked"
    assert r["blast_radius"] == 48
    assert client.get(f"/v1/decisions/{r['id']}").json()["status"] == "blocked"


def test_blast_radius_from_inventory_not_agent(client):
    FakeClient.answers = ASKY
    r = client.post("/v1/check", json={"tool": "reset_password", "args": {"group": "Grade 6 Students"},
                                       "ticket": "a few kids", "devices_affected": 1}).json()
    assert r["blast_radius"] == 120


def test_ask_then_approve(client):
    r = post(client, ASKY, tool="reset_password", args={"group": "Grade 6 Students"}).json()
    assert r["status"] == "pending"
    pending = client.get("/v1/decisions", params={"status": "pending"}).json()
    assert [d["id"] for d in pending] == [r["id"]]
    done = client.post(f"/v1/decisions/{r['id']}/review", json={"action": "approve", "reviewer": "deep"}).json()
    assert done["status"] == "approved" and done["reviewer"] == "deep"
    # Can't review twice
    again = client.post(f"/v1/decisions/{r['id']}/review", json={"action": "deny", "reviewer": "x"})
    assert again.status_code == 409


def test_cannot_approve_a_block(client):
    r = post(client, BLOCKY).json()
    resp = client.post(f"/v1/decisions/{r['id']}/review", json={"action": "approve", "reviewer": "deep"})
    assert resp.status_code == 409


def test_api_key_enforced(client, monkeypatch):
    monkeypatch.setenv("FLEETGUARD_API_KEY", "secret")
    FakeClient.answers = ASKY
    body = {"tool": "lookup_asset", "args": {}, "ticket": "t"}
    assert client.post("/v1/check", json=body).status_code == 401
    assert client.post("/v1/check", json=body, headers={"X-API-Key": "secret"}).status_code == 200


def test_unknown_decision_404(client):
    assert client.get("/v1/decisions/nope").status_code == 404
