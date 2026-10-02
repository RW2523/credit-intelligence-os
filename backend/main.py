"""KT Credit Intelligence — API. Runs entirely on this machine."""
from __future__ import annotations
import os, sys, json, asyncio, datetime as dt, shutil, re, mimetypes, csv, io
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import store
store.init()
import clock, seed, domain, council, llm, auth, assistant, docgen
import lang as L
from fmt import rm, date as fdate
from engines import lmi as lmi_engine, docs as docs_engine, policy as policy_engine, distress, crosssell
from engines.risk import MODEL
from connectors import ccris, sola, ekyc

mimetypes.add_type("text/javascript", ".mjs")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOADS = os.path.join(ROOT, "data", "uploads")
os.makedirs(UPLOADS, exist_ok=True)
MAX_UPLOAD = 10 * 1024 * 1024
ALLOWED_EXT = {"pdf", "png", "jpg", "jpeg", "csv", "txt"}

app = FastAPI(title="KT Credit Intelligence")

OPEN = {"/api/auth/login", "/api/auth/logout", "/api/auth/demo", "/api/health"}


@app.middleware("http")
async def session(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and path not in OPEN:
        user = auth.read(request.cookies.get(auth.COOKIE), domain.MEMBERS)
        if not user:
            return JSONResponse({"detail": "Not signed in"}, status_code=401)
        request.state.user = user
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    return resp


def U(req: Request) -> dict:
    return req.state.user


def need(req: Request, *views: str) -> dict:
    u = U(req)
    if not auth.can(u, *views):
        raise HTTPException(403, f"{u['role_label']} does not have access to this")
    return u


def staff(req: Request) -> dict:
    u = U(req)
    if u["role"] == "member":
        raise HTTPException(403, "Staff only")
    return u


def own_member(req: Request) -> dict:
    u = U(req)
    if u["role"] != "member":
        raise HTTPException(403, "Member portal only")
    return u


@app.on_event("startup")
async def _startup():
    await llm.probe()
    domain.seeded_documents()                          # builds the evidence set if the demo day changed
    if not store.ledger_read(limit=1):
        for a in sorted(domain.applications(), key=lambda x: x["submitted"]):
            store.ledger_append(a["id"], "Application Received", a["channel"],
                                f"{a['product']} of {rm(a['amount'])} over {a['term']} months submitted via {a['channel']}",
                                {"application": a["id"], "member": a["member_id"], "amount": a["amount"]},
                                at=a["submitted"])
    asyncio.create_task(llm.warm())
    if os.environ.get("CIOS_PRERUN_COUNCIL", "1") == "1" and not store.get("council:APP-104233"):
        asyncio.create_task(_prerun_councils())


async def _prerun_councils():
    """Give the queue a few real Council recommendations so a fresh demo isn't empty."""
    await asyncio.sleep(5)
    for aid in ("APP-104233", "APP-104265"):
        try:
            await _run_council(aid, None)
        except Exception:                                      # noqa: BLE001
            pass


# ================================================================== auth
class Login(BaseModel):
    username: str
    password: str


@app.post("/api/auth/login")
async def login(body: Login, request: Request):
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0]
    if auth.throttled(ip):
        raise HTTPException(429, "Too many attempts — try again in a few minutes.")
    rec = auth.verify(body.username, body.password, domain.MEMBERS)
    if not rec:
        auth.failed(ip)
        raise HTTPException(401, "Incorrect ID or password")
    store.append_list("access_log", dict(user=rec["username"], role=rec["role"], at=clock.now_iso(), ip=ip), cap=500)
    resp = JSONResponse({"user": rec})
    resp.set_cookie(auth.COOKIE, auth.issue(rec), max_age=auth.TTL, httponly=True, samesite="lax", path="/")
    return resp


@app.post("/api/auth/logout")
async def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(auth.COOKIE, path="/")
    return resp


@app.get("/api/auth/demo")
async def demo():
    return {"demo": auth.DEMO, "accounts": auth.demo_accounts(domain.MEMBERS),
            "staff_password": auth.STAFF_PASSWORD if auth.DEMO else None,
            "member_pin": auth.MEMBER_PIN if auth.DEMO else None,
            "institution": seed.INSTITUTION}


@app.get("/api/auth/me")
async def me(request: Request):
    return {"user": U(request)}


# ================================================================== meta
@app.get("/api/bootstrap")
async def bootstrap(request: Request):
    u = U(request)
    base = {
        "user": u, "products": seed.PRODUCTS, "financing": seed.FINANCING, "branches": seed.BRANCHES,
        "branch_info": seed.BRANCH_INFO, "doc_ms": seed.DOC_MS, "llm": llm.status(),
        "today": clock.TODAY.isoformat(), "now": clock.now_iso(), "frozen": clock.FROZEN,
        "institution": seed.INSTITUTION, "deduction_cap": seed.DEDUCTION_CAP_PCT,
        "can": {"distress": u["role"] in auth.DISTRESS_ROLES, "crosssell": u["role"] in auth.CROSSSELL_ROLES,
                "autonomy": u["role"] == "board", "approve_policy": u["role"] == "board"},
    }
    if u["role"] == "member":
        return base
    return dict(base, roles={k: {kk: vv for kk, vv in v.items()} for k, v in auth.ROLES.items()},
                policies=seed.POLICY_LIBRARY, autonomy=store.autonomy(),
                policy_version=store.get("policy_version", "v4.0"), overrides=store.get("policy_overrides", {}),
                model={"risk": MODEL.version, "trained_on": MODEL.trained_on, "base_rate": MODEL.base_rate},
                staff=seed.STAFF)


@app.get("/api/health")
async def health():
    s = await llm.probe()
    return {"ok": True, "llm": {k: s.get(k) for k in ("available", "model", "models")},
            "ledger": store.ledger_verify(), "today": clock.TODAY.isoformat(), "tz": "Asia/Kuala_Lumpur",
            "documents": len(domain.documents()), "members": len(domain.MEMBERS)}


# ============================================================= portfolio
@app.get("/api/portfolio")
async def portfolio(request: Request):
    need(request, "overview", "cockpit")
    return domain.portfolio()


@app.get("/api/applications")
async def list_applications(request: Request, q: str = "", product: str = "", branch: str = "", risk: str = "",
                            status: str = "", officer: str = ""):
    need(request, "applications")
    rows = domain.queue_rows()

    def keep(r):
        if q and q.lower() not in f"{r['name']} {r['id']} {r['product']} {r['member_id']}".lower(): return False
        for f, k in ((product, "product"), (branch, "branch"), (risk, "risk"), (status, "status"), (officer, "officer")):
            if f and f != "All" and r[k] != f: return False
        return True
    return {"rows": [r for r in rows if keep(r)],
            "facets": {k: sorted({r[k] for r in rows}) for k in ("product", "branch", "risk", "status", "officer")}}


@app.get("/api/applications/{aid}")
async def get_application(aid: str, request: Request):
    need(request, "applications", "workbench", "documents", "ledger")
    case = domain.build_case(aid)
    if not case:
        raise HTTPException(404, "case not found")
    mid = case["application"]["member_id"]
    case["ledger"] = store.ledger_read(aid, 60)
    case["comms"] = [c for c in _comms() if c["member_id"] == mid]
    m = domain.MEMBERS.get(mid)
    if m:
        case["external"] = {"ccris": ccris.report(m), "sola": sola.eligibility(m), "ekyc": ekyc.status(m)}
    return case


class Intake(BaseModel):
    member_id: str = ""
    applicant_name: str = ""
    product: str
    amount: float
    term: int
    purpose: str = ""
    branch: str = "Kuala Lumpur"
    existing_commitments: float | None = None
    declared_income: float | None = None
    employer: str = ""
    employment: str = "Serving — permanent & confirmed"
    guarantor: str | None = None
    channel: str = "Branch"


