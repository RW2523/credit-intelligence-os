"""Cross-selling options — AI-ranked next-best offers per member.

Each suggestion carries the reason chain KT asked for, e.g.

  Member A → existing financing → good repayment history → no takaful        ⇒ takaful offer
  Member B → salary + savings → no personal financing → high repayment capacity ⇒ financing offer
  Member C → declining engagement                                              ⇒ retention intervention

Responsible-lending rules are built in: no financing offer to a member whose distress band is
Elevated or High, whose deductions are near the 60% cap, or whose financing would outlast their
service without a pension mandate; members who withheld marketing consent or are on the
do-not-contact list are shown but cannot be contacted (POL-013).
"""
from __future__ import annotations
import datetime as dt

from clock import TODAY
from fmt import rm
import seed
from connectors import ccris, sola
from engines import policy as policy_engine, distress


def _engagement_drop(m: dict) -> float:
    eng = m.get("engagement") or []
    if len(eng) < 8:
        return 0.0
    e0, e1 = sum(eng[:4]) / 4, sum(eng[-4:]) / 4
    return round(max(0.0, (e0 - e1) / e0 * 100), 1) if e0 else 0.0


def _savings_drop(m: dict) -> float:
    t = m.get("savings_trend") or []
    if len(t) < 8:
        return 0.0
    a, b = sum(t[:4]) / 4, sum(t[-4:]) / 4
    return round(max(0.0, (a - b) / a * 100), 1) if a else 0.0


def _ontime(m: dict, n: int = 12) -> tuple[int, int]:
    pays = (m.get("payments") or [])[-n:]
    return sum(1 for p in pays if p["days_late"] <= 2), len(pays)


