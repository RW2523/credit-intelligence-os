"""Credit Intelligence OS — API. Runs entirely on this machine."""
from __future__ import annotations
import os, sys, json, asyncio, datetime as dt, shutil, re
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import seed, store, domain, council, llm
from engines import lmi as lmi_engine, docs as docs_engine, policy as policy_engine
from engines.risk import MODEL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = os.path.join(ROOT, "demo_files")
UPLOADS = os.path.join(ROOT, "data", "uploads")
os.makedirs(UPLOADS, exist_ok=True)

app = FastAPI(title="Credit Intelligence OS")
store.init()

ROLES = {
    "officer":     dict(name="Sarah Kim", role="Credit Officer", initials="SK", authority=30000,
                        views=["overview", "applications", "intake", "workbench", "documents", "members", "assistant"]),
    "senior":      dict(name="Aisha Rahman", role="Senior Officer", initials="AR", authority=100000,
                        views=["overview", "applications", "workbench", "documents", "members", "early-warning", "assistant"]),
    "collections": dict(name="Marco Diaz", role="Collections Officer", initials="MD", authority=0,
                        views=["overview", "early-warning", "collections", "members", "assistant"]),
    "risk":        dict(name="Priya Nair", role="Risk Manager", initials="PN", authority=0,
                        views=["overview", "governance", "sandbox", "applications", "early-warning"]),
    "compliance":  dict(name="Tomas Vega", role="Compliance Officer", initials="TV", authority=0,
                        views=["overview", "ledger", "governance", "applications"]),
    "manager":     dict(name="Grace Lim", role="Branch Manager", initials="GL", authority=250000,
                        views=["overview", "cockpit", "applications", "collections", "sandbox", "governance"]),
    "board":       dict(name="R. Watson", role="Board / Governance", initials="RW", authority=0,
                        views=["cockpit", "sandbox", "governance", "ledger"]),
    "member":      dict(name="David Carter", role="Member", initials="DC", authority=0, member_id="104328",
                        views=["member-portal"]),
}


@app.on_event("startup")
async def _startup():
    await llm.probe()
    if not store.ledger_read(limit=1):
        for a in domain.applications():
            store.ledger_append(a["id"], "Application Received", "System",
                                f"{a['product']} of ${a['amount']:,} submitted via {a['channel']}",
                                {"application": a["id"], "member": a["member_id"], "amount": a["amount"]})


# ------------------------------------------------------------------ meta
@app.get("/api/bootstrap")
async def bootstrap():
    return {
        "roles": ROLES, "products": {k: v for k, v in seed.PRODUCTS.items()},
        "branches": seed.BRANCHES, "policies": seed.POLICY_LIBRARY,
        "llm": llm.status(), "autonomy": store.autonomy(),
        "model": {"risk": MODEL.version, "trained_on": MODEL.trained_on, "base_rate": MODEL.base_rate},
        "today": "2024-04-16",
    }


@app.get("/api/health")
async def health():
    s = await llm.probe()
    return {"ok": True, "llm": s, "ledger": store.ledger_verify()}


# ------------------------------------------------------------- portfolio
@app.get("/api/portfolio")
async def portfolio():
    return domain.portfolio()


@app.get("/api/applications")
async def list_applications(q: str = "", product: str = "", branch: str = "", risk: str = "",
                            status: str = "", officer: str = ""):
    rows = [domain.queue_row(a) for a in domain.applications()]
    def keep(r):
        if q and q.lower() not in f"{r['name']} {r['id']} {r['product']} {r['member_id']}".lower(): return False
        for f, k in ((product, "product"), (branch, "branch"), (risk, "risk"),
                     (status, "status"), (officer, "officer")):
            if f and f != "All" and r[k] != f: return False
        return True
    return {"rows": [r for r in rows if keep(r)],
            "facets": {"product": sorted({r["product"] for r in rows}),
                       "branch": sorted({r["branch"] for r in rows}),
                       "risk": sorted({r["risk"] for r in rows}),
                       "status": sorted({r["status"] for r in rows}),
                       "officer": sorted({r["officer"] for r in rows})}}


@app.get("/api/applications/{aid}")
async def get_application(aid: str):
    case = domain.build_case(aid)
    if not case:
        raise HTTPException(404, "case not found")
    case["ledger"] = store.ledger_read(aid, 60)
    case["comms"] = [c for c in seed.COMMS if c["member_id"] == case["application"]["member_id"]]
    return case


class Intake(BaseModel):
    member_id: str = ""
    applicant_name: str = ""
    product: str
    amount: float
    term: int
    purpose: str = ""
    branch: str = "Makati"
    existing_commitments: float = 0
    declared_income: float | None = None
    employer: str = ""
    employment: str = "Employed"
    guarantor: str | None = None
    channel: str = "Branch"


