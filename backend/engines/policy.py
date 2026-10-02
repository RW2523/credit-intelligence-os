"""Deterministic policy, eligibility and affordability engine.

Nothing in here is an LLM call. Every number the Council, the officer or the member sees is produced
by these functions so it can be reproduced from a snapshot. The officer workbench and the member's
"Check Before You Borrow" both call assess(), so the two can never disagree.

Profit is charged at a FLAT annual rate, the convention for cooperative personal financing in
Malaysia: instalment = amount x (1 + rate x years) / months.
"""
from __future__ import annotations
import datetime as dt
import math

from clock import TODAY, months_between
from fmt import rm
from seed import PRODUCTS, DEDUCTION_CAP_PCT, MIN_GROSS_SALARY
from engines import docs as docs_engine

BINDING_LABEL = {
    "dsr": "debt service ratio ceiling",
    "deduction_cap": f"{DEDUCTION_CAP_PCT}% salary-deduction cap",
    "exposure": "aggregate exposure limit",
    "product_ceiling": "product maximum",
}


def instalment(amount: float, term_months: int, annual_rate: float) -> float:
    return amount * (1 + annual_rate / 100 * term_months / 12) / term_months


def principal_for(monthly: float, term_months: int, annual_rate: float) -> float:
    """Inverse of instalment(): the amount a monthly capacity supports over the term."""
    return monthly * term_months / (1 + annual_rate / 100 * term_months / 12)


def verified_income(member: dict, docs_extract: dict) -> dict:
    """POL-003: use the lower verified figure when variance > 10%.

    Bank salary credits are take-home pay, so payroll financing deductions are added back before
    they are compared with the payslip — otherwise every salaried member would look under-earning.
    """
    declared = member["declared_income"]
    bank = docs_engine.bank_income(docs_extract, member) or member.get("bank_income") or declared
    payslip = docs_extract.get("payslip_income") or member.get("payslip_income") or 0
    candidates = [c for c in (payslip, bank) if c]
    verified = min(candidates) if candidates else declared
    variance = round(abs(declared - verified) / declared * 100, 1) if declared else 0.0
    return {
        "declared_annual": declared, "payslip_annual": round(payslip, 2), "bank_annual": round(bank, 2),
        "verified_annual": round(verified, 2), "verified_monthly": round(verified / 12, 2),
        "variance_pct": variance, "material_variance": variance > 10.0,
        "basis": "POL-003 lower verified figure" if variance > 10 else "declared income corroborated",
        "note": member.get("declared_note"),
    }


def _floor100(x: float) -> float:
    return max(0.0, math.floor(x / 100) * 100)