def _create_application(body: Intake, actor: str, officer: str, channel: str) -> tuple[str, dict]:
    if body.product not in seed.FINANCING:
        raise HTTPException(400, "Unknown financing product")
    apps = domain.applications()
    n = 1 + len([a for a in apps if a["id"].startswith("APP-9")])
    aid = f"APP-9{n:05d}"
    mid = body.member_id or ""
    if mid not in domain.MEMBERS:
        if not body.declared_income:
            raise HTTPException(400, "A new applicant needs a declared income")
        base = domain.MEMBERS["104328"]
        name = body.applicant_name or "New Applicant"
        mid = mid or f"9{n:05d}"
        gross = round(body.declared_income / 12 / 0.88, 2)
        domain.MEMBERS[mid] = dict(base, id=mid, name=name, full_name=name, given_name=name.split()[0],
                                   initials=auth.initials(name), declared_income=body.declared_income,
                                   payslip_income=body.declared_income, bank_income=body.declared_income,
                                   gross_monthly=gross, other_deductions=round(gross * 0.12, 2),
                                   employer=body.employer or "—", employment=body.employment, outstanding=0,
                                   prior_financings=0, since=clock.TODAY.isoformat(), reliability=85, savings=1500,
                                   share_capital=800, payments=[], deduction=0, external_deductions=0,
                                   financing_deductions=0, branch=body.branch, takaful=[], engagement=[5] * 12)
        store.bump()
    elif body.declared_income:
        domain.MEMBERS[mid] = dict(domain.MEMBERS[mid], declared_income=body.declared_income)
        store.bump()
    m = domain.MEMBERS[mid]
    now = clock.now_iso()
    existing = body.existing_commitments if body.existing_commitments is not None else m.get("financing_deductions", 0)
    a = dict(id=aid, member_id=mid, product=body.product, amount=body.amount, term=body.term, purpose=body.purpose,
             submitted=now, snapshot_at=now, branch=body.branch if body.branch in seed.BRANCHES else m["branch"],
             status="Officer Review", officer=officer, channel=channel, guarantor=body.guarantor,
             existing_commitments=existing, case_type="origination", applicant_name=body.applicant_name)
    apps.insert(0, a)
    domain.save_applications(apps)
    case = domain.build_case(aid)
    store.ledger_append(aid, "Application Received", actor, f"{body.product} of {rm(body.amount)} submitted via {channel}",
                        {"application": a})
    store.ledger_append(aid, "Case Snapshot Frozen", "System",
                        f"Snapshot {case['snapshot']['hash']} frozen under policy {case['policy']['policy_version']}",
                        case["snapshot"])
    store.ledger_append(aid, "Policy Evaluation", "Policy Engine",
                        f"{case['policy']['result']} — DSR {case['policy']['dsr']}%"
                        + (f", deductions {case['policy']['deduction_ratio']}% of gross" if case['policy']['deduction_ratio'] else ""),
                        {"gates": case["policy"]["gates"], "max_financing": case["policy"]["max_financing"]})
    store.ledger_append(aid, "Risk Evaluation", "Risk Model", f"{case['risk']['grade']} — PD {case['risk']['pd']*100:.1f}%",
                        {"pd": case["risk"]["pd"], "reason_codes": case["risk"]["reason_codes"]})
    store.append_list("notifications", dict(kind="case", tone="blue", title="New application",
                                            detail=f"{aid} — {m['name']} · {body.product} {rm(body.amount)}",
                                            at=now, link=f"workbench:{aid}"))
    return aid, case


@app.post("/api/applications")
async def create_application(body: Intake, request: Request):
    u = need(request, "intake")
    aid, case = _create_application(body, f"{u['name']} ({u['role_label']})", u["name"], body.channel)
    return {"id": aid, "case": case}


# ============================================================= documents
@app.get("/api/documents")
async def all_documents(request: Request):
    need(request, "documents")
    return {"rows": domain.documents(), "pipeline": docs_engine.PIPELINE}


@app.get("/api/documents/{doc_id}")
async def one_document(doc_id: str, request: Request):
    need(request, "documents", "applications")
    d = next((x for x in domain.documents() if x["id"] == doc_id), None)
    if not d:
        raise HTTPException(404, "document not found")
    return d


@app.get("/api/files/{name}")
async def serve_file(name: str, request: Request):
    u = U(request)
    name = os.path.basename(name)
    doc = next((d for d in domain.documents() if d["file"] == name), None)
    if u["role"] == "member":
        if not doc or doc["member_id"] != u["member_id"]:
            raise HTTPException(403, "Not your document")
    elif not auth.can(u, "documents", "applications", "ledger"):
        raise HTTPException(403, "No access to evidence")
    for base in (docgen.OUT, UPLOADS):
        p = os.path.join(base, name)
        if os.path.exists(p):
            return FileResponse(p, headers={"Cache-Control": "private, max-age=300"})
    raise HTTPException(404, "file not found")


# Malay and English labels on uploaded documents -> the keys the extraction engine understands
LABEL_MAP = {
    "nama": "Employee Name", "name": "Employee Name", "no. tentera / pekerja": "Service No",
    "pangkat / gred": "Rank / Grade", "bulan gaji": "Pay Period", "jumlah pendapatan kasar": "Gross Monthly",
    "gross pay": "Gross Monthly", "jumlah potongan statutori & lain-lain": "Other Deductions",
    "jumlah potongan pembiayaan": "Financing Deductions", "koperasi tentera (kt)": "KT Deduction",
    "gaji bersih (net pay)": "Net Pay", "gaji bersih": "Net Pay", "net pay": "Net Pay",
    "pemegang akaun": "Account Holder", "purata kredit gaji bulanan": "Avg Monthly Salary Credit",
    "taraf perkhidmatan": "Service Status", "tarikh bersara wajib": "Retirement Date",
}
_NUMERIC = re.compile(r"^(RM\s?)?[\d,]+(\.\d+)?$")


def _pdf_fields(path: str) -> list[dict]:
    """Label/value pairs from an uploaded PDF, boxed from the text positions pypdf reports."""
    from pypdf import PdfReader
    page = PdfReader(path).pages[0]
    W, H = float(page.mediabox.width), float(page.mediabox.height)
    runs = []

    def visit(text, cm, tm, fd, fs):
        t = (text or "").strip()
        if t:
            size = (fs or 10) * (abs(tm[0]) if tm[0] else 1)
            runs.append((t, tm[4] * cm[0] + cm[4], tm[5] * cm[3] + cm[5], max(6.0, min(28.0, size))))
    page.extract_text(visitor_text=visit)
    lines: dict[int, list] = {}
    for t, x, y, s in runs:
        lines.setdefault(round(y / 3), []).append((x, t, s, y))

    def box(x, y, s, text):
        from reportlab.pdfbase.pdfmetrics import stringWidth
        try:
            w = stringWidth(text, "Helvetica", s)
        except Exception:                                           # noqa: BLE001
            w = s * 0.52 * len(text)
        return [round((x - 2.5) / W * 100, 2), round((H - y - s * 0.8 - 2.5) / H * 100, 2),
                round((w + 5) / W * 100, 2), round((s * 1.05 + 5) / H * 100, 2)]

    out = []
    for _, parts in sorted(lines.items(), key=lambda kv: -kv[0]):
        parts.sort()
        i = 0
        while i < len(parts):
            x, t, s, y = parts[i]
            if ": " in t and not _NUMERIC.match(t):                 # "Label: value" in one run
                k, v = t.split(": ", 1)
                out.append(dict(k=LABEL_MAP.get(k.strip().lower(), k.strip()), v=v.strip(), c=86, page=1,
                                bbox=box(x, y, s, t), label=k.strip()))
                i += 1
                continue
            if i + 1 < len(parts):
                nx, nt, ns, ny = parts[i + 1]
                is_label = any(ch.isalpha() for ch in t) and not _NUMERIC.match(t)
                junk = nt in ("RM", "SPECIMEN · DATA SINTETIK") or t.isupper() and not _NUMERIC.match(nt.replace(" ", ""))
                if is_label and not junk and (_NUMERIC.match(nt.replace(" ", "")) or nx - x > 60):
                    out.append(dict(k=LABEL_MAP.get(t.lower(), t), v=nt, c=88 if _NUMERIC.match(nt) else 84, page=1,
                                    bbox=box(nx, ny, ns, nt), label=t))
                    i += 2
                    continue
            i += 1
        if len(out) >= 32:
            break
    return out


