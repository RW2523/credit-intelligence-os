"""The AI Credit Council — a bounded, evidence-grounded deliberation.

Each specialist agent receives ONLY the deterministic facts in its remit,
returns a stance plus cited evidence ids, and is then checked for grounding.
A Challenger attacks the emerging conclusion, affected agents may revise, and
a Synthesizer produces the governed recommendation. Nothing here decides
anything — the Autonomy Dial and the human own the decision.
"""
from __future__ import annotations
import json, re, asyncio
import llm

STANCES = ["Support", "Caution", "Concern", "Oppose"]

SYSTEM = (
    "You are a specialist member of a credit union's AI Credit Council. "
    "You reason ONLY from the FACTS given. Never invent numbers, names, policies or documents — "
    "if a number is not in the facts, do not mention it. Every claim must cite an evidence id. "
    "Your POSITION has already been derived from the deterministic engines: write the reasoning that "
    "supports it, in the voice of your remit. Do NOT write any figures, percentages or amounts — the "
    "interface shows them next to your words. Refer to them in words ('the declared income', 'the "
    "variance', 'the affordability headroom'). Set escalate=true ONLY if the facts reveal a serious "
    "problem your position understates, and then say exactly what it is. "
    "You never state a final approve/decline decision — a human officer decides. "
    "Reply with strict JSON only."
)

SCHEMA = ('{"headline":"one sentence, max 20 words, states your position in plain language",'
          '"reasoning":"2-3 sentences citing the specific numbers in the facts",'
          '"evidence":["E-XXX",...],"escalate":false,"escalate_reason":""}')

AGENTS = [
    dict(id="document", name="Document & Evidence Agent", icon="file",
         remit="Are the documents complete, authentic, internally consistent and sufficient for this product?"),
    dict(id="policy", name="Policy & Affordability Agent", icon="scale",
         remit="Does the case satisfy hard policy gates, affordability and limits under the frozen policy version?"),
    dict(id="risk", name="Credit Risk Agent", icon="chart",
         remit="What does the calibrated model and repayment history say about probability of default?"),
    dict(id="fraud", name="Fraud & Integrity Agent", icon="shield",
         remit="Are there identity, document-integrity or network signals warranting investigation? Never allege fraud."),
    dict(id="member", name="Member Relationship Agent", icon="users",
         remit="What is this member's standing, tenure, contribution and servicing history with the cooperative?"),
]
CHALLENGER = dict(id="challenger", name="Challenger", icon="alert",
                  remit="What could make the emerging conclusion wrong? Demand the missing evidence.")


# ------------------------------------------------------------------ facts
def build_facts(case: dict) -> dict:
    a, m, p, r, f = case["application"], case["member"], case["policy"], case["risk"], case["fraud"]
    d, rec = case["documents_summary"], case["reconciliation"]
    ev = {}

    def add(eid, kind, text, ref=None):
        ev[eid] = dict(id=eid, kind=kind, text=text, ref=ref)

    add("E-APP", "application", f"{a['product']} of ${a['amount']:,} over {a['term']} months for {a['purpose']}.", a["id"])
    add("E-POL", "policy", f"Policy {p['policy_version']}: DSR {p['dsr']}% against a {p['dsr_ceiling']}% ceiling; "
        f"instalment ${p['instalment']:,.0f}; eligibility {p['eligibility']}; affordability {p['affordability']}; "
        f"gates failing: {', '.join(p['failures']) or 'none'}.", "POL-001")
    add("E-INC", "income", f"Declared income ${p['income']['declared_annual']:,}; verified ${p['income']['verified_annual']:,}; "
        f"variance {p['income']['variance_pct']}% ({p['income']['basis']}).", "POL-003")
    add("E-RISK", "model", f"Risk model {r['model_version']}: probability of default {r['pd']*100:.1f}% ({r['grade']}, band {r['band']}); "
        f"score {r['score']}. Top reason codes: {'; '.join(r['reason_codes']) or 'none'}.", r["model_version"])
    add("E-FRAUD", "integrity", f"Integrity level {f['level']} (score {f['score']}). {f['headline']}. "
        f"Signals: {'; '.join(s['detail'] for s in f['signals'][:3])}.", "POL-006")
    add("E-DOCS", "documents", f"{d['verified']} of {d['required']} mandatory documents verified. "
        f"Missing: {', '.join(d['missing']) or 'none'}.", "POL-008")
    for i, x in enumerate(rec["exceptions"][:3]):
        add(f"E-EXC{i+1}", "exception", f"{x['title']} — {x['detail']} ({x['classification']}).", x["policy"])
    add("E-MEM", "member", f"Member since {m['since']} ({p['tenure_months']} months); {m['prior_loans']} prior facilities; "
        f"{m['reliability']}% payment reliability; savings ${m['savings']:,} and share capital ${m['share_capital']:,}; "
        f"current outstanding ${m['outstanding']:,}.", m["id"])
    if case.get("lmi"):
        l = case["lmi"]
        add("E-LMI", "behaviour", f"Longitudinal state {l['state']['state']}; 30-day late-payment probability "
            f"{l['forecast']['p_late_30d']*100:.0f}%; {l['corroboration']['verdict']}.", "LMI")
    return ev