def assess(application: dict, member: dict, docs_extract: dict, thresholds: dict | None = None) -> dict:
    p = PRODUCTS[application["product"]]
    th = {k: v for k, v in (thresholds or {}).items() if v is not None}
    dsr_ceiling = th.get("dsr_ceiling", p["max_dti"])
    exposure_multiple = th.get("exposure_multiple", 4.0)
    cap_pct = th.get("deduction_cap", DEDUCTION_CAP_PCT)
    min_gross = th.get("min_gross", MIN_GROSS_SALARY)

    inc = verified_income(member, docs_extract)
    net_monthly = inc["verified_monthly"]
    term, rate, amount = application["term"], p["rate"], application["amount"]
    new_pmt = round(instalment(amount, term, rate), 2)
    existing = application.get("existing_commitments", 0)
    total_obligations = round(existing + new_pmt, 2)
    dsr = round(total_obligations / net_monthly * 100, 2) if net_monthly else 999.0

    since = dt.date.fromisoformat(member["since"])
    tenure_m = months_between(since, TODAY)
    equity = member["savings"] + member["share_capital"]
    exposure = member["outstanding"] + amount
    exposure_cap = round(equity * exposure_multiple, 2)

    gross = docs_extract.get("gross_payslip") or member.get("gross_monthly") or 0
    other = docs_extract.get("other_payslip") or member.get("other_deductions") or 0
    by_deduction = p["salary_deduction"] and member.get("salaried", True) and gross > 0
    deduction_ratio = round((other + existing + new_pmt) / gross * 100, 2) if by_deduction else None

    # ---- maximum supportable financing, and which limit binds it
    limits = {
        "dsr": principal_for(max(0.0, net_monthly * dsr_ceiling / 100 - existing), term, rate),
        "product_ceiling": float(p["max"]),
        "exposure": exposure_cap - member["outstanding"],
    }
    if by_deduction:
        limits["deduction_cap"] = principal_for(max(0.0, gross * cap_pct / 100 - other - existing), term, rate)
    binding = min(limits, key=limits.get)
    max_financing = _floor100(limits[binding])        # never negative: RM0 means nothing is supportable
    shortfall = {
        "dsr_monthly": round(max(0.0, existing - net_monthly * dsr_ceiling / 100), 2),
        "exposure": round(max(0.0, member["outstanding"] - exposure_cap), 2),
        "equity_needed": round(max(0.0, member["outstanding"] - exposure_cap) / exposure_multiple, 2),
        "deduction_monthly": round(max(0.0, other + existing - gross * cap_pct / 100), 2) if by_deduction else 0.0,
    }

    retire = member.get("retirement_date")
    beyond_retirement = False
    if retire and p["salary_deduction"] and member.get("member_type") != "retiree":
        end_month = months_between(TODAY, dt.date.fromisoformat(retire))
        beyond_retirement = term > end_month
    needs_min_gross = application["product"] in ("Personal Financing-i", "Express Financing-i")

    gates = [
        dict(id="POL-002", name="Membership tenure", required=f"≥ {p['min_tenure_m']} months",
             actual=f"{tenure_m} months", passed=tenure_m >= p["min_tenure_m"], hard=True),
        dict(id="POL-012", name="Eligibility — income & service", hard=True,
             required=f"gross ≥ {rm(min_gross)}, confirmed service" if needs_min_gross else "member in good standing",
             actual=f"{rm(gross)} gross" if needs_min_gross else "in good standing",
             passed=(gross >= min_gross) if needs_min_gross and member.get("salaried", True) else True),
        dict(id="POL-001", name="Debt service ratio", required=f"≤ {dsr_ceiling}% of verified net",
             actual=f"{dsr}%", passed=dsr <= dsr_ceiling, hard=True),
        dict(id="POL-011", name=f"Salary deduction cap ({cap_pct}% of gross)", hard=True,
             required=f"≤ {cap_pct}% of gross" if by_deduction else "applies to salary deduction",
             actual=f"{deduction_ratio}%" if by_deduction else "n/a — repaid by standing instruction",
             passed=(deduction_ratio <= cap_pct) if by_deduction else True),
        dict(id="POL-009", name="Product amount limits", required=f"{rm(p['min'])} – {rm(p['max'])}",
             actual=rm(amount), passed=p["min"] <= amount <= p["max"], hard=True),
        dict(id="POL-004", name="Aggregate exposure",
             required=f"≤ {rm(exposure_cap)} ({exposure_multiple:g}× savings + share capital)",
             actual=rm(exposure), passed=exposure <= exposure_cap, hard=True),
        dict(id="POL-010", name="Financing tenure", required=f"{p['min_term']} – {p['max_term']} months",
             actual=f"{term} months", passed=p["min_term"] <= term <= p["max_term"], hard=True),
        dict(id="POL-003", name="Income corroboration", required="variance ≤ 10%",
             actual=f"{inc['variance_pct']}%", passed=not inc["material_variance"], hard=False),
    ]
    if beyond_retirement:
        gates.append(dict(id="POL-010", name="Tenure vs retirement", required="ends before compulsory retirement",
                          actual=f"retires {retire[:7]}", passed=False, hard=False))
    # an advisory gate routes the case to a person; it does not by itself fail the case
    hard_fail = [g for g in gates if not g["passed"] and g.get("hard")]
    advisory = [g for g in gates if not g["passed"] and not g.get("hard")]

    if amount <= 30000:
        authority = "Credit Officer"
    elif amount <= 100000:
        authority = "Senior Officer"
    elif amount <= 250000:
        authority = "Credit Committee"
    else:
        authority = "Board"

    return {
        "policy_version": "v4.0",
        "product": application["product"],
        "product_ms": p["ms"], "contract": p["contract"],
        "income": inc,
        "instalment": new_pmt,
        "rate": rate, "rate_type": "flat",
        "total_profit": round(new_pmt * term - amount, 2),
        "total_payable": round(new_pmt * term, 2),
        "existing_commitments": existing,
        "total_obligations": total_obligations,
        "dsr": dsr,
        "dsr_ceiling": dsr_ceiling,
        "headroom": round(dsr_ceiling - dsr, 2),
        "gross_monthly": gross, "other_deductions": other,
        "deduction_ratio": deduction_ratio, "deduction_cap": cap_pct, "by_salary_deduction": by_deduction,
        "tenure_months": tenure_m,
        "equity": equity,
        "exposure": exposure,
        "exposure_cap": exposure_cap,
        "exposure_multiple": exposure_multiple,
        "max_financing": max_financing,
        "max_financing_binding": binding,
        "max_financing_binding_label": BINDING_LABEL[binding],
        "max_financing_limits": {k: round(max(0.0, v), 0) for k, v in limits.items()},
        "shortfall": shortfall,
        "required_documents": p["docs"],
        "authority_required": authority,
        "gates": gates,
        "result": "FAIL" if hard_fail else "PASS",
        "affordability": "PASS" if dsr <= dsr_ceiling and (deduction_ratio is None or deduction_ratio <= cap_pct) else "FAIL",
        "eligibility": "PASS" if all(g["passed"] for g in gates
                                     if g.get("hard") and g["id"] not in ("POL-001", "POL-011")) else "FAIL",
        "failures": [g["name"] for g in hard_fail],
        "advisories": [g["name"] for g in advisory],
    }


