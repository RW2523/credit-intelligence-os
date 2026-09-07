"""Deterministic policy, eligibility and affordability engine.

Nothing in here is an LLM call. Every number the Council or the officer sees
must be produced by these functions so it can be reproduced from a snapshot.
"""
from __future__ import annotations
import datetime as dt
from seed import PRODUCTS

TODAY = dt.date(2024, 4, 16)


def _months_between(a: dt.date, b: dt.date) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month)


def instalment(amount: float, term_months: int, annual_rate: float) -> float:
    r = annual_rate / 100 / 12
    if r == 0:
        return amount / term_months
    return amount * r / (1 - (1 + r) ** (-term_months))


def verified_income(member: dict, docs_extract: dict) -> dict:
    """POL-003: use the lower verified figure when variance > 10%."""
    declared = member["declared_income"]
    bank = docs_extract.get("bank_income") or member.get("bank_income") or declared
    payslip = docs_extract.get("payslip_income") or member.get("payslip_income") or 0
    candidates = [c for c in (payslip, bank) if c]
    verified = min(candidates) if candidates else declared
    variance = round(abs(declared - verified) / declared * 100, 1) if declared else 0.0
    return {
        "declared_annual": declared, "payslip_annual": payslip, "bank_annual": bank,
        "verified_annual": verified, "verified_monthly": round(verified / 12, 2),
        "variance_pct": variance, "material_variance": variance > 10.0,
        "basis": "POL-003 lower verified figure" if variance > 10 else "declared income corroborated",
    }


def assess(application: dict, member: dict, docs_extract: dict, thresholds: dict | None = None) -> dict:
    p = PRODUCTS[application["product"]]
    th = thresholds or {}
    dsr_ceiling = th.get("dsr_ceiling", p["max_dti"])
    exposure_multiple = th.get("exposure_multiple", 4.0)

    inc = verified_income(member, docs_extract)
    net_monthly = inc["verified_monthly"]
    new_pmt = round(instalment(application["amount"], application["term"], p["rate"]), 2)
    existing = application.get("existing_commitments", 0)
    total_obligations = round(existing + new_pmt, 2)
    dsr = round(total_obligations / net_monthly * 100, 2) if net_monthly else 999.0

    since = dt.date.fromisoformat(member["since"])
    tenure_m = _months_between(since, TODAY)
    equity = member["savings"] + member["share_capital"]
    exposure = member["outstanding"] + application["amount"]
    exposure_cap = round(equity * exposure_multiple, 2)

    max_affordable = max(0.0, (net_monthly * dsr_ceiling / 100) - existing)
    # invert the annuity for the affordable principal
    r = p["rate"] / 100 / 12
    max_principal = round(max_affordable * (1 - (1 + r) ** (-application["term"])) / r, -2) if r else 0
    max_financing = round(min(max_principal, p["max"], exposure_cap - member["outstanding"]), 2)

    gates = [
        dict(id="POL-002", name="Membership tenure", required=f"≥ {p['min_tenure_m']} months",
             actual=f"{tenure_m} months", passed=tenure_m >= p["min_tenure_m"], hard=True),
        dict(id="POL-001", name="Debt service ratio", required=f"≤ {dsr_ceiling}%",
             actual=f"{dsr}%", passed=dsr <= dsr_ceiling, hard=True),
        dict(id="POL-005", name="Product amount ceiling", required=f"≤ ${p['max']:,}",
             actual=f"${application['amount']:,}", passed=application["amount"] <= p["max"], hard=True),
        dict(id="POL-004", name="Aggregate exposure", required=f"≤ ${exposure_cap:,.0f} ({exposure_multiple}× equity)",
             actual=f"${exposure:,.0f}", passed=exposure <= exposure_cap, hard=True),
        dict(id="POL-001", name="Term limit", required=f"≤ {p['max_term']} months",
             actual=f"{application['term']} months", passed=application["term"] <= p["max_term"], hard=True),
        dict(id="POL-003", name="Income corroboration", required="variance ≤ 10%",
             actual=f"{inc['variance_pct']}%", passed=not inc["material_variance"], hard=False),
    ]
    # an advisory gate routes the case to a person; it does not by itself fail the case
    hard_fail = [g for g in gates if not g["passed"] and g.get("hard")]
    advisory = [g for g in gates if not g["passed"] and not g.get("hard")]

    amount = application["amount"]
    if amount <= 30000:
        authority = "Credit Officer"
    elif amount <= 100000:
        authority = "Senior Officer"
    else:
        authority = "Credit Committee"

    return {
        "policy_version": "v3.4",
        "product": application["product"],
        "income": inc,
        "instalment": new_pmt,
        "existing_commitments": existing,
        "total_obligations": total_obligations,
        "dsr": dsr,
        "dsr_ceiling": dsr_ceiling,
        "headroom": round(dsr_ceiling - dsr, 2),
        "tenure_months": tenure_m,
        "equity": equity,
        "exposure": exposure,
        "exposure_cap": exposure_cap,
        "max_financing": max_financing,
        "required_documents": p["docs"],
        "authority_required": authority,
        "gates": gates,
        "result": "FAIL" if hard_fail else "PASS",
        "affordability": "PASS" if dsr <= dsr_ceiling else "FAIL",
        "eligibility": "PASS" if all(g["passed"] for g in gates
                                     if g.get("hard") and g["name"] != "Debt service ratio") else "FAIL",
        "failures": [g["name"] for g in hard_fail],
        "advisories": [g["name"] for g in advisory],
        "rate": p["rate"],
    }