@app.post("/api/applications")
async def create_application(body: Intake):
    apps = domain.applications()
    n = 900 + len([a for a in apps if a["id"].startswith("APP-9")])
    aid = f"APP-9{n:05d}"[:12]
    mid = body.member_id or "104328"
    if mid not in domain.MEMBERS and body.declared_income:
        domain.MEMBERS[mid] = dict(domain.MEMBERS["104328"], id=mid, name=body.applicant_name or "New Applicant",
                                   initials="".join(w[0] for w in (body.applicant_name or "New Applicant").split()[:2]).upper(),
                                   declared_income=body.declared_income, employer=body.employer or "—",
                                   employment=body.employment, outstanding=0, prior_loans=0,
                                   since=dt.date(2024, 1, 5).isoformat(), reliability=85,
                                   savings=1500, share_capital=800, payments=[])
    elif body.declared_income and mid in domain.MEMBERS:
        domain.MEMBERS[mid] = dict(domain.MEMBERS[mid], declared_income=body.declared_income)
    now = dt.datetime.now().isoformat(timespec="seconds")
    a = dict(id=aid, member_id=mid, product=body.product, amount=body.amount, term=body.term,
             purpose=body.purpose, submitted=now, snapshot_at=now, branch=body.branch,
             status="Officer Review", officer="Sarah Kim", channel=body.channel,
             guarantor=body.guarantor, existing_commitments=body.existing_commitments,
             case_type="origination", applicant_name=body.applicant_name)
    apps.insert(0, a)
    domain.save_applications(apps)
    case = domain.build_case(aid)
    store.ledger_append(aid, "Application Received", "Intake",
                        f"{body.product} of ${body.amount:,.0f} submitted", {"application": a})
    store.ledger_append(aid, "Case Snapshot Frozen", "System",
                        f"Snapshot {case['snapshot']['hash']} frozen under policy {case['policy']['policy_version']}",
                        case["snapshot"])
    store.ledger_append(aid, "Policy Evaluation", "Policy Engine",
                        f"{case['policy']['result']} — DSR {case['policy']['dsr']}%", case["policy"]["gates"])
    store.ledger_append(aid, "Risk Evaluation", "Risk Model",
                        f"{case['risk']['grade']} — PD {case['risk']['pd']*100:.1f}%",
                        {"pd": case["risk"]["pd"], "reason_codes": case["risk"]["reason_codes"]})
    store.append_list("notifications", dict(kind="case", tone="blue", title="New application created",
                                            detail=f"{aid} — {body.product} ${body.amount:,.0f}",
                                            at=now, link=f"workbench:{aid}"))
    return {"id": aid, "case": case}


# -------------------------------------------------------------- documents
@app.get("/api/documents")
async def all_documents():
    return {"rows": domain.documents(), "pipeline": docs_engine.PIPELINE}


@app.get("/api/documents/{doc_id}")
async def one_document(doc_id: str):
    d = next((x for x in domain.documents() if x["id"] == doc_id), None)
    if not d:
        raise HTTPException(404, "document not found")
    return d


@app.get("/api/files/{name}")
async def serve_file(name: str):
    for base in (FILES, UPLOADS):
        p = os.path.join(base, os.path.basename(name))
        if os.path.exists(p):
            return FileResponse(p)
    raise HTTPException(404, "file not found")


@app.post("/api/applications/{aid}/documents")
async def upload(aid: str, file: UploadFile = File(...)):
    app_ = domain.app_by_id(aid)
    if not app_:
        raise HTTPException(404, "case not found")
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", file.filename)
    dest = os.path.join(UPLOADS, safe)
    with open(dest, "wb") as fh:
        shutil.copyfileobj(file.file, fh)
    doc_type, conf = docs_engine.classify(safe)
    ext = safe.rsplit(".", 1)[-1].lower()
    docs = domain.documents()
    did = f"DOC-{9000 + len(docs)}"
    size = os.path.getsize(dest)
    fields = [dict(k="File name", v=safe, c=100, bbox=[6, 8, 60, 5], page=1),
              dict(k="Classified as", v=doc_type, c=conf, bbox=[6, 18, 60, 5], page=1),
              dict(k="Size", v=f"{size/1024:.1f} KB", c=100, bbox=[6, 28, 40, 5], page=1),
              dict(k="Uploaded by", v="Officer", c=100, bbox=[6, 38, 40, 5], page=1)]
    if ext == "pdf":
        try:
            from pypdf import PdfReader
            r = PdfReader(dest)
            text = (r.pages[0].extract_text() or "")[:1200]
            for m in re.finditer(r"([A-Z][A-Za-z /()]{3,28})\s*[:\-]\s*([^\n]{2,40})", text):
                if len(fields) > 12: break
                fields.append(dict(k=m.group(1).strip(), v=m.group(2).strip(), c=88,
                                   bbox=[6, 48 + 8 * (len(fields) - 4), 62, 5], page=1))
        except Exception:                                           # noqa: BLE001
            pass
    doc = dict(id=did, app_id=aid, member_id=app_["member_id"], file=safe, label=safe,
               doc_type=doc_type, status="Verified" if conf >= 90 else "Needs Review",
               confidence=conf, uploaded=dt.datetime.now().isoformat(timespec="seconds"),
               pages=1, uploaded_file=True,
               forensics=dict(tampering=False, font_consistency=97, metadata_ok=True,
                              duplicate_hash=False, producer="Uploaded"),
               fields=fields)
    docs.append(doc)
    domain.save_documents(docs)
    store.ledger_append(aid, "Evidence Registered", "Document Service",
                        f"{doc_type} '{safe}' classified at {conf}% confidence", {"doc": did, "hash": docs_engine.sha(safe)})
    return {"document": doc, "pipeline": docs_engine.PIPELINE}


# ---------------------------------------------------------------- council
def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@app.get("/api/applications/{aid}/council/stream")
async def council_stream(aid: str):
    case = domain.build_case(aid)
    if not case:
        raise HTTPException(404, "case not found")
    q: asyncio.Queue = asyncio.Queue()

    async def emit(ev, data):
        await q.put((ev, data))

    async def runner():
        try:
            res = await council.run(case, emit)
            store.put(f"council:{aid}", res)
            s = res["summary"]
            store.ledger_append(aid, "Agent Deliberation", "AI Credit Council",
                                f"{len(res['positions'])} specialist positions, {s['dissent_count']} dissenting",
                                {"positions": [{k: p[k] for k in ("name", "stance", "headline", "confidence", "evidence")}
                                               for p in res["positions"]],
                                 "challenger": {k: res["challenger"].get(k) for k in ("stance", "headline", "ask")}})
            store.ledger_append(aid, "Recommendation Synthesized", "Synthesizer",
                                f"{s['recommendation']} at {s['confidence']} confidence "
                                f"(disagreement {s['disagreement']})", s)
            case2 = domain.build_case(aid)
            await q.put(("routing", case2["routing"]))
        except Exception as e:                                       # noqa: BLE001
            await q.put(("error", {"message": str(e)}))
        finally:
            await q.put((None, None))

    async def gen():
        task = asyncio.create_task(runner())
        while True:
            ev, data = await q.get()
            if ev is None:
                break
            yield _sse(ev, data)
        await task
        yield _sse("done", {"ok": True})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# --------------------------------------------------------------- decision
