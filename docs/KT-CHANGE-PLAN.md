# KT Credit Intelligence — Change Plan

**Source documents:** `KT Things to Modify (1).docx` (commit `12a3720`, 48 paragraphs + 13 screenshots) and the follow-up brief: *intuitive UI; an intelligent chat interface that interprets the data as the user requires; sample data aligned with Koperasi Tentera; make it look better for them.*
**Codebase baseline:** `main` at `12a3720`, ~5,900 lines (FastAPI backend, plain-ES-module frontend, SQLite, Ollama).
**Date:** 2 October 2026.

Every item in the document — text *and* screenshots — is traced to a work item in §8. Nothing is deferred without being named.

---

## 0. Delivery status — built and tested (2 Oct 2026)

All 22 work items are implemented on branch `kt-localisation`. Verification on the DGX Spark against a
fresh database: **41 unit/API tests**, **24/24 live assistant questions** (13 BM, 11 EN), **55/55 HTTP
smoke checks** with the local model, and **168/168 browser checks** across every role and view.

| Item | Status | What was built | Verified by |
|---|---|---|---|
| W-01 Login & roles | Done | Staff and member sign-in, signed sessions, rate limiting; every API call checked server-side; authority limits RM30k / RM100k / RM250k; actors from the session | `test_api` role matrix; browser: each role sees only its surfaces |
| W-02 Ringgit | Done | `RM` everywhere (UI, API, ledger, prompts, documents) | browser + smoke: no `$` on any screen or response |
| W-03 KT members & branches | Done | 83 members — TD, TLDM, TUDM, MINDEF, veterans — with ranks, units, camps, MyKad, service no.; 6 KT branches; KT staff names | `test_seed` |
| W-04 Products & terms | Done | Personal / Express / Fees / SME / Term / Contract Financing-i, Motor & General Takaful, Ar-Rahnu KT; flat profit rates; financing / profit / takaful vocabulary; unique policy IDs (POL-001…013) | `test_seed`; prompts audited |
| W-05 2026 & MYT | Done | Demo day anchored (`CIOS_TODAY` to freeze); every timestamp `+08:00`; payments on the 25th via Biro ANGKASA | `test_api` timestamps; `test_seed` dates |
| W-06 Malaysian documents | Done | 110 generated documents (slip gaji, penyata bank, surat pengesahan, MyKad, ANGKASA schedule, SSM, Borang B, sebut harga …), SPECIMEN-watermarked, fictional bank | `test_documents` |
| W-07 Highlight placement | Done | PDF.js canvas rendering; boxes from the generator's own coordinates; uploads boxed from pypdf positions; image and CSV row highlighting | 420/420 PDF fields verified by text position; browser checks every payslip box sits on the page |
| W-08 −200 | Done | Maximum floored at RM0, binding limit named, constraint-aware "what changes the outcome" (RM433/month; RM50 equity); 60% cap added | `test_policy` incl. 1,000 random cases |
| W-09 qwen3:30b | Done | Default model for assistants and Council; kept loaded; per-feature override; `ops/bench_llm.sh` | 40 tok/s, 0.3 s first token; Council ≈ 48 s warm; case question ≈ 4 s warm |
| W-10 Malay quality | Done | Language detection, Malaysian-Malay style guide, Indonesian-word detection and repair (incl. "simpangan"→"simpanan"), BM hardship/complaint cues | `test_assistant_eval`: 13/13 BM, 0 Indonesian words |
| W-11 Balance confusion | Done | Labelled fact block (balance vs pending application), figure validation and regeneration, deterministic fallback | eval: RM18,250 never RM25,000 |
| W-12 Intelligent chat | Done | KT Assistant: role-scoped tools, charts for aggregates, streamed, history, figure grounding that blocks fabricated numbers | browser + smoke: tool call, chart, grounding badge |
| W-13 Check Before You Borrow | Done | Member page using the officer's engine; maximum, binding limit, DSR and 60% meters, gates, documents, apply | `test_api` parity RM32,800 |
| W-14 Chart legends & hover | Done | Legend on every chart, crosshair tooltip with each series, legend toggles; bar/donut/step tooltips | browser: hover and toggle |
| W-15 Ledger JSON | Done | Plain-language rendering per stage; JSON behind "technical record"; chain link shown | browser |
| W-16 Policy sandbox | Done | Starts from production; plain-language help; current vs candidate; affected members; min-confidence and max-PD wired; 60% cap & min salary controls; two-Board-member approval bumps the policy version | `test_api`; browser propose → approve |
| W-17 Possible bankruptcy | Done | Calibrated model (cohort 0.30%), drivers, supportive actions, national context with citations, restricted roles, access logged, model card | `test_distress`, `test_api` |
| W-18 Cross-selling | Done | Patterns A/B/C with reason chains + KT extras, responsible-lending rules, consent/DNC, feedback, drafts BM/EN, CSV; simulated CCRIS/SOLA/eKYC adapters | `test_distress`; browser (marketing never sees distress) |
| W-19 UI | Done | KT identity (interim mark), role landing pages, BM/EN switch, responsive, print statement, guided demo per role | browser at desktop and phone width |
| W-20 Sample data | Done | 83 members, 22 live cases, 8 collections cases, distress and cross-sell signals | `test_seed` |
| W-21 Foundation | Done | `clock`, `fmt`, `lang`, i18n, pytest suite, browser suite, smoke script | — |
| W-22 Deployment | Done (in branch) | `ops/cios.service` (MYT, qwen3), `ops/status.sh` checks Tailscale Funnel and Ollama; sign-in ends anonymous access | — |

**Not done, by design or pending KT:** real CCRIS / SOLA / eKYC connections (adapters are simulated, K9);
KT's own logo and colours (interim mark, K7); product terms are placeholders (K1); staff screens are
bilingual for navigation, headings and key labels, with some longer staff text still in English; the
optional `qwen2.5vl` grounding for scanned uploads (W-07 stretch) was not built.

## 1. Where the platform is today (facts the plan depends on)

| Area | Current state |
|---|---|
| Process | One FastAPI process on `127.0.0.1:8899` serves the API **and** `frontend/` as static files (`backend/main.py:921-922`). No Node, no build step. |
| Routing | Hash routes `#view/param` (`frontend/app.js:59-77`); `#workbench/APP-104310` → `views/applications.js:131`. |
| State | SQLite `data/cios.db` via `backend/store.py` (key/value + hash-chained ledger). Seed data is copied into the DB on first run; **seed edits only appear after `CIOS_RESET=1`**. |
| Data | Everything synthetic lives in `backend/seed.py`: `TODAY = date(2024,4,16)`, `BRANCHES = ["Makati","Cebu","Davao"]`, 6 conventional loan products, 12 members with `+63` phones, Philippine employers. |
| Auth | **None.** Role is a `<select>` in the sidebar (`app.js:123-126`), lives only in `state.role`, resets to `officer` on reload. Actors are hardcoded (`applications.js:386`, `main.py:280,443,716,789`, `portal.js:4`). |
| LLM | `backend/llm.py`: `CIOS_MODEL` default `llama3.2:3b`; `CIOS_FAST_MODEL` exists but is unused; `num_ctx` 4096. Ollama is serving `qwen3:30b-a3b-instruct-2507-q4_K_M` (18.6 GB), `qwen2.5vl:7b` (vision, 6 GB) and `llama3.2:3b`. |
| Deployment | `~/.config/systemd/user/cios.service` pins `CIOS_MODEL=llama3.2:3b`. Public URL `https://spark-079e.tail1917c3.ts.net` is a **Tailscale Funnel** → `:8899`; the Cloudflare tunnel in `ops/` is inactive. `:8443` also exposes port 3000 (a Next.js server unrelated to this app). Server clock is UTC. |
| Tests | No unit tests. Only `ops/smoke.sh <url>` (curl assertions). |
| i18n | None. `<html lang="en">`, all strings inline, formats hardcoded `en-US`. |
| Charts | Hand-written SVG in `frontend/lib.js:128-214`; no legend component, hover is a bare `<title>`. |

---

## 2. Cross-cutting decisions (apply to every work item)

