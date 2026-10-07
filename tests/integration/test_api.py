from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "sample"


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def v1(client):
    return client.post("/documents/sample").json()["document_id"]


@pytest.fixture(scope="module")
def v2(client):
    with open(SAMPLES / "sample_hld_v2.pdf", "rb") as f:
        r = client.post("/documents", files={"file": ("sample_hld_v2.pdf", f, "application/pdf")},
                        data={"version": "v2"})
    assert r.status_code == 201
    return r.json()["document_id"]


def test_health(client):
    assert client.get("/health").json()["status"] == "healthy"


def test_rejects_non_pdf(client):
    r = client.post("/documents", files={"file": ("a.txt", b"hello", "text/plain")})
    assert r.status_code == 400


def test_rejects_fake_pdf(client):
    r = client.post("/documents", files={"file": ("a.pdf", b"not a pdf", "application/pdf")})
    assert r.status_code == 400


def test_unknown_document_is_400(client):
    assert client.get("/documents/nope").status_code == 400


def test_entities_extracted(client, v1):
    ents = client.get(f"/architecture/{v1}/entities").json()
    kinds = {e["entity_type"] for e in ents}
    assert kinds == {"component", "interface", "port", "signal", "dependency", "functional_flow"}
    assert all(e["evidence"] for e in ents)


def test_clean_hld_has_no_findings(client, v1):
    assert client.get(f"/validation/{v1}").json()["findings"] == []


def test_seeded_defects_detected(client, v2):
    rules = {f["rule_id"] for f in client.get(f"/validation/{v2}").json()["findings"]}
    assert {"V003", "V005"} <= rules


def test_review_workflow(client, v2):
    fid = client.get(f"/validation/{v2}").json()["findings"][0]["finding_id"]
    r = client.post(f"/validation/{v2}/review",
                    json={"finding_id": fid, "status": "accepted", "reviewer": "qa"})
    assert r.status_code == 200
    first = client.get(f"/validation/{v2}").json()["findings"][0]
    assert first["review"]["status"] == "accepted"


def test_grounded_answer_with_citation(client, v1):
    r = client.post("/queries", json={"question": "Which component provides IDoorStatus?",
                                      "document_id": v1}).json()
    assert r["grounded"] and "DoorControl provides interface IDoorStatus" in r["answer"]
    assert r["citations"] and r["citations"][0]["page_number"]


def test_unanswerable_question_not_hallucinated(client, v1):
    r = client.post("/queries", json={"question": "What is the maximum engine torque?",
                                      "document_id": v1}).json()
    assert r["grounded"] is False and r["citations"] == []


def test_impact_analysis(client, v1):
    r = client.get(f"/architecture/{v1}/impact/IDoorStatus").json()
    names = {i["name"] for i in r["impacted"]}
    assert {"DoorControl", "BodyControlManager"} <= names


def test_comparison(client, v1, v2):
    r = client.get("/comparison", params={"old_document_id": v1, "new_document_id": v2}).json()
    assert r["categories"]["components"]["added"][0]["name"] == "ClimateControl"
    assert r["categories"]["signals"]["modified"][0]["changes"]["data_type"]["new"] == "uint32"
    assert r["summary"]["total_changes"] > 0


def test_report(client, v1, v2):
    text = client.get(f"/reports/{v2}", params={"compare_with": v1}).text
    assert "Validation Findings" in text and "Revision Comparison" in text


def test_exports(client, v1):
    data = client.get(f"/export/{v1}.json").json()
    assert {"document", "inventory", "entities", "relationships", "findings"} <= set(data)
    csv_text = client.get(f"/export/{v1}/entities.csv").text
    assert csv_text.splitlines()[0].startswith("entity_type,name") and "DoorControl" in csv_text
    assert client.get(f"/export/{v1}/relationships.csv").status_code == 200
    assert client.get(f"/export/{v1}/bogus.csv").status_code == 400


def test_version_endpoint(client):
    data = client.get("/version").json()
    assert data["answerability_model"]["version"] and data["embedding_model"]
    assert "git_sha" in data and data["auth_enabled"] is False