def offers(m: dict, dist: dict | None = None) -> list[dict]:
    dist = dist or distress.MODEL.score(m)
    out = []
    held = set(m.get("takaful") or [])
    on_time, cycles = _ontime(m)
    s = sola.eligibility(m)
    risky = dist["band"] in ("Elevated", "High")

    # A — takaful for members with financing, clean conduct and no cover
    if m.get("outstanding", 0) > 0 and cycles >= 12 and on_time == cycles and not risky:
        prod = "Motor Takaful" if m.get("vehicle") and "Motor Takaful" not in held else \
            "General Takaful" if "General Takaful" not in held else None
        if prod:
            chain = [f"Existing KT financing ({rm(m['outstanding'])} outstanding)",
                     f"Good repayment history ({on_time}/{cycles} deductions on time)",
                     f"No {prod.lower()} with KT" + (f" — vehicle on file: {m['vehicle']}" if prod == "Motor Takaful" else "")]
            out.append(dict(kind="takaful", product=prod, pattern="A", chain=chain,
                            identifies="Potential takaful offer", propensity=0.42 + 0.03 * min(5, m.get("prior_financings", 0)),
                            value=480 if prod == "Motor Takaful" else 260,
                            pitch=f"{prod} with contributions by salary deduction"))

    # B — financing for members with salary and savings, no personal financing, and real capacity
    has_pf = m.get("outstanding", 0) > 0
    if not has_pf and m.get("member_type") != "retiree" and not risky and m.get("gross_monthly", 0) >= seed.MIN_GROSS_SALARY:
        term = 60
        mtr = m.get("months_to_retirement")
        if mtr is not None:
            term = max(12, min(term, mtr - 3))
        app = dict(product="Personal Financing-i", amount=20000, term=term,
                   existing_commitments=m.get("financing_deductions", 0))
        p = policy_engine.assess(app, m, {})
        if p["max_financing"] >= 10000 and s["monthly_headroom"] >= 400:
            chain = [f"Salary {rm(m['gross_monthly'])}/month and savings {rm(m['savings'])}",
                     "No personal financing with KT",
                     f"High repayment capacity — up to {rm(p['max_financing'])} over {term} months within policy"]
            out.append(dict(kind="financing", product="Personal Financing-i", pattern="B", chain=chain,
                            identifies="Potential financing offer", propensity=0.30 + min(0.25, m["savings"] / 200000),
                            value=round(min(p["max_financing"], 50000) * 0.0365 * term / 12 * 0.5),
                            max_financing=p["max_financing"], term=term,
                            pitch=f"Personal Financing-i up to {rm(min(p['max_financing'], 50000))}, pre-assessed"))

    # C — retention when engagement and savings contributions are fading
    eng, sav = _engagement_drop(m), _savings_drop(m)
    if eng >= 40 or (eng >= 25 and sav >= 40):
        chain = [f"Declining engagement — activity down {eng:.0f}% over the year"]
        if sav >= 25:
            chain.append(f"Savings contributions down {sav:.0f}%")
        chain.append(f"{(TODAY.year - int(m['since'][:4]))}-year member" if m.get("since") else "Member")
        out.append(dict(kind="retention", product="Retention call", pattern="C", chain=chain,
                        identifies="Retention intervention", propensity=0.55,
                        value=round(m.get("savings", 0) * 0.04 + m.get("share_capital", 0) * 0.06),
                        pitch="Branch officer call: dividend reminder, savings plan, member benefits"))

    # KT-specific extras
    deps = [a for a in (m.get("dependants") or []) if 18 <= a <= 23]
    near_retirement = (m.get("months_to_retirement") or 999) <= 36
    if deps and not risky and m.get("member_type") != "retiree" and not near_retirement \
            and s["monthly_headroom"] >= 300:
        out.append(dict(kind="financing", product="Fees Financing-i", pattern="KT", identifies="Education financing",
                        chain=[f"{len(deps)} dependant(s) of tertiary-education age", "Fees Financing-i not held",
                               f"Deduction headroom {rm(s['monthly_headroom'])}/month"],
                        propensity=0.28, value=600, pitch="Fees Financing-i for a dependant's tertiary fees"))
    if m.get("gold_grams", 0) >= 20 and (_savings_drop(m) > 30 or risky):
        out.append(dict(kind="rahnu", product="Ar-Rahnu KT", pattern="KT", identifies="Short-term liquidity",
                        chain=[f"Gold holdings on record (~{m['gold_grams']} g)", "Savings falling — short-term cash need",
                               "Ar-Rahnu avoids adding a long-tenure salary deduction"],
                        propensity=0.22, value=120, pitch="Ar-Rahnu KT: cash against gold, renewable 6-month term"))
    mtr = m.get("months_to_retirement")
    if mtr is not None and 0 < mtr <= 24:
        out.append(dict(kind="advice", product="Pre-retirement review", pattern="KT", identifies="Retirement planning",
                        chain=[f"Compulsory retirement in {mtr} months",
                               "Salary deduction switches to pension deduction at retirement"],
                        propensity=0.6, value=0, pitch="Pre-retirement review: deductions, savings and dividends"))

    for o in out:
        o["score"] = round(o["propensity"] * (o["value"] or 50), 1)
        o["contactable"] = bool(m.get("marketing_consent")) and not m.get("dnc")
    return sorted(out, key=lambda o: -o["score"])


def portfolio(members: list[dict], feedback: dict | None = None) -> dict:
    feedback = feedback or {}
    rows = []
    for m in members:
        d = distress.MODEL.score(m)
        for o in offers(m, d)[:2]:                       # the two best actions per member
            key = f"{m['id']}:{o['product']}"
            rows.append(dict(o, member_id=m["id"], name=m["name"], initials=m["initials"], branch=m["branch"],
                             service=m.get("service_label"), distress=d["band"],
                             feedback=feedback.get(key)))
    rows.sort(key=lambda r: (r["feedback"] is not None, -r["score"]))
    summary = {}
    for r in rows:
        summary[r["identifies"]] = summary.get(r["identifies"], 0) + 1
    return {"rows": rows, "summary": summary,
            "external": {"ccris": "Experian CCRIS — simulated", "sola": "SOLA — simulated",
                         "ekyc": "Digibanc eKYC — simulated",
                         "note": "KT's Digibanc platform integrates Experian CCRIS, TCS blacklist screening and SOLA "
                                 "(Codebase Technologies case study). These adapters return simulated data until "
                                 "sandbox credentials are provided."}}