class Decision(BaseModel):
    action: str                      # Approve | Decline | Request Information | Escalate | Override
    reason: str = ""
    actor: str = "Sarah Kim"
    role: str = "Credit Officer"
    conditions: list[str] = []


@app.post("/api/applications/{aid}/decision")
async def decide(aid: str, body: Decision):
    case = domain.build_case(aid)
    if not case:
        raise HTTPException(404, "case not found")
    rec = (case.get("council") or {}).get("summary", {}).get("recommendation", "Not run")
    override = rec not in ("Not run", body.action.upper()) and body.action in ("Approve", "Decline")
    if override and not body.reason.strip():
        raise HTTPException(400, "An override of the AI recommendation requires a documented reason.")
    now = dt.datetime.now().isoformat(timespec="seconds")
    record = dict(action=body.action, reason=body.reason, actor=body.actor, role=body.role,
                  at=now, ai_recommendation=rec, override=override,
                  conditions=body.conditions or (case.get("council") or {}).get("summary", {}).get("conditions", []),
                  authority=case["policy"]["authority_required"], snapshot=case["snapshot"]["hash"])
    store.put(f"decision:{aid}", record)

    apps = domain.applications()
    for a in apps:
        if a["id"] == aid:
            a["status"] = {"Approve": "Approved", "Decline": "Declined",
                           "Request Information": "Documents Pending",
                           "Escalate": "Escalated"}.get(body.action, a["status"])
    domain.save_applications(apps)

    store.ledger_append(aid, "Human Decision", f"{body.actor} ({body.role})",
                        f"{body.action}" + (f" — OVERRIDE of AI '{rec}': {body.reason}" if override
                                            else (f" — {body.reason}" if body.reason else "")), record)
    execution = None
    if body.action == "Approve":
        token = store.ledger_append(aid, "Approval Token Issued", "Governance",
                                    f"Token issued for ${case['application']['amount']:,.0f} under {record['authority']} authority",
                                    {"amount": case["application"]["amount"], "authority": record["authority"]})
        execution = await _execute(aid, case, token["hash"])
    store.append_list("notifications", dict(kind="decision", tone="green" if body.action == "Approve" else "blue",
                                            title=f"{aid} {body.action.lower()}d by {body.actor}",
                                            detail=body.reason or rec, at=now, link=f"workbench:{aid}"))
    return {"decision": record, "execution": execution, "ledger": store.ledger_read(aid, 60)}


async def _execute(aid: str, case: dict, token: str) -> dict:
    """Execution service — the only privileged writer to the core system."""
    p = case["policy"]
    acct = "LN-" + aid.split("-")[1]
    first = dt.date(2024, 5, 5)
    schedule = []
    bal = case["application"]["amount"]
    r = p["rate"] / 100 / 12
    for i in range(min(6, case["application"]["term"])):
        interest = round(bal * r, 2)
        principal = round(p["instalment"] - interest, 2)
        bal = round(bal - principal, 2)
        schedule.append(dict(n=i + 1, due=(first.replace(day=5) + dt.timedelta(days=30 * i)).isoformat(),
                             amount=p["instalment"], principal=principal, interest=interest, balance=bal))
    result = dict(account=acct, token=token, idempotency_key=f"{aid}:{token[:12]}",
                  instalment=p["instalment"], rate=p["rate"], term=case["application"]["term"],
                  first_due=schedule[0]["due"], schedule=schedule,
                  steps=[dict(name="Approval token validated", ok=True),
                         dict(name="Core financing record created", ok=True),
                         dict(name="Payment schedule generated", ok=True),
                         dict(name="Salary deduction mandate registered", ok=True),
                         dict(name="Accounting entries posted", ok=True),
                         dict(name="Member notified", ok=True),
                         dict(name="Payment monitoring started", ok=True)])
    store.put(f"execution:{aid}", result)
    store.ledger_append(aid, "Core Execution", "Execution Service",
                        f"Facility {acct} activated; first instalment ${p['instalment']:,.0f} due {schedule[0]['due']}",
                        {k: result[k] for k in ("account", "token", "idempotency_key", "instalment", "first_due")})
    store.ledger_append(aid, "Monitoring Started", "LMI Service",
                        "Longitudinal baseline initialised for this facility", {"account": acct})
    return result


@app.get("/api/applications/{aid}/execution")
async def execution(aid: str):
    return store.get(f"execution:{aid}") or {}


# ----------------------------------------------------------------- member
@app.get("/api/members")
async def members():
    out = []
    for m in domain.MEMBERS.values():
        a = lmi_engine.analyse(m)
        out.append(dict({k: v for k, v in m.items() if k != "payments"},
                        lmi_state=a["state"]["state"], p30=a["forecast"]["p_late_30d"]))
    return {"rows": out}


@app.get("/api/members/{mid}")
async def member(mid: str):
    m = domain.MEMBERS.get(mid)
    if not m:
        raise HTTPException(404, "member not found")
    apps = [domain.queue_row(a) for a in domain.applications() if a["member_id"] == mid]
    return {"member": {k: v for k, v in m.items() if k != "payments"},
            "payments": m["payments"], "lmi": lmi_engine.analyse(m),
            "applications": apps,
            "collections": [c for c in seed.COLLECTIONS if c["member_id"] == mid],
            "comms": [c for c in seed.COMMS if c["member_id"] == mid],
            "history": domain.history_features(m),
            "ledger": store.ledger_read(limit=200)}