@app.post("/api/applications/{aid}/documents")
async def upload(aid: str, request: Request, file: UploadFile = File(...)):
    u = U(request)
    app_ = domain.app_by_id(aid)
    if not app_:
        raise HTTPException(404, "case not found")
    if u["role"] == "member":
        if app_["member_id"] != u["member_id"]:
            raise HTTPException(403, "Not your application")
    elif not auth.can(u, "applications", "documents", "intake"):
        raise HTTPException(403, "No access")
    raw_name = file.filename or "document"
    ext = raw_name.rsplit(".", 1)[-1].lower() if "." in raw_name else ""
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"File type .{ext} is not accepted")
    safe = f"{aid}_{re.sub(r'[^A-Za-z0-9._-]', '_', raw_name)}"[:120]
    dest = os.path.join(UPLOADS, safe)
    size = 0
    with open(dest, "wb") as fh:
        while chunk := await file.read(1 << 16):
            size += len(chunk)
            if size > MAX_UPLOAD:
                fh.close(); os.remove(dest)
                raise HTTPException(413, "File is larger than 10 MB")
            fh.write(chunk)
    doc_type, conf = docs_engine.classify(raw_name)
    docs = domain.documents()
    did = f"DOC-{9000 + len(docs)}"
    fields = []
    if ext == "pdf":
        try:
            fields = _pdf_fields(dest)
        except Exception:                                           # noqa: BLE001
            fields = []
    meta = [dict(k="File name", v=raw_name, c=100, page=1, meta=True),
            dict(k="Classified as", v=f"{doc_type} ({seed.DOC_MS.get(doc_type, doc_type)})", c=conf, page=1, meta=True),
            dict(k="Size", v=f"{size/1024:.1f} KB", c=100, page=1, meta=True),
            dict(k="Uploaded by", v=f"{u['name']} ({u['role_label']})", c=100, page=1, meta=True)]
    doc = dict(id=did, app_id=aid, member_id=app_["member_id"], file=safe, label=raw_name, doc_type=doc_type,
               doc_type_ms=seed.DOC_MS.get(doc_type, doc_type), status="Verified" if conf >= 90 and fields else "Needs Review",
               confidence=conf, uploaded=clock.now_iso(), pages=1, uploaded_file=True,
               forensics=dict(tampering=False, font_consistency=97, metadata_ok=True, duplicate_hash=False,
                              producer="Uploaded"), fields=meta + fields)
    domain.add_document(doc)
    store.ledger_append(aid, "Evidence Registered", f"{u['name']} ({u['role_label']})",
                        f"{doc_type} '{raw_name}' classified at {conf}% confidence; {len(fields)} field(s) located",
                        {"doc": did, "hash": docs_engine.sha(safe), "fields": len(fields)})
    return {"document": doc, "pipeline": docs_engine.PIPELINE}


# =============================================================== council
def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


async def _run_council(aid: str, emit):
    case = domain.build_case(aid)
    res = await council.run(case, emit)
    store.put(f"council:{aid}", res)
    s = res["summary"]
    store.ledger_append(aid, "Agent Deliberation", "AI Credit Council",
                        f"{len(res['positions'])} specialist positions, {s['dissent_count']} dissenting",
                        {"positions": [{k: p[k] for k in ("name", "stance", "headline", "confidence", "evidence")}
                                       for p in res["positions"]],
                         "challenger": {k: res["challenger"].get(k) for k in ("stance", "headline", "ask")}})
    store.ledger_append(aid, "Recommendation Synthesized", "Synthesizer",
                        f"{s['recommendation']} at {s['confidence']} confidence (disagreement {s['disagreement']})", s)
    return res


@app.get("/api/applications/{aid}/council/stream")
async def council_stream(aid: str, request: Request):
    need(request, "applications")
    if not domain.build_case(aid):
        raise HTTPException(404, "case not found")
    q: asyncio.Queue = asyncio.Queue()

    async def emit(ev, data):
        await q.put((ev, data))

    async def runner():
        try:
            await _run_council(aid, emit)
            await q.put(("routing", domain.build_case(aid)["routing"]))
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


# ============================================================== decision
class Decision(BaseModel):
    action: str                      # Approve | Decline | Request Information | Escalate
    reason: str = ""
    conditions: list[str] = []


@app.post("/api/applications/{aid}/decision")
async def decide(aid: str, body: Decision, request: Request):
    u = need(request, "workbench", "applications")
    case = domain.build_case(aid)
    if not case:
        raise HTTPException(404, "case not found")
    if body.action not in ("Approve", "Decline", "Request Information", "Escalate"):
        raise HTTPException(400, "Unknown action")
    amount = case["application"]["amount"]
    if body.action in ("Approve", "Decline"):
        if u["authority"] <= 0:
            raise HTTPException(403, f"A {u['role_label']} has no approval authority — escalate instead.")
        if amount > u["authority"]:
            raise HTTPException(403, f"{rm(amount)} exceeds your authority of {rm(u['authority'])} "
                                     f"(POL-005: needs {case['policy']['authority_required']}). Escalate the case.")
    if body.action == "Approve" and case["policy"]["result"] == "FAIL" and not body.reason.strip():
        raise HTTPException(400, "Approving a case that fails a hard policy gate requires a documented exception.")
    rec = (case.get("council") or {}).get("summary", {}).get("recommendation", "Not run")
    override = rec not in ("Not run", body.action.upper()) and body.action in ("Approve", "Decline")
    if override and not body.reason.strip():
        raise HTTPException(400, "An override of the AI recommendation requires a documented reason.")
    now = clock.now_iso()
    record = dict(action=body.action, reason=body.reason, actor=u["name"], role=u["role_label"], at=now,
                  ai_recommendation=rec, override=override,
                  conditions=body.conditions or (case.get("council") or {}).get("summary", {}).get("conditions", []),
                  authority=case["policy"]["authority_required"], snapshot=case["snapshot"]["hash"])
    store.put(f"decision:{aid}", record)
    apps = domain.applications()
    for a in apps:
        if a["id"] == aid:
            a["status"] = {"Approve": "Approved", "Decline": "Declined", "Request Information": "Documents Pending",
                           "Escalate": "Escalated"}.get(body.action, a["status"])
    domain.save_applications(apps)
    store.ledger_append(aid, "Human Decision", f"{u['name']} ({u['role_label']})",
                        f"{body.action}" + (f" — OVERRIDE of AI '{rec}': {body.reason}" if override
                                            else (f" — {body.reason}" if body.reason else "")), record)
    execution = None
    if body.action == "Approve":
        token = store.ledger_append(aid, "Approval Token Issued", "Governance",
                                    f"Token issued for {rm(amount)} under {record['authority']} authority",
                                    {"amount": amount, "authority": record["authority"]})
        execution = await _execute(aid, case, token["hash"])
    if body.action in ("Request Information", "Escalate"):
        store.delete(f"decision:{aid}")                     # these move the case on; they are not final decisions
    store.append_list("notifications", dict(kind="decision", tone="green" if body.action == "Approve" else "blue",
                                            title=f"{aid} — {body.action} by {u['name']}",
                                            detail=body.reason or rec, at=now, link=f"workbench:{aid}"))
    return {"decision": record, "execution": execution, "ledger": store.ledger_read(aid, 60)}


async def _execute(aid: str, case: dict, token: str) -> dict:
    """Execution service — the only privileged writer to the core financing system."""
    p, a = case["policy"], case["application"]
    acct = "PF-" + aid.split("-")[1]
    first = seed.next_deduction_date()
    if (first - clock.TODAY).days < 10:
        first = clock.add_months(first, 1, seed.PAYDAY)
    principal_part = round(a["amount"] / a["term"], 2)
    profit_part = round(p["instalment"] - principal_part, 2)
    schedule, bal = [], a["amount"]
    for i in range(min(6, a["term"])):
        bal = round(bal - principal_part, 2)
        schedule.append(dict(n=i + 1, due=clock.add_months(first, i, seed.PAYDAY).isoformat(),
                             amount=p["instalment"], principal=principal_part, profit=profit_part, balance=bal))
    channel = "Biro ANGKASA salary deduction" if p["by_salary_deduction"] else "Standing instruction"
    result = dict(account=acct, token=token, idempotency_key=f"{aid}:{token[:12]}", instalment=p["instalment"],
                  rate=p["rate"], rate_type="flat", contract=p["contract"], term=a["term"], channel=channel,
                  first_due=schedule[0]["due"], total_profit=p["total_profit"], total_payable=p["total_payable"],
                  schedule=schedule,
                  steps=[dict(name="Approval token validated", ok=True),
                         dict(name=f"{p['contract']} trade executed (commodity purchase & sale)", ok=True),
                         dict(name="Financing record created in the core system", ok=True),
                         dict(name="Repayment schedule generated", ok=True),
                         dict(name=f"{channel} mandate registered", ok=True),
                         dict(name="Accounting entries posted", ok=True),
                         dict(name="Member notified (SMS + KT Online)", ok=True),
                         dict(name="Repayment monitoring started", ok=True)])
    store.put(f"execution:{aid}", result)
    store.ledger_append(aid, "Core Execution", "Execution Service",
                        f"Facility {acct} activated; first instalment {rm(p['instalment'], 2)} due {fdate(schedule[0]['due'])}",
                        {k: result[k] for k in ("account", "token", "idempotency_key", "instalment", "first_due", "channel")})
    store.ledger_append(aid, "Monitoring Started", "Early Warning Service",
                        "Personal repayment baseline initialised for this facility", {"account": acct})
    return result