ALL_EVIDENCE = ["E-APP", "E-POL", "E-INC", "E-RISK", "E-FRAUD", "E-DOCS",
                "E-EXC1", "E-EXC2", "E-EXC3", "E-MEM", "E-LMI"]

REMIT_EVIDENCE = {
    "challenger": ALL_EVIDENCE,
    "document": ["E-DOCS", "E-EXC1", "E-EXC2", "E-EXC3", "E-INC"],
    "policy":   ["E-POL", "E-INC", "E-APP"],
    "risk":     ["E-RISK", "E-MEM", "E-LMI", "E-POL"],
    "fraud":    ["E-FRAUD", "E-INC", "E-EXC1"],
    "member":   ["E-MEM", "E-LMI", "E-APP"],
}


# ---------------------------------------------------- deterministic priors
def prior(agent_id: str, case: dict) -> dict:
    p, r, f = case["policy"], case["risk"], case["fraud"]
    d, rec = case["documents_summary"], case["reconciliation"]
    if agent_id == "document":
        if d["missing"]:
            return dict(stance="Concern", confidence=0.8,
                        headline=f"{len(d['missing'])} mandatory document(s) are still missing.",
                        reasoning=f"Missing: {', '.join(d['missing'])}. The evidence set is incomplete for this product under POL-008.",
                        evidence=["E-DOCS"])
        if rec["exceptions"]:
            return dict(stance="Caution", confidence=0.74,
                        headline="Evidence is complete but one cross-source discrepancy remains open.",
                        reasoning=f"{rec['exceptions'][0]['title']}: {rec['exceptions'][0]['detail']}. This is a verification item, not an integrity finding.",
                        evidence=["E-DOCS", "E-EXC1"])
        return dict(stance="Support", confidence=0.88, headline="Required evidence is complete, readable and internally consistent.",
                    reasoning="All mandatory documents are verified and cross-source comparison found no discrepancy.",
                    evidence=["E-DOCS"])
    if agent_id == "policy":
        if p["result"] == "FAIL":
            return dict(stance="Oppose", confidence=0.9, headline=f"Hard policy gate fails: {', '.join(p['failures'])}.",
                        reasoning=f"DSR is {p['dsr']}% against a {p['dsr_ceiling']}% ceiling. Maximum supportable financing is ${p['max_financing']:,.0f}.",
                        evidence=["E-POL"])
        if p["headroom"] < 5:
            return dict(stance="Caution", confidence=0.72, headline="Affordability passes but with thin headroom.",
                        reasoning=f"DSR {p['dsr']}% leaves only {p['headroom']} points below the {p['dsr_ceiling']}% ceiling.",
                        evidence=["E-POL", "E-INC"])
        return dict(stance="Support", confidence=0.86, headline="All hard gates pass with adequate affordability headroom.",
                    reasoning=f"DSR {p['dsr']}% against a {p['dsr_ceiling']}% ceiling; requested amount is within the {p['authority_required']} authority band.",
                    evidence=["E-POL"])
    if agent_id == "risk":
        if r["pd"] > 0.13:
            return dict(stance="Concern", confidence=0.78, headline=f"Calibrated risk is {r['grade'].lower()} at {r['pd']*100:.1f}% probability of default.",
                        reasoning="Reason codes: " + "; ".join(r["reason_codes"][:2]) + ".", evidence=["E-RISK"])
        if r["pd"] > 0.06:
            return dict(stance="Caution", confidence=0.75, headline=f"Moderate calibrated risk at {r['pd']*100:.1f}% probability of default.",
                        reasoning="Positive repayment conduct partially offsets " + (r["reason_codes"][0].split('— ')[-1].lower() if r["reason_codes"] else "adverse factors") + ".",
                        evidence=["E-RISK", "E-MEM"])
        return dict(stance="Support", confidence=0.9, headline=f"Low calibrated risk at {r['pd']*100:.1f}% probability of default.",
                    reasoning="Repayment history and affordability both sit in the favourable band.", evidence=["E-RISK"])
    if agent_id == "fraud":
        if f["level"] in ("Critical", "Elevated"):
            return dict(stance="Concern", confidence=0.8, headline="Integrity signals warrant investigation before any execution.",
                        reasoning=f["headline"] + " " + f["disclaimer"], evidence=["E-FRAUD"])
        if f["level"] == "Watch":
            return dict(stance="Caution", confidence=0.7, headline="Minor anomalies present; no identity mismatch found.",
                        reasoning=f["signals"][0]["detail"] + ". " + f["disclaimer"], evidence=["E-FRAUD"])
        return dict(stance="Support", confidence=0.9, headline="No identity, document or network integrity signal detected.",
                    reasoning="Document hashes are unique and identity fields reconcile with core member data.", evidence=["E-FRAUD"])
    if agent_id == "member":
        m = case["member"]
        if m["reliability"] >= 92 and case["policy"]["tenure_months"] >= 24:
            return dict(stance="Support", confidence=0.88, headline="Long-standing member with strong repayment and contribution history.",
                        reasoning=f"{case['policy']['tenure_months']} months of membership, {m['prior_loans']} prior facilities repaid, {m['reliability']}% reliability.",
                        evidence=["E-MEM"])
        if m["reliability"] < 80:
            return dict(stance="Concern", confidence=0.76, headline="Repayment reliability is below the cooperative benchmark.",
                        reasoning=f"{m['reliability']}% reliability with {m['prior_loans']} prior facilities.", evidence=["E-MEM"])
        return dict(stance="Caution", confidence=0.72, headline="Relationship is sound but comparatively short.",
                    reasoning=f"{case['policy']['tenure_months']} months of membership and {m['prior_loans']} prior facility(ies).",
                    evidence=["E-MEM"])
    return dict(stance="Caution", confidence=0.6, headline="No position", reasoning="", evidence=[])