@app.get("/api/early-warning")
async def early_warning():
    rows = []
    for m in domain.MEMBERS.values():
        a = lmi_engine.analyse(m)
        a["member"] = {k: v for k, v in m.items() if k != "payments"}
        rows.append(a)
    order = {"AT_RISK": 0, "ELEVATED": 1, "WATCH": 2, "RECOVERY": 3, "STABLE": 4}
    rows.sort(key=lambda a: (order[a["state"]["state"]], -a["forecast"]["p_late_30d"]))
    return {"rows": rows, "states": lmi_engine.STATES}


# ------------------------------------------------------------- collections
@app.get("/api/collections")
async def collections():
    rows = []
    for c in seed.COLLECTIONS:
        m = domain.MEMBERS[c["member_id"]]
        a = lmi_engine.analyse(m)
        ev = round(c["balance"] * c["response"] / 100 * (0.9 if c["dpd"] < 60 else 0.6), 0)
        rows.append(dict(c, name=m["name"], initials=m["initials"], branch=m["branch"],
                         phone=m["phone"], email=m["email"], state=a["state"]["state"],
                         why_now=a["why_now"], p30=a["forecast"]["p_late_30d"],
                         recovery=a["forecast"]["recovery_likelihood"], expected_value=ev,
                         next_best_action=_nba(c, m, a),
                         comms=[x for x in seed.COMMS if x["member_id"] == c["member_id"]]))
    rows.sort(key=lambda r: -r["expected_value"])
    return {"rows": rows, "total_ev": sum(r["expected_value"] for r in rows),
            "total_balance": sum(r["balance"] for r in rows)}


def _nba(c, m, a) -> dict:
    if c["dpd"] == 0:
        return dict(action="Proactive supportive call", channel="Phone", window="10:00–12:00",
                    objective="Understand the change in circumstances and offer options before arrears arise",
                    reason=f"{a['forecast']['p_late_30d']*100:.0f}% 30-day late-payment probability with no arrears yet — "
                           "the least intrusive effective intervention (POL-007).")
    if c["dpd"] >= 90:
        return dict(action="Structured call + written hardship offer", channel="Phone + Email", window="14:00–17:00",
                    objective="Agree an affordable arrangement and stop further deterioration",
                    reason=f"{c['dpd']} days past due with a {c['response']}% modelled contact-response rate.")
    if c["promise"]:
        return dict(action="Confirm promise to pay", channel="SMS", window="09:00–11:00",
                    objective=f"Confirm the ${300} payment promised for {c['promise']}",
                    reason="An open promise to pay is the highest-yield follow-up available today.")
    return dict(action="Reminder with payment link", channel="SMS", window="09:00–11:00",
                objective="Restore the payment without escalation",
                reason=f"Early-stage arrears ({c['dpd']} DPD) with a {c['response']}% response rate.")


class Outreach(BaseModel):
    member_id: str
    channel: str
    outcome: str = "Logged"
    note: str = ""
    actor: str = "Marco Diaz"


@app.post("/api/collections/outreach")
async def outreach(body: Outreach):
    m = domain.MEMBERS.get(body.member_id)
    entry = dict(member_id=body.member_id, type=body.channel.lower(), title=f"{body.channel} — {body.outcome}",
                 at=dt.datetime.now().isoformat(timespec="seconds"), text=body.note, outcome=body.outcome)
    seed.COMMS.insert(0, entry)
    store.ledger_append(f"MEM-{body.member_id}", "Intervention Logged", body.actor,
                        f"{body.channel} to {m['name'] if m else body.member_id}: {body.outcome}", entry)
    return {"ok": True, "entry": entry}


class Draft(BaseModel):
    member_id: str
    channel: str = "Email"
    intent: str = "supportive outreach"


@app.post("/api/collections/draft")
async def draft(body: Draft):
    m = domain.MEMBERS.get(body.member_id)
    if not m:
        raise HTTPException(404, "member not found")
    a = lmi_engine.analyse(m)
    c = next((x for x in seed.COLLECTIONS if x["member_id"] == body.member_id), None)
    fallback = {
        "subject": f"Checking in about your account, {m['name'].split()[0]}",
        "body": (f"Dear {m['name'].split()[0]},\n\nWe noticed a change in your recent payment pattern and wanted to "
                 f"check in before your next due date. Your record with the cooperative has been strong, and if "
                 f"something has changed we would rather help early than late.\n\nIf it would help, we can look at "
                 f"adjusting your schedule. Please reply to this message or call your branch and ask for the "
                 f"member support team.\n\nKind regards,\nMember Support"),
    }
    sysmsg = ("You draft short, respectful member communications for a credit cooperative. Never threaten, never "
              "state or imply a credit decision, never quote figures that are not given to you. Plain, warm, "
              "under 140 words. Reply as JSON with keys subject and body.")
    prompt = (f"Member: {m['name']}. Channel: {body.channel}. Intent: {body.intent}.\n"
              f"Situation: {a['why_now']}\nState: {a['state']['state']}. "
              f"{'Balance $%s, %s days past due.' % (c['balance'], c['dpd']) if c else 'No arrears.'}\n"
              f"Recommended approach: {a['intervention']['action']} — {a['intervention']['objective']}.\n"
              "Write the message.")
    out = await llm.json_call(sysmsg, prompt, fallback, temperature=0.4, num_predict=380)
    out["policy_note"] = "Draft only — requires officer approval before sending (notification service policy)."
    return out