@app.get("/api/applications/{aid}/execution")
async def execution(aid: str, request: Request):
    need(request, "applications", "workbench")
    return store.get(f"execution:{aid}") or {}


# ================================================================ members
def _comms():
    return store.get("comms_logged", []) + seed.COMMS


def _member_public(m: dict) -> dict:
    return {k: v for k, v in m.items() if k not in ("payments", "pattern")}


@app.get("/api/members")
async def members(request: Request, branch: str = "", q: str = ""):
    need(request, "members")
    out = []
    for m in domain.MEMBERS.values():
        if branch and m["branch"] != branch:
            continue
        if q and q.lower() not in f"{m['name']} {m['id']} {m['service_no']}".lower():
            continue
        a = lmi_engine.analyse(m)
        out.append(dict(_member_public(m), lmi_state=a["state"]["state"], p30=a["forecast"]["p_late_30d"]))
    return {"rows": out}


def _sensitive_access(u: dict, mid: str, what: str):
    key = f"access:{u['username']}:{mid}:{what}:{clock.TODAY.isoformat()}"
    if not store.get(key):
        store.put(key, True)
        store.ledger_append(f"MEM-{mid}", "Sensitive Access", f"{u['name']} ({u['role_label']})",
                            f"Viewed {what} for member {mid} (POL-013)", {"member": mid, "view": what})


@app.get("/api/members/{mid}")
async def member(mid: str, request: Request):
    u = U(request)
    if u["role"] == "member":
        if mid != u["member_id"]:
            raise HTTPException(403, "Not your record")
    elif not auth.can(u, "members"):
        raise HTTPException(403, "No access to members")
    m = domain.MEMBERS.get(mid)
    if not m:
        raise HTTPException(404, "member not found")
    apps = [a for a in domain.applications() if a["member_id"] == mid]
    app_ids = {a["id"] for a in apps}
    ledger = [r for r in store.ledger_read(limit=400) if r["case_id"] in app_ids or r["case_id"] == f"MEM-{mid}"]
    out = {"member": _member_public(m), "payments": m["payments"], "lmi": lmi_engine.analyse(m),
           "applications": [domain.queue_row(a) for a in apps],
           "collections": [c for c in seed.COLLECTIONS if c["member_id"] == mid],
           "comms": [c for c in _comms() if c["member_id"] == mid],
           "history": domain.history_features(m), "ledger": ledger[:60],
           "next_deduction": seed.next_deduction_date().isoformat()}
    if u["role"] != "member":
        out["external"] = {"ccris": ccris.report(m), "sola": sola.eligibility(m), "ekyc": ekyc.status(m)}
    if u["role"] in auth.DISTRESS_ROLES:
        out["distress"] = distress.MODEL.score(m)
        out["distress_context"] = distress.CONTEXT
        _sensitive_access(u, mid, "financial-distress outlook")
    if u["role"] in auth.CROSSSELL_ROLES:
        out["crosssell"] = crosssell.offers(m)
    return out


@app.get("/api/early-warning")
async def early_warning(request: Request):
    need(request, "early-warning")
    rows = []
    for m in domain.MEMBERS.values():
        if not m["payments"]:
            continue
        a = lmi_engine.analyse(m)
        a["member"] = _member_public(m)
        rows.append(a)
    order = {"AT_RISK": 0, "ELEVATED": 1, "WATCH": 2, "RECOVERY": 3, "STABLE": 4}
    rows.sort(key=lambda a: (order[a["state"]["state"]], -a["forecast"]["p_late_30d"]))
    return {"rows": rows, "states": lmi_engine.STATES}


# ============================================================ collections
@app.get("/api/collections")
async def collections(request: Request):
    need(request, "collections", "cockpit")
    return _collections()


def _collections():
    rows = []
    for c in seed.COLLECTIONS:
        m = domain.MEMBERS[c["member_id"]]
        a = lmi_engine.analyse(m)
        ev = round(c["balance"] * c["response"] / 100 * (0.9 if c["dpd"] < 60 else 0.6), 0)
        rows.append(dict(c, name=m["name"], initials=m["initials"], branch=m["branch"], phone=m["phone"],
                         email=m["email"], state=a["state"]["state"], why_now=a["why_now"],
                         p30=a["forecast"]["p_late_30d"], recovery=a["forecast"]["recovery_likelihood"],
                         expected_value=ev, next_best_action=_nba(c, m, a),
                         comms=[x for x in _comms() if x["member_id"] == c["member_id"]]))
    rows.sort(key=lambda r: -r["expected_value"])
    return {"rows": rows, "total_ev": sum(r["expected_value"] for r in rows),
            "total_balance": sum(r["balance"] for r in rows)}


def _nba(c, m, a) -> dict:
    if c["dpd"] == 0 and c["stage"] == "Recovery":
        return dict(action="Confirm recovery and close the case", channel="Internal task", window="—",
                    objective="Record the recovery; keep the history",
                    reason="Three consecutive on-time deductions since the change point.")
    if c["dpd"] == 0:
        return dict(action="Proactive supportive call", channel="Phone", window="10:00–12:00",
                    objective="Understand the change in circumstances and offer options before arrears arise",
                    reason=f"{a['forecast']['p_late_30d']*100:.0f}% 30-day late-payment probability with no arrears yet — "
                           "the least intrusive effective intervention (POL-007).")
    if c["dpd"] >= 90:
        return dict(action="Structured call, rescheduling offer and AKPK referral", channel="Phone + letter",
                    window="14:00–17:00", objective="Agree an affordable arrangement and stop further deterioration",
                    reason=f"{c['dpd']} days past due with a {c['response']}% modelled contact-response rate.")
    if c["promise"]:
        return dict(action="Confirm promise to pay", channel="SMS", window="09:00–11:00",
                    objective=f"Confirm the RM300 payment promised for {fdate(c['promise'])}",
                    reason="An open promise to pay is the highest-yield follow-up available today.")
    return dict(action="Reminder with payment link", channel="SMS", window="09:00–11:00",
                objective="Restore the deduction without escalation",
                reason=f"Early-stage arrears ({c['dpd']} DPD) with a {c['response']}% response rate.")


class Outreach(BaseModel):
    member_id: str
    channel: str
    outcome: str = "Logged"
    note: str = ""


@app.post("/api/collections/outreach")
async def outreach(body: Outreach, request: Request):
    u = need(request, "collections", "members", "crosssell")
    m = domain.MEMBERS.get(body.member_id)
    if not m:
        raise HTTPException(404, "member not found")
    entry = dict(member_id=body.member_id, type=body.channel.lower(), title=f"{body.channel} — {body.outcome}",
                 at=clock.now_iso(), text=body.note, outcome=body.outcome, by=u["name"])
    store.put("comms_logged", [entry] + store.get("comms_logged", []))
    store.ledger_append(f"MEM-{body.member_id}", "Intervention Logged", f"{u['name']} ({u['role_label']})",
                        f"{body.channel} to {m['name']}: {body.outcome}", entry)
    return {"ok": True, "entry": entry}


class Draft(BaseModel):
    member_id: str
    channel: str = "Email"
    intent: str = "supportive outreach"
    lang: str = "ms"
    product: str | None = None


@app.post("/api/collections/draft")
async def draft(body: Draft, request: Request):
    need(request, "collections", "members", "crosssell")
    return await _draft(body)


