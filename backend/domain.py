"""Case assembly — freezes a CaseSnapshot and runs every deterministic engine."""
from __future__ import annotations
import copy, hashlib, json, datetime as dt
import seed, store, docgen
from clock import TODAY
from connectors import ccris
from engines import policy as policy_engine, fraud as fraud_engine, docs as docs_engine, lmi as lmi_engine
from engines.risk import MODEL

MEMBERS = {m["id"]: m for m in seed.members()}


def applications() -> list[dict]:
    return store.get("applications") or copy.deepcopy(seed.APPLICATIONS)


def save_applications(apps): store.put("applications", apps)


_SEEDED: list[dict] | None = None


def seeded_documents() -> list[dict]:
    global _SEEDED
    if _SEEDED is None:
        _SEEDED = docgen.documents(MEMBERS, seed.APPLICATIONS)
    return _SEEDED


def documents() -> list[dict]:
    """Generated evidence for the seeded cases plus everything uploaded since."""
    return seeded_documents() + store.get("uploaded_documents", [])


def add_document(doc: dict):
    store.put("uploaded_documents", store.get("uploaded_documents", []) + [doc])


def app_by_id(aid: str) -> dict | None:
    return next((a for a in applications() if a["id"] == aid), None)


def docs_for(aid: str) -> list[dict]:
    return [d for d in documents() if d["app_id"] == aid]


def required_docs(app: dict) -> list[str]:
    return seed.PRODUCTS[app["product"]]["docs"]


def history_features(member: dict) -> dict:
    lates = [p["days_late"] for p in member["payments"]]
    return {
        "max_days_late": max(lates) if lates else 0,
        "recent_inquiries": ccris.report(member)["recent_inquiries"],
        "utilisation": min(100, round(member["outstanding"] / max(1, member["savings"] + member["share_capital"]) * 40, 1)),
        "on_time_rate": round(sum(1 for l in lates if l <= 2) / len(lates) * 100, 1) if lates else 100,
    }


def snapshot_hash(app, member, docs) -> str:
    body = json.dumps({"a": app, "m": {k: v for k, v in member.items() if k != "payments"},
                       "d": [d["id"] for d in docs]}, sort_keys=True, default=str)
    return "snap:" + hashlib.sha256(body.encode()).hexdigest()[:20]


def member_for(app: dict) -> dict:
    return MEMBERS.get(app["member_id"]) or dict(MEMBERS["104328"], id=app["member_id"],
                                                 name=app.get("applicant_name", "New Applicant"))


# case assembly is pure given (store version, thresholds) — cache it so the cockpit and portfolio
# views, which touch every case several times, stay fast
_CACHE: dict = {}


def build_case(aid: str, thresholds: dict | None = None) -> dict | None:
    key = (aid, json.dumps(thresholds or {}, sort_keys=True), store.VERSION[0])
    hit = _CACHE.get(key)
    if hit is not None:
        return dict(hit)
    case = _build_case(aid, thresholds)
    if case is not None:
        if len(_CACHE) > 4000:
            _CACHE.clear()
        _CACHE[key] = case
        return dict(case)
    return None


def _build_case(aid: str, thresholds: dict | None = None) -> dict | None:
    app = app_by_id(aid)
    if not app:
        return None
    member = member_for(app)
    docs = docs_for(aid)
    required = required_docs(app)

    extract = docs_engine.extract_summary(docs)
    # Board-approved policy changes are in force for every case; a sandbox replay layers its candidate on top
    effective = {**store.get("policy_overrides", {}), **(thresholds or {})}
    pol = policy_engine.assess(app, member, extract, effective)
    pol["policy_version"] = store.get("policy_version", "v4.0")
    comp = docs_engine.completeness(app, docs, required)
    recon = docs_engine.reconcile(app, member, docs)
    fr = fraud_engine.assess(member, app, docs, applications_90d={"104265": 4, "104310": 3}.get(member["id"], 1))
    feats = MODEL.features_for(member, app, pol, history_features(member))
    rk = MODEL.score(feats)
    lm = lmi_engine.analyse(member)

    case = {
        "application": app,
        "member": {k: v for k, v in member.items() if k not in ("payments", "pattern")},
        "member_payments": member["payments"],
        "policy": pol, "risk": rk, "fraud": fr,
        "documents": docs, "documents_summary": comp, "reconciliation": recon,
        "forensics": docs_engine.forensics_report(docs),
        "lmi": lm,
        "risk_features": feats,
        "snapshot": {"hash": snapshot_hash(app, member, docs),
                     "frozen_at": app.get("snapshot_at", app["submitted"]),
                     "policy_version": pol["policy_version"], "model_version": rk["model_version"],
                     "documents": [d["id"] for d in docs]},
    }
    case["policy"]["max_financing_note"] = policy_engine.max_financing_explanation(pol, app["amount"])
    case["decision_factors"] = policy_engine.decision_factors(pol, rk, fr, comp)
    case["counterfactuals"] = policy_engine.counterfactuals(pol, rk, fr, comp, app["amount"])
    case["council"] = store.get(f"council:{aid}")
    case["decision"] = store.get(f"decision:{aid}")
    case["routing"] = store.route(case)
    case["pipeline"] = docs_engine.PIPELINE
    return case