def decision_factors(policy: dict, risk: dict, fraud: dict, docs: dict) -> list[dict]:
    """Ranked Decision Factors — what is actually driving the outcome."""
    f = []
    f.append(dict(name="Affordability headroom", weight=round(min(1.0, max(0.0, policy["headroom"] / 15)), 2),
                  direction="positive" if policy["headroom"] > 0 else "negative",
                  detail=f"DSR {policy['dsr']}% against a {policy['dsr_ceiling']}% ceiling"))
    f.append(dict(name="Calibrated credit risk", weight=round(1 - risk["pd"] * 6, 2),
                  direction="negative" if risk["pd"] > 0.08 else "positive",
                  detail=f"{risk['grade']} — {risk['pd']*100:.1f}% probability of default"))
    f.append(dict(name="Evidence completeness", weight=round(docs["verified"] / max(1, docs["required"]), 2),
                  direction="positive" if docs["verified"] >= docs["required"] else "negative",
                  detail=f"{docs['verified']} of {docs['required']} mandatory documents verified"))
    f.append(dict(name="Integrity signal", weight=round(1 - fraud["score"], 2),
                  direction="negative" if fraud["score"] > 0.5 else "positive",
                  detail=fraud["headline"]))
    if policy["income"]["material_variance"]:
        f.append(dict(name="Income verification", weight=0.25, direction="negative",
                      detail=f"{policy['income']['variance_pct']}% variance between declared and verified income"))
    f.sort(key=lambda x: abs(0.5 - x["weight"]), reverse=True)
    return f


def counterfactuals(policy: dict, risk: dict, fraud: dict, docs: dict) -> dict:
    """'What changes the outcome?' — deterministic sensitivity statements."""
    better, worse = [], []
    if docs["missing"]:
        better.append(f"Missing evidence is supplied: {', '.join(docs['missing'])}")
    if policy["income"]["material_variance"]:
        better.append("Employer confirmation reconciles the income variance to within 10%")
    if policy["headroom"] < 6:
        better.append(f"Requested amount reduced to about ${policy['max_financing']:,.0f} (DSR falls below {policy['dsr_ceiling']}%)")
    if risk["pd"] > 0.06:
        better.append("No new credit inquiries in the next 90 days")
    if not better:
        better.append("Current evidence already supports the recommendation")

    worse.append(f"Verified income falls more than 20% below ${policy['income']['verified_annual']:,.0f}")
    worse.append(f"Additional commitments push DSR above {policy['dsr_ceiling']}%")
    if fraud["score"] > 0.3:
        worse.append("Identity or document integrity inconsistency is confirmed")
    worse.append("A payment on an existing facility becomes 30+ days late before drawdown")
    return {"improves": better, "deteriorates": worse}
