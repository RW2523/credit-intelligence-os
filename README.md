# Credit Intelligence OS

A working, local-first credit intelligence platform for a cooperative — origination, decision
intelligence, an AI Credit Council, member intelligence, early warning, collections, copilots,
governance and an auditable decision ledger, running as **one system** on your Mac.

Everything runs on this machine. No cloud calls, no API keys. The reasoning agents use a **small
local model** through Ollama; every number they talk about comes from deterministic engines, never
from the model.

---

## Run it

```bash
./run.sh
```

That is all. The script creates a Python environment, installs dependencies, pulls the small model
(`llama3.2:3b`, ~2 GB, once), starts the server and opens <http://127.0.0.1:8899>.

To start again from a clean slate: `CIOS_RESET=1 ./run.sh`
To use a different local model: `CIOS_MODEL=qwen2.5:3b ./run.sh`

**The platform works without a model too.** If Ollama isn't running, every agent falls back to its
deterministic position and the UI marks those positions `rule-based`. Nothing breaks.

---

## The 6-minute demo

1. **Portfolio Overview** — pipeline, approval rate, exposure-weighted predicted delinquency, risk
   mix, AI highlights, and members drifting from their own baseline.
2. **Applications → David Carter (APP-104328)** → **Open Workbench**.
3. Press **Run Council**. Five specialists reason one after another, a **Challenger** attacks the
   emerging conclusion, and the Policy agent **revises its position** in response. Takes ~20 s.
4. Open the **Documents & evidence** tab, then **Document Intelligence** in the sidebar. Click any
   extracted field — `Net Monthly`, say — and the box is drawn on the actual PDF where the value was
   found. Scroll down for the cross-source reconciliation: application vs payslip vs bank vs core
   data, with the 17.3% income variance flagged as *a verification item, not an allegation of fraud*.
5. Back in the workbench, read **What changes the outcome?** and then **Approve** a clean case
   (James Lee, APP-104172) — an approval token is issued, the execution service creates the facility
   and the amortisation schedule, and monitoring starts.
6. **Early Warning** — David Carter has been a perfect payer for 14 months and has now slipped. The
   change point is detected against *his own* baseline, corroborated by salary-deduction and savings
   data, and suppressed where a known bank outage explains it. Daniel Brooks is in **RECOVERY**.
7. **Collections** — the same members, ranked by expected value, each with a *why now* and a next
   best action. Press **Draft message** — the local model writes it, and it is a draft requiring
   officer approval.
8. **Policy Sandbox** — drag the DSR ceiling to 34% and **Run simulation**. Every frozen snapshot is
   replayed; you see which five cases change outcome and which segments are affected. Nothing
   touches production.
9. **Autonomy Dial / kill switch** — move the dial, or engage the kill switch, and watch the routing
   on any case change to `HUMAN`.
10. **Decision Ledger** → type `APP-104172` → **Reconstruct**. Eleven steps from snapshot to
    outcome, hash-chained and verified.
11. **Member Assistant** — ask "I lost my job and I'm worried about next month's payment". It never
    states a credit decision; it detects the hardship cue and creates a support task.

---

## What is actually implemented

| Layer | Implementation |
|---|---|
| **Policy & affordability** | Pure Python. Annuity instalment, DSR, tenure, exposure, term, product ceilings, authority bands, maximum supportable financing. Advisory gates route to a person; hard gates fail the case. |
| **Credit risk** | scikit-learn: logistic regression + gradient boosting with isotonic calibration, trained at startup on a 6,000-row synthetic population; additive log-odds contributions produce controlled reason codes (R01–R10). Probabilities are shrunk toward the base rate so no case is ever claimed at 0% or 100%. |
| **Fraud & integrity** | Deterministic rules + Isolation Forest + a guarantor/device relationship graph. A high score is an *investigation signal*, never a finding of fraud. |
| **Document intelligence** | Classification, field extraction with per-field confidence and **bounding boxes**, forensics (tamper, font consistency, metadata, duplicate hash), cross-source reconciliation and exception detection. Uploaded PDFs are really parsed with `pypdf`. |
| **Longitudinal member intelligence** | CUSUM change-point detection against each member's own baseline, a logistic 30/90-day forecast, corroboration and suppression rules, a five-state machine with hysteresis, and recovery detection. |
| **AI Credit Council** | A bounded workflow, not a chatroom: 5 specialists → Challenger → targeted revision → Synthesizer. Each agent sees only the evidence in its remit and must cite evidence ids. |
| **Grounding discipline** | Two checks. Citations not in the evidence register are stripped and counted. **Any figure the model writes triggers a rewrite** — the reasoning is replaced with the engine's own wording and the model's draft is kept for audit. The governance dashboard counts both. |
| **Autonomy & execution** | A board-set Autonomy Dial with hard limits is the only path to autonomous execution, plus a kill switch. Approval tokens and idempotency keys guard the execution service, which is the only privileged writer. |
| **Decision ledger** | SQLite, append-only, SHA-256 hash-chained, with full-chain verification and 11-step case reconstruction. |
| **Assistants** | A case copilot with hybrid policy retrieval and token streaming, and a member assistant that is prohibited from stating a credit decision and hands hardship and complaint cues to a person. |

### Where the model is and isn't used

The local model **never** computes eligibility, affordability, risk, fraud, a forecast or a routing
decision. It writes the *language* of an agent's position, the Challenger's question, outreach
drafts and copilot answers. Its stance can escalate a position (with a stated reason) but never
soften one. This is visible in the UI: every rewritten claim is labelled, and the model's original
draft is one click away.

---

## Roles

Switch role in the bottom-left. Credit Officer, Senior Officer, Collections Officer, Risk Manager,
Compliance Officer, Branch Manager, Board/Governance, Member — each lands on the surface that
matters to them.

## Layout

```
backend/
  main.py            FastAPI surface — 36 routes
  domain.py          case assembly, snapshot freezing
  council.py         AI Credit Council orchestration + grounding checks
  llm.py             Ollama client (small models only)
  store.py           SQLite: ledger, decisions, governance config
  seed.py            synthetic members, applications, documents, policies
  engines/           policy.py  risk.py  fraud.py  lmi.py  docs.py
frontend/            no build step — ES modules, hand-written CSS
demo_files/          synthetic PDFs / PNG / CSVs used as real evidence
data/cios.db         created on first run
```

## Scope

All names, figures, documents and predictions are **synthetic**. The platform does not connect to a
real core banking system and makes no real credit decisions. The architecture is arranged so a
production backend can replace the simulated data and services without redesigning the flows.