async def _draft(body: Draft) -> dict:
    m = domain.MEMBERS.get(body.member_id)
    if not m:
        raise HTTPException(404, "member not found")
    a = lmi_engine.analyse(m)
    c = next((x for x in seed.COLLECTIONS if x["member_id"] == body.member_id), None)
    ms = body.lang == "ms"
    g = m["given_name"]
    if body.product:
        fallback = {"subject": (f"Tawaran untuk anda, {g}" if ms else f"An offer for you, {g}"),
                    "body": (f"Salam sejahtera {g},\n\nSebagai ahli Koperasi Tentera, anda mungkin berminat dengan "
                             f"{seed.PRODUCTS.get(body.product, {}).get('ms', body.product)}. Pegawai cawangan "
                             f"{m['branch']} boleh menerangkan butirannya tanpa sebarang komitmen.\n\nSila balas mesej ini "
                             "atau hubungi cawangan anda.\n\nYang ikhlas,\nKoperasi Tentera" if ms else
                             f"Dear {g},\n\nAs a Koperasi Tentera member you may be interested in {body.product}. Your "
                             f"{m['branch']} branch officer can explain the details with no obligation.\n\nPlease reply "
                             "to this message or contact your branch.\n\nKind regards,\nKoperasi Tentera")}
    else:
        fallback = {"subject": (f"Kami ingin bertanya khabar, {g}" if ms else f"Checking in about your account, {g}"),
                    "body": (f"Salam sejahtera {g},\n\nKami perasan ada perubahan pada corak potongan bayaran anda dan "
                             "ingin bertanya khabar sebelum tarikh potongan seterusnya. Rekod anda bersama Koperasi Tentera "
                             "selama ini baik, dan jika ada perubahan kami lebih suka membantu lebih awal.\n\nJika perlu, "
                             "kami boleh menyemak semula jadual ansuran anda. Sila balas mesej ini atau hubungi cawangan "
                             "anda dan minta pasukan Sokongan Ahli.\n\nYang ikhlas,\nSokongan Ahli, Koperasi Tentera" if ms else
                             f"Dear {g},\n\nWe noticed a change in your recent deduction pattern and wanted to check in "
                             "before your next deduction date. Your record with Koperasi Tentera has been strong, and if "
                             "something has changed we would rather help early than late.\n\nIf it would help, we can look "
                             "at rescheduling your instalments. Please reply to this message or call your branch and ask "
                             "for the Member Support team.\n\nKind regards,\nMember Support, Koperasi Tentera")}
    sysmsg = ("You draft short, respectful member communications for Koperasi Tentera, a Malaysian credit "
              "co-operative. Never threaten, never state or imply a financing decision, never quote figures that are "
              "not given to you. Plain, warm, under 140 words. Use Islamic financing terms ('financing', 'profit rate', "
              "'takaful'). Reply as JSON with keys subject and body. "
              + ("Write in Bahasa Malaysia. " + L.STYLE_MS if ms else "Write in English."))
    prompt = (f"Member: {m['name']} (address them as {g}). Channel: {body.channel}. "
              + (f"Purpose: introduce {body.product} — {seed.PRODUCTS.get(body.product, {}).get('desc', '')}\n" if body.product
                 else f"Intent: {body.intent}.\nSituation: {a['why_now']}\nState: {a['state']['state']}. "
                      + (f"Arrears {rm(c['balance'])}, {c['dpd']} days past due.\n" if c and c['dpd'] else "No arrears.\n")
                      + f"Recommended approach: {a['intervention']['action']} — {a['intervention']['objective']}.\n")
              + "Write the message.")
    out = await llm.json_call(sysmsg, prompt, fallback, temperature=0.4, num_predict=420)
    if ms:
        out["subject"], out["body"] = L.normalise_ms(out["subject"]), L.normalise_ms(out["body"])
    out["lang"] = body.lang
    out["policy_note"] = "Draft only — requires officer approval before sending (notification service policy)."
    return out


# ============================================================= assistants
@app.post("/api/ask")
async def ask(req: Request):
    """Case copilot (workbench) and portfolio analyst (cockpit) — the same tool-using agent."""
    u = staff(req)
    body = await req.json()
    return _agent_stream(u, body)


@app.post("/api/assistant")
async def staff_assistant(req: Request):
    u = need(req, "assistant", "cockpit")
    body = await req.json()
    return _agent_stream(u, body)


def _agent_stream(u: dict, body: dict):
    q = (body.get("question") or "").strip()[:1500]
    if not q:
        raise HTTPException(400, "Ask a question")
    aid = body.get("application_id")
    if aid and not auth.can(u, "applications", "workbench"):
        aid = None

    async def gen():
        async for ev, data in assistant.staff_agent(u, q, body.get("history") or [], aid, body.get("lang") or "en"):
            yield _sse(ev, data)
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/member-assistant")
async def member_assistant(req: Request):
    u = own_member(req)
    body = await req.json()
    q = (body.get("question") or "").strip()[:800]
    if not q:
        raise HTTPException(400, "Ask a question")
    return await assistant.member_answer(u["member_id"], q, body.get("lang") or "ms", body.get("history") or [])


# ======================================================== member portal
@app.get("/api/me")
async def my_account(request: Request):
    u = own_member(request)
    m = domain.MEMBERS[u["member_id"]]
    apps = [a for a in domain.applications() if a["member_id"] == m["id"]]
    rows = []
    for a in apps:
        c = domain.build_case(a["id"])
        rows.append(dict(id=a["id"], product=a["product"], product_ms=seed.PRODUCTS[a["product"]]["ms"],
                         amount=a["amount"], term=a["term"], status=a["status"],
                         status_ms=L.STATUS_MS.get(a["status"], a["status"]), submitted=a["submitted"],
                         missing=c["documents_summary"]["missing"],
                         missing_ms=[seed.DOC_MS.get(d, d) for d in c["documents_summary"]["missing"]],
                         documents=[dict(id=d["id"], label=d["label"], type=d["doc_type"], type_ms=d.get("doc_type_ms"),
                                         status=d["status"]) for d in c["documents"]]))
    takaful = m.get("takaful") or []
    return {"member": _member_public(m), "payments": m["payments"][-12:], "applications": rows,
            "next_deduction": seed.next_deduction_date().isoformat(), "takaful": takaful,
            "products": {k: dict(ms=v["ms"], kind=v["kind"], rate=v["rate"], min=v["min"], max=v["max"],
                                 min_term=v["min_term"], max_term=v["max_term"], docs=v["docs"], desc=v["desc"],
                                 contract=v["contract"]) for k, v in seed.PRODUCTS.items()},
            "branch": seed.BRANCH_INFO[m["branch"]] | {"key": m["branch"]},
            "support": [t for t in store.get("support_tasks", []) if t.get("member_id") == m["id"]][:5]}


class SelfCheck(BaseModel):
    product: str = "Personal Financing-i"
    amount: float = 20000
    term: int = 60


@app.post("/api/me/affordability")
async def my_affordability(body: SelfCheck, request: Request):
    """'Check Before You Borrow' — the same engine the officer workbench uses, on the member's own data."""
    u = own_member(request)
    m = domain.MEMBERS[u["member_id"]]
    if body.product not in seed.FINANCING:
        raise HTTPException(400, "Unknown product")
    p = seed.PRODUCTS[body.product]
    term = max(p["min_term"], min(p["max_term"], int(body.term)))
    app = dict(product=body.product, amount=float(body.amount), term=term,
               existing_commitments=m["financing_deductions"])
    pol = policy_engine.assess(app, m, {})
    # the same evaluation at the product's maximum tenure shows how far a longer term stretches the limit
    longest = policy_engine.assess(dict(app, term=p["max_term"]), m, {})
    store.ledger_append(f"MEM-{m['id']}", "Affordability Self-Check", "Member Portal",
                        f"{body.product} {rm(body.amount)} over {term} months — indicative maximum {rm(pol['max_financing'])}",
                        {"product": body.product, "amount": body.amount, "term": term,
                         "max_financing": pol["max_financing"], "binding": pol["max_financing_binding"]})
    keep = ("instalment", "rate", "rate_type", "total_profit", "total_payable", "existing_commitments",
            "total_obligations", "dsr", "dsr_ceiling", "headroom", "gross_monthly", "other_deductions",
            "deduction_ratio", "deduction_cap", "by_salary_deduction", "tenure_months", "equity", "exposure",
            "exposure_cap", "max_financing", "max_financing_binding", "max_financing_binding_label", "shortfall",
            "contract", "product_ms", "income")
    gates = [dict(id=g["id"], name=g["name"], passed=g["passed"], hard=g["hard"], required=g["required"],
                  actual=g["actual"]) for g in pol["gates"]]
    return {"product": body.product, "term": term, "amount": body.amount,
            "result": {k: pol[k] for k in keep}, "gates": gates, "within_policy": pol["result"] == "PASS",
            "explanation": policy_engine.max_financing_explanation(pol, None),
            "max_at_longest_term": longest["max_financing"], "longest_term": p["max_term"],
            "documents": [dict(en=d, ms=seed.DOC_MS.get(d, d)) for d in p["docs"]],
            "min_gross": seed.MIN_GROSS_SALARY,
            "disclaimer": {"en": "Indicative only — this is not an approval or an offer. The AI Credit Council and a KT "
                                 "officer make the decision after verifying your documents.",
                           "ms": "Anggaran sahaja — ini bukan kelulusan atau tawaran. Keputusan dibuat oleh Majlis "
                                 "Kredit AI dan pegawai KT selepas dokumen anda disahkan."}}