def queue_row(app: dict) -> dict:
    case = build_case(app["id"])
    m = case["member"]
    council = case.get("council")
    return {
        "id": app["id"], "member_id": app["member_id"], "name": m["name"], "initials": m["initials"],
        "product": app["product"], "amount": app["amount"], "term": app["term"], "branch": app["branch"],
        "status": app["status"], "officer": app["officer"], "submitted": app["submitted"],
        "service": m.get("service"),
        "risk": case["risk"]["grade"], "pd": case["risk"]["pd"], "score": case["risk"]["score"],
        "dsr": case["policy"]["dsr"], "policy": case["policy"]["result"],
        "deduction_ratio": case["policy"]["deduction_ratio"],
        "max_financing": case["policy"]["max_financing"],
        "docs": {"v": case["documents_summary"]["verified"], "t": case["documents_summary"]["required"]},
        "missing": case["documents_summary"]["missing"],
        "fraud": case["fraud"]["level"],
        "recommendation": (council or {}).get("summary", {}).get("recommendation", "Not run"),
        "confidence": (council or {}).get("summary", {}).get("confidence"),
        "disagreement": (council or {}).get("summary", {}).get("disagreement"),
        "route": case["routing"]["path"], "authority": case["policy"]["authority_required"],
        "decided": bool(case["decision"]), "decision": (case["decision"] or {}).get("action"),
        "lmi_state": case["lmi"]["state"]["state"],
        "next": _next_action(case),
    }


def _next_action(case: dict) -> str:
    if case["decision"]: return "Decided"
    if case["fraud"]["level"] in ("Critical", "Elevated"): return "Investigate"
    if case["documents_summary"]["missing"]: return "Request docs"
    if case["policy"]["result"] == "FAIL": return "Decline review"
    if not case["council"]: return "Run Council"
    return "Officer decision"


def queue_rows() -> list[dict]:
    return [queue_row(a) for a in applications()]


def portfolio(rows: list[dict] | None = None) -> dict:
    rows = rows if rows is not None else queue_rows()
    alerts = [lmi_engine.analyse(m) for m in MEMBERS.values()]
    warn = [a for a in alerts if a["state"]["state"] in ("ELEVATED", "AT_RISK", "WATCH")]
    approved = sum(1 for r in rows if r["decision"] == "Approve")
    risk_mix = {}
    for r in rows:
        risk_mix[r["risk"]] = risk_mix.get(r["risk"], 0) + 1
    exposure = sum(r["amount"] for r in rows)
    pd_w = sum(r["pd"] * r["amount"] for r in rows) / max(1, exposure)
    today = TODAY.isoformat()
    return {
        "kpis": {
            # platform-wide intake today (the trend) — the queue holds the cases that need a person
            "applications_today": seed.TREND[-1]["a"] if seed.TREND[-1]["date"] == today else
                                  len([r for r in rows if r["submitted"][:10] == today]),
            "pipeline": len(rows),
            "approval_rate": round(sum(t["ap"] for t in seed.TREND) / sum(t["a"] for t in seed.TREND) * 100, 1),
            "avg_processing": "1.6 days",
            "predicted_delinquency": round(pd_w * 100, 2),
            "exposure": exposure,
            "early_warnings": len([a for a in alerts if a["state"]["state"] in ("ELEVATED", "AT_RISK")]),
            "decided": sum(1 for r in rows if r["decided"]),
            "approved": approved,
            "members": len(MEMBERS),
        },
        "trend": seed.TREND,
        "risk_mix": risk_mix,
        "queue": sorted(rows, key=lambda r: (r["decided"], -r["amount"]))[:8],
        "early_warning": sorted(warn, key=lambda a: -a["forecast"]["p_late_30d"])[:5],
        "highlights": highlights(rows, alerts),
        "recent_documents": sorted(documents(), key=lambda d: d["uploaded"], reverse=True)[:5],
        "autonomy": store.autonomy(),
        "ledger": store.ledger_verify(),
        "today": today,
    }


def highlights(rows, alerts) -> list[dict]:
    h = []
    fr = [r for r in rows if r["fraud"] in ("Critical", "Elevated")]
    if fr:
        h.append(dict(tone="red", title=f"{len(fr)} case(s) carry an integrity investigation signal",
                      detail=", ".join(r["name"] for r in fr[:3]) + " — investigation signal, not proven fraud.",
                      action="applications"))
    dr = [a for a in alerts if a["state"]["state"] in ("ELEVATED", "AT_RISK")]
    if dr:
        dr.sort(key=lambda a: -a["forecast"]["p_late_30d"])
        h.append(dict(tone="amber", title=f"{len(dr)} member(s) drifting from their own payment baseline",
                      detail=f"Led by {dr[0]['name']} — {dr[0]['why_now'][:110]}", action="early-warning"))
    cap = [r for r in rows if r["deduction_ratio"] and r["deduction_ratio"] > seed.DEDUCTION_CAP_PCT and not r["decided"]]
    if cap:
        h.append(dict(tone="amber", title=f"{len(cap)} case(s) breach the {seed.DEDUCTION_CAP_PCT}% salary-deduction cap",
                      detail=", ".join(r["name"] for r in cap[:3]) + " — total deductions would exceed 60% of gross pay.",
                      action="applications"))
    rec = [a for a in alerts if a["state"]["state"] == "RECOVERY"]
    if rec:
        h.append(dict(tone="green", title=f"{len(rec)} member(s) meeting recovery criteria",
                      detail=f"{rec[0]['name']} has returned to on-time deductions for 3 consecutive cycles.",
                      action="early-warning"))
    md = [r for r in rows if r["docs"]["v"] < r["docs"]["t"] and not r["decided"]]
    if md:
        h.append(dict(tone="blue", title=f"{len(md)} case(s) waiting on mandatory evidence",
                      detail="Requesting documents early is the single biggest driver of turnaround time.",
                      action="applications"))
    return h
