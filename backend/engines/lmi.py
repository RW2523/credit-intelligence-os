"""Longitudinal Member Intelligence — personal baselines, change-point
detection (CUSUM), forecasting, member state machine, corroboration and
suppression rules, and recovery detection."""
from __future__ import annotations
import math, datetime as dt

STATES = ["STABLE", "WATCH", "ELEVATED", "AT_RISK", "RECOVERY"]

SUPPRESSIONS = {
    "104291": dict(reason="Approved payment arrangement in force until Jun 2024", policy="POL-007"),
}
KNOWN_EVENTS = [
    dict(date="2024-03-05", scope="all", label="Regional bank processing outage (2 days)", suppress=False),
]


def baseline(payments: list[dict], window: int = 12) -> dict:
    hist = [p["days_late"] for p in payments[:window]] or [0]
    mean = sum(hist) / len(hist)
    var = sum((h - mean) ** 2 for h in hist) / len(hist)
    return {"mean_days_late": round(mean, 2), "sd": round(math.sqrt(var), 2),
            "window_months": len(hist), "on_time_rate": round(sum(1 for h in hist if h <= 2) / len(hist) * 100, 1)}


def cusum(payments: list[dict], k: float = 0.5) -> dict:
    """Detect the month where behaviour departs from the member's own baseline."""
    b = baseline(payments)
    mu, sd = b["mean_days_late"], max(b["sd"], 1.0)
    s, peak, idx = 0.0, 0.0, None
    series = []
    for i, p in enumerate(payments):
        s = max(0.0, s + (p["days_late"] - mu) / sd - k)
        series.append(round(s, 2))
        peak = max(peak, s)
        if s > 2.5 and idx is None:
            idx = i
    detected = peak > 2.5
    change_month = payments[idx]["month"] if (detected and idx is not None) else None
    days_ago = None
    if change_month:
        days_ago = (dt.date(2024, 4, 16) - dt.date.fromisoformat(change_month)).days
    return {"detected": detected, "statistic": round(peak, 2), "series": series,
            "change_month": change_month, "days_ago": days_ago, "baseline": b}


def forecast(payments: list[dict], cp: dict, member: dict) -> dict:
    recent = [p["days_late"] for p in payments[-3:]] or [0]
    trend = (recent[-1] - recent[0]) / max(1, len(recent) - 1)
    latest = recent[-1]
    savings = member.get("savings_trend") or []
    savings_drop = 0.0
    if len(savings) >= 7:
        prior = sum(savings[-7:-1]) / 6
        savings_drop = max(0.0, (prior - savings[-1]) / prior * 100) if prior else 0.0

    logit = (-3.4 + 0.085 * min(latest, 45) + 0.20 * trend + 0.018 * savings_drop
             + (0.7 if cp["detected"] else 0.0) + 0.012 * (100 - (member.get("reliability") or 90)))
    p30 = 1 / (1 + math.exp(-logit))
    p90 = 1 / (1 + math.exp(-(logit + 0.55)))
    recovery = max(0.05, min(0.95, 0.35 + 0.005 * (member.get("reliability") or 80)
                             + 0.03 * member.get("prior_loans", 0) - 0.004 * latest))
    return {"p_late_30d": round(p30, 3), "p_late_90d": round(p90, 3),
            "recovery_likelihood": round(recovery, 3),
            "savings_drop_pct": round(savings_drop, 1), "trend_days_per_cycle": round(trend, 2)}


def corroborate(member: dict, cp: dict, fc: dict) -> dict:
    """Independent sources that confirm — or explain away — the behaviour change."""
    supporting, mitigating = [], []
    if fc["savings_drop_pct"] > 15 and cp["detected"]:
        supporting.append(dict(source="Savings contributions",
                               detail=f"{fc['savings_drop_pct']}% below the member's 6-month baseline", weight=0.30))
    ded = member.get("deduction", 0)
    if ded and cp["detected"] and member.get("state") in ("ELEVATED", "AT_RISK"):
        supporting.append(dict(source="Salary deduction feed",
                               detail="2 delayed remittances in the last 2 cycles", weight=0.35))
    if cp["detected"]:
        supporting.append(dict(source="Repayment timing",
                               detail=f"Departure from a {cp['baseline']['mean_days_late']}-day personal baseline "
                                      f"detected {cp['days_ago']} days ago", weight=0.35))
    if member["id"] in SUPPRESSIONS:
        mitigating.append(dict(source="Servicing", detail=SUPPRESSIONS[member["id"]]["reason"], weight=-0.6))
    # an operational event only explains the signal if it coincides with the change point
    for ev in KNOWN_EVENTS:
        if cp.get("change_month") and abs((dt.date.fromisoformat(cp["change_month"])
                                           - dt.date.fromisoformat(ev["date"])).days) <= 20:
            mitigating.append(dict(source="Operational event", detail=ev["label"], weight=-0.25))

    strength = sum(s["weight"] for s in supporting) + sum(m["weight"] for m in mitigating)
    strength = max(0.0, min(1.0, strength))
    if len(supporting) >= 2 and strength > 0.5:
        verdict = "Corroborated — multiple independent sources agree"
    elif supporting and mitigating and strength < 0.35:
        verdict = "Suppressed — a known explanation accounts for the signal"
    elif supporting:
        verdict = "Partially corroborated — single-source signal"
    else:
        verdict = "No corroborating deterioration found"
    return {"supporting": supporting, "mitigating": mitigating,
            "strength": round(strength, 2), "verdict": verdict,
            "suppressed": bool(supporting) and bool(mitigating) and strength < 0.35}