class MemberApply(BaseModel):
    product: str
    amount: float
    term: int
    purpose: str = ""


@app.post("/api/me/applications")
async def my_apply(body: MemberApply, request: Request):
    u = own_member(request)
    m = domain.MEMBERS[u["member_id"]]
    aid, case = _create_application(Intake(member_id=m["id"], product=body.product, amount=body.amount,
                                           term=body.term, purpose=body.purpose or "—", branch=m["branch"]),
                                    f"{m['name']} (member)", seed.STAFF["officer"], "KT Online (member portal)")
    return {"id": aid, "status": "Officer Review", "missing": case["documents_summary"]["missing"]}


# ===================================================== sensitive analytics
@app.get("/api/members/{mid}/distress")
async def member_distress(mid: str, request: Request):
    u = U(request)
    if u["role"] not in auth.DISTRESS_ROLES:
        raise HTTPException(403, "Financial-distress outlooks are restricted (POL-013)")
    m = domain.MEMBERS.get(mid)
    if not m:
        raise HTTPException(404, "member not found")
    _sensitive_access(u, mid, "financial-distress outlook")
    return dict(distress.MODEL.score(m), context=distress.CONTEXT)


@app.get("/api/crosssell")
async def crosssell_list(request: Request):
    u = U(request)
    if u["role"] not in auth.CROSSSELL_ROLES:
        raise HTTPException(403, "Cross-selling options are restricted (POL-013)")
    p = crosssell.portfolio(list(domain.MEMBERS.values()), store.get("crosssell_feedback", {}))
    if u["role"] == "marketing":                         # marketing never sees distress bands
        for r in p["rows"]:
            r.pop("distress", None)
    key = f"access:{u['username']}:crosssell:{clock.TODAY.isoformat()}"
    if not store.get(key):
        store.put(key, True)
        store.ledger_append("GOVERNANCE", "Sensitive Access", f"{u['name']} ({u['role_label']})",
                            "Opened the cross-selling list (POL-013)", {"rows": len(p["rows"])})
    return p


class Feedback(BaseModel):
    member_id: str
    product: str
    outcome: str      # Accepted | Declined | Not suitable | Contacted


@app.post("/api/crosssell/feedback")
async def crosssell_feedback(body: Feedback, request: Request):
    u = U(request)
    if u["role"] not in auth.CROSSSELL_ROLES:
        raise HTTPException(403, "Restricted")
    fb = store.get("crosssell_feedback", {})
    fb[f"{body.member_id}:{body.product}"] = dict(outcome=body.outcome, by=u["name"], at=clock.now_iso())
    store.put("crosssell_feedback", fb)
    store.ledger_append(f"MEM-{body.member_id}", "Cross-sell Feedback", f"{u['name']} ({u['role_label']})",
                        f"{body.product}: {body.outcome}", {"product": body.product, "outcome": body.outcome})
    return {"ok": True}


@app.post("/api/crosssell/draft")
async def crosssell_draft(body: Draft, request: Request):
    u = U(request)
    if u["role"] not in auth.CROSSSELL_ROLES:
        raise HTTPException(403, "Restricted")
    m = domain.MEMBERS.get(body.member_id)
    if not m:
        raise HTTPException(404, "member not found")
    if not m.get("marketing_consent") or m.get("dnc"):
        raise HTTPException(409, "This member has not consented to marketing contact.")
    return await _draft(body)


@app.get("/api/crosssell.csv")
async def crosssell_csv(request: Request):
    u = U(request)
    if u["role"] not in auth.CROSSSELL_ROLES:
        raise HTTPException(403, "Restricted")
    p = crosssell.portfolio(list(domain.MEMBERS.values()), store.get("crosssell_feedback", {}))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["member_id", "name", "branch", "offer", "identifies", "reason_chain", "score", "contactable"])
    for r in p["rows"]:
        w.writerow([r["member_id"], r["name"], r["branch"], r["product"], r["identifies"], " → ".join(r["chain"]),
                    r["score"], "yes" if r["contactable"] else "no"])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=kt_cross_sell_{clock.TODAY.isoformat()}.csv"})


@app.get("/api/support-tasks")
async def support_tasks(request: Request):
    staff(request)
    return {"rows": store.get("support_tasks", [])}


# ================================================================ sandbox
class Sim(BaseModel):
    dsr_ceiling: float | None = None
    exposure_multiple: float | None = None
    deduction_cap: float | None = None
    min_gross: float | None = None
    min_confidence: float | None = None
    max_pd: float | None = None


def _production() -> dict:
    o = store.get("policy_overrides", {})
    lim = store.autonomy()["limits"]
    return {"dsr_ceiling": o.get("dsr_ceiling"), "exposure_multiple": o.get("exposure_multiple", 4.0),
            "deduction_cap": o.get("deduction_cap", seed.DEDUCTION_CAP_PCT),
            "min_gross": o.get("min_gross", seed.MIN_GROSS_SALARY),
            "min_confidence": lim["min_confidence"], "max_pd": lim["max_pd"]}


def _replay_confidence(case: dict) -> float:
    """Council confidence for a case: the recorded run if there is one, else a deterministic replay of the
    Council's rule-based positions (no model call), so every frozen snapshot has a comparable figure."""
    if case.get("council"):
        return case["council"]["summary"]["confidence"]
    positions = [dict(id=a["id"], **council.prior(a["id"], case)) for a in council.AGENTS]
    ch = council.challenger_prior(case, positions)
    return council.synthesize(case, positions, ch)["confidence"]


@app.post("/api/sandbox/simulate")
async def simulate(body: Sim, request: Request):
    need(request, "sandbox")
    prod = _production()
    cand = dict(prod, **{k: v for k, v in body.model_dump().items() if v is not None})
    pol_keys = ("dsr_ceiling", "exposure_multiple", "deduction_cap", "min_gross")

    def outcome(case, th):
        conf = _replay_confidence(case)
        if case["policy"]["result"] == "FAIL": return "Decline", conf
        if case["documents_summary"]["missing"]: return "Request info", conf
        if case["risk"]["pd"] > th["max_pd"] or conf < th["min_confidence"]: return "Refer to officer", conf
        return "Approve", conf

    rows = []
    for a in domain.applications():
        if store.get(f"decision:{a['id']}"):
            continue
        base = domain.build_case(a["id"], {k: prod[k] for k in pol_keys})
        new = domain.build_case(a["id"], {k: cand[k] for k in pol_keys})
        bo, bc = outcome(base, prod)
        no, nc = outcome(new, cand)
        rows.append(dict(id=a["id"], name=new["member"]["name"], branch=a["branch"], product=a["product"],
                         service=new["member"].get("service_label"), amount=a["amount"],
                         before=bo, after=no, dsr=new["policy"]["dsr"], deduction=new["policy"]["deduction_ratio"],
                         pd=new["risk"]["pd"], confidence=nc, binding=new["policy"]["max_financing_binding"],
                         failures=new["policy"]["failures"], max_before=base["policy"]["max_financing"],
                         max_after=new["policy"]["max_financing"]))

    def agg(key):
        outs = [r[key] for r in rows]
        appr = [r for r in rows if r[key] == "Approve"]
        exposure = sum(r["amount"] for r in appr)
        pdw = sum(r["pd"] * r["amount"] for r in appr) / max(1, exposure)
        return {"approve": outs.count("Approve"), "refer": outs.count("Refer to officer"),
                "request": outs.count("Request info"), "decline": outs.count("Decline"), "exposure": exposure,
                "predicted_delinquency": round(pdw * 100, 2),
                "approval_rate": round(outs.count("Approve") / max(1, len(outs)) * 100, 1),
                "capacity": sum(r["max_before" if key == "before" else "max_after"] for r in rows)}
    changed = [r for r in rows if r["before"] != r["after"]]
    segs: dict = {}
    for r in changed:
        for dim in ("product", "branch", "service"):
            segs.setdefault(dim, {}).setdefault(r[dim], 0)
            segs[dim][r[dim]] += 1
    binding: dict = {}
    for r in rows:
        binding[r["binding"]] = binding.get(r["binding"], 0) + 1
    rec = {"production": prod, "candidate": cand, "baseline": agg("before"), "candidate_result": agg("after"),
           "changed": changed, "segments": segs, "binding": binding, "cases": len(rows),
           "policy_version": store.get("policy_version", "v4.0"),
           "note": "Simulation replays the frozen snapshot of every open case. Nothing in production changes until "
                   "a proposal is approved by a second Board member."}
    return rec


