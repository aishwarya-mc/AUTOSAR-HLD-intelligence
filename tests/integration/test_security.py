import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

KEYS = "adm:admin:alice,rev:reviewer:bob:projA,view:viewer:carol:projA|projB,other:viewer:dave:projB"


@pytest.fixture(scope="module")
def client():
    settings = get_settings()
    settings.auth_enabled, settings.api_keys = True, KEYS
    yield TestClient(app)
    settings.auth_enabled, settings.api_keys = False, ""


def h(key):
    return {"X-API-Key": key}


@pytest.fixture(scope="module")
def doc_a(client):
    r = client.post("/documents/sample", params={"project": "projA"}, headers=h("rev"))
    assert r.status_code == 201
    return r.json()["document_id"]


def test_health_is_public(client):
    assert client.get("/health").status_code == 200


def test_missing_or_bad_key_rejected(client):
    assert client.get("/documents").status_code == 401
    assert client.get("/documents", headers=h("nope")).status_code == 401


def test_viewer_cannot_upload(client):
    assert client.post("/documents/sample", headers=h("view")).status_code == 403


def test_reviewer_cannot_use_other_project(client):
    r = client.post("/documents/sample", params={"project": "projB"}, headers=h("rev"))
    assert r.status_code == 403


def test_project_isolation(client, doc_a):
    assert doc_a in [d["document_id"] for d in client.get("/documents", headers=h("view")).json()]
    assert client.get("/documents", headers=h("other")).json() == []
    assert client.get(f"/architecture/{doc_a}/model", headers=h("other")).status_code == 403
    q = {"question": "Which component provides IDoorStatus?", "document_id": doc_a}
    assert client.post("/queries", json=q, headers=h("other")).status_code == 403
    assert client.post("/queries", json=q, headers=h("view")).status_code == 200


def test_review_requires_reviewer_and_records_identity(client, doc_a):
    with open("data/sample/sample_hld_v2.pdf", "rb") as f:
        r = client.post("/documents", files={"file": ("v2.pdf", f, "application/pdf")},
                        data={"project": "projA", "version": "v2"}, headers=h("rev"))
    v2 = r.json()["document_id"]
    fid = client.get(f"/validation/{v2}", headers=h("view")).json()["findings"][0]["finding_id"]
    body = {"finding_id": fid, "status": "accepted", "reviewer": "spoofed"}
    assert client.post(f"/validation/{v2}/review", json=body, headers=h("view")).status_code == 403
    assert client.post(f"/validation/{v2}/review", json=body, headers=h("rev")).status_code == 200
    first = client.get(f"/validation/{v2}", headers=h("view")).json()["findings"][0]
    assert first["review"]["reviewer"] == "bob"  # taken from the key, not the request body


def test_delete_is_admin_only(client, doc_a):
    assert client.delete(f"/documents/{doc_a}", headers=h("rev")).status_code == 403


def test_audit_log(client, doc_a):
    assert client.get("/audit", headers=h("rev")).status_code == 403
    entries = client.get("/audit", headers=h("adm")).json()
    actions = {(e["user"], e["action"]) for e in entries}
    assert ("bob", "load_sample") in actions and ("carol", "query") in actions
    assert any(e["action"] == "review" and e["user"] == "bob" for e in entries)


def test_component_report(client, doc_a):
    text = client.get(f"/reports/{doc_a}/component/WindowControl", headers=h("view")).text
    assert "Component report: WindowControl" in text and "IVehicleState" in text
    assert "Cited pages" in text
    assert client.get(f"/reports/{doc_a}/component/Nope", headers=h("view")).status_code == 400