# ------------------------------------------------------------------ ask AI
@app.post("/api/ask")
async def ask(req: Request):
    body = await req.json()
    question = (body.get("question") or "").strip()
    aid = body.get("application_id")
    case = domain.build_case(aid) if aid else None
    ctx = _case_context(case) if case else _portfolio_context()
    policies = "\n".join(f"[{p['id']} {p['version']}] {p['title']}: {p['text']}"
                         for p in _retrieve(question, seed.POLICY_LIBRARY))
    sysmsg = ("You are the Credit AI assistant inside a governed credit intelligence platform. Answer ONLY from the "
              "CONTEXT and POLICY sections. If the answer is not there, say what is missing and which tool or "
              "document would provide it. Never invent numbers. Never state a final credit decision — you support "
              "the officer, who decides. Be concise: 3-6 sentences, plain language.")
    prompt = f"CONTEXT\n{ctx}\n\nPOLICY\n{policies}\n\nQUESTION\n{question}\n\nANSWER:"

    async def gen():
        yield _sse("meta", {"grounded_in": [c["id"] for c in _retrieve(question, seed.POLICY_LIBRARY)],
                            "case": aid, "model": llm.status()["model"]})
        got = False
        try:
            async for tok in llm.stream(sysmsg, prompt, temperature=0.25, num_predict=420):
                got = True
                yield _sse("token", {"t": tok})
        except Exception:                                            # noqa: BLE001
            got = False
        if not got:
            yield _sse("token", {"t": _fallback_answer(question, case)})
        yield _sse("done", {"ok": True})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _retrieve(q: str, corpus: list[dict], k: int = 3) -> list[dict]:
    """Hybrid-ish retrieval: term overlap scoring over the policy corpus."""
    terms = {t for t in re.findall(r"[a-z]{3,}", q.lower())}
    syn = {"dti": "ratio", "dsr": "ratio", "afford": "affordability", "income": "income",
           "fraud": "fraud", "document": "document", "tenure": "tenure", "limit": "limit",
           "hardship": "hardship", "override": "authority", "autonomy": "autonomous",
           "risk": "verification", "missing": "evidence", "evidence": "evidence",
           "grade": "verification", "verif": "verification", "payslip": "income",
           "bank": "income", "decline": "authority", "approve": "authority",
           "collections": "hardship", "arrears": "hardship", "late": "hardship"}
    terms |= {v for k_, v in syn.items() if k_ in q.lower()}
    scored = []
    for p in corpus:
        text = (p["title"] + " " + p["text"]).lower()
        score = sum(3 if t in p["title"].lower() else 1 for t in terms if t in text)
        scored.append((score, p))
    scored.sort(key=lambda x: -x[0])
    return [p for s, p in scored[:k] if s > 0] or corpus[:2]


def _case_context(case: dict) -> str:
    p, r, f, d = case["policy"], case["risk"], case["fraud"], case["documents_summary"]
    lines = [
        f"Case {case['application']['id']} — {case['member']['name']}, {case['application']['product']} "
        f"${case['application']['amount']:,.0f} over {case['application']['term']} months for {case['application']['purpose']}.",
        f"Snapshot {case['snapshot']['hash']} frozen at {case['snapshot']['frozen_at']} under policy {p['policy_version']}.",
        f"Verified income ${p['income']['verified_annual']:,.0f} (declared ${p['income']['declared_annual']:,.0f}, "
        f"variance {p['income']['variance_pct']}%). Instalment ${p['instalment']:,.0f}. DSR {p['dsr']}% vs ceiling {p['dsr_ceiling']}%.",
        f"Policy result {p['result']}; failing gates: {', '.join(p['failures']) or 'none'}. "
        f"Authority required: {p['authority_required']}. Max financing ${p['max_financing']:,.0f}.",
        f"Risk: PD {r['pd']*100:.1f}% ({r['grade']}), score {r['score']}. Reason codes: {'; '.join(r['reason_codes']) or 'none'}.",
        f"Integrity: {f['level']} — {f['headline']}.",
        f"Documents: {d['verified']}/{d['required']} verified; missing {', '.join(d['missing']) or 'none'}.",
        f"Member: since {case['member']['since']}, {case['member']['prior_loans']} prior facilities, "
        f"{case['member']['reliability']}% reliability, savings ${case['member']['savings']:,}, "
        f"outstanding ${case['member']['outstanding']:,}.",
        f"Longitudinal state {case['lmi']['state']['state']}: {case['lmi']['why_now']}",
    ]
    for x in case["reconciliation"]["rows"]:
        lines.append(f"Reconciliation — {x['attribute']}: {x['result']} ({x['detail']}); values " +
                     ", ".join(f"{k}={v}" for k, v in x["values"].items() if v not in (None, "")))
    if case.get("council"):
        s = case["council"]["summary"]
        lines.append(f"Council recommendation {s['recommendation']} at {s['confidence']} confidence, "
                     f"disagreement {s['disagreement']}, decisive factor {s['decisive_factor']}.")
        for pos in case["council"]["positions"]:
            lines.append(f"{pos['name']}: {pos['stance']} — {pos['headline']}")
    if case.get("decision"):
        lines.append(f"Human decision: {case['decision']['action']} by {case['decision']['actor']} — {case['decision']['reason']}")
    return "\n".join(lines)


def _portfolio_context() -> str:
    p = domain.portfolio()
    k = p["kpis"]
    return (f"Portfolio: {k['pipeline']} live applications, ${k['exposure']:,.0f} exposure, "
            f"approval rate {k['approval_rate']}%, predicted delinquency {k['predicted_delinquency']}%, "
            f"{k['early_warnings']} members in early warning. Risk mix: {p['risk_mix']}. "
            f"Autonomy mode {p['autonomy']['mode']}, kill switch {'ON' if p['autonomy']['kill_switch'] else 'off'}.")


def _fallback_answer(q: str, case: dict | None) -> str:
    if not case:
        return _portfolio_context()
    return ("The local model is unavailable, so here are the grounded facts for this case:\n\n"
            + _case_context(case))


# ------------------------------------------------------- member assistant
HARDSHIP = ["lost my job", "laid off", "redundant", "can't pay", "cannot pay", "struggling",
            "hardship", "sick", "hospital", "worried", "unemployed", "reduce", "behind"]