def challenger_prior(case: dict, positions: list[dict]) -> dict:
    p, rec, d = case["policy"], case["reconciliation"], case["documents_summary"]
    if p["income"]["material_variance"]:
        return dict(stance="Concern", confidence=0.8,
                    headline="The emerging conclusion assumes an income figure that is not corroborated.",
                    reasoning=f"Declared income differs from verified deposits by {p['income']['variance_pct']}%. "
                              "If the bank deposits exclude recurring obligations, affordability is overstated.",
                    ask="Obtain employer confirmation or one further month of bank statements before execution.",
                    evidence=["E-INC", "E-EXC1"], target="policy")
    if d["missing"]:
        return dict(stance="Concern", confidence=0.82,
                    headline="A recommendation is being formed while mandatory evidence is still absent.",
                    reasoning=f"Missing: {', '.join(d['missing'])}. POL-008 does not permit approval with mandatory evidence outstanding.",
                    ask="Request the outstanding documents and re-run the Council.",
                    evidence=["E-DOCS"], target="document")
    if case["risk"]["pd"] > 0.1:
        return dict(stance="Caution", confidence=0.7,
                    headline="Model risk is being offset by relationship history that may not repeat.",
                    reasoning="Historical reliability is backward-looking; the reason codes point at current-period behaviour.",
                    ask="Confirm no new commitments have been taken in the last 90 days.",
                    evidence=["E-RISK", "E-MEM"], target="risk")
    return dict(stance="Support", confidence=0.66,
                headline="No material weakness found in the emerging conclusion.",
                reasoning="Evidence is complete, affordability has headroom and no integrity signal is open.",
                ask="None — proceed on the current evidence.", evidence=["E-DOCS", "E-POL"], target=None)