| # | Decision | Value |
|---|---|---|
| X1 | Institution | **Koperasi Angkatan Tentera Malaysia Berhad (KATMB / "Koperasi Tentera", "KT")** — credit co-operative est. 1960, ~155,000 members: serving Armed Forces (ATM: Tentera Darat, TLDM, TUDM), MINDEF civil servants, retirees/veterans. |
| X2 | Currency | Malaysian Ringgit. Display `RM18,250` (KPIs, whole ringgit) and `RM501.80` (instalments, schedules, ledger). Locale `en-MY` / `ms-MY`. No `$` anywhere. |
| X3 | Time | `Asia/Kuala_Lumpur` (UTC+8, no DST) end-to-end. All stored timestamps tz-aware ISO (`+08:00`). "Today" = `CIOS_TODAY` env if set (demo-day freeze), else real MYT date. All seed dates are **generated relative to today** so the demo never goes stale, and land in 2026. |
| X4 | Terminology | Islamic financing vocabulary everywhere (glossary §9.1): *financing* not *loan*, *profit rate* not *interest rate*, *takaful* not *insurance*, *ta'widh* not *late penalty*. |
| X5 | Products | KT's catalogue (§9.2): Personal Financing-i, Express Financing-i, Fees Financing-i, SME Financing-i, Term Financing-i, Contract Financing-i, Motor Takaful, General Takaful, Ar-Rahnu KT. |
| X6 | Languages | Bahasa Malaysia (Malaysian standard, **not** Indonesian) and English. Member-facing surfaces default BM with EN toggle; staff surfaces EN with BM toggle. |
| X7 | Model | Chat/assistant/council default → `qwen3:30b` (resolves to the installed `qwen3:30b-a3b-instruct-2507-q4_K_M`; MoE with ~3B active parameters, tool-calling capable). `llama3.2:3b` retained as `CIOS_FAST_MODEL` fallback. Vision tasks → `qwen2.5vl:7b`. |
| X8 | Role hierarchy | Member (0) < Credit Officer (1) < Senior Officer (2) < Branch Manager (3) < Head of Credit / Risk Manager / Compliance (4) < Board (5). "Officers of certain hierarchy" in the document = level ≥ 2 unless KT says otherwise (§7). |
| X9 | Affordability rules | Keep KT's DSR gate on verified net income **and** add the Malaysian government rule that total salary deductions may not exceed **60% of gross salary** (Biro ANGKASA / SPGA). Both shown; the binding one is named. |

---

## 3. Work items

Each item: **Source** (D = document paragraph, S = screenshot, U = follow-up brief) · **Observed** · **Root cause** · **Change** (with files) · **Acceptance** · **Decisions**.

### A. Access & identity

#### W-01 Login screen and role hierarchy
**Source:** D0 "0. Add a Login Screen"; S12 (role dropdown bottom-left); U1.
**Observed:** No login. Anyone on the public URL gets the officer view and can switch to Board with a dropdown. Server logs show automated probes (`/.ssh/id_ed25519`, `/.svn/wc.db`) — the app is reachable by anyone.
**Change:**
- New `frontend/views/login.js` + route `#login`: KT-branded, BM/EN, two tabs — *Staff* (staff ID + password) and *Member* (No. Tentera / MyKad + PIN, mirroring KT Online). Demo accounts per role listed on the screen in demo mode only.
- Backend `backend/auth.py`: users table in `cios.db` (hashed passwords via `passlib[bcrypt]`), signed session cookie (`itsdangerous`), `Depends(current_user)` on every `/api/*` route, role→views enforced server-side (today it is display-only, `app.js:35-56`). Rate-limit login attempts.
- Remove the role `<select>`; replace with user card + *Log out*. Keep a *Switch demo user* control only when `CIOS_DEMO=1`.
- Replace hardcoded actors with the session user: `applications.js:386`, `main.py:280-281`, `443`, `716`, `789`, `portal.js:4` (`mid='104328'`).
- Use `ROLES[*].authority` (`main.py:23-40`, currently never read) as the hierarchy level + approval limit; this is what gates W-17 and W-18.
- Member accounts: one per seeded member, so the panel can log in as different members.
**Acceptance:** Unauthenticated `/api/*` → 401; a member cannot open `#applications`; a Credit Officer cannot see the Bankruptcy section; the actor on ledger entries is the logged-in user; bots hitting the Funnel URL see only the login page.
**Decisions:** staff identifier format (staff ID vs email); whether members log in by No. Tentera or MyKad; SSO/eKYC via Digibanc is out of scope for this phase.

### B. Localisation to Koperasi Tentera

#### W-02 Currency → Ringgit
**Source:** D1 "Change the money from US dollars ($) to Ringgit (RM)"; S1, S2, S4, S10, S12 (every `$`).
**Change:**
- `frontend/lib.js:8` `money()` → `'RM' + toLocaleString('en-MY', …)`; `num/date/dtime` (`lib.js:10-12`) → `en-MY`.
- New `backend/fmt.py` with `rm(x, d=0)`; replace every inline `f"${x:,.0f}"`: `main.py` 49, 146, 156, 315, 350, 431, 483, 549-560, 580, 613-616, 861, 867; `council.py` 57-73, 115, 232, 279; `engines/policy.py` 70-73, 149, 155; `store.py` 148; `seed.py` 207-276, 312, 340, 385-409.
- LLM prompts (`main.py:501-504`, `620-624`, `478-480`; `council.py:15-26`) told the currency is RM and to write amounts as `RM12,345`.
- Re-scale all synthetic amounts into realistic RM (see W-20): KT Personal Financing-i is RM1,000–RM200,000; armed-forces basic pay RM1,500–RM9,000 by rank.
**Acceptance:** `grep -rn '\$' frontend backend | grep -v '\${'` returns no currency uses; smoke test asserts `RM` on portal, workbench, cockpit, ledger payloads.

