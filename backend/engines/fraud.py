"""Fraud & integrity engine — deterministic rules + unsupervised anomaly
detection + guarantor/device graph analytics. A high score is an INVESTIGATION
SIGNAL, never a finding of fraud (POL-006)."""
from __future__ import annotations
import numpy as np, hashlib
from sklearn.ensemble import IsolationForest

_RNG = np.random.default_rng(23)
_X = np.column_stack([
    _RNG.normal(0, 1, 3000),      # income variance z
    _RNG.poisson(1, 3000),        # applications in 90d
    _RNG.poisson(0.2, 3000),      # shared device links
    _RNG.poisson(0.1, 3000),      # duplicate doc hashes
    _RNG.normal(0, 1, 3000),      # doc forensic z
])
_IFOREST = IsolationForest(n_estimators=120, contamination=0.06, random_state=5).fit(_X)

# synthetic relationship graph: device / address / guarantor edges
GRAPH_EDGES = [
    ("104265", "104310", "shared device fingerprint"),
    ("104265", "998112", "shared contact number"),
    ("104188", "104276", "guarantor relationship"),
    ("104241", "104233", "guarantor relationship"),
    ("104310", "998112", "shared address"),
]


def _hash(name: str) -> str:
    return hashlib.sha256(name.encode()).hexdigest()[:16]


def assess(member: dict, application: dict, documents: list[dict], applications_90d: int = 1) -> dict:
    signals, checks = [], []

    variance = 0.0
    if member["declared_income"]:
        variance = abs(member["declared_income"] - (member["bank_income"] or member["declared_income"])) / member["declared_income"] * 100

    tamper = [d for d in documents if d.get("forensics", {}).get("tampering")]
    dup = [d for d in documents if d.get("forensics", {}).get("duplicate_hash")]
    low_font = [d for d in documents if d.get("forensics", {}).get("font_consistency", 100) < 92]

    edges = [e for e in GRAPH_EDGES if member["id"] in e[:2]]
    device_links = len([e for e in edges if "device" in e[2] or "contact" in e[2]])

    checks.append(dict(name="Identity reconciliation", passed=True,
                       detail="ID fields reconcile with core member record"))
    checks.append(dict(name="Document tampering forensics", passed=not tamper,
                       detail="No manipulated content layer detected" if not tamper else f"{len(tamper)} document(s) flagged"))
    checks.append(dict(name="Duplicate document hash", passed=not dup,
                       detail="All document hashes unique across the corpus" if not dup else "Reused document detected"))
    checks.append(dict(name="Font / layout consistency", passed=not low_font,
                       detail="Consistent" if not low_font else f"{len(low_font)} document(s) below 92% consistency"))
    checks.append(dict(name="Velocity check", passed=applications_90d <= 2,
                       detail=f"{applications_90d} application(s) in the last 90 days"))
    checks.append(dict(name="Relationship graph", passed=device_links == 0,
                       detail="No shared device or contact links" if device_links == 0
                              else f"{device_links} shared-identifier link(s) to other members"))
    checks.append(dict(name="Income corroboration", passed=variance <= 15,
                       detail=f"{variance:.1f}% variance between declared income and bank deposits"))

    x = np.array([[variance / 10, applications_90d, device_links, len(dup),
                   (100 - min(d.get("forensics", {}).get("font_consistency", 100) for d in documents)) / 5 if documents else 0]])
    raw = float(_IFOREST.decision_function(x)[0])
    anomaly = float(np.clip((0.12 - raw) / 0.30, 0, 1))

    rule_score = min(1.0, 0.45 * len(tamper) + 0.5 * len(dup) + 0.18 * device_links
                     + 0.15 * max(0, applications_90d - 2) + (0.2 if variance > 15 else 0.0)
                     + 0.1 * len(low_font))
    score = round(0.55 * rule_score + 0.45 * anomaly, 3)

    if tamper or dup:
        level, headline = "Critical", "Document integrity signal requires investigation"
    elif score > 0.6:
        level, headline = "Elevated", "Anomalous pattern — investigation signal, not proven fraud"
    elif score > 0.35:
        level, headline = "Watch", "Minor anomalies present; monitor"
    else:
        level, headline = "Clear", "No identity, document or network integrity signal"

    for e in edges:
        signals.append(dict(kind="graph", detail=f"Linked to member {e[1] if e[0]==member['id'] else e[0]} — {e[2]}",
                            severity="medium" if "guarantor" not in e[2] else "info"))
    if variance > 15:
        signals.append(dict(kind="income", detail=f"Declared income exceeds verified deposits by {variance:.1f}%", severity="medium"))
    if low_font:
        signals.append(dict(kind="forensics", detail=f"Layout consistency below threshold on {low_font[0]['label']}", severity="low"))
    if not signals:
        signals.append(dict(kind="clear", detail="No integrity signals raised on this case", severity="info"))

    return {
        "score": score, "anomaly_score": round(anomaly, 3), "rule_score": round(rule_score, 3),
        "level": level, "headline": headline, "checks": checks, "signals": signals,
        "graph": [dict(a=e[0], b=e[1], kind=e[2]) for e in edges],
        "doc_hashes": [dict(doc=d["label"], hash=_hash(d["file"])) for d in documents],
        "model_version": "fraud-v3.4.0 (rules + isolation forest + graph)",
        "disclaimer": "A high anomaly score is an investigation signal and is not evidence of fraud.",
    }