# ------------------------------------------------------------- synthesis
def synthesize(case: dict, positions: list[dict], challenge: dict) -> dict:
    p, r, f, d = case["policy"], case["risk"], case["fraud"], case["documents_summary"]
    weights = {"Support": 1.0, "Caution": 0.55, "Concern": 0.2, "Oppose": 0.0}
    scores = [weights[x["stance"]] for x in positions]
    agreement = sum(scores) / len(scores)
    dissent = sum(1 for x in positions if x["stance"] in ("Concern", "Oppose"))
    spread = max(scores) - min(scores)
    disagreement = round(spread * 0.6 + (dissent / len(positions)) * 0.4, 2)

    if p["result"] == "FAIL":
        rec, why = "DECLINE", f"Hard policy gate fails: {', '.join(p['failures'])}."
    elif f["level"] == "Critical":
        rec, why = "INVESTIGATE", "Document-integrity signal must be resolved before any credit decision."
    elif d["missing"]:
        rec, why = "REQUEST INFORMATION", f"Mandatory evidence outstanding: {', '.join(d['missing'])}."
    elif dissent == 0 and r["pd"] < 0.07 and p["headroom"] >= 8:
        rec, why = "APPROVE", "All gates pass, risk is low and the Council is unanimous."
    elif r["pd"] > 0.18:
        rec, why = "DECLINE", f"Calibrated probability of default is {r['pd']*100:.1f}%, outside the acceptable band."
    else:
        rec, why = "OFFICER REVIEW", "Policy passes but at least one agent holds an unresolved reservation."

    confidence = round(max(0.35, min(0.97, 0.55 + 0.35 * agreement - 0.25 * disagreement
                                     + (0.08 if d["complete"] else -0.10)
                                     - (0.10 if p["income"]["material_variance"] else 0.0))), 2)
    decisive = max(case["decision_factors"], key=lambda x: abs(0.5 - x["weight"]))
    unresolved = [x["headline"] for x in positions if x["stance"] in ("Concern", "Oppose")]
    if challenge["stance"] in ("Concern", "Oppose"):
        unresolved.append(challenge["headline"])
    return {
        "recommendation": rec, "rationale": why, "confidence": confidence,
        "disagreement": disagreement, "dissent_count": f"{dissent} / {len(positions)}",
        "decisive_factor": decisive["name"], "decisive_detail": decisive["detail"],
        "unresolved": unresolved, "challenger_ask": challenge.get("ask"),
        "conditions": _conditions(case, rec),
    }


def _conditions(case: dict, rec: str) -> list[str]:
    c = []
    if case["documents_summary"]["missing"]:
        c.append("Receive and verify: " + ", ".join(case["documents_summary"]["missing"]))
    if case["policy"]["income"]["material_variance"]:
        c.append("Employer confirmation of income before drawdown")
    if rec == "APPROVE":
        c.append(f"Standard terms at {case['policy']['rate']}% over {case['application']['term']} months")
        c.append(f"Salary deduction mandate for ${case['policy']['instalment']:,.0f} per month")
    if case["fraud"]["level"] in ("Elevated", "Critical"):
        c.append("Integrity investigation cleared by Compliance")
    return c


# ------------------------------------------------------------ orchestration
_NUM = re.compile(r"\d[\d,.]*")


def _numeric_check(pos: dict, fallback: dict) -> dict:
    """The engines own every number. If the model restated a figure, the claim is
    rewritten from the deterministic prior and the rewrite is recorded."""
    text = str(pos.get("reasoning", ""))
    stripped = re.sub(r"E-[A-Z0-9]+", "", text)
    if _NUM.search(stripped):
        pos["reasoning_model"] = text
        pos["reasoning"] = fallback["reasoning"]
        pos["numeric_rewrite"] = True
    else:
        pos["numeric_rewrite"] = False
    return pos


def _grounding_check(pos: dict, evidence: dict) -> dict:
    cited = [e for e in pos.get("evidence", []) if e in evidence]
    unsupported = [e for e in pos.get("evidence", []) if e not in evidence]
    pos["evidence"] = cited or list(evidence)[:1]
    pos["grounded"] = not unsupported
    pos["unsupported_citations"] = unsupported
    if pos.get("stance") not in STANCES:
        pos["stance"] = "Caution"
    try:
        pos["confidence"] = round(float(pos.get("confidence", 0.7)), 2)
    except (TypeError, ValueError):
        pos["confidence"] = 0.7
    return pos


def _prompt(agent: dict, case: dict, evidence: dict, extra: str = "", stance: dict | None = None) -> str:
    ids = REMIT_EVIDENCE.get(agent["id"], ALL_EVIDENCE)
    facts = [evidence[i] for i in ids if i in evidence]
    lines = "\n".join(f'- [{f["id"]}] {f["text"]}' for f in facts)
    pos = (f"YOUR POSITION (already decided by the engines): {stance['stance'].upper()} — "
           f"{stance['headline']}\n" if stance else "")
    return (f"ROLE: {agent['name']}\nREMIT: {agent['remit']}\n\n"
            f"CASE: {case['application']['id']} — {case['member']['name']}, "
            f"{case['application']['product']}, ${case['application']['amount']:,}.\n\n"
            f"EVIDENCE (cite these ids only):\n{lines}\n\n{pos}{extra}\n"
            f"Return JSON exactly of this shape:\n{SCHEMA}")