#### W-03 KT members, employers, branches, staff
**Source:** D2 "Members, employers and branches are from another country… KT's members are Armed Forces personnel, MINDEF civil servants and retirees, paid monthly, with repayments taken from salary. The panel needs to see their own members on screen."; S2 (Makati/Cebu/Davao; Carter/Torres/Brooks; +63); S10 (By branch); U3.
**Change (`backend/seed.py` → new generator `backend/seedgen.py`, see W-20):**
- **Member types:** `serving_atm` (Tentera Darat / TLDM / TUDM, with rank and No. Tentera), `mindef_civil` (MINDEF civil servant, grade e.g. N19/N29/N41), `retiree` (veteran on pension via JHEV/KWAP). Fields: MyKad number (`YYMMDD-PB-####`), service number, unit/camp, pay grade, join date, retirement date.
- **Employers:** Angkatan Tentera Malaysia (per service), Kementerian Pertahanan (MINDEF), Jabatan Hal Ehwal Veteran (pensioners).
- **Repayment channel:** `salary_deduction_angkasa` (Biro ANGKASA SPGA) for serving/civil; `pension_deduction` for retirees. Shown on Member 360 and portal.
- **Branches** (from KATMB's published contacts; confirm the full list with KT): Cawangan Utama Kuala Lumpur (Wangsa Maju), Kiosk Kem KEMENTAH (Sungai Besi), Lumut (Perak), Kuantan (Pahang), Kota Kinabalu (Sabah), Kok Lanas – Kem Desa Pahlawan (Kelantan).
- **Names:** Malaysian naming conventions (bin/binti, a/l, a/p, anak), with rank prefixes (Prebet, Kpl, Sjn, PW II, Lt, Kapt, Mej; Lt M for TLDM; (B) for retired). Examples in §9.3.
- **Phones** `+60 1x-xxx xxxx`; addresses in camps/towns above.
- **Staff:** officers, managers and board personas become KT staff names (`main.py:23-40`): e.g. Credit Officer *Noraini binti Hashim*, Senior Officer *Aisha binti Abdul Rahman*, Collections *Mohd Azlan bin Yusof*, Risk *Priya a/p Nair*, Compliance *Tan Wei Jian*, Branch Manager *Grace Lim Mei Ling*, Board *Dato' Hj. Zulkifli bin Ahmad*. (Synthetic; swap for real staff if KT prefers.)
- Cockpit "By branch" / "By officer" (`main.py:894-917`) follow automatically.
**Acceptance:** Applications list, Member 360, Portfolio, Cockpit show only KT-plausible members, branches and officers; no `+63`, no Philippine city.

#### W-04 KT products and Islamic-finance terminology
**Source:** D3 "Products are not KT's, and the wording is conventional banking – Change everywhere… Use KT's product names, 'financing' instead of 'loan', and 'profit rate' instead of 'interest rate'"; S2 (Personal/Business/Auto/Education/Home/Car Loan); S4 (policy text); S11/S12 (autonomy limits list "Personal Loan, Auto Loan, Education Loan"); S1 ("Personal Loan — $25,000").
**Change:**
- `seed.PRODUCTS` (`seed.py:9-22`) → catalogue in §9.2 with: EN name, BM name, Shariah contract, min/max amount, tenure range, profit rate (flat p.a.), required documents, `kind` (`financing` | `takaful` | `rahnu`). Only `financing`/`rahnu` products appear in the credit queue; `takaful` products feed W-18.
- Every other product list: `store.py:105` (autonomy limits), `main.py:706` (sandbox segment test → use `kind`/product code), `seed.POLICY_LIBRARY` (`seed.py:330-347`), `intake.js:27`.
- Terminology sweep (glossary §9.1): `intake.js:74` "Interest rate" → "Profit rate (flat, p.a.)"; `applications.js:408,411` and `main.py:333-337` schedule columns "Principal/Interest" → "Financing amount/Profit"; "Loan balance" → "Financing balance"; collections wording "late fee/penalty" → "ta'widh (late-payment compensation)"; "insurance" → "takaful"; `risk.py` / `seed.py` field `prior_loans` → `prior_financings` (internal, optional).
- Prompts and council agent remits (`council.py:32-45`) use the new vocabulary.
- Add a *Shariah contract* line on workbench Overview and portal (e.g. "Tawarruq (commodity murabahah)").
- Fix duplicate policy ID: S4 shows `POL-001` on both *Debt service ratio* and *Term limit* — give Term limit its own ID (`seed.py:330-347`).
**Acceptance:** `grep -rniE '\b(loan|interest|insurance|penalty)\b' frontend backend` returns only glossary/comment lines; the panel sees KT product names in queue filters, cockpit "By product", autonomy limits and policy library.
**Decisions:** confirm product terms (amounts, tenures, profit rates, contracts) with KT; public sources give Personal Financing-i as RM1,000–200,000, 6–120 months, ~3.65% p.a. — treat as placeholders until confirmed.

#### W-05 Dates into 2026, demo-day "today", Malaysia time
**Source:** D4 "Shift all synthetic dates into 2026, set 'today' to the demo day, and… all the date/time are in Malaysia time (UTC+8)"; S1 (payments Nov 2023–Apr 2024); S3 ("uploaded Apr 15"); S10 (axis Apr 1–15); S11 (ledger "Sep 29, 08:54 PM" vs payload `2026-09-29T20:54:30`, "Board Resolution 2024-04").
**Root cause:** `TODAY = date(2024,4,16)` hardcoded in `seed.py:6`, `engines/policy.py:10`, `engines/lmi.py:41`; `main.py:61` `"today":"2024-04-16"`; `domain.py:142` `startswith("2024-04-15")`; `main.py:132` member-since; `store.py:107-108`; `lmi.py:10,13`; `seed.py:385,398,401,408`; first repayment hardcoded `date(2024,5,5)` at `main.py:324-354`; naive `datetime.now()` on a UTC server at `main.py:136,215,294,450,642,725,890`, `store.py:55,120`; frontend formats in browser zone; `COMMS` entries dated after today (`seed.py:306-317`).
**Change:**
- New `backend/clock.py`: `TZ = ZoneInfo("Asia/Kuala_Lumpur")`, `now()`, `today()` honouring `CIOS_TODAY`. Replace every reference above.
- Seed generator produces all dates relative to `today()` (applications submitted T-6…T-1, payments 18 cycles ending last deduction date, trend last 16 days, comms ≤ today, board resolution `2026-xx`).
- Repayment schedule anchored to the deduction day (see decision) rather than 5th/+30d.
- Ledger/API emit ISO with `+08:00`; frontend `date/dtime` pass `timeZone:'Asia/Kuala_Lumpur'` and show "MYT" on timestamps; `ago()` compares against server time from bootstrap.
- `cios.service`: `Environment=TZ=Asia/Kuala_Lumpur`, `Environment=CIOS_TODAY=` (set on demo day). `run.sh` passes them through. README "Demo day" section.
- Reset `cios.db` once (`CIOS_RESET=1`) so the UTC-stamped ledger rows disappear.
**Acceptance:** No `2024` literal in `backend/`; every rendered date is in 2026; ledger time equals wall-clock KL time; `CIOS_TODAY=2026-10-15` makes every "today" element agree.
**Decisions:** deduction day — current demo says "5th of next month"; government pay is posted around the 25th (JANM schedule) and ANGKASA deductions follow it. Recommend 25th; KT to confirm.

#### W-06 Demo documents regenerated in Malaysian form
**Source:** D5/S3 (payslip "TechCorp Inc.", March 2024); survey finding that `demo_files/*.pdf` contain SSS/PhilHealth/Pag-IBIG and "Northstar Cooperative Bank", and the script that made them is not in the repo.
**Change:** `demo_files/generate.py` (ReportLab, deterministic) producing per member: *Slip Gaji* (MINDEF/JANM layout: Gaji Pokok, ITP, ITKA, elaun; potongan: PCB/LHDN, KWAP/pencen or KWSP, PERKESO, Biro ANGKASA, Koperasi Tentera), *Penyata Bank* (Maybank/CIMB/Bank Islam/BSN layout), *Surat Pengesahan Jawatan* from the unit, *Kad Pengenalan* / *Kad Pengenalan Tentera* (PNG), *Surat Pencen* for retirees, *Lesen Perniagaan (SSM)* for SME cases, salary-deduction CSV. The generator **records the exact drawn position of every field** into `demo_files/manifest.json`; `seed.DOCUMENTS` reads bboxes and values from the manifest — so seed values and document content can never disagree (this is half of W-07).
**Acceptance:** Every extracted field value in the UI appears verbatim in its PDF (automated check with pypdf); no Philippine institution names remain.

### C. Bugs reported

#### W-07 Document Intelligence highlights point at the wrong place
**Source:** D5 "The extracted fields in the document intelligence is not pointing to the right area in the document."; S3 (box "Gross Monthly — $4,333 (97%)" drawn over the Overtime/Income Tax rows; the PDF itself reads 52,000.00 gross and 43,000.00 net).
**Root cause (four compounding):**
1. Boxes are % of a fixed 520 px container (`styles.css:320-327`, `documents.js:90-101`), but the PDF is in an `<iframe>` whose viewer scales the 612×792 page to the frame width, adds margins and scrolls — the container and the page do not share a coordinate system.
2. Seeded boxes are hand-typed or formulaic — `bbox=[8, 20+10*i, 60, 5]` (`seed.py:382`) — and generated docs reuse David Carter's / Maria Torres's files for every member (`_FILE_FOR`, `seed.py:354-368`).
3. Seeded values do not match the PDFs (payslip 4,333 vs 52,000; employment letter 2018 vs 2022; business permit name/number; bank account ****4821 vs 1842).
4. Uploads (`main.py:184-224`) get invented boxes (`198-201`, `209-210`); PNGs ignore `object-fit` letterboxing.
**Change:**
- Render PDFs with **PDF.js** (cdnjs) onto a `<canvas>` at a known scale, multi-page; overlay positioned in PDF points → canvas pixels. Images: compute rendered rect from `naturalWidth/Height`. CSV: highlight the row.
- Bboxes come from the generator manifest (W-06) for seeded docs, and from `pypdf` `extract_text(visitor_text=…)` positions for uploads; store as `{page, x, y, w, h}` in PDF points.
- Optional stretch: `qwen2.5vl:7b` grounding for scanned uploads.
- Keep the 11-step pipeline strip (S3) and "Click an extracted field to highlight where it was found"; add a *Page n of m* indicator.
**Acceptance:** For all 60 registered documents, clicking each field draws the box over the exact value; test compares the text under each bbox with the field value.

#### W-08 "Maximum supportable financing" shows −200 and the counterfactual repeats it
**Source:** D6 "On Robert James's case, 'Maximum supportable financing' shows $-200, and 'What changes the outcome' says 'Requested amount reduced to about $-200'. Link: …/#workbench/APP-104310"; S4.
**Root cause (reproduced):** `engines/policy.py:63` — `max_financing = min(max_principal, p["max"], exposure_cap - member["outstanding"])`. Robert James: equity 2,100 + 1,400 = 3,500 → cap 3,500 × 4 = 14,000; outstanding 14,200 → `−200`, never floored. His DSR is 74.42% vs 40%, so `max_principal` is already 0 (floored at `:59`), but the exposure term is not. `counterfactuals()` (`policy.py:149`) then prints "reduced to about ${max_financing} (DSR falls below 40%)" whenever headroom < 6 — even when the figure is ≤ 0 and the binding constraint is exposure, not DSR.
**Change:**
- Floor at zero and record the **binding constraint**: `max_financing = max(0, …)`, plus `max_financing_binding ∈ {dsr, product_ceiling, exposure, deduction_cap}` and the shortfall (RM/month of commitments to shed, or RM of equity to add).
- Counterfactuals become constraint-aware: if `max_financing == 0` → "No new financing is supportable at current commitments: existing deductions use 56% of net pay against a 40% ceiling, and exposure RM14,200 already exceeds the RM14,000 cap (4× equity). Improves if existing commitments fall by RM434/month or savings/share capital rise by RM50." Never emit "reduce to about RM−200".
- Propagate the same object to the Council Policy agent (`council.py:115`) and chat context (`main.py:554`); UI `applications.js:536` shows `RM0` with a *why* tag.
- Add the 60%-of-gross deduction gate (X9) as a sixth policy gate.
**Acceptance:** Unit test: `max_financing >= 0` for every seeded case and for 1,000 random cases; APP-104310 text reads as above; no `-RM` / `RM-` anywhere.

### D. AI assistant quality and model

#### W-09 Run the chat helpers on qwen3:30b
**Source:** D7 (last sentence) and D13 "Can the larger installed model (qwen3:30b) run the chat helpers instead of llama 3.2:3b?"; S12 (top-bar chip `llama3.2:3b`).
**Answer:** Yes — it is already pulled and served. `llm._resolve` matches on base name, so `CIOS_MODEL=qwen3:30b` picks `qwen3:30b-a3b-instruct-2507-q4_K_M`.
**Change:**
- `cios.service` + `run.sh` default → `CIOS_MODEL=qwen3:30b`, `CIOS_FAST_MODEL=llama3.2:3b`.
- `llm.py`: per-feature model selection (`generate(model=…)` exists but no caller uses it): assistant/copilot/cockpit → `MODEL`; Council (6 calls per case, `council.py:284-364`) → `MODEL` by default with `CIOS_COUNCIL_MODEL` override if latency on the DGX Spark demands; `num_ctx` 4096 → 8192.
- Top-bar chip and `/api/health` show the served tag.
- Benchmark script `ops/bench_llm.sh`: tokens/s and first-token latency for both models on the Spark; record in README.
**Acceptance:** Health shows qwen3 tag; member assistant p95 first token < 2 s on the Spark; Council run completes < 60 s.

#### W-10 Malay answers: weak, wrong, and Indonesian
**Source:** D7 "Malay answers are weak and sometimes wrong. Asked 'Berapa baki pinjaman saya dan bila bayaran seterusnya?'… the assistant said the balance 'cannot be seen in real time', though $18,250 is on the same screen. Replies use Indonesian words ('Anda', 'kabar', 'Asisten Kebijakan', 'karena') rather than Malaysian Malay."; S5 (question is Malay), S6 (Google Translate detects the reply as **Indonesian**: "Saya tidak dapat memberikan informasi tentang pinjaman Anda. Anda dapat menghubungi Officer Review…"), S7.
**Root cause:** No language handling at all (`main.py:620-624` prompt is English-only, hardship/complaint keyword lists `main.py:594-596` are English-only); a 3B model defaults to Indonesian for Malay input; the application status string "Officer Review" was read as a person to contact; the "never state a decision" instruction over-triggers into refusal.
**Change:**
- Language detection per message (`backend/lang.py`: Malay/English stop-word heuristic; `lang` also selectable in the portal toggle). Reply in the member's language.
- BM system prompt with an explicit **Malaysian-standard style guide** (§9.4): use *anda* / *tuan/puan*, *kerana* not *karena*, *khabar* not *kabar*, *maklumat* not *informasi*, *ansuran* not *angsuran*, *akaun* not *rekening*, *pembiayaan* not *pinjaman*, *kadar keuntungan* not *bunga*, "Pembantu Dasar" not "Asisten Kebijakan"; statuses translated (*Officer Review* → *Semakan Pegawai*) and defined as statuses, not people.
- Post-generation check flags Indonesian markers (`karena, kabar, bisa, uang, kantor, Anda`) and regenerates once with a correction instruction.
- Hardship/complaint detection gets BM keywords (*hilang kerja, diberhentikan, tidak mampu bayar, susah, sakit, aduan, tidak puas hati*).
- Suggestion chips (`portal.js:45-47`) bilingual; portal UI strings via the i18n layer (W-21).
- Evaluation set of 24 BM/EN questions with expected facts (`backend/tests/test_assistant_eval.py`, runs against live Ollama, reports pass/fail table) — this is the measure the panel asked for.
**Acceptance:** "Berapa baki pinjaman saya dan bila bayaran seterusnya?" → "Baki pembiayaan anda ialah RM18,250. Ansuran seterusnya RM650 akan dipotong daripada gaji pada 25 Okt 2026." Eval set ≥ 95% in both languages; zero Indonesian-marker hits.

#### W-11 Outstanding balance confused with financing amount
**Source:** D8 "…the response is not accurate. At the top of the screen I can see David's outstanding balance is 18,250 but the AI says it is 25,000$. It is getting confused with the total loan amount and outstanding balance."; S8/S9 (free-text "loan balance" → $25,000; chip "What's my outstanding balance?" → $18,250).
**Root cause:** `main.py:613-619` facts string places "Outstanding balance $18,250" immediately beside "Open application APP-104328 — Personal Loan $25,000"; "$650" and "5th of next month" are hardcoded; nothing checks the model's numbers.
**Change:**
- Structured, labelled facts block: `BAKI_SEMASA / OUTSTANDING_BALANCE = RM18,250 (amount still owed on existing financing)`, `PERMOHONAN_BARU / NEW_APPLICATION = APP-104328, Pembiayaan Peribadi-i, RM25,000, status Semakan Pegawai — not disbursed, not part of the balance`, `ANSURAN_SETERUSNYA = RM650 on 25 Oct 2026 via salary deduction` computed from the schedule, not hardcoded.
- **Intent router first, LLM second:** the five known intents (balance, next payment, documents outstanding, application status, hardship) are answered deterministically in BM/EN — exactly what the chips already do — and the LLM handles free-form phrasing with the facts block.
- **Numeric grounding check** (reuse the pattern in `council.py:242-253`): any `RM` figure in the answer must appear in the facts block, otherwise substitute the correct figure or regenerate.
**Acceptance:** "How much is my loan balance?" / "Berapa baki pinjaman saya?" → RM18,250 in 20/20 runs; the application amount is never reported as a balance.

#### W-12 Intelligent, role-aware chat that interprets the data the user asks for
**Source:** U2 "Chat interface to users… an intelligent [assistant] which can interpret the data as user requires"; S10 ("Ask the cockpit"); S1/S7 (Member Assistant).
**Change — one assistant framework, three personas:**
- **Member Assistant** (portal): own account only; never a credit decision (existing guard kept).
- **Officer Copilot** (workbench, existing `/api/ask`, `main.py:492-522`): case-aware.
- **Cockpit / Board Analyst** (governance): portfolio-wide questions.
- **Architecture:** tool-calling with qwen3 (`backend/assistant/`): tools `get_member`, `get_application`, `affordability(product, amount, tenure)`, `portfolio_query(filter, group_by, metric)`, `ledger_search`, `policy_lookup`, `repayment_schedule`, `trend(metric, days)`. Model plans → tools run against the real data → answer cites the source ("from repayment schedule, 6 rows") → numeric grounding check. Tool scope is enforced by the session role (W-01) so a member's tools only see their own ID.
- Rich answers: tables and inline charts (reuse `lib.js` charts) when the question is aggregate ("show approvals by branch this month"); follow-up suggestions; streaming; per-session conversation memory; BM/EN.
- Graceful degradation: when Ollama is down the deterministic intents still work (extends `main.py:586-590`).
- Example prompts per role shipped as chips; the 24-question eval (W-10) extends to officer and board questions.
**Acceptance:** "Which Lumut cases are waiting on documents?", "Berapa jumlah pendedahan Pembiayaan Peribadi-i bulan ini?", "Why did Robert James fail policy?" all return correct, sourced answers.

### E. Member self-service

#### W-13 "Check Before You Borrow" (member view)
**Source:** D9 "For the member only view: it would be good if he has 'Check Before You Borrow' view. Before the member submits the application the system calculates his maximum loan approval amount in accordance with the DSR and other affordability calculations (which is already available under 'workbench' of 'credit officer')."
**Change:**
- Portal card + route `#member-portal/check` (BM: *Semak Sebelum Memohon*): choose product, amount, tenure; income pre-filled from the payslip on file; existing deductions from the member record.
- New `POST /api/member/affordability` that calls **the same `engines/policy.assess()`** the officer workbench uses (single source of truth; also replaces the duplicated client-side maths in `intake.js:61-89`).
- Output: maximum supportable financing (RM), instalment at the requested amount, DSR gauge vs ceiling, 60%-gross deduction check, eligibility notes (min salary RM2,000, confirmed service), *what would improve it* (W-08 counterfactuals), documents you will need, and a clear disclaimer: *indicative only — not an approval; the Credit Council and a KT officer decide.*
- "Proceed to apply" pre-fills the application. The check is logged to the ledger as `Affordability self-check` without creating an application.
**Acceptance:** For David Carter the member figure equals the officer-workbench figure to the ringgit; no decision language appears.

### F. Governance & management views

#### W-14 Cockpit charts: legends and hover values
**Source:** D10 "Under management Cockpit, the graphs should have legends and data points on hover indicating each lines and the dots"; S10 (three unlabeled lines, Apr 1–15).
**Root cause:** `governance.js:307` calls `lineChart(p.trend, {keys:['a','ap','de']})` with no `labels`; `lib.js:141` hover is an SVG `<title>` reading "a: 21".
**Change:** `lib.js` chart kit gains: `legend` (interactive — hover highlights the series, click toggles), HTML tooltip at the nearest x showing the date and every series value, crosshair, enlarged dot on hover, axis titles, number formatting via `money/num`. Apply to `lineChart`, `barChart`, `donut`, `stepChart`; the Overview's manual legend (`overview.js:36-40`) switches to the shared one. Cockpit passes `labels: ['Applications','Approved','Declined']`. Dates on the axis come from W-05.
**Acceptance:** Every chart in Cockpit, Overview, Member 360 early-warning and Collections has a legend and hover values.

#### W-15 Decision Ledger shows raw JSON — answer and change
**Source:** D11 "Why does the decision ledger under Board/Governance has the JSON data in it?"; S11 (record #25 payload).
**Answer for KT (also §4):** the ledger is an append-only, hash-chained audit record. Each entry stores the *exact* machine input/output at that moment (thresholds, limits, model outputs) so an auditor can re-verify any decision independently. It is shown raw only because no human-readable renderer was built yet — the content is correct, the presentation is not.
**Change:** per-stage renderers (`governance.js:259` drawer, `:283` reconstruction steps, `:92` propose-change drawer, `:214` pending changes): *Autonomy Change* → "Mode ADVISE → ASSIST · max amount RM15,000 · products: Pembiayaan Peribadi-i, … · approved by Board Resolution 2026-04"; *Policy Change* → before/after table; *Agent Deliberation* → each agent's position and confidence; *Application Received* → summary card. A *Show technical record* toggle keeps the JSON for auditors, with the chain verification badge ("#25 ← #24 ✓"). Stage names in EN/BM.
**Acceptance:** A board member can read every ledger record without seeing JSON unless they ask for it.

#### W-16 Policy Sandbox — what it is for, and making that obvious
**Source:** D12 "How exactly does the Policy sandbox and its controls helps the Board/governance?"; S12.
**Answer for KT (also §4):** The Board owns credit policy and the degree of AI autonomy. The sandbox lets it **test a policy change on the whole frozen portfolio before adopting it**: move a threshold, replay every case, see how many approvals/declines flip, what exposure and expected delinquency do, and which members are affected — evidence before a resolution. The *Autonomy Dial* is the Board's control over how much the AI may do (observe → advise → assist → act with approval → autonomous within limits) and the *kill switch* stops it instantly. *Promote* records a proposal in the ledger; nothing in production changes without a governed approval.
**Gaps found in the code:** `min_confidence` slider is accepted but ignored (`main.py:680-684`); `max_pd` is applied as `pd > max_pd × 3.5` (opaque); `promote` (`main.py:720-729`) only writes "Pending Board Approval" — no approval step; no current-vs-candidate comparison in the UI; limits list conventional products.
**Change:**
- Wire `min_confidence` (council confidence below it → *Refer to officer*); apply `max_pd` directly; add the 60%-gross deduction cap and minimum-salary gates as sandbox controls.
- UI: side-by-side *Current policy* vs *Candidate* (approval rate, exposure, PD-weighted delinquency, affected members list with names and branches); one-line plain-language note under each slider ("Lower DSR ceiling → fewer approvals, lower risk"); a *Why this matters to the Board* panel.
- Approval workflow: propose → second board member approves → policy version bumps (v3.4 → v3.5) → ledger entry; both steps visible in the Decision Ledger (W-15).
- Autonomy limits products → KT catalogue.
**Acceptance:** Moving each slider changes the simulation; a proposal cannot reach production without a second approver; the Board can explain the sandbox from the screen alone.

### G. New AI capabilities

#### W-17 "Possible Bankruptcy" section in Member 360 (restricted by hierarchy)
**Source:** D14 "A new section under Member 360 for officers of certain hierarchy to show 'Possible Bankruptcy'. Why? We use AI to predict possible bankruptcy. 4,194 civil servants were declared bankrupt from 2020 to June 2025, about 0.3% of 1.6 million civil servants (Deputy Finance Minister's answer in Parliament, Malay Mail, 13 Aug 2025). 3,602 were declared bankrupt from 2020 to Sept 2024: 1,009 in 2020, 678 in 2021, 621 in 2022, 628 in 2023, and 666 in Jan–Sep 2024 (Minister Azalina's written answer, Malay Mail, 7 Nov 2024)."
**Change:**
- `backend/engines/bankruptcy.py`: explainable scorer (logistic model trained on a synthetic cohort calibrated to the cited **~0.3% base rate**, ~620–1,000 cases/year). Features: total-deductions-to-gross ratio vs the 60% cap; DSR; number of facilities and aggregate outstanding (CCRIS-style, from W-18 connector); arrears trend (days late over 12 months); salary trend; months to retirement (pay cliff); outstanding ÷ annual income; legal/blacklist flag; engagement decline; recent Ar-Rahnu/cash-out behaviour; exposure vs the Insolvency Act petition threshold (RM100,000 since the 2020 amendment — verify).
- Output: band (*Low / Watch / Elevated / High*), probability, top-5 drivers with direction, trend sparkline, **recommended action** (early contact, restructuring/rescheduling, AKPK counselling referral, deduction review) — never an automatic adverse action.
- UI (`members.js` Member 360, new section): band chip, drivers, actions, and an info card with the national context above (both citations) so officers read the score against the base rate.
- Access: hierarchy level ≥ 2 (Senior Officer), Collections, Risk, Manager, Board; hidden from Credit Officer level 1 and always from members; every view is ledger-logged as a sensitive access.
- Governance: model card on *Model Governance* (`governance.js:159-217`): calibration, fairness by service/branch/gender, PDPA note, human-in-the-loop statement.
**Acceptance:** Section visible only to permitted roles; each score has drivers and an action; the model card exists; the base-rate card shows the cited figures.
**Decisions:** exact roles allowed; whether the Board sees individual names or aggregates only.

#### W-18 "Cross-selling options" tab (restricted by hierarchy) + external data
**Source:** D15 "Separate tab for officers of certain hierarchy named 'Cross selling options'. This is an AI powered suggestion list of the members who are potential customers for cross-selling. Do we have any external data source available? Yes, Raees… their platform in their case study indicates that they have integrated Digibanc with Experian's CCRIS for Credit and blacklist checks and SOLA. https://www.codebtech.com/reimagining-cooperative-lending-in-malaysia/ — Member A: existing financing → good repayment history → no insurance product → Potential insurance/takaful offer. Member B: salary + savings → no personal financing → high repayment capacity → Potential financing offer. Member C: declining engagement → Retention intervention."; S13 (Codebase Technologies page: eKYC, Experian CCRIS, TCS blacklist, SOLA).
**Change:**
- `backend/engines/crosssell.py` producing per-member opportunities with the **reason chain shown exactly as the document's examples**:
  - **Takaful offer** — has financing · good conduct (0 late in 12 m) · no Motor/General Takaful → Motor Takaful (vehicle on file) or General Takaful.
  - **Financing offer** — salary + savings · no Personal Financing-i · affordability headroom (from `policy.assess`) ≥ RM X → Personal Financing-i / Express Financing-i, with the pre-computed maximum.
  - **Retention intervention** — declining engagement (logins, savings contributions, share top-ups, transactions trending down) → outreach by branch officer.
  - KT-specific extras: Fees Financing-i for members with school-age dependants in Jan/Jun; Term Financing-i for members within 24 months of retirement; Ar-Rahnu KT for members with gold holdings and short-term cash needs.
- Score = propensity × value; filters by branch, service, product; *next best action* with a BM/EN outreach draft (reuse the collections draft generator, `main.py:463-488`); consent / do-not-contact flag; accept/decline feedback loop; CSV export; each list view ledger-logged.
- Seed fields added: takaful products held, vehicle on file, dependants, savings/share trend, engagement events, gold holdings (W-20).
- **External data answer:** yes — KT's Digibanc platform (Codebase Technologies case study) already integrates **Experian CCRIS** (credit history across institutions) with **TCS blacklist screening**, **SOLA** salary-deduction eligibility, and **eKYC** under the BNM framework. Plan: `backend/connectors/` adapter interface (`ccris.py`, `sola.py`, `ekyc.py`) with **simulated responses now** (facilities count, outstanding, 12-month conduct, legal status/blacklist; SOLA deduction headroom) feeding W-08 affordability, W-17 bankruptcy and W-18 cross-sell. UI shows an *External data: simulated* badge until KT provides Digibanc/Experian credentials; the real adapters are a later phase.
- Access: hierarchy level ≥ 2 plus a new *Marketing* role; hidden from members.
**Acceptance:** The tab lists members under each of the three example patterns with the reason chain visible; connector badge shows simulated; outreach draft is in the member's language.

### H. Look, feel and data (follow-up brief)

#### W-19 Intuitive UI overhaul
**Source:** U1 "make and build an intuitive UI"; U3 "looks better for them"; S1–S12 throughout.
**Change:**
- **Branding:** replace the "CI" badge/wordmark (`app.js:100-103`, `index.html:6,20`, `styles.css:94-101`) with KT identity — logo, colours and typography from KT's brand guide (request); interim palette: military green `#1F4D3A` + gold `#C9A227` on the existing dark/light token system (`styles.css:5-65`). Title "KT Credit Intelligence · Koperasi Tentera".
- **Role landing pages:** each role opens on *What needs me today* (officer: queue by SLA; manager: branch KPIs; board: cockpit summary; member: balance + next deduction).
- **Navigation:** regroup `NAV` (`app.js:8-29`) into *Origination · Members · Collections · Governance · Assistants*; breadcrumbs; persistent global search with BM/EN.
- **Language toggle** BM/EN in the top bar (W-21 i18n layer; member portal first, then staff screens).
- **Plain language:** tooltips/definitions for PD, DSR, LMI, ta'widh; status chips consistent and bilingual; no raw JSON (W-15); empty, loading and error states on every view.
- **Member portal** redesigned in the spirit of KT Online: balance and next-deduction cards, statement download (PDF), *Apply*, *Check Before You Borrow* (W-13), *Takaful & Ar-Rahnu* (W-18), assistant.
- Responsive to tablet width for branch counters; contrast and keyboard-navigation pass; light theme polish (recently added).
- A *Guided demo* (per role, 6–8 steps) for the panel.
**Acceptance:** Panel walkthrough script per role completes without explanation from the presenter.

#### W-20 Sample data aligned with Koperasi Tentera and the platform's features
**Source:** U3 "based on this company make the sample data aligned with and works related [to the] platform"; D2, D3, D4.
**Change:** `backend/seedgen.py` (deterministic, `random.seed(7)`) replaces hand-written `seed.py` tables:
- 80 members across the 6 branches; mix ≈ 55% serving ATM (3 services, ranks from Prebet to Mej), 25% MINDEF civil servants, 20% retirees; realistic pay by rank/grade; savings (*Simpanan*), share capital (*Modal Syer*), annual dividend history.
- Financing mix across the KT catalogue; a few Ar-Rahnu accounts; takaful holdings; 24-month repayment histories via ANGKASA/pension deduction with realistic late patterns; 25 live applications spanning every status; 8 collections cases; 12 early-warning cases; cross-sell and bankruptcy signals seeded so W-17/W-18 have something to show.
- Comms in BM; documents from W-06; trend series for the last 16 days and 12 months.
- All in RM, 2026, MYT; every record passes the integrity tests in W-21.
**Acceptance:** `pytest tests/test_seed_integrity.py` passes (no future dates, all products in catalogue, all amounts within product limits, all bboxes match PDFs, all branches in list).

### I. Engineering foundation

#### W-21 Config, clock, i18n layer, tests
**Source:** required by W-02, W-05, W-10, W-19, W-20.
**Change:** `backend/config.py` (currency, timezone, demo today, model names, demo mode); `backend/clock.py` (W-05); `frontend/i18n.js` with `t('key')` and `frontend/locales/{en,ms}.json`; `pytest` suite (`tests/`): policy/affordability (W-08), seed integrity (W-20), document bbox check (W-07), assistant eval (W-10), auth (W-01); extend `ops/smoke.sh` for RM, 2026 dates, login; `make reset / test / demo` targets.

#### W-22 Deployment & exposure hygiene
**Source:** observed during the status check; relevant to W-01.
**Change:** `cios.service` env (`CIOS_MODEL=qwen3:30b`, `TZ`, `CIOS_TODAY`); `ops/status.sh` checks Tailscale Funnel (not the inactive Cloudflare unit) and the standalone `ollama serve`; close the `:8443 → port 3000` Funnel entry if it was not intended; login (W-01) ends anonymous public access.

---

## 4. Answers to the two questions in the document (ready to send to KT)

**"Why does the Decision Ledger have JSON data in it?"**
The ledger is KT's tamper-evident audit trail. Every decision, policy change, sandbox run and autonomy change is appended with a hash that links to the previous record, so nothing can be altered later without detection. The *payload* is the exact data the system used at that moment — thresholds, limits, the AI agents' positions — kept verbatim so an auditor or regulator can re-run the decision. Showing it as raw JSON was a shortcut; W-15 renders each record in plain English/BM with the technical record one click away.

**"How exactly does the Policy Sandbox and its controls help the Board?"**
The Board sets credit policy and decides how much the AI may do. The sandbox is a *what-if* room: move a control (DSR ceiling, exposure multiple, minimum AI confidence, maximum probability of default — and, after W-16, the 60% deduction cap and minimum salary), replay every case in the portfolio under that policy, and see what would change: approval rate, exposure, expected delinquency, and exactly which members' outcomes flip. The Board can therefore pass a resolution on evidence rather than opinion. The *Autonomy Dial* sets the AI's authority — from observing silently to acting within Board-set limits — and the *kill switch* halts it immediately. *Promote* records a proposal in the ledger; nothing reaches production until a second Board approval is recorded (W-16 adds that step). Two controls were not actually wired (minimum confidence; the PD rule); W-16 fixes them.

---

## 5. Phased delivery

| Phase | Work items | Outcome | Est. effort* |
|---|---|---|---|
| **1 — Foundations & reported bugs** | W-21, W-05, W-08, W-07, W-09, W-11, W-10, W-14, W-15, W-16, W-22 | Every bug and question in the document resolved; clock/timezone/model correct; tests in place | 7–9 days |
| **2 — Koperasi Tentera localisation** | W-02, W-03, W-04, W-06, W-20 | The panel sees their own members, branches, products, currency and documents | 8–10 days |
| **3 — Access & member self-service** | W-01, W-13 | Login with real roles; *Check Before You Borrow* | 5–6 days |
| **4 — New AI capabilities** | W-12, W-17, W-18 | Role-aware intelligent chat; Possible Bankruptcy; Cross-selling with simulated CCRIS/SOLA | 10–12 days |
| **5 — UI polish & demo readiness** | W-19, guided demo, README, rehearsal on `CIOS_TODAY` | Panel-ready | 4–5 days |

\*One engineer, working days, rough. Phases 2 and 4 can run in parallel with 2 engineers (≈ 4 weeks wall-clock). Each phase ends with `pytest` + `ops/smoke.sh` green and a short demo.

Order rationale: Phase 1 first because every later item builds on the clock, the formatter, the model switch and the tests; Phase 2 before Phase 4 because the new AI modules need KT-shaped data to be meaningful.

---

## 6. Decisions needed from KT

| # | Decision | Needed for | Default if no answer |
|---|---|---|---|
| K1 | Confirm product catalogue terms: amounts, tenures, profit rates, Shariah contracts, required documents | W-04 | Public-source placeholders in §9.2 |
| K2 | Full branch list and names | W-03 | The six published branches |
| K3 | Deduction/pay day for ANGKASA and pension deductions | W-05 | 25th |
| K4 | DSR ceiling on net income to keep (40%?) alongside the 60%-of-gross rule | W-08/W-16 | 40% and 60% both enforced |
| K5 | Which hierarchy levels may see *Possible Bankruptcy* and *Cross-selling*; does the Board see names or aggregates | W-17/W-18 | Level ≥ 2; Board aggregates |
| K6 | Staff login identifier; member login by No. Tentera or MyKad | W-01 | Staff ID; No. Tentera |
| K7 | Brand assets (logo, colours, fonts) | W-19 | Interim green/gold |
| K8 | Demo day date and default language for the panel | W-05/W-19 | Real date; BM for member, EN for staff |
| K9 | Access to Digibanc / Experian CCRIS / SOLA sandboxes | W-18 | Simulated connectors |
| K10 | Use real staff names or synthetic | W-03 | Synthetic |
| K11 | PDPA position on predictive bankruptcy scoring and retention of sensitive-access logs | W-17 | Human-in-the-loop, logged, no automatic action |

---

## 7. Risks and notes

- **qwen3:30b latency on the DGX Spark** — MoE with ~3B active parameters should be fast, but the Council makes 6+ calls per case; W-09 benchmarks and keeps a per-feature override.
- **Seed changes need a DB reset** — the ledger demo history is lost on reset; W-20 reseeds a believable history.
- **The repository root holds a 2.2 MB `.docx`** — move it to `docs/requests/` on the next commit so the root stays clean.
- **Public exposure** — until W-01 lands, the Funnel URL is open to anyone; consider Tailscale ACL/Funnel-off between demo sessions.
- **Numbers from public aggregator sites** (profit rate, limits) are placeholders, flagged in the UI as *illustrative* until K1.

---

## 8. Traceability — every item in the document and brief

| Ref | Document wording (abridged) / screenshot | Work item(s) | Phase |
|---|---|---|---|
| D0 | "0. Add a Login Screen" | W-01 | 3 |
| D1 | "Change the money from US dollars ($) to Ringgit (RM)" | W-02 | 2 |
| S1 | Member portal: `$18,250`, `$12,420`, `$8,200`, `$650`, "Personal Loan — $25,000", payments Nov 2023–Apr 2024, "due 5th of next month" | W-02, W-04, W-05, W-11 | 1–2 |
| D2 | "Members, employers and branches are from another country… Armed Forces personnel, MINDEF civil servants and retirees, paid monthly, repayments taken from salary. The panel needs to see their own members on screen." | W-03, W-20 | 2 |
| S2 | Applications list: Makati/Cebu/Davao, Carter/Torres/Brooks…, Personal/Business/Auto/Education/Home/Car Loan, officers Sarah Kim/Marco Diaz/Aisha Rahman | W-03, W-04, W-20 | 2 |
| D3 | "Products are not KT's… wording is conventional banking – change everywhere… Personal Financing, Express Financing, Fees Financing, SME Financing, Term Financing-i, Contract Financing, Motor Takaful, General Takaful, Ar-Rahnu KT… 'financing' instead of 'loan', 'profit rate' instead of 'interest rate'" | W-04 | 2 |
| D4 | "Shift all synthetic dates into 2026, set 'today' to the demo day… all date/time in Malaysia time (UTC+8)" | W-05, W-21 | 1 |
| D5 | "The extracted fields in the document intelligence is not pointing to the right area in the document." | W-07, W-06 | 1–2 |
| S3 | Payslip highlight over wrong rows; "TechCorp Inc.", "March 2024", "$4,333"; 11-step pipeline; "Click an extracted field to highlight" | W-07, W-06, W-02, W-05 | 1–2 |
| D6 | "Robert James… 'Maximum supportable financing' shows $-200… 'Requested amount reduced to about $-200'… #workbench/APP-104310" | W-08 | 1 |
| S4 | Affordability panel and policy gates; duplicate `POL-001`; "Authority required: Credit Officer" | W-08, W-04, W-01 | 1–3 |
| D7 | "Malay answers are weak and sometimes wrong… 'cannot be seen in real time'… Indonesian words ('Anda', 'kabar', 'Asisten Kebijakan', 'karena')… llama3.2:3b… qwen3:30b is installed, can we try with that?" | W-10, W-09 | 1 |
| S5, S6, S7 | Google Translate: question is Malay; reply detected as Indonesian and refuses; chat transcript | W-10 | 1 |
| D8 | "When we initiate in English, the replies are better… not accurate… outstanding balance is 18,250 but the AI says 25,000… confused with the total loan amount" | W-11 | 1 |
| S8, S9 | Free-text "$25,000" vs chip "$18,250" | W-11 | 1 |
| D9 | "'Check Before You Borrow'… calculates his maximum loan approval amount in accordance with the DSR and other affordability calculations (already available under 'workbench' of 'credit officer')" | W-13 | 3 |
| D10 | "Management Cockpit graphs should have legends and data points on hover indicating each line and the dots" | W-14 | 1 |
| S10 | Cockpit: unlabeled 3-line chart Apr 1–15; `$` KPIs; "By product" loan names; "By branch" Makati/Davao/Cebu; "Ask the cockpit" | W-14, W-02, W-04, W-03, W-05, W-12 | 1–4 |
| D11 | "Why does the decision ledger under Board/Governance have the JSON data in it?" | W-15 (+ §4 answer) | 1 |
| S11 | Ledger record #25 raw payload; "Sep 29, 08:54 PM"; "Board Resolution 2024-04"; products list | W-15, W-05, W-04 | 1–2 |
| D12 | "How exactly does the Policy sandbox and its controls help the Board/governance?" | W-16 (+ §4 answer) | 1 |
| S12 | Sandbox sliders, Autonomy Dial, limits (`$15,000`, loan names), top-bar `llama3.2:3b` | W-16, W-02, W-04, W-09 | 1–2 |
| D13 | "Can the larger installed model (qwen3:30b) run the chat helpers instead of llama 3.2:3b?" | W-09 | 1 |
| D14 | "Possible Bankruptcy" section in Member 360 for officers of certain hierarchy; 4,194 (2020–Jun 2025, ~0.3% of 1.6 M, Malay Mail 13 Aug 2025); 3,602 (2020–Sep 2024: 1,009 / 678 / 621 / 628 / 666, Malay Mail 7 Nov 2024) | W-17, W-01 | 4 |
| D15 | "Cross selling options" tab for officers of certain hierarchy; external data — Digibanc + Experian CCRIS + SOLA (codebtech.com); Member A/B/C examples | W-18, W-01 | 4 |
| S13 | Codebase Technologies page: eKYC (BNM), Experian CCRIS, TCS blacklist, SOLA | W-18 | 4 |
| U1 | "make and build an intuitive UI" | W-19 | 5 |
| U2 | "Chat interface… an intelligent [assistant] which can interpret the data as user requires" | W-12, W-10, W-11 | 1, 4 |
| U3 | "Koperasi Tentera… sample data aligned with [it] and works related [to] the platform… looks better for them" | W-20, W-03, W-04, W-06, W-19 | 2, 5 |
| U4 | "a final plan… md file… do not miss a single thing" | this document | — |

---

## 9. Appendices

### 9.1 Terminology glossary (replace everywhere, including prompts)

| Conventional (remove) | KT / Islamic (use) | Bahasa Malaysia |
|---|---|---|
| loan | financing | pembiayaan |
| loan balance | financing balance / outstanding balance | baki pembiayaan |
| interest rate | profit rate (flat, p.a.) | kadar keuntungan |
| interest (schedule column) | profit | keuntungan |
| principal | financing amount | jumlah pembiayaan |
| borrower | member / customer | ahli / pelanggan |
| lender | the Cooperative / KT | Koperasi |
| late fee / penalty interest | ta'widh (late-payment compensation) | ta'widh |
| insurance / premium | takaful / contribution | takaful / sumbangan |
| pawn | Ar-Rahnu | Ar-Rahnu |
| instalment | instalment | ansuran |
| salary deduction | salary deduction (Biro ANGKASA) | potongan gaji |
| Officer Review (status) | Officer Review | Semakan Pegawai |
| Request docs | Documents requested | Dokumen diminta |
| Approve / Decline | Approve / Decline | Lulus / Tolak |

### 9.2 Proposed product catalogue (placeholders until K1)

| Code | Product (EN) | BM | Kind | Contract | Amount (RM) | Tenure | Rate (flat p.a.) |
|---|---|---|---|---|---|---|---|
| PF-i | Personal Financing-i | Pembiayaan Peribadi-i | financing | Tawarruq | 1,000–200,000 | 6–120 m | ~3.65% |
| EF-i | Express Financing-i | Pembiayaan Ekspres-i | financing | Tawarruq | 1,000–20,000 | 6–36 m | ~4.5% |
| FF-i | Fees Financing-i | Pembiayaan Yuran-i | financing | Tawarruq | 1,000–50,000 | 6–60 m | ~3.9% |
| SME-i | SME Financing-i | Pembiayaan PKS-i | financing | Murabahah/Tawarruq | 10,000–300,000 | 12–84 m | ~5.0% |
| TF-i | Term Financing-i | Pembiayaan Berjangka-i | financing | Tawarruq | 5,000–150,000 | 12–120 m | ~4.2% |
| CF-i | Contract Financing-i | Pembiayaan Kontrak-i | financing | Murabahah | 10,000–500,000 | 3–36 m | ~5.5% |
| MT | Motor Takaful | Takaful Motor | takaful | Wakalah | — | annual | contribution |
| GT | General Takaful | Takaful Am | takaful | Wakalah | — | annual | contribution |
| AR | Ar-Rahnu KT | Ar-Rahnu KT | rahnu | Qard + Rahn + Ujrah | up to 70% of gold value | 6 m renewable | safekeeping fee |

### 9.3 Example member personas (synthetic)

| Member | Type | Employer / unit | Branch | Note |
|---|---|---|---|---|
| Sjn Ahmad Faizal bin Rosli | Serving, Tentera Darat | Rejimen Askar Melayu Diraja, Kem Sungai Besi | Kiosk Kem KEMENTAH | PF-i RM25,000, good conduct, no takaful → cross-sell A |
| Kpl Nurul Huda binti Zakaria | Serving, TUDM | Pangkalan Udara Kuantan | Kuantan | Savings high, no financing → cross-sell B |
| Lt M Mohd Hafiz bin Ismail | Serving, TLDM | Pangkalan TLDM Lumut | Lumut | Applicant, Fees Financing-i |
| Mej (B) Ramasamy a/l Muthu | Retiree | JHEV pension | Cawangan Utama KL | Term Financing-i, near petition threshold → bankruptcy *Watch* |
| Puan Siti Khadijah binti Omar | MINDEF civil servant, N29 | Wisma Pertahanan | Cawangan Utama KL | Declining engagement → retention C |
| Encik Tan Wei Jian | MINDEF civil servant, N41 | Kementerian Pertahanan | Kota Kinabalu | SME Financing-i applicant |
| Prebet Jeffrey anak Nyalau | Serving, Tentera Darat | Rejimen Renjer Diraja, Kuching | Kota Kinabalu* | Express Financing-i, high DSR → fails 60% rule |

\*or a Sarawak branch if KT confirms one (K2).

### 9.4 Bahasa Malaysia style guide for the assistant (Malaysian standard, not Indonesian)

| Avoid (Indonesian) | Use (Malaysian) |
|---|---|
| Anda (capitalised) | anda / tuan / puan |
| karena | kerana |
| kabar | khabar |
| informasi | maklumat |
| bisa | boleh |
| uang | wang |
| angsuran | ansuran |
| rekening | akaun |
| kantor | pejabat |
| butuh | perlu |
| Senin | Isnin |
| Asisten Kebijakan | Pembantu Dasar |
| pinjaman / bunga | pembiayaan / kadar keuntungan |

Tone: *Salam sejahtera*, short sentences, "Pembantu Ahli KT" as the assistant's name, dates as "25 Okt 2026", amounts as "RM18,250".

### 9.5 Assistant evaluation set (seed; W-10 extends to 24+)

| # | Question | Expected facts |
|---|---|---|
| 1 | Berapa baki pinjaman saya dan bila bayaran seterusnya? | RM18,250; next deduction date; RM650; potongan gaji |
| 2 | How much is my loan balance and when is the next payment? | same |
| 3 | What's my outstanding balance? | RM18,250 (never RM25,000) |
| 4 | Apa status permohonan saya? | APP-104328, Pembiayaan Peribadi-i RM25,000, Semakan Pegawai |
| 5 | Dokumen apa yang masih diperlukan? | list from case |
| 6 | Saya hilang kerja dan risau tentang bayaran bulan depan | hardship acknowledged; support task; no decision |
| 7 | Bolehkah saya memohon RM50,000? | points to *Semak Sebelum Memohon*; no approval language |
| 8 (officer) | Why did Robert James fail policy? | DSR 74.42% vs 40%; exposure RM14,200 vs RM14,000; variance 20.5% |
| 9 (board) | Approval rate by branch this month? | table from portfolio |

### 9.6 Files touched (inventory)

| File | Work items |
|---|---|
| `backend/main.py` | W-01, W-02, W-05, W-08, W-09, W-10, W-11, W-12, W-13, W-16, W-17, W-18 |
| `backend/seed.py` → `backend/seedgen.py` | W-03, W-04, W-05, W-06, W-20 |
| `backend/engines/policy.py` | W-08, W-13, W-16 |
| `backend/engines/docs.py` | W-07 |
| `backend/engines/lmi.py`, `risk.py` | W-05, W-04 |
| `backend/engines/bankruptcy.py` (new), `crosssell.py` (new) | W-17, W-18 |
| `backend/connectors/` (new) | W-18 |
| `backend/assistant/` (new), `backend/lang.py` (new) | W-10, W-11, W-12 |
| `backend/auth.py` (new) | W-01 |
| `backend/clock.py`, `config.py`, `fmt.py` (new) | W-02, W-05, W-21 |
| `backend/council.py` | W-02, W-04, W-08, W-09 |
| `backend/store.py` | W-04, W-05, W-16 |
| `backend/llm.py` | W-09 |
| `frontend/lib.js` | W-02, W-05, W-14 |
| `frontend/app.js`, `index.html`, `styles.css` | W-01, W-19, W-21 |
| `frontend/i18n.js`, `locales/` (new) | W-10, W-19, W-21 |
| `frontend/views/login.js` (new) | W-01 |
| `frontend/views/portal.js` | W-02, W-10, W-11, W-13, W-19 |
| `frontend/views/applications.js` | W-02, W-04, W-08 |
| `frontend/views/documents.js` | W-07 |
| `frontend/views/governance.js` | W-14, W-15, W-16 |
| `frontend/views/members.js` | W-17, W-19 |
| `frontend/views/crosssell.js` (new) | W-18 |
| `frontend/views/overview.js`, `collections.js`, `intake.js` | W-02, W-04, W-14 |
| `demo_files/generate.py` (new), `manifest.json` | W-06, W-07 |
| `tests/` (new), `ops/smoke.sh`, `ops/status.sh`, `ops/bench_llm.sh` | W-21, W-22, W-09 |
| `run.sh`, `~/.config/systemd/user/cios.service`, `README.md` | W-05, W-09, W-22 |

---

### Sources used for KT facts
- KATMB contact page (branches): https://www.katmb.com.my/contact-us
- Koperasi Tentera overview (est. 1960, ~155k members): https://koperasi.info/kt/koperasi-tentera.html
- KT personal financing terms (public aggregator): https://koperasi.business/pinjaman-peribadi-koperasi-tentera-kt/
- 60% salary-deduction rule / ANGKASA: https://www.bernama.com/en/news.php?id=2352168 and https://en.wikipedia.org/wiki/Cooperative_loans_in_Malaysia
- Digibanc–KT case study (CCRIS, SOLA, eKYC): https://www.codebtech.com/reimagining-cooperative-lending-in-malaysia/
- Bankruptcy statistics: as cited in the KT document (Malay Mail, 13 Aug 2025 and 7 Nov 2024)
