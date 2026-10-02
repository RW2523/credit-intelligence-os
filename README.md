# KT Credit Intelligence

A credit-intelligence platform for **Koperasi Angkatan Tentera Malaysia Berhad (Koperasi Tentera, KT)** —
Islamic financing origination, member servicing, early warning, collections, financial-distress and
cross-selling analytics, governance and an auditable decision ledger — running as one system on this
machine. Members are Armed Forces personnel, MINDEF civil servants and veterans; amounts are in Ringgit;
every timestamp is Malaysia time (UTC+8).

All members, figures and documents are **synthetic**. Product names and branch locations follow KT's
public information; terms (profit rates, limits) are placeholders until KT confirms them.

The change list this build answers is in [`docs/KT-CHANGE-PLAN.md`](docs/KT-CHANGE-PLAN.md) (with the
original request in `docs/requests/`).

---

## Run it

```bash
./run.sh
```

Creates the Python environment, makes sure the local model is available, generates the demo evidence and
serves <http://127.0.0.1:8899>.

| Setting | Effect |
|---|---|
| `CIOS_RESET=1 ./run.sh` | start from a clean database (re-anchors the demo to today) |
| `CIOS_TODAY=2026-10-15` | freeze "today" to the demo day; every seeded date and new event moves with it |
| `CIOS_MODEL` | main model for every assistant and the Council (default `qwen3:30b`) |
| `CIOS_NUM_CTX` | context size to request; unset (default) uses the Ollama server's default so every app sharing the model asks for the same thing |
| `CIOS_FAST_MODEL` | fallback model (default `llama3.2:3b`) |
| `CIOS_COUNCIL_MODEL` | optional separate model for the six Council calls |
| `CIOS_DEMO=0` | hide the demo accounts on the sign-in page |
| `CIOS_DEMO_PASSWORD`, `CIOS_MEMBER_PIN` | demo credentials (default `KT-demo-2026` / `123456`) |
| `CIOS_SECRET` | fixed session-signing key (otherwise one is generated and stored) |

The platform works without a model: every assistant falls back to deterministic, grounded answers and
the UI says so.

## Sign in

Staff sign in with a staff ID; members sign in with their KT member number and PIN. With `CIOS_DEMO=1`
the sign-in page lists one-click demo accounts.

| ID | Role | Sees |
|---|---|---|
| `noraini` | Credit Officer (up to RM30,000) | overview, applications, intake, documents, Member 360, KT Assistant |
| `aisha` | Senior Credit Officer (up to RM100,000) | + early warning, cross-selling, **possible-bankruptcy outlook** |
| `azlan` | Collections Officer | early warning, collections, Member 360 (+ distress outlook) |
| `priya` | Risk Manager | governance, policy sandbox, early warning (+ distress outlook) |
| `siewling` | Compliance Officer | decision ledger, governance (+ distress outlook) |
| `kamarul` | Branch Manager (Credit Committee, up to RM250,000) | cockpit and everything operational |
| `zulkifli`, `rohana` | Board | cockpit (aggregates only), sandbox, governance, ledger, Autonomy Dial |
| `farah` | Marketing & Member Growth | cross-selling (never distress bands), Member 360 |
| `104328`, `104310`, `104415` … | Member | own account, Check Before You Borrow, Member Assistant |

Roles are enforced on the server for every API call, not just hidden in the menu.

## A ten-minute KT demo

1. **Member (104328, Sjn Ahmad Faizal)** — the portal opens in Bahasa Malaysia: balance RM18,250, next
   deduction RM650 on the 25th via Biro ANGKASA. Ask *"Berapa baki pinjaman saya dan bila bayaran
   seterusnya?"* — the answer is in Malaysian Malay, with the balance (never the RM25,000 application).
   Open **Semak Sebelum Memohon** — the indicative maximum (RM32,800 over 48 months) is the same figure the
   officer's workbench shows, with the binding limit named.
2. **Credit Officer (noraini)** — Portfolio Overview → *What needs attention today*. Open
   **Kpl Mohd Ridzuan, APP-104310**: maximum supportable financing reads **RM0** with the reasons
   (commitments use 56% of net pay against 40%; KT exposure RM14,200 over the RM14,000 cap) — not "−200".
   Try to approve the RM120,000 contract case: refused, above the officer's authority.