async def run(case: dict, emit=None):
    """Run the full deliberation. `emit` is an async callback for streaming."""
    evidence = build_facts(case)
    async def send(ev, data):
        if emit:
            await emit(ev, data)

    await send("start", {"agents": [a["name"] for a in AGENTS] + [CHALLENGER["name"]],
                         "evidence": list(evidence.values()),
                         "model": llm.status()})

    ESCALATE = {"Support": "Caution", "Caution": "Concern", "Concern": "Oppose", "Oppose": "Oppose"}
    positions = []
    for agent in AGENTS:
        await send("agent_start", {"id": agent["id"], "name": agent["name"]})
        fb = prior(agent["id"], case)
        got = await llm.json_call(SYSTEM, _prompt(agent, case, evidence, stance=fb), fb,
                                  num_predict=300)
        # the engines own the stance; the model owns the narrative and may escalate with a reason
        stance = fb["stance"]
        escalated = bool(got.get("escalate")) and str(got.get("escalate_reason", "")).strip()
        if escalated:
            stance = ESCALATE[stance]
        got["stance"] = stance
        got["confidence"] = fb["confidence"] if not escalated else round(max(0.4, fb["confidence"] - 0.08), 2)
        got["escalated"] = bool(escalated)
        got = _numeric_check(got, fb)
        got = _grounding_check(got, evidence)
        pos = dict(agent, **got)
        positions.append(pos)
        await send("agent", pos)

    # ---- challenger attacks the emerging conclusion
    await send("agent_start", {"id": "challenger", "name": CHALLENGER["name"]})
    emerging = "; ".join(f"{p['name']}: {p['stance']} — {p['headline']}" for p in positions)
    cfb = challenger_prior(case, positions)
    ch = await llm.json_call(
        SYSTEM,
        _prompt(dict(CHALLENGER), case, evidence, stance=cfb,
                extra=f"EMERGING COUNCIL POSITIONS:\n{emerging}\n"
                      "Identify the single most important way this conclusion could be wrong, and state the "
                      "specific evidence that would settle it."),
        cfb, num_predict=300)
    ch["stance"] = cfb["stance"]
    ch["confidence"] = cfb["confidence"]
    # challenger sees all evidence
    ch["evidence"] = [e for e in ch.get("evidence", []) if e in evidence] or cfb["evidence"]
    ch = _numeric_check(ch, cfb)
    ch = _grounding_check(ch, evidence)
    ch.setdefault("ask", cfb["ask"])
    ch.setdefault("target", cfb.get("target"))
    challenger = dict(CHALLENGER, **ch)
    await send("agent", challenger)

    # ---- evidence repair: the targeted agent revises
    revision = None
    if challenger.get("target") and challenger["stance"] in ("Concern", "Oppose"):
        tgt = next((p for p in positions if p["id"] == challenger["target"]), None)
        if tgt:
            await send("challenge", {"from": "Challenger", "to": tgt["name"],
                                     "question": challenger["headline"], "ask": challenger.get("ask")})
            softer = {"Support": "Caution", "Caution": "Concern", "Concern": "Concern", "Oppose": "Oppose"}
            revision = dict(tgt)
            revision["stance"] = softer[tgt["stance"]]
            revision["confidence"] = round(max(0.4, tgt["confidence"] - 0.12), 2)
            revision["headline"] = tgt["headline"].rstrip(".") + ", subject to the Challenger's verification request."
            revision["revised"] = True
            revision["revision_note"] = challenger.get("ask")
            positions = [revision if p["id"] == tgt["id"] else p for p in positions]
            await send("revision", revision)

    summary = synthesize(case, positions, challenger)
    result = {"positions": positions, "challenger": challenger, "summary": summary,
              "evidence": list(evidence.values()),
              "grounding": {"unsupported": sum(len(p.get("unsupported_citations", [])) for p in positions + [challenger]),
                            "numeric_rewrites": sum(1 for p in positions + [challenger] if p.get("numeric_rewrite")),
                            "llm_positions": sum(1 for p in positions + [challenger] if p.get("_source") == "llm"),
                            "total_positions": len(positions) + 1},
              "revision": revision}
    await send("summary", result)
    return result