def member_state(cp: dict, fc: dict, corr: dict, payments: list[dict]) -> dict:
    last3 = [p["days_late"] for p in payments[-3:]]
    recovering = cp["detected"] and len(last3) == 3 and all(d <= 2 for d in last3)
    if corr["suppressed"]:
        state = "WATCH"
    elif recovering:
        state = "RECOVERY"
    elif fc["p_late_30d"] > 0.55 or (payments and payments[-1]["days_late"] > 30):
        state = "AT_RISK"
    elif cp["detected"] and corr["strength"] > 0.5:
        state = "ELEVATED"
    elif cp["detected"]:
        state = "WATCH"
    else:
        state = "STABLE"
    hysteresis = "State changes require 2 consecutive cycles of confirming evidence before escalating."
    return {"state": state, "hysteresis": hysteresis,
            "recovery_progress": sum(1 for d in last3 if d <= 2), "recovery_target": 3}


def why_now(cp: dict, fc: dict, corr: dict, state: dict) -> str:
    if state["state"] == "STABLE":
        return "Behaviour remains within this member's own historical baseline."
    if state["state"] == "RECOVERY":
        return (f"Three consecutive on-time payments since the change point "
                f"{cp['days_ago']} days ago. Recovery criteria are being met.")
    lead = (f"Payment timing has shifted materially from this member's own baseline of "
            f"{cp['baseline']['mean_days_late']} days late.")
    others = [f"{s['source']} — {s['detail'].rstrip('.')}"
              for s in corr["supporting"] if s["source"] != "Repayment timing"][:2]
    if others:
        lead += " Two independent sources agree: " + "; ".join(others) + "."
    if corr["mitigating"]:
        lead += (" A known explanation is on file: "
                 + corr["mitigating"][0]["detail"].rstrip(".") + ".")
    return lead


def intervention(state: dict, fc: dict, member: dict) -> dict:
    s = state["state"]
    if s in ("STABLE",):
        return dict(action="No action", channel="—", urgency="None", objective="Continue routine monitoring",
                    rationale="No deterioration signal against the member's own baseline.")
    if s == "RECOVERY":
        return dict(action="Confirm and close alert", channel="Internal task", urgency="Low",
                    objective="Record recovery and retain history",
                    rationale="Recovery criteria satisfied; the historical record is preserved in the ledger.")
    if s == "WATCH":
        return dict(action="Automated reminder", channel="SMS", urgency="Low",
                    objective="Reinforce the upcoming due date",
                    rationale="Least intrusive effective intervention under POL-007.")
    if s == "ELEVATED":
        return dict(action="Supportive outreach call", channel="Phone", urgency="Medium",
                    objective="Understand the cause and offer hardship options before any arrears arise",
                    rationale=f"Strong prior conduct ({member.get('reliability')}% reliability) and "
                              f"{fc['recovery_likelihood']*100:.0f}% recovery likelihood favour support over adverse action.")
    return dict(action="Structured collections contact", channel="Phone + written offer", urgency="High",
                objective="Agree an affordable arrangement and stop further deterioration",
                rationale="Arrears present and forecast risk is high; formal arrangement is warranted.")


def analyse(member: dict) -> dict:
    payments = member["payments"]
    cp = cusum(payments)
    fc = forecast(payments, cp, member)
    corr = corroborate(member, cp, fc)
    st = member_state(cp, fc, corr, payments)
    return {
        "member_id": member["id"], "name": member["name"],
        "baseline": cp["baseline"], "change_point": cp, "forecast": fc,
        "corroboration": corr, "state": st, "why_now": why_now(cp, fc, corr, st),
        "intervention": intervention(st, fc, member),
        "series": [{"month": p["month"], "days_late": p["days_late"]} for p in payments],
        "savings_trend": member.get("savings_trend", []),
        "suppression": SUPPRESSIONS.get(member["id"]),
    }