def decision_factors(policy: dict, risk: dict, fraud: dict, docs: dict) -> list[dict]:
    """Ranked Decision Factors — what is actually driving the outcome."""
    f = []
    f.append(dict(name="Affordability headroom", weight=round(min(1.0, max(0.0, policy["headroom"] / 15)), 2),
                  direction="positive" if policy["headroom"] > 0 else "negative",
                  detail=f"DSR {policy['dsr']}% against a {policy['dsr_ceiling']}% ceiling"))
    if policy["deduction_ratio"] is not None:
        room = policy["deduction_cap"] - policy["deduction_ratio"]
        f.append(dict(name="Salary deduction cap", weight=round(min(1.0, max(0.0, room / 20)), 2),
                      direction="positive" if room >= 0 else "negative",
                      detail=f"Total deductions {policy['deduction_ratio']}% of gross against the {policy['deduction_cap']}% cap"))
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


def max_financing_explanation(policy: dict, amount: float | None = None) -> str:
    """Plain-language reason for the maximum, naming every limit that is already exhausted."""
    s, inc = policy["shortfall"], policy["income"]
    parts = []
    if s["dsr_monthly"] > 0:
        used = policy["existing_commitments"] / max(1, inc["verified_monthly"]) * 100
        parts.append(f"existing commitments of {rm(policy['existing_commitments'])}/month already use {used:.0f}% of "
                     f"verified net pay against a {policy['dsr_ceiling']}% ceiling — they would need to fall by "
                     f"{rm(s['dsr_monthly'])}/month")
    if s["exposure"] > 0:
        parts.append(f"KT exposure of {rm(policy['exposure'] - (amount or 0))} already exceeds the "
                     f"{rm(policy['exposure_cap'])} cap ({policy['exposure_multiple']:g}× savings and share capital) — "
                     f"savings or share capital would need to rise by {rm(s['equity_needed'])}")
    if s["deduction_monthly"] > 0:
        parts.append(f"salary deductions already exceed the {policy['deduction_cap']}% cap on gross pay by "
                     f"{rm(s['deduction_monthly'])}/month")
    if policy["max_financing"] <= 0:
        if not parts:
            parts.append(f"the {policy['max_financing_binding_label']} leaves no room at this tenure")
        return "No new financing is supportable at current commitments: " + "; ".join(parts) + "."
    return (f"Up to {rm(policy['max_financing'])} over the requested tenure — the "
            f"{policy['max_financing_binding_label']} is the binding limit.")


def counterfactuals(policy: dict, risk: dict, fraud: dict, docs: dict, amount: float | None = None) -> dict:
    """'What changes the outcome?' — deterministic, constraint-aware sensitivity statements."""
    better, worse = [], []
    if docs["missing"]:
        better.append(f"Missing evidence is supplied: {', '.join(docs['missing'])}")
    if policy["income"]["material_variance"]:
        better.append("Employer or unit confirmation reconciles the income variance to within 10%")
    mf = policy["max_financing"]
    if mf <= 0:
        better.append(max_financing_explanation(policy, amount))
    elif amount and mf < amount:
        better.append(f"Requested amount reduced to about {rm(mf)} — the {policy['max_financing_binding_label']} "
                      f"is the binding limit")
    elif policy["headroom"] < 6:
        better.append(f"A longer tenure or a smaller amount widens the thin DSR headroom ({policy['headroom']} points)")
    if risk["pd"] > 0.06:
        better.append("No new credit inquiries (CCRIS) in the next 90 days")
    if not better:
        better.append("Current evidence already supports the recommendation")

    worse.append(f"Verified income falls more than 20% below {rm(policy['income']['verified_annual'])} a year")
    worse.append(f"Additional commitments push DSR above {policy['dsr_ceiling']}%")
    if policy["deduction_ratio"] is not None:
        worse.append(f"Total salary deductions rise above {policy['deduction_cap']}% of gross pay")
    if fraud["score"] > 0.3:
        worse.append("Identity or document integrity inconsistency is confirmed")
    worse.append("A salary deduction on an existing facility is missed before disbursement")
    return {"improves": better, "deteriorates": worse}
