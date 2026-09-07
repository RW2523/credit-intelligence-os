"""Case assembly — freezes a CaseSnapshot and runs every deterministic engine."""
from __future__ import annotations
import copy, hashlib, json, datetime as dt
import seed, store
from engines import policy as policy_engine, fraud as fraud_engine, docs as docs_engine, lmi as lmi_engine
from engines.risk import MODEL

MEMBERS = {m["id"]: m for m in seed.members()}


def applications() -> list[dict]:
    base = copy.deepcopy(seed.APPLICATIONS)
    return store.get("applications", base)


def save_applications(apps): store.put("applications", apps)


def _base_documents() -> list[dict]:
    return copy.deepcopy(seed.DOCUMENTS) + seed.generated_documents(MEMBERS)


def documents() -> list[dict]:
    return store.get("documents", _base_documents())


def save_documents(docs): store.put("documents", docs)


def app_by_id(aid: str) -> dict | None:
    return next((a for a in applications() if a["id"] == aid), None)


def docs_for(aid: str) -> list[dict]:
    return [d for d in documents() if d["app_id"] == aid]


def required_docs(app: dict) -> list[str]:
    return seed.REQUIRED_BY_APP.get(app["id"], seed.PRODUCTS[app["product"]]["docs"])


def history_features(member: dict) -> dict:
    lates = [p["days_late"] for p in member["payments"]]
    return {
        "max_days_late": max(lates) if lates else 0,
        "recent_inquiries": {"104328": 3, "104310": 5, "104265": 4}.get(member["id"], 1),
        "utilisation": min(100, round(member["outstanding"] / max(1, member["savings"] + member["share_capital"]) * 40, 1)),
        "on_time_rate": round(sum(1 for l in lates if l <= 2) / len(lates) * 100, 1) if lates else 100,
    }


def snapshot_hash(app, member, docs) -> str:
    body = json.dumps({"a": app, "m": {k: v for k, v in member.items() if k != "payments"},
                       "d": [d["id"] for d in docs]}, sort_keys=True, default=str)
    return "snap:" + hashlib.sha256(body.encode()).hexdigest()[:20]


def build_case(aid: str, thresholds: dict | None = None) -> dict | None:
    app = app_by_id(aid)
    if not app:
        return None
    member = MEMBERS.get(app["member_id"]) or dict(MEMBERS["104328"], id=app["member_id"],
                                                   name=app.get("applicant_name", "New Applicant"))
    docs = docs_for(aid)
    required = required_docs(app)

    extract = docs_engine.extract_summary(docs)
    pol = policy_engine.assess(app, member, extract, thresholds)
    comp = docs_engine.completeness(app, docs, required)
    recon = docs_engine.reconcile(app, member, docs)
    fr = fraud_engine.assess(member, app, docs, applications_90d={"104265": 4, "104310": 3}.get(member["id"], 1))
    feats = MODEL.features_for(member, app, pol, history_features(member))
    rk = MODEL.score(feats)
    lm = lmi_engine.analyse(member)

    case = {
        "application": app,
        "member": {k: v for k, v in member.items() if k != "payments"},
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
    case["decision_factors"] = policy_engine.decision_factors(pol, rk, fr, comp)
    case["counterfactuals"] = policy_engine.counterfactuals(pol, rk, fr, comp)
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
        "product": app["product"], "amount": app["amount"], "branch": app["branch"],
        "status": app["status"], "officer": app["officer"], "submitted": app["submitted"],
        "risk": case["risk"]["grade"], "pd": case["risk"]["pd"], "score": case["risk"]["score"],
        "dsr": case["policy"]["dsr"], "policy": case["policy"]["result"],
        "docs": {"v": case["documents_summary"]["verified"], "t": case["documents_summary"]["required"]},
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


def portfolio() -> dict:
    rows = [queue_row(a) for a in applications()]
    alerts = [lmi_engine.analyse(m) for m in MEMBERS.values()]
    warn = [a for a in alerts if a["state"]["state"] in ("ELEVATED", "AT_RISK", "WATCH")]
    approved = sum(1 for r in rows if r["decision"] == "Approve")
    risk_mix = {}
    for r in rows:
        risk_mix[r["risk"]] = risk_mix.get(r["risk"], 0) + 1
    exposure = sum(r["amount"] for r in rows)
    pd_w = sum(r["pd"] * r["amount"] for r in rows) / max(1, exposure)
    return {
        "kpis": {
            "applications_today": len([r for r in rows if r["submitted"].startswith("2024-04-15")]) or len(rows),
            "pipeline": len(rows),
            "approval_rate": round(sum(1 for t in seed.TREND for _ in [0]) and
                                   sum(t["ap"] for t in seed.TREND) / sum(t["a"] for t in seed.TREND) * 100, 1),
            "avg_processing": "1.8 days",
            "predicted_delinquency": round(pd_w * 100, 2),
            "exposure": exposure,
            "early_warnings": len([a for a in alerts if a["state"]["state"] in ("ELEVATED", "AT_RISK")]),
            "decided": sum(1 for r in rows if r["decided"]),
            "approved": approved,
        },
        "trend": seed.TREND,
        "risk_mix": risk_mix,
        "queue": sorted(rows, key=lambda r: (r["decided"], -r["amount"]))[:8],
        "early_warning": sorted(warn, key=lambda a: -a["forecast"]["p_late_30d"])[:5],
        "highlights": highlights(rows, alerts),
        "recent_documents": sorted(documents(), key=lambda d: d["uploaded"], reverse=True)[:5],
        "autonomy": store.autonomy(),
        "ledger": store.ledger_verify(),
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
        h.append(dict(tone="amber", title=f"{len(dr)} member(s) drifting from their own payment baseline",
                      detail=f"Led by {dr[0]['name']} — {dr[0]['why_now'][:110]}", action="early-warning"))
    rec = [a for a in alerts if a["state"]["state"] == "RECOVERY"]
    if rec:
        h.append(dict(tone="green", title=f"{len(rec)} member(s) meeting recovery criteria",
                      detail=f"{rec[0]['name']} has returned to on-time payment for 3 consecutive cycles.",
                      action="early-warning"))
    md = [r for r in rows if r["docs"]["v"] < r["docs"]["t"] and not r["decided"]]
    if md:
        h.append(dict(tone="blue", title=f"{len(md)} case(s) waiting on mandatory evidence",
                      detail="Requesting documents early is the single biggest driver of turnaround time.",
                      action="applications"))
    return h