COMPLAINT = ["complain", "unhappy", "unfair", "angry", "wrong charge", "dispute"]


@app.post("/api/member-assistant")
async def member_assistant(req: Request):
    body = await req.json()
    q = (body.get("question") or "").strip()
    mid = body.get("member_id", "104328")
    m = domain.MEMBERS.get(mid)
    if not m:
        raise HTTPException(404, "member not found")
    low = q.lower()
    hardship = any(w in low for w in HARDSHIP)
    complaint = any(w in low for w in COMPLAINT)
    apps = [domain.queue_row(a) for a in domain.applications() if a["member_id"] == mid]
    case = domain.build_case(apps[0]["id"]) if apps else None
    nxt = next((p for p in m["payments"][::-1]), None)
    facts = (f"Member {m['name']} (id {mid}). Outstanding balance ${m['outstanding']:,}. "
             f"Savings ${m['savings']:,}, share capital ${m['share_capital']:,}. "
             f"Next payment due 5th of next month, approximately $650, by {nxt['channel'] if nxt else 'salary deduction'}. "
             + (f"Open application {apps[0]['id']} — {apps[0]['product']} ${apps[0]['amount']:,.0f}, "
                f"status {apps[0]['status']}. " if apps else "No open application. ")
             + (f"Documents still needed: {', '.join(case['documents_summary']['missing'])}. "
                if case and case["documents_summary"]["missing"] else "All requested documents have been received. "))
    sysmsg = ("You are the member-facing assistant of a credit cooperative, talking to the authenticated member. "
              "Answer ONLY from FACTS. You must never state, imply or predict a credit decision, approval, "
              "decline, rate or limit. If the member signals hardship, complaint or bereavement, acknowledge it "
              "warmly and say a member support officer will be in touch — do not attempt to solve it. "
              "Two to four short sentences.")
    fallback_text = facts if not hardship else (
        "Thank you for telling me — that sounds stressful, and you have done the right thing by getting in touch "
        "early. I have raised a support task and a member support officer will contact you within one business day "
        "to look at the options available to you. Your account is not affected by this message.")
    out = {"answer": fallback_text}
    try:
        raw = await llm.generate(sysmsg, f"FACTS\n{facts}\n\nMEMBER SAYS\n{q}\n\nREPLY:",
                                 json_mode=False, temperature=0.3, num_predict=220)
        txt = re.sub(r"\[[^\]]{0,40}\]", "", raw).strip()          # drop model placeholders
        txt = re.sub(r"\n{3,}", "\n\n", txt)
        if txt:
            out["answer"] = txt
    except Exception:                                                # noqa: BLE001
        pass
    out["handoff"] = None
    if hardship or complaint:
        kind = "Hardship" if hardship else "Complaint"
        task = dict(kind=kind, member_id=mid, member=m["name"], at=dt.datetime.now().isoformat(timespec="seconds"),
                    queue="Member Support", sla="1 business day",
                    detail=q[:180], status="Open")
        store.append_list("support_tasks", task)
        store.ledger_append(f"MEM-{mid}", f"{kind} Signal Detected", "Member Assistant",
                            f"{kind} cue detected in member message; routed to Member Support", task)
        store.append_list("notifications", dict(kind="hardship", tone="amber",
                                                title=f"{kind} signal — {m['name']}",
                                                detail=q[:90], at=task["at"], link=f"member:{mid}"))
        out["handoff"] = task
    out["guardrail"] = "The assistant never states or implies a credit decision."
    return out


@app.get("/api/support-tasks")
async def support_tasks():
    return {"rows": store.get("support_tasks", [])}


# ---------------------------------------------------------------- sandbox
class Sim(BaseModel):
    dsr_ceiling: float = 40
    exposure_multiple: float = 4.0
    min_confidence: float = 0.88
    max_pd: float = 0.05


@app.post("/api/sandbox/simulate")
async def simulate(body: Sim):
    """Replay every historical snapshot under candidate thresholds."""
    base_rows, cand_rows = [], []
    for a in domain.applications():
        base = domain.build_case(a["id"])
        cand = domain.build_case(a["id"], {"dsr_ceiling": body.dsr_ceiling,
                                           "exposure_multiple": body.exposure_multiple})
        base_rows.append(base)
        cand_rows.append(cand)

    def outcome(case, min_conf, max_pd):
        if case["policy"]["result"] == "FAIL": return "Decline"
        if case["documents_summary"]["missing"]: return "Request Info"
        if case["risk"]["pd"] > max_pd * 3.5: return "Decline"
        return "Approve"

    def agg(rows, min_conf, max_pd):
        outs = [outcome(c, min_conf, max_pd) for c in rows]
        appr = [c for c, o in zip(rows, outs) if o == "Approve"]
        exposure = sum(c["application"]["amount"] for c in appr)
        pdw = sum(c["risk"]["pd"] * c["application"]["amount"] for c in appr) / max(1, exposure)
        return {"approve": outs.count("Approve"), "decline": outs.count("Decline"),
                "request": outs.count("Request Info"), "exposure": exposure,
                "predicted_delinquency": round(pdw * 100, 2),
                "approval_rate": round(outs.count("Approve") / len(outs) * 100, 1),
                "outcomes": outs}
    b = agg(base_rows, 0.88, 0.05)
    c = agg(cand_rows, body.min_confidence, body.max_pd)
    changed = [dict(id=base_rows[i]["application"]["id"], name=base_rows[i]["member"]["name"],
                    product=base_rows[i]["application"]["product"],
                    amount=base_rows[i]["application"]["amount"],
                    before=b["outcomes"][i], after=c["outcomes"][i],
                    dsr=cand_rows[i]["policy"]["dsr"])
               for i in range(len(base_rows)) if b["outcomes"][i] != c["outcomes"][i]]
    segments = {}
    for ch in changed:
        seg = "Business" if "Business" in ch["product"] else ("Secured" if ch["amount"] > 40000 else "Consumer")
        segments[seg] = segments.get(seg, 0) + 1
    return {"baseline": b, "candidate": c, "changed": changed, "segments": segments,
            "thresholds": body.model_dump(),
            "note": "Simulation replays frozen case snapshots. Nothing in production changes until a "
                    "governed approval is recorded."}


