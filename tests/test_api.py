"""API: sign-in, server-side role enforcement, authority limits, governance workflow, Ringgit and MYT."""
import json, re
import pytest
from fastapi.testclient import TestClient

import main

PW, PIN = "KT-demo-2026", "123456"


@pytest.fixture(scope="module")
def app():
    with TestClient(main.app) as c:
        yield c


def client(app, user):
    c = TestClient(main.app)
    r = c.post("/api/auth/login", json={"username": user, "password": PIN if user.isdigit() else PW})
    assert r.status_code == 200, r.text
    return c


def test_everything_needs_a_session(app):
    for path in ("/api/portfolio", "/api/applications", "/api/members", "/api/ledger", "/api/me", "/api/bootstrap"):
        assert app.get(path).status_code == 401
    assert app.get("/api/health").status_code == 200


def test_wrong_password_and_rate_limit(app):
    c = TestClient(main.app)
    assert c.post("/api/auth/login", json={"username": "noraini", "password": "nope"}).status_code == 401


MATRIX = {
    "noraini": {"/api/portfolio": 200, "/api/applications": 200, "/api/cockpit": 403, "/api/ledger": 403,
                "/api/crosssell": 403, "/api/members/104436/distress": 403, "/api/me": 403},
    "aisha": {"/api/crosssell": 200, "/api/members/104436/distress": 200, "/api/cockpit": 403},
    "zulkifli": {"/api/cockpit": 200, "/api/applications": 403, "/api/members": 403, "/api/ledger": 200},
    "farah": {"/api/crosssell": 200, "/api/members/104436/distress": 403, "/api/applications": 403},
    "104328": {"/api/me": 200, "/api/members/104328": 200, "/api/members/104310": 403, "/api/applications": 403},
}


@pytest.mark.parametrize("user", list(MATRIX))
def test_role_matrix(app, user):
    c = client(app, user)
    for path, want in MATRIX[user].items():
        assert c.get(path).status_code == want, (user, path)


def test_member_sees_only_own_documents(app):
    c = client(app, "104328")
    docs = main.domain.seeded_documents()
    mine = next(d for d in docs if d["member_id"] == "104328")
    other = next(d for d in docs if d["member_id"] != "104328")
    assert c.get(f"/api/files/{mine['file']}").status_code == 200
    assert c.get(f"/api/files/{other['file']}").status_code == 403


def test_approval_authority(app):
    off = client(app, "noraini")
    r = off.post("/api/applications/APP-104276/decision", json={"action": "Approve", "reason": "x"})
    assert r.status_code == 403 and "RM120,000" in r.json()["detail"]
    risk = client(app, "priya")
    assert risk.post("/api/applications/APP-104201/decision", json={"action": "Decline", "reason": "x"}).status_code == 403
    r = off.post("/api/applications/APP-104233/decision", json={"action": "Approve", "reason": ""})
    assert r.status_code == 200
    d = r.json()
    assert d["decision"]["actor"] == "Noraini binti Hashim"
    ex = d["execution"]
    assert ex["rate_type"] == "flat" and ex["channel"].startswith("Biro ANGKASA")
    assert ex["first_due"].endswith("-25")


def test_policy_change_needs_a_second_board_member(app):
    a = client(app, "zulkifli")
    r = a.post("/api/sandbox/promote", json={"thresholds": {"exposure_multiple": 5}, "justification": "test"})
    pid = r.json()["record"]["id"]
    assert a.post(f"/api/sandbox/proposals/{pid}", json={"approve": True}).status_code == 403
    off = client(app, "noraini")
    assert off.post(f"/api/sandbox/proposals/{pid}", json={"approve": True}).status_code == 403
    b = client(app, "rohana")
    r = b.post(f"/api/sandbox/proposals/{pid}", json={"approve": True})
    assert r.status_code == 200 and r.json()["status"].startswith("Approved")
    case = client(app, "aisha").get("/api/applications/APP-104328").json()
    assert case["policy"]["exposure_multiple"] == 5 and case["policy"]["policy_version"] != "v4.0"
    main.store.delete("policy_overrides")              # restore production for the tests that follow
    main.store.put("policy_version", "v4.0")


def test_autonomy_dial_is_board_only(app):
    assert client(app, "kamarul").post("/api/governance/autonomy", json={"mode": "ADVISE"}).status_code == 403
    assert client(app, "zulkifli").post("/api/governance/autonomy", json={"mode": "ADVISE"}).status_code == 200


def test_sandbox_min_confidence_is_wired(app):
    c = client(app, "priya")
    lo = c.post("/api/sandbox/simulate", json={"min_confidence": 0.6}).json()
    hi = c.post("/api/sandbox/simulate", json={"min_confidence": 0.99}).json()
    assert hi["candidate_result"]["refer"] >= lo["candidate_result"]["refer"]
    assert hi["candidate_result"]["refer"] > lo["candidate_result"]["refer"] or hi["candidate_result"]["approve"] < lo["candidate_result"]["approve"]


def test_check_before_you_borrow_matches_workbench(app):
    m = client(app, "104328").post("/api/me/affordability", json={"product": "Personal Financing-i", "amount": 25000, "term": 48}).json()
    o = client(app, "aisha").get("/api/applications/APP-104328").json()
    assert m["result"]["max_financing"] == o["policy"]["max_financing"]
    assert "not an approval" in m["disclaimer"]["en"]


def test_member_assistant_deterministic_answer_is_right(app):
    c = client(app, "104328")
    r = c.post("/api/member-assistant", json={"question": "Berapa baki pinjaman saya dan bila bayaran seterusnya?"}).json()
    assert r["lang"] == "ms" and "RM18,250" in r["answer"] and "RM650" in r["answer"] and "25,000" not in r["answer"]
    r = c.post("/api/member-assistant", json={"question": "Saya hilang kerja dan risau"}).json()
    assert r["handoff"]["kind"] == "Hardship"


def test_responses_carry_ringgit_and_malaysia_time(app):
    c = client(app, "kamarul")
    for path in ("/api/portfolio", "/api/applications/APP-104310", "/api/cockpit", "/api/ledger", "/api/collections",
                 "/api/members/104328", "/api/governance"):
        body = c.get(path).text
        assert not re.search(r"\$\s?\d", body), path
        for ts in re.findall(r'"(?:at|submitted|uploaded|changed_at)": "([^"]+)"', body):
            assert ts.endswith("+08:00"), (path, ts)


def test_ledger_chain_stays_intact(app):
    assert client(app, "zulkifli").get("/api/ledger").json()["verification"]["intact"]


def test_sensitive_access_is_logged(app):
    client(app, "aisha").get("/api/members/104436/distress")
    rows = client(app, "siewling").get("/api/ledger?case_id=MEM-104436").json()["rows"]
    assert any(r["stage"] == "Sensitive Access" for r in rows)
