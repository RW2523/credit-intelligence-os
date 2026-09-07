"""State: seeded demo domain in memory + SQLite for everything mutable
(decisions, uploads, ledger, governance config, notifications)."""
from __future__ import annotations
import sqlite3, json, hashlib, datetime as dt, os, threading

DB = os.path.join(os.path.dirname(__file__), "..", "data", "cios.db")
_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ledger (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, case_id TEXT, stage TEXT,
  actor TEXT, summary TEXT, payload TEXT, prev_hash TEXT, hash TEXT);
CREATE INDEX IF NOT EXISTS ledger_case ON ledger(case_id);
"""


def conn():
    c = sqlite3.connect(DB, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    with conn() as c:
        c.executescript(SCHEMA)


# ------------------------------------------------------------------- kv
def get(key, default=None):
    with conn() as c:
        r = c.execute("SELECT v FROM kv WHERE k=?", (key,)).fetchone()
    return json.loads(r["v"]) if r else default


def put(key, value):
    with _lock, conn() as c:
        c.execute("INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                  (key, json.dumps(value)))
    return value


def append_list(key, item, cap=400):
    lst = get(key, [])
    lst.insert(0, item)
    return put(key, lst[:cap])


# --------------------------------------------------------------- ledger
def ledger_append(case_id: str, stage: str, actor: str, summary: str, payload: dict) -> dict:
    with _lock, conn() as c:
        prev = c.execute("SELECT hash FROM ledger ORDER BY seq DESC LIMIT 1").fetchone()
        prev_hash = prev["hash"] if prev else "genesis"
        at = dt.datetime.now().isoformat(timespec="seconds")
        body = json.dumps(payload, sort_keys=True, default=str)
        h = hashlib.sha256(f"{prev_hash}|{at}|{case_id}|{stage}|{actor}|{summary}|{body}".encode()).hexdigest()
        cur = c.execute(
            "INSERT INTO ledger(at,case_id,stage,actor,summary,payload,prev_hash,hash) VALUES(?,?,?,?,?,?,?,?)",
            (at, case_id, stage, actor, summary, body, prev_hash, h))
        seq = cur.lastrowid
    return dict(seq=seq, at=at, case_id=case_id, stage=stage, actor=actor,
                summary=summary, payload=payload, prev_hash=prev_hash, hash=h)


def ledger_read(case_id: str | None = None, limit: int = 300) -> list[dict]:
    q = "SELECT * FROM ledger"
    args: tuple = ()
    if case_id:
        q += " WHERE case_id=?"
        args = (case_id,)
    q += " ORDER BY seq DESC LIMIT ?"
    with conn() as c:
        rows = c.execute(q, args + (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["payload"] = json.loads(d["payload"])
        out.append(d)
    return out


def ledger_verify() -> dict:
    with conn() as c:
        rows = c.execute("SELECT * FROM ledger ORDER BY seq ASC").fetchall()
    prev = "genesis"
    broken = []
    for r in rows:
        h = hashlib.sha256(
            f"{prev}|{r['at']}|{r['case_id']}|{r['stage']}|{r['actor']}|{r['summary']}|{r['payload']}".encode()
        ).hexdigest()
        if h != r["hash"] or r["prev_hash"] != prev:
            broken.append(r["seq"])
        prev = r["hash"]
    return {"records": len(rows), "intact": not broken, "broken": broken,
            "head": prev if rows else "genesis"}


# --------------------------------------------------------- governance cfg
DEFAULT_AUTONOMY = {
    "mode": "ASSIST",
    "modes": ["SHADOW", "ADVISE", "ASSIST", "ACT_WITH_APPROVAL", "AUTONOMOUS_WITHIN_LIMITS"],
    "kill_switch": False,
    "limits": {"max_amount": 15000, "max_pd": 0.05, "min_confidence": 0.88,
               "max_disagreement": 0.15, "products": ["Personal Loan", "Auto Loan", "Education Loan"],
               "require_complete_docs": True, "max_fraud_score": 0.2},
    "approved_by": "Board Resolution 2024-04",
    "changed_at": "2024-04-01T09:00:00",
}
DEFAULT_THRESHOLDS = {"dsr_ceiling": None, "exposure_multiple": 4.0, "min_confidence": 0.75}


def autonomy() -> dict:
    return get("autonomy", DEFAULT_AUTONOMY)


def set_autonomy(patch: dict, actor: str) -> dict:
    cur = autonomy()
    cur.update(patch)
    cur["changed_at"] = dt.datetime.now().isoformat(timespec="seconds")
    cur["changed_by"] = actor
    put("autonomy", cur)
    ledger_append("GOVERNANCE", "Autonomy Change", actor,
                  f"Autonomy set to {cur['mode']}; kill switch {'ON' if cur['kill_switch'] else 'off'}", cur)
    return cur


def route(case: dict) -> dict:
    """Autonomy Dial routing — the ONLY path to autonomous execution."""
    a = autonomy()
    lim, s = a["limits"], case["council"]["summary"] if case.get("council") else None
    reasons = []
    if a["kill_switch"]:
        return {"path": "HUMAN", "mode": a["mode"], "autonomous": False,
                "reasons": ["Kill switch is engaged — all autonomous execution is stopped"]}
    if a["mode"] in ("SHADOW", "ADVISE", "ASSIST"):
        reasons.append(f"Autonomy mode {a['mode']} does not permit execution by the system")
    if not s:
        reasons.append("Council has not yet deliberated on this case")
    else:
        if s["recommendation"] != "APPROVE":
            reasons.append(f"Council recommendation is {s['recommendation']}, not APPROVE")
        if s["confidence"] < lim["min_confidence"]:
            reasons.append(f"Confidence {s['confidence']} below the Board limit of {lim['min_confidence']}")
        if s["disagreement"] > lim["max_disagreement"]:
            reasons.append(f"Agent disagreement {s['disagreement']} above the limit of {lim['max_disagreement']}")
    if case["application"]["amount"] > lim["max_amount"]:
        reasons.append(f"Amount ${case['application']['amount']:,} above the autonomous limit of ${lim['max_amount']:,}")
    if case["risk"]["pd"] > lim["max_pd"]:
        reasons.append(f"Probability of default {case['risk']['pd']:.3f} above the limit of {lim['max_pd']}")
    if case["application"]["product"] not in lim["products"]:
        reasons.append(f"{case['application']['product']} is not in the autonomous product set")
    if lim["require_complete_docs"] and not case["documents_summary"]["complete"]:
        reasons.append("Mandatory evidence is incomplete")
    if case["fraud"]["score"] > lim["max_fraud_score"]:
        reasons.append(f"Integrity score {case['fraud']['score']} above the limit of {lim['max_fraud_score']}")

    if reasons:
        return {"path": "HUMAN", "mode": a["mode"], "autonomous": False, "reasons": reasons,
                "authority": case["policy"]["authority_required"]}
    return {"path": "AUTONOMOUS", "mode": a["mode"], "autonomous": True,
            "reasons": ["Every Board-set autonomy condition is satisfied"],
            "authority": case["policy"]["authority_required"]}