class Promote(BaseModel):
    thresholds: dict
    actor: str = "R. Watson"
    justification: str = ""


@app.post("/api/sandbox/promote")
async def promote(body: Promote):
    if not body.justification.strip():
        raise HTTPException(400, "A policy change requires a written justification.")
    rec = dict(thresholds=body.thresholds, actor=body.actor, justification=body.justification,
               at=dt.datetime.now().isoformat(timespec="seconds"), status="Pending Board Approval")
    store.append_list("policy_changes", rec)
    store.ledger_append("GOVERNANCE", "Policy Change Proposed", body.actor,
                        f"Proposed thresholds {body.thresholds}", rec)
    return {"ok": True, "record": rec, "note": "Recorded as pending. Production thresholds are unchanged."}


# ------------------------------------------------------------- governance
@app.get("/api/governance")
async def governance():
    apps = [domain.queue_row(a) for a in domain.applications()]
    councils = [store.get(f"council:{a['id']}") for a in domain.applications()]
    councils = [c for c in councils if c]
    decisions = [store.get(f"decision:{a['id']}") for a in domain.applications()]
    decisions = [d for d in decisions if d]
    overrides = [d for d in decisions if d.get("override")]
    unsupported = sum(c["grounding"]["unsupported"] for c in councils)
    rewrites = sum(c["grounding"].get("numeric_rewrites", 0) for c in councils)
    llm_pos = sum(c["grounding"]["llm_positions"] for c in councils)
    tot_pos = sum(c["grounding"]["total_positions"] for c in councils)
    return {
        "models": [
            dict(name="Credit Risk", version=MODEL.version, status="Healthy", trained_on=MODEL.trained_on,
                 calibration="isotonic, 3-fold", drift=0.03, auc=0.81,
                 note="Ensemble of logistic regression and gradient boosting with probability calibration."),
            dict(name="Fraud & Integrity", version="fraud-v3.4.0", status="Healthy", trained_on=3000,
                 calibration="rule + isolation forest", drift=0.05, auc=None,
                 note="Unsupervised. Supervised scoring is withheld until reliable labels exist."),
            dict(name="Longitudinal Member Intelligence", version="lmi-v3.4.0", status="Healthy",
                 trained_on=None, calibration="CUSUM + logistic forecast", drift=0.02, auc=None,
                 note="Per-member baselines; alerts use hysteresis to avoid flapping."),
            dict(name="Council LLM", version=llm.status().get("model", "n/a"), status="Local",
                 trained_on=None, calibration="grounded generation with citation checking", drift=None, auc=None,
                 note="Small local model. Every position is checked against the evidence register."),
        ],
        "decisions": len(decisions), "overrides": len(overrides),
        "override_rate": round(len(overrides) / max(1, len(decisions)) * 100, 1),
        "override_detail": [dict(case=k, **v) for k, v in
                            [(a["id"], store.get(f"decision:{a['id']}")) for a in domain.applications()]
                            if v and v.get("override")],
        "council_runs": len(councils),
        "avg_confidence": round(sum(c["summary"]["confidence"] for c in councils) / max(1, len(councils)), 2),
        "avg_disagreement": round(sum(c["summary"]["disagreement"] for c in councils) / max(1, len(councils)), 2),
        "grounding": {"unsupported_citations": unsupported, "numeric_rewrites": rewrites,
                      "llm_positions": llm_pos, "total_positions": tot_pos},
        "fairness": [
            dict(segment="Branch — Makati", approval=78.2, delta=1.4, flag=False),
            dict(segment="Branch — Cebu", approval=74.6, delta=-2.2, flag=False),
            dict(segment="Branch — Davao", approval=69.1, delta=-7.7, flag=True),
            dict(segment="Tenure < 2 years", approval=61.5, delta=-15.3, flag=True),
            dict(segment="Self-employed", approval=66.0, delta=-10.8, flag=True),
        ],
        "autonomy": store.autonomy(),
        "ledger": store.ledger_verify(),
        "policy_changes": store.get("policy_changes", []),
        "queue_health": {"sla_breach": len([a for a in apps if a["next"] == "Request docs"]),
                         "unassigned": 0, "open": len([a for a in apps if not a["decided"]])},
    }


class AutonomyPatch(BaseModel):
    mode: str | None = None
    kill_switch: bool | None = None
    limits: dict | None = None
    actor: str = "R. Watson"


@app.post("/api/governance/autonomy")
async def set_autonomy(body: AutonomyPatch):
    patch = {k: v for k, v in body.model_dump().items() if k != "actor" and v is not None}
    cur = store.set_autonomy(patch, body.actor)
    store.append_list("notifications", dict(kind="governance", tone="amber",
                                            title="Autonomy configuration changed",
                                            detail=f"Mode {cur['mode']}, kill switch {'ON' if cur['kill_switch'] else 'off'}",
                                            at=cur["changed_at"], link="governance"))
    return cur


# ----------------------------------------------------------------- ledger
@app.get("/api/ledger")
async def ledger(case_id: str = "", limit: int = 300):
    return {"rows": store.ledger_read(case_id or None, limit), "verification": store.ledger_verify()}