class Promote(BaseModel):
    thresholds: dict
    justification: str = ""


@app.post("/api/sandbox/promote")
async def promote(body: Promote, request: Request):
    u = need(request, "sandbox")
    if not body.justification.strip():
        raise HTTPException(400, "A policy change requires a written justification.")
    allowed = {"dsr_ceiling", "exposure_multiple", "deduction_cap", "min_gross", "min_confidence", "max_pd"}
    th = {k: v for k, v in body.thresholds.items() if k in allowed and v is not None}
    if not th:
        raise HTTPException(400, "No threshold changes to propose.")
    props = store.get("policy_changes", [])
    rec = dict(id=f"PC-{len(props) + 1:03d}", thresholds=th, before={k: _production().get(k) for k in th},
               actor=u["name"], actor_username=u["username"], role=u["role_label"], justification=body.justification,
               at=clock.now_iso(), status="Pending Board approval")
    store.put("policy_changes", [rec] + props)
    store.ledger_append("GOVERNANCE", "Policy Change Proposed", f"{u['name']} ({u['role_label']})",
                        f"{rec['id']}: " + ", ".join(f"{k.replace('_', ' ')} {'product default' if rec['before'].get(k) is None else rec['before'].get(k)} → {v}"
                                                     for k, v in th.items()), rec)
    return {"ok": True, "record": rec, "note": "Recorded as pending. Production is unchanged until a Board member "
                                               "other than the proposer approves it."}


class Review(BaseModel):
    approve: bool
    note: str = ""


@app.post("/api/sandbox/proposals/{pid}")
async def review_proposal(pid: str, body: Review, request: Request):
    u = U(request)
    if u["role"] != "board":
        raise HTTPException(403, "Only the Board can approve a policy change")
    props = store.get("policy_changes", [])
    rec = next((p for p in props if p["id"] == pid), None)
    if not rec:
        raise HTTPException(404, "proposal not found")
    if rec["status"] != "Pending Board approval":
        raise HTTPException(409, f"Already {rec['status'].lower()}")
    if rec.get("actor_username") == u["username"]:
        raise HTTPException(403, "The proposer cannot approve their own change — a second Board member must.")
    rec.update(status="Approved — in force" if body.approve else "Rejected", reviewed_by=u["name"],
               reviewed_at=clock.now_iso(), review_note=body.note)
    if body.approve:
        o = store.get("policy_overrides", {})
        for k in ("dsr_ceiling", "exposure_multiple", "deduction_cap", "min_gross"):
            if k in rec["thresholds"]:
                o[k] = rec["thresholds"][k]
        store.put("policy_overrides", o)
        lim = {k: rec["thresholds"][k] for k in ("min_confidence", "max_pd") if k in rec["thresholds"]}
        if lim:
            a = store.autonomy()
            store.set_autonomy({"limits": dict(a["limits"], **lim)}, f"{u['name']} (Board)")
        v = store.get("policy_version", "v4.0")
        major, minor = v[1:].split(".")
        store.put("policy_version", f"v{major}.{int(minor) + 1}")
        rec["policy_version"] = store.get("policy_version")
    store.put("policy_changes", props)
    store.ledger_append("GOVERNANCE", "Policy Change Approved" if body.approve else "Policy Change Rejected",
                        f"{u['name']} (Board)", f"{pid} {'approved — now in force as ' + rec.get('policy_version', '') if body.approve else 'rejected'}"
                        + (f": {body.note}" if body.note else ""), rec)
    return rec


# ============================================================= governance
def _fairness(rows: list[dict]) -> list[dict]:
    total = len(rows) or 1
    overall = sum(1 for r in rows if r["policy"] == "PASS") / total * 100
    out = []
    for dim, label in (("branch", "Branch"), ("service", "Service"), ("product", "Product")):
        groups: dict = {}
        for r in rows:
            groups.setdefault(r.get(dim) or "—", []).append(r)
        for k, g in groups.items():
            rate = sum(1 for r in g if r["policy"] == "PASS") / len(g) * 100
            out.append(dict(segment=f"{label} — {seed.SERVICE_LABEL.get(k, k)}", approval=round(rate, 1), n=len(g),
                            delta=round(rate - overall, 1), flag=len(g) >= 3 and abs(rate - overall) >= 15))
    out.sort(key=lambda x: (not x["flag"], -abs(x["delta"])))
    return out[:10]


@app.get("/api/governance")
async def governance(request: Request):
    need(request, "governance", "cockpit")
    return _governance()


def _governance(rows: list[dict] | None = None):
    rows = rows if rows is not None else domain.queue_rows()
    apps = domain.applications()
    councils = [c for c in (store.get(f"council:{a['id']}") for a in apps) if c]
    decisions = [d for d in (store.get(f"decision:{a['id']}") for a in apps) if d]
    overrides = [d for d in decisions if d.get("override")]
    gsum = lambda k: sum(c["grounding"].get(k, 0) for c in councils)
    return {
        "models": [
            dict(name="Credit Risk", version=MODEL.version, status="Healthy", trained_on=MODEL.trained_on,
                 calibration="isotonic, 3-fold", drift=0.03, auc=0.81,
                 note="Ensemble of logistic regression and gradient boosting with probability calibration."),
            dict(name="Financial Distress (possible bankruptcy)", version=distress.MODEL.version, status="Healthy",
                 trained_on=distress.MODEL.trained_on, calibration=f"cohort base rate {distress.MODEL.base_rate*100:.2f}% "
                 "(cited: ~0.3% of civil servants)", drift=0.01, auc=None,
                 note="Logistic model with reason codes. Decision support only; restricted to authorised roles (POL-013)."),
            dict(name="Fraud & Integrity", version="fraud-v4.0.0", status="Healthy", trained_on=3000,
                 calibration="rules + isolation forest + graph", drift=0.05, auc=None,
                 note="Unsupervised. A high score is an investigation signal, never a finding."),
            dict(name="Early Warning (longitudinal)", version="lmi-v4.0.0", status="Healthy", trained_on=None,
                 calibration="CUSUM + logistic forecast", drift=0.02, auc=None,
                 note="Per-member baselines; alerts use hysteresis to avoid flapping."),
            dict(name="Assistants & Council LLM", version=llm.status().get("model", "n/a"), status="Local",
                 trained_on=None, calibration="grounded generation with figure checking", drift=None, auc=None,
                 note="Runs on this machine. Every figure is checked against the engines' facts."),
        ],
        "distress_card": {"base_rate": distress.MODEL.base_rate, "positives": distress.MODEL.positives,
                          "trained_on": distress.MODEL.trained_on, "features": [l for _, l in distress.FEATURES],
                          "context": distress.CONTEXT,
                          "guardrails": ["Never triggers an automatic adverse action",
                                         "Visible only to Senior Officer, Collections, Risk, Compliance and Branch Manager",
                                         "Board sees aggregates only", "Every view is written to the ledger",
                                         "PDPA 2010: used for member support, not marketing"]},
        "decisions": len(decisions), "overrides": len(overrides),
        "override_rate": round(len(overrides) / max(1, len(decisions)) * 100, 1),
        "override_detail": [dict(case=a["id"], **d) for a in apps
                            for d in [store.get(f"decision:{a['id']}")] if d and d.get("override")],
        "council_runs": len(councils),
        "avg_confidence": round(sum(c["summary"]["confidence"] for c in councils) / max(1, len(councils)), 2),
        "avg_disagreement": round(sum(c["summary"]["disagreement"] for c in councils) / max(1, len(councils)), 2),
        "grounding": {"unsupported_citations": gsum("unsupported"), "numeric_rewrites": gsum("numeric_rewrites"),
                      "llm_positions": gsum("llm_positions"), "total_positions": gsum("total_positions")},
        "fairness": _fairness(rows),
        "autonomy": store.autonomy(), "ledger": store.ledger_verify(),
        "policy_changes": store.get("policy_changes", []), "policy_version": store.get("policy_version", "v4.0"),
        "production": _production(),
        "queue_health": {"sla_breach": len([r for r in rows if r["next"] == "Request docs"]),
                         "unassigned": 0, "open": len([r for r in rows if not r["decided"]])},
    }