3. **Document Intelligence** — open a *slip gaji*; click *Gross Monthly*: the box lands on RM4,680.00 on
   the rendered payslip, at any zoom.
4. **Senior Officer (aisha)** — Member 360 → **Mej (B) Ramasamy**: the *Possible bankruptcy* section
   (restricted, access logged) with drivers, recommended support and the national context. Then
   **Cross-selling options**: takaful / financing / retention with the reason chain for each member.
5. **KT Assistant** — ask *"Which Lumut cases are waiting on documents?"* or *"Jumlah pembiayaan mengikut
   cawangan"*: it calls data tools, draws a chart and reports how many of its figures were traced to data.
6. **Board (zulkifli)** — **Management Cockpit**: hover the trend for every value; click the legend to hide
   a line. **Policy Sandbox**: move the DSR ceiling, replay the portfolio, read which members change
   outcome, and propose. Sign in as **rohana** to approve it as the second Board member — the policy version
   increments and the change takes effect. **Decision Ledger**: every record in plain language, the raw JSON
   one click away.

## Deployment (Linux / DGX Spark)

`ops/cios.service` is the reference systemd user unit (MYT timezone, `qwen3:30b`). The public URL is a
Tailscale Funnel to `127.0.0.1:8899`.

```bash
ops/status.sh        # service, model, public endpoint
ops/smoke.sh http://127.0.0.1:8899           # HTTP smoke test (SMOKE_LLM=1 adds the model paths)
ops/bench_llm.sh     # tokens/s and latency per model
```

### If the assistants are slow

`ops/status.sh` shows where the model runs. It should say **on GPU** (≈90 tokens/s on the Spark). If it
says **on CPU** (≈3 tokens/s, 30–40 s per answer), the Ollama container has lost GPU access — inside it
`nvidia-smi` fails with "Failed to initialize NVML: Unknown Error", a known Docker/NVIDIA issue. Restart it:

```bash
docker restart cios-ollama
```

The top bar also turns the model chip amber ("· CPU") when this happens. A permanent host-level fix for the
GPU dropout is to run Docker with the `cgroupfs` cgroup driver or use the NVIDIA Container Toolkit's CDI
device mode.

The Ollama container is shared with another application that uses the same qwen3 model. KT shares that one
loaded instance (it requests no context size of its own): requesting a different size would make Ollama reload
the 18 GB model each time the two apps alternate, and a second copy does not fit beside the vision model.

## Tests

```bash
.venv/bin/python -m pytest tests -q                                   # policy, seed, documents, API, language, distress
CIOS_EVAL_LLM=1 .venv/bin/python -m pytest tests/test_assistant_eval.py -s   # 24-question BM/EN assistant evaluation
.venv/bin/python tests/e2e_browser.py http://127.0.0.1:8899 shots --llm      # every role and view in a real browser
.venv/bin/python tests/bbox_check.py data/docs                         # every highlight box contains its value
```

## How it fits together

* `backend/seed.py` — KT branches, products (flat profit rates), members across TD / TLDM / TUDM / MINDEF /
  veterans, applications, collections; all dated relative to the demo day.
* `backend/docgen.py` — generates the evidence (slip gaji, penyata bank, surat pengesahan, MyKad, ANGKASA
  schedule, SSM, Borang B …) and records where every value is drawn, so highlights are exact.
* `backend/engines/policy.py` — DSR on verified net pay, the 60%-of-gross deduction cap, exposure and product
  limits; the maximum supportable financing never goes below zero and names its binding limit.
* `backend/engines/distress.py`, `crosssell.py` — possible-bankruptcy outlook (calibrated to ~0.3%) and
  cross-sell suggestions with responsible-lending rules.
* `backend/connectors/` — Experian CCRIS, SOLA and eKYC adapters, **simulated** until KT provides sandbox access.
* `backend/assistant.py`, `lang.py` — Member Assistant (BM/EN, figure-checked) and the tool-calling KT Assistant.
* `backend/auth.py` — sign-in, sessions and the role hierarchy.
* `frontend/` — plain ES modules; PDF.js is vendored in `frontend/vendor/pdfjs` so nothing loads from the internet.