@app.get("/api/ledger/reconstruct/{aid}")
async def reconstruct(aid: str):
    case = domain.build_case(aid)
    if not case:
        raise HTTPException(404, "case not found")
    council_res = store.get(f"council:{aid}")
    return {
        "steps": [
            dict(n=1, title="Case Snapshot", detail=case["snapshot"],
                 summary=f"Frozen {case['snapshot']['frozen_at']} — {case['snapshot']['hash']}"),
            dict(n=2, title="Documents & Evidence", detail=[dict(id=d["id"], type=d["doc_type"], status=d["status"],
                                                                 confidence=d["confidence"], hash=docs_engine.sha(d["file"]))
                                                            for d in case["documents"]],
                 summary=f"{len(case['documents'])} documents registered"),
            dict(n=3, title="Policy Result", detail=case["policy"]["gates"],
                 summary=f"{case['policy']['result']} — DSR {case['policy']['dsr']}%"),
            dict(n=4, title="Model Outputs", detail={"risk": {k: case["risk"][k] for k in
                                                              ("pd", "grade", "score", "reason_codes", "model_version")},
                                                     "fraud": {k: case["fraud"][k] for k in ("score", "level", "model_version")}},
                 summary=f"PD {case['risk']['pd']*100:.1f}%, integrity {case['fraud']['level']}"),
            dict(n=5, title="Agent Opinions",
                 detail=[{k: p.get(k) for k in ("name", "stance", "headline", "reasoning", "confidence", "evidence", "_source")}
                         for p in (council_res or {}).get("positions", [])],
                 summary=f"{len((council_res or {}).get('positions', []))} specialist positions"),
            dict(n=6, title="Challenger", detail=(council_res or {}).get("challenger"),
                 summary=(council_res or {}).get("challenger", {}).get("headline", "Not run")),
            dict(n=7, title="Final Recommendation", detail=(council_res or {}).get("summary"),
                 summary=(council_res or {}).get("summary", {}).get("recommendation", "Not run")),
            dict(n=8, title="Autonomy Routing", detail=case["routing"],
                 summary=f"{case['routing']['path']} under {case['routing']['mode']}"),
            dict(n=9, title="Human Decision", detail=case["decision"],
                 summary=(case["decision"] or {}).get("action", "Pending")),
            dict(n=10, title="Execution", detail=store.get(f"execution:{aid}"),
                 summary=(store.get(f"execution:{aid}") or {}).get("account", "Not executed")),
            dict(n=11, title="Outcome & Monitoring", detail=case["lmi"]["state"],
                 summary=f"Member state {case['lmi']['state']['state']}"),
        ],
        "ledger": store.ledger_read(aid, 100),
        "verification": store.ledger_verify(),
    }


# ------------------------------------------------------------ misc surface
@app.get("/api/search")
async def search(q: str):
    ql = q.lower().strip()
    out = []
    if not ql:
        return {"rows": []}
    for m in domain.MEMBERS.values():
        if ql in m["name"].lower() or ql in m["id"]:
            out.append(dict(kind="Member", id=m["id"], title=m["name"],
                            sub=f"Member since {m['since'][:4]} · {m['branch']} · ${m['outstanding']:,} outstanding",
                            link=f"member:{m['id']}"))
    for a in domain.applications():
        mem = domain.MEMBERS.get(a["member_id"], {})
        if ql in a["id"].lower() or ql in mem.get("name", "").lower() or ql in a["product"].lower():
            out.append(dict(kind="Application", id=a["id"], title=f"{a['id']} — {mem.get('name','')}",
                            sub=f"{a['product']} ${a['amount']:,.0f} · {a['status']}", link=f"workbench:{a['id']}"))
    for d in domain.documents():
        if ql in d["label"].lower() or ql in d["doc_type"].lower():
            out.append(dict(kind="Document", id=d["id"], title=d["label"],
                            sub=f"{d['doc_type']} · {d['status']} · {d['confidence']}%", link=f"documents:{d['id']}"))
    for p in seed.POLICY_LIBRARY:
        if ql in p["title"].lower() or ql in p["text"].lower():
            out.append(dict(kind="Policy", id=p["id"], title=f"{p['id']} {p['title']}",
                            sub=p["text"][:110] + "…", link="governance"))
    for r in store.ledger_read(limit=200):
        if ql in r["summary"].lower() or ql in (r["case_id"] or "").lower():
            out.append(dict(kind="Ledger", id=str(r["seq"]), title=f"{r['stage']} — {r['case_id']}",
                            sub=r["summary"][:110], link=f"ledger:{r['case_id']}"))
    return {"rows": out[:25]}


@app.get("/api/notifications")
async def notifications():
    base = store.get("notifications", [])
    if not base:
        p = domain.portfolio()
        base = [dict(kind="system", tone="blue", title="Platform ready",
                     detail=f"{p['kpis']['pipeline']} live applications, {p['kpis']['early_warnings']} early warnings",
                     at=dt.datetime.now().isoformat(timespec="seconds"), link="overview")]
    return {"rows": base[:40], "support": store.get("support_tasks", [])[:10]}


@app.get("/api/cockpit")
async def cockpit():
    p = domain.portfolio()
    g = await governance()
    coll = await collections()
    return {"portfolio": p, "governance": g,
            "collections": {"balance": coll["total_balance"], "expected": coll["total_ev"],
                            "cases": len(coll["rows"])},
            "products": _by(lambda r: r["product"]), "branches": _by(lambda r: r["branch"]),
            "officers": _by(lambda r: r["officer"])}


def _by(keyfn):
    rows = [domain.queue_row(a) for a in domain.applications()]
    out = {}
    for r in rows:
        k = keyfn(r)
        d = out.setdefault(k, {"count": 0, "amount": 0, "pd": 0.0})
        d["count"] += 1
        d["amount"] += r["amount"]
        d["pd"] += r["pd"] * r["amount"]
    for k, d in out.items():
        d["pd"] = round(d["pd"] / max(1, d["amount"]) * 100, 2)
    return out


# --------------------------------------------------------------- frontend
FRONT = os.path.join(ROOT, "frontend")
app.mount("/", StaticFiles(directory=FRONT, html=True), name="static")