class AutonomyPatch(BaseModel):
    mode: str | None = None
    kill_switch: bool | None = None
    limits: dict | None = None


@app.post("/api/governance/autonomy")
async def set_autonomy(body: AutonomyPatch, request: Request):
    u = U(request)
    if u["role"] != "board":
        raise HTTPException(403, "The Autonomy Dial is Board-controlled")
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if "mode" in patch and patch["mode"] not in store.autonomy()["modes"]:
        raise HTTPException(400, "Unknown mode")
    cur = store.set_autonomy(patch, f"{u['name']} (Board)")
    store.append_list("notifications", dict(kind="governance", tone="amber", title="Autonomy configuration changed",
                                            detail=f"Mode {cur['mode']}, kill switch {'ON' if cur['kill_switch'] else 'off'}",
                                            at=cur["changed_at"], link="governance"))
    return cur


# ================================================================== ledger
@app.get("/api/ledger")
async def ledger(request: Request, case_id: str = "", limit: int = 300):
    need(request, "ledger", "governance")
    return {"rows": store.ledger_read(case_id or None, min(limit, 1000)), "verification": store.ledger_verify()}


@app.get("/api/ledger/reconstruct/{aid}")
async def reconstruct(aid: str, request: Request):
    need(request, "ledger", "governance")
    case = domain.build_case(aid)
    if not case:
        raise HTTPException(404, "case not found")
    cr = store.get(f"council:{aid}")
    ex = store.get(f"execution:{aid}")
    p = case["policy"]
    return {
        "steps": [
            dict(n=1, title="Case snapshot", kind="snapshot", detail=case["snapshot"],
                 summary=f"Frozen {case['snapshot']['frozen_at']} — {case['snapshot']['hash']}"),
            dict(n=2, title="Documents & evidence", kind="documents",
                 detail=[dict(id=d["id"], type=d["doc_type"], status=d["status"], confidence=d["confidence"],
                              hash=d.get("sha256") or docs_engine.sha(d["file"])) for d in case["documents"]],
                 summary=f"{len(case['documents'])} documents registered"),
            dict(n=3, title="Policy result", kind="gates", detail=p["gates"],
                 summary=f"{p['result']} — DSR {p['dsr']}%, maximum {rm(p['max_financing'])}"),
            dict(n=4, title="Model outputs", kind="models",
                 detail={"risk": {k: case["risk"][k] for k in ("pd", "grade", "score", "reason_codes", "model_version")},
                         "fraud": {k: case["fraud"][k] for k in ("score", "level", "model_version")}},
                 summary=f"PD {case['risk']['pd']*100:.1f}%, integrity {case['fraud']['level']}"),
            dict(n=5, title="Agent opinions", kind="positions",
                 detail=[{k: x.get(k) for k in ("name", "stance", "headline", "reasoning", "confidence", "evidence", "_source")}
                         for x in (cr or {}).get("positions", [])],
                 summary=f"{len((cr or {}).get('positions', []))} specialist positions"),
            dict(n=6, title="Challenger", kind="challenger", detail=(cr or {}).get("challenger"),
                 summary=(cr or {}).get("challenger", {}).get("headline", "Not run")),
            dict(n=7, title="Final recommendation", kind="summary", detail=(cr or {}).get("summary"),
                 summary=(cr or {}).get("summary", {}).get("recommendation", "Not run")),
            dict(n=8, title="Autonomy routing", kind="routing", detail=case["routing"],
                 summary=f"{case['routing']['path']} under {case['routing']['mode']}"),
            dict(n=9, title="Human decision", kind="decision", detail=case["decision"],
                 summary=(case["decision"] or {}).get("action", "Pending")),
            dict(n=10, title="Execution", kind="execution", detail=ex, summary=(ex or {}).get("account", "Not executed")),
            dict(n=11, title="Outcome & monitoring", kind="monitoring", detail=case["lmi"]["state"],
                 summary=f"Member state {case['lmi']['state']['state']}"),
        ],
        "ledger": store.ledger_read(aid, 100),
        "verification": store.ledger_verify(),
    }


# ============================================================ misc surface
@app.get("/api/search")
async def search(q: str, request: Request):
    u = staff(request)
    ql = q.lower().strip()
    out = []
    if not ql:
        return {"rows": []}
    if auth.can(u, "members"):
        for m in domain.MEMBERS.values():
            if ql in m["name"].lower() or ql in m["id"] or ql in m.get("service_no", "").lower():
                out.append(dict(kind="Member", id=m["id"], title=m["name"],
                                sub=f"{m['service_label']} · {m['branch']} · {rm(m['outstanding'])} outstanding",
                                link=f"members:{m['id']}"))
    if auth.can(u, "applications"):
        for a in domain.applications():
            mem = domain.MEMBERS.get(a["member_id"], {})
            if ql in a["id"].lower() or ql in mem.get("name", "").lower() or ql in a["product"].lower():
                out.append(dict(kind="Application", id=a["id"], title=f"{a['id']} — {mem.get('name', '')}",
                                sub=f"{a['product']} {rm(a['amount'])} · {a['status']}", link=f"workbench:{a['id']}"))
    if auth.can(u, "documents"):
        for d in domain.documents():
            if ql in d["label"].lower() or ql in d["doc_type"].lower() or ql in (d.get("doc_type_ms") or "").lower():
                out.append(dict(kind="Document", id=d["id"], title=d["label"],
                                sub=f"{d['doc_type']} · {d['app_id']} · {d['status']}", link=f"documents:{d['id']}"))
    for p in seed.POLICY_LIBRARY:
        if ql in p["title"].lower() or ql in p["text"].lower():
            out.append(dict(kind="Policy", id=p["id"], title=f"{p['id']} {p['title']}", sub=p["text"][:110] + "…",
                            link="governance" if auth.can(u, "governance") else ""))
    if auth.can(u, "ledger"):
        for r in store.ledger_read(limit=200):
            if ql in r["summary"].lower() or ql in (r["case_id"] or "").lower():
                out.append(dict(kind="Ledger", id=str(r["seq"]), title=f"{r['stage']} — {r['case_id']}",
                                sub=r["summary"][:110], link=f"ledger:{r['case_id']}"))
    return {"rows": out[:25]}


@app.get("/api/notifications")
async def notifications(request: Request):
    staff(request)
    base = store.get("notifications", [])
    if not base:
        k = domain.portfolio()["kpis"]
        base = [dict(kind="system", tone="blue", title="Platform ready",
                     detail=f"{k['pipeline']} live applications, {k['early_warnings']} members in early warning",
                     at=clock.now_iso(), link="overview")]
    return {"rows": base[:40], "support": store.get("support_tasks", [])[:10]}


@app.get("/api/cockpit")
async def cockpit(request: Request):
    u = need(request, "cockpit")
    rows = domain.queue_rows()
    p = domain.portfolio(rows)
    coll = _collections()
    members = list(domain.MEMBERS.values())
    dp = distress.portfolio(members)
    cs = crosssell.portfolio(members, store.get("crosssell_feedback", {}))
    return {"portfolio": p, "governance": _governance(rows),
            "collections": {"balance": coll["total_balance"], "expected": coll["total_ev"], "cases": len(coll["rows"])},
            "products": _by(rows, "product"), "branches": _by(rows, "branch"), "officers": _by(rows, "officer"),
            "services": _by(rows, "service"),
            "distress": {k: dp[k] for k in ("bands", "by_branch", "expected_cases_12m", "members", "context")},
            "crosssell": cs["summary"]}


def _by(rows, key):
    out = {}
    for r in rows:
        k = seed.SERVICE_LABEL.get(r[key], r[key]) if key == "service" else r[key]
        d = out.setdefault(k, {"count": 0, "amount": 0, "pd": 0.0})
        d["count"] += 1
        d["amount"] += r["amount"]
        d["pd"] += r["pd"] * r["amount"]
    for k, d in out.items():
        d["pd"] = round(d["pd"] / max(1, d["amount"]) * 100, 2)
    return out


# ================================================================ frontend
FRONT = os.path.join(ROOT, "frontend")
app.mount("/", StaticFiles(directory=FRONT, html=True), name="static")
