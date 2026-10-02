"""Assistants: the Member Assistant (portal) and KT Assistant (staff analyst with tools).

Member Assistant
  * replies in the member's language (Malaysian Malay or English) — detected per message;
  * answers from a LABELLED fact block in which the outstanding balance and a pending application can
    never be confused (the application is explicitly "not disbursed, not part of the balance");
  * every figure in the model's reply must exist in the fact block, the reply must contain the figures
    the question asked for, Malay replies are checked for Indonesian vocabulary, and decision language is
    forbidden. A reply that fails is regenerated once with the problems listed, then replaced by the
    deterministic answer — so the member never sees a wrong number.

KT Assistant (officers, managers, board)
  * a tool-calling agent over live platform data, scoped by the signed-in role;
  * aggregate answers come with a chart; every answer reports which of its figures were traced back to
    the tool outputs.
"""
from __future__ import annotations
import json, re, datetime as dt

import llm, seed, store, domain, auth
import lang as L
from fmt import rm, date as fdate
from clock import TODAY
from engines import lmi as lmi_engine, distress, crosssell, policy as policy_engine

# =========================================================== member side
HARDSHIP = ["lost my job", "laid off", "redundant", "can't pay", "cannot pay", "struggling", "hardship", "sick",
            "hospital", "worried", "unemployed", "behind on", "hilang kerja", "diberhentikan", "dibuang kerja",
            "tak mampu", "tidak mampu", "susah", "sakit", "masuk hospital", "risau", "bimbang", "tak cukup duit",
            "kesempitan", "terdesak", "tertunggak"]
COMPLAINT = ["complain", "unhappy", "unfair", "angry", "wrong charge", "dispute", "aduan", "tidak puas hati",
             "tak puas hati", "marah", "silap potong", "salah potong", "tidak adil"]
INTENTS = {
    "balance": ["baki", "balance", "outstanding", "owe", "hutang", "berapa lagi"],
    "next": ["bayaran seterusnya", "bayaran akan datang", "potongan seterusnya", "ansuran seterusnya", "next payment",
             "next deduction", "bila bayar", "bila potong", "when is my", "due date", "tarikh potongan", "bila bayaran",
             "seterusnya"],
    "documents": ["dokumen", "document", "papers", "hantar apa", "perlu hantar", "still need"],
    "application": ["permohonan", "application", "status", "approved yet", "lulus"],
    "savings": ["simpanan", "savings", "modal syer", "share capital", "saham", "dividen", "dividend"],
    "borrow": ["boleh pinjam", "boleh mohon", "layak", "kelayakan", "berapa boleh", "can i borrow", "how much can i",
               "eligible", "mohon lagi", "borrow more", "maximum"],
    "greeting": ["hai", "hello", "hi ", "assalamualaikum", "selamat pagi", "selamat petang", "good morning"],
}
FORBIDDEN = ["approved", "will be approved", "you qualify", "guaranteed", "declined", "rejected", "diluluskan",
             "akan diluluskan", "layak mendapat", "pasti lulus", "ditolak", "tidak diluluskan"]


def detect_intents(q: str) -> list[str]:
    low = f" {q.lower()} "
    found = [k for k, kws in INTENTS.items() if any(w in low for w in kws)]
    return found or ["other"]


def member_context(mid: str) -> dict:
    m = domain.MEMBERS[mid]
    apps = [a for a in domain.applications() if a["member_id"] == mid]
    open_apps = [a for a in apps if a["status"] not in ("Approved", "Declined")]
    case = domain.build_case(open_apps[0]["id"]) if open_apps else None
    missing = case["documents_summary"]["missing"] if case else []
    nxt = seed.next_deduction_date()
    return dict(m=m, app=open_apps[0] if open_apps else None, missing=missing, next=nxt,
                last=[(p["month"], p["days_late"]) for p in m["payments"][-3:]])


def facts_block(c: dict) -> str:
    m, a = c["m"], c["app"]
    lines = [
        f"MEMBER = {m['name']} (no. anggota {m['id']}), {m.get('service_label', '')}",
        f"OUTSTANDING_BALANCE / BAKI_PEMBIAYAAN_SEMASA = {rm(m['outstanding'])} — the amount still owed on existing "
        f"KT financing" if m["outstanding"] else "OUTSTANDING_BALANCE / BAKI_PEMBIAYAAN_SEMASA = RM0 — no KT financing",
    ]
    if m["deduction"]:
        lines.append(f"NEXT_DEDUCTION / ANSURAN_SETERUSNYA = {rm(m['deduction'])} on {fdate(c['next'], 'en')} "
                     f"({fdate(c['next'], 'ms')}) by {m['repayment_channel']} salary/pension deduction")
    lines.append(f"SAVINGS / SIMPANAN = {rm(m['savings'])}; SHARE_CAPITAL / MODAL_SYER = {rm(m['share_capital'])}")
    if a:
        lines.append(f"PENDING_APPLICATION / PERMOHONAN_BARU = {a['id']}, {a['product']} "
                     f"({seed.PRODUCTS[a['product']]['ms']}) {rm(a['amount'])} over {a['term']} months — status "
                     f"'{a['status']}' ('{L.STATUS_MS.get(a['status'], a['status'])}'). NOT disbursed and NOT part "
                     f"of the outstanding balance. A status is a stage, not a person.")
        lines.append("DOCUMENTS_STILL_NEEDED / DOKUMEN_DIPERLUKAN = " +
                     (", ".join(f"{d} ({seed.DOC_MS.get(d, d)})" for d in c["missing"]) or "none — all received"))
    else:
        lines.append("PENDING_APPLICATION / PERMOHONAN_BARU = none")
    lines.append("SELF_CHECK = for 'how much can I borrow' the member uses 'Check Before You Borrow' "
                 "('Semak Sebelum Memohon') in this portal; the assistant never estimates a limit")
    if c["last"]:
        lines.append("LAST_DEDUCTIONS = " + "; ".join(f"{fdate(d)}: {'on time' if late <= 2 else f'{late} days late'}"
                                                      for d, late in c["last"]))
    return "\n".join(lines)


def template(c: dict, intents: list[str], lng: str, hardship=False, complaint=False) -> str:
    m, a = c["m"], c["app"]
    ms = lng == "ms"
    out = []
    if hardship or complaint:
        out.append("Terima kasih kerana memaklumkan kepada kami. Saya telah membuka tugasan sokongan dan pegawai "
                   "Sokongan Ahli akan menghubungi anda dalam masa satu hari bekerja untuk membincangkan pilihan yang "
                   "ada, termasuk penjadualan semula. Akaun anda tidak terjejas oleh mesej ini." if ms else
                   "Thank you for telling us — you have done the right thing by getting in touch early. I have opened a "
                   "support task and a Member Support officer will contact you within one business day to go through "
                   "the options, including rescheduling. Your account is not affected by this message.")
        return " ".join(out)
    for it in intents:
        if it == "balance":
            out.append((f"Baki pembiayaan semasa anda ialah {rm(m['outstanding'])}." if ms else
                        f"Your outstanding financing balance is {rm(m['outstanding'])}.") if m["outstanding"] else
                       ("Anda tiada baki pembiayaan dengan KT." if ms else "You have no outstanding KT financing."))
        elif it == "next" and m["deduction"]:
            out.append(f"Ansuran seterusnya sebanyak {rm(m['deduction'])} akan dipotong melalui {m['repayment_channel']} "
                       f"pada {fdate(c['next'], 'ms')}." if ms else
                       f"Your next instalment of {rm(m['deduction'])} will be deducted via {m['repayment_channel']} on "
                       f"{fdate(c['next'])}.")
        elif it == "application":
            if a:
                st = L.STATUS_MS.get(a["status"], a["status"]) if ms else a["status"]
                out.append(f"Permohonan {a['id']} ({seed.PRODUCTS[a['product']]['ms']}, {rm(a['amount'])}) sedang di "
                           f"peringkat '{st}'. Jumlah ini belum dikeluarkan dan bukan sebahagian daripada baki anda." if ms
                           else f"Your application {a['id']} ({a['product']}, {rm(a['amount'])}) is at the '{st}' "
                                f"stage. This amount has not been disbursed and is not part of your balance.")
            else:
                out.append("Anda tiada permohonan yang sedang diproses." if ms else "You have no application in progress.")
        elif it == "documents":
            if c["missing"]:
                docs = ", ".join(seed.DOC_MS.get(d, d) if ms else d for d in c["missing"])
                out.append(f"Kami masih memerlukan: {docs}." if ms else f"We still need: {docs}.")
            elif a:
                out.append("Semua dokumen yang diminta telah diterima." if ms else "All requested documents have been received.")
        elif it == "savings":
            out.append(f"Simpanan anda {rm(m['savings'])} dan modal syer {rm(m['share_capital'])}." if ms else
                       f"Your savings are {rm(m['savings'])} and your share capital is {rm(m['share_capital'])}.")
        elif it == "borrow":
            out.append("Saya tidak boleh membuat keputusan pembiayaan, tetapi anda boleh melihat anggaran kelayakan anda "
                       "sendiri di 'Semak Sebelum Memohon' dalam portal ini. Keputusan muktamad dibuat oleh pegawai KT."
                       if ms else "I can't make a financing decision, but you can see your own indicative limit under "
                       "'Check Before You Borrow' in this portal. The final decision is made by a KT officer.")
        elif it == "greeting":
            out.append(f"Salam sejahtera, {m['given_name']}. Bagaimana saya boleh membantu?" if ms else
                       f"Hello {m['given_name']}, how can I help?")
    if not out:
        out.append("Saya boleh membantu tentang baki pembiayaan, ansuran seterusnya, status permohonan, dokumen yang "
                   "diperlukan, simpanan, atau mengatur panggilan daripada Sokongan Ahli." if ms else
                   "I can help with your financing balance, next instalment, application status, documents still "
                   "needed, savings, or arrange a call from Member Support.")
    return " ".join(out)


_NUM = re.compile(r"(?<![\w.\-])(\d[\d,]*(?:\.\d+)?)")
_RM = re.compile(r"\bRM\s?(?=\d)")


def numbers(text: str) -> list[str]:
    """Every figure in a text, reading 'RM188,000' as 188,000 (the currency prefix must not hide digits)."""
    return _NUM.findall(_RM.sub("RM ", text or ""))


def _nums(text: str) -> set[str]:
    out = set()
    for x in numbers(text):
        v = x.replace(",", "").rstrip(".")
        if not v:
            continue
        out.add(v)
        if "." in v:
            out.add(v.rstrip("0").rstrip("."))
    return out


def validate(ans: str, c: dict, facts: str, intents: list[str], lng: str) -> list[str]:
    problems = []
    allowed = _nums(facts) | {str(TODAY.year), str(TODAY.year + 1), "1", "2", "3"}
    for n in _nums(ans):
        if n not in allowed:
            problems.append(f"the figure {n} is not in FACTS")
    m, a = c["m"], c["app"]
    plain = (ans or "").replace(",", "")
    if "balance" in intents and m["outstanding"] and str(int(m["outstanding"])) not in plain:
        problems.append(f"the outstanding balance is {rm(m['outstanding'])} and must be stated")
    if "balance" in intents and a and str(int(a["amount"])) in plain and str(int(m["outstanding"])) not in plain:
        problems.append("the application amount was given as the balance")
    if "next" in intents and m["deduction"] and str(int(m["deduction"])) not in plain:
        problems.append(f"the next instalment {rm(m['deduction'])} and its date must be stated")
    low = (ans or "").lower()
    if any(w in low for w in FORBIDDEN) and "tidak boleh membuat keputusan" not in low and "can't make" not in low:
        problems.append("it states or implies a credit decision")
    if lng == "ms":
        hits = L.indonesian_hits(ans)
        if hits:
            problems.append("it uses Indonesian words: " + ", ".join(hits))
        if L.detect(ans, "ms") != "ms":
            problems.append("it is not written in Bahasa Malaysia")
    elif L.detect(ans, "en") != "en":
        problems.append("it is not written in English")
    if "cannot be seen" in low or "tidak dapat dilihat" in low or "tidak boleh dilihat" in low:
        problems.append("it claims the information is unavailable, but it is in FACTS")
    if any(w in low for w in ("akan menghubungi", "will contact", "will be in touch", "akan dihubungi", "will call")):
        problems.append("it promises a call or contact that nobody has arranged")
    if "borrow" in intents and "semak sebelum memohon" not in low and "check before you borrow" not in low:
        problems.append("for a borrowing question it must point to 'Semak Sebelum Memohon' / 'Check Before You Borrow'")
    return problems


def _member_system(lng: str, m: dict) -> str:
    if lng == "ms":
        return ("Anda ialah Pembantu Ahli Koperasi Tentera (KT), bercakap dengan ahli yang telah log masuk, "
                f"{m['given_name']}. Jawab HANYA berdasarkan FAKTA. Baki pembiayaan semasa dan permohonan baru ialah "
                "dua perkara berbeza — jangan sekali-kali campurkan. Jangan nyatakan atau ramalkan sebarang keputusan "
                "pembiayaan, had atau kadar; untuk soalan 'berapa boleh saya pinjam', arahkan ahli ke 'Semak Sebelum "
                "Memohon' dalam portal ini. Jangan janjikan panggilan atau hubungan daripada pegawai. Jawab soalan "
                "yang ditanya sahaja, dalam satu hingga tiga ayat ringkas. " + L.STYLE_MS)
    return ("You are the Koperasi Tentera (KT) Member Assistant, talking to the signed-in member, "
            f"{m['given_name']}. Answer ONLY from FACTS. The outstanding balance and a pending application are "
            "different things — never mix them. Never state, imply or predict a financing decision, limit or rate; "
            "for 'how much can I borrow' point the member to 'Check Before You Borrow' in this portal. Never promise "
            "a call or contact from an officer. Use 'financing' (not 'loan') and 'profit rate' (not 'interest'). "
            "Amounts as RM18,250. Answer only what was asked, in one to three short sentences.")


async def member_answer(mid: str, question: str, lang_hint: str = "ms", history: list | None = None) -> dict:
    c = member_context(mid)
    m = c["m"]
    lng = L.detect(question, default=lang_hint if lang_hint in ("ms", "en") else "ms")
    low = question.lower()
    hardship = any(w in low for w in HARDSHIP)
    complaint = any(w in low for w in COMPLAINT)
    intents = detect_intents(question)
    facts = facts_block(c)
    fallback = template(c, intents, lng, hardship, complaint)
    out = {"lang": lng, "intents": intents, "source": "template", "answer": fallback, "attempts": 0, "problems": []}
    if llm.status().get("available") and not (hardship or complaint):
        msgs = [{"role": "system", "content": _member_system(lng, m)}]
        for h in (history or [])[-6:]:
            if h.get("role") in ("user", "assistant") and h.get("content"):
                msgs.append({"role": h["role"], "content": str(h["content"])[:600]})
        hint = ("Soalan ini tentang: " if lng == "ms" else "This question is about: ") + ", ".join(intents)
        msgs.append({"role": "user", "content": f"FAKTA / FACTS\n{facts}\n\n{hint}\n\n"
                                                f"{'SOALAN AHLI' if lng == 'ms' else 'MEMBER ASKS'}: {question}"})
        for attempt in range(2):
            try:
                txt = ""
                async for kind, val in llm.chat(msgs, temperature=0.2, num_predict=260):
                    if kind == "token":
                        txt += val
                txt = re.sub(r"\[[^\]]{0,40}\]", "", llm.clean(txt)).strip()
            except Exception as e:                                       # noqa: BLE001
                out["problems"] = [f"model unavailable: {str(e)[:80]}"]
                break
            out["attempts"] = attempt + 1
            if L.indonesian_hits(txt) or "impangan" in txt:
                fixed = L.normalise_ms(txt)
                if not validate(fixed, c, facts, intents, lng):
                    txt = fixed
            probs = validate(txt, c, facts, intents, lng)
            if not probs:
                out.update(answer=txt, source="llm", problems=[])
                break
            out["problems"] = probs
            msgs += [{"role": "assistant", "content": txt},
                     {"role": "user", "content": ("Jawapan itu ada masalah: " if lng == "ms" else "That reply has problems: ")
                      + "; ".join(probs) + (". Tulis semula menggunakan FAKTA sahaja." if lng == "ms"
                                            else ". Rewrite it using FACTS only.")}]
    elif hardship or complaint:
        out["source"] = "support"
    out["handoff"] = None
    if hardship or complaint:
        kind = "Hardship" if hardship else "Complaint"
        task = dict(kind=kind, member_id=mid, member=m["name"], at=_now(), queue="Member Support",
                    sla="1 business day", detail=question[:180], status="Open", lang=lng)
        store.append_list("support_tasks", task)
        store.ledger_append(f"MEM-{mid}", f"{kind} Signal Detected", "Member Assistant",
                            f"{kind} cue detected in a member message ({'BM' if lng == 'ms' else 'EN'}); routed to Member Support", task)
        store.append_list("notifications", dict(kind="hardship", tone="amber", title=f"{kind} signal — {m['name']}",
                                                detail=question[:90], at=task["at"], link=f"members:{mid}"))
        out["handoff"] = task
    out["guardrail"] = ("Pembantu ini tidak sekali-kali membuat keputusan pembiayaan." if lng == "ms"
                        else "The assistant never states or implies a financing decision.")
    out["grounding"] = {"figures": sorted(_nums(out["answer"])), "checked": True}
    return out


def _now():
    import clock
    return clock.now_iso()


# =========================================================== staff side
def case_context(case: dict) -> str:
    p, r, f, d = case["policy"], case["risk"], case["fraud"], case["documents_summary"]
    a, m = case["application"], case["member"]
    lines = [
        f"Case {a['id']} — {m['name']} ({m.get('service_label', '')}, {m['branch']}), {a['product']} "
        f"({p['contract']}) {rm(a['amount'])} over {a['term']} months for {a['purpose']}. Status {a['status']}.",
        f"Snapshot {case['snapshot']['hash']} frozen {case['snapshot']['frozen_at']} under policy {p['policy_version']}.",
        f"Income: declared {rm(p['income']['declared_annual'])}, payslip {rm(p['income']['payslip_annual'])}, bank "
        f"{rm(p['income']['bank_annual'])}; verified {rm(p['income']['verified_annual'])} (variance {p['income']['variance_pct']}%).",
        f"Instalment {rm(p['instalment'], 2)} at {p['rate']}% flat; existing commitments {rm(p['existing_commitments'])}; "
        f"DSR {p['dsr']}% vs {p['dsr_ceiling']}% ceiling" + (f"; total salary deductions {p['deduction_ratio']}% of gross "
        f"vs {p['deduction_cap']}% cap" if p['deduction_ratio'] is not None else "") + ".",
        f"Policy {p['result']}; failing: {', '.join(p['failures']) or 'none'}; advisories: {', '.join(p['advisories']) or 'none'}. "
        f"Authority required: {p['authority_required']}.",
        f"Maximum supportable financing {rm(p['max_financing'])} — {p.get('max_financing_note', '')}",
        f"Exposure {rm(p['exposure'])} against cap {rm(p['exposure_cap'])}.",
        f"Risk: PD {r['pd']*100:.1f}% ({r['grade']}), score {r['score']}. Reason codes: {'; '.join(r['reason_codes']) or 'none'}.",
        f"Integrity: {f['level']} — {f['headline']}.",
        f"Documents: {d['verified']}/{d['required']} verified; missing {', '.join(d['missing']) or 'none'}.",
        f"Member: since {m['since']}, {m['prior_financings']} prior financings, {m['reliability']}% reliability, savings "
        f"{rm(m['savings'])}, share capital {rm(m['share_capital'])}, KT outstanding {rm(m['outstanding'])}.",
        f"Early-warning state {case['lmi']['state']['state']}: {case['lmi']['why_now']}",
    ]
    for x in case["reconciliation"]["rows"]:
        lines.append(f"Reconciliation — {x['attribute']}: {x['result']} ({x['detail']}).")
    if case.get("council"):
        s = case["council"]["summary"]
        lines.append(f"Council: {s['recommendation']} at {s['confidence']} confidence, disagreement {s['disagreement']}.")
    if case.get("decision"):
        lines.append(f"Decision: {case['decision']['action']} by {case['decision']['actor']} — {case['decision']['reason']}")
    return "\n".join(lines)


def _rows():
    return domain.queue_rows()


def _t_list_applications(user, status="", branch="", product="", missing_docs=None, risk="", limit=25):
    err = _filter_error(None, product, branch, status)
    if err:
        return err
    rows = [r for r in _rows()
            if (not status or status.lower() in r["status"].lower())
            and (not branch or branch.lower() in r["branch"].lower())
            and (not product or product.lower() in r["product"].lower())
            and (not risk or risk.lower() == r["risk"].lower())
            and (missing_docs is None or bool(r["missing"]) == bool(missing_docs))]
    return {"count": len(rows), "total_amount_rm": round(sum(r["amount"] for r in rows)),
            "rows": [dict(id=r["id"], name=r["name"], product=r["product"], amount=r["amount"],
                                              branch=r["branch"], status=r["status"], policy=r["policy"], dsr=r["dsr"],
                                              risk=r["risk"], missing=r["missing"], next=r["next"]) for r in rows[:limit]]}


GROUPS = {"branch": "branch", "product": "product", "officer": "officer", "status": "status", "risk": "risk",
          "service": "service"}


STATUSES = ["Officer Review", "Documents Pending", "In Verification", "Ready to Approve", "Credit Analysis",
            "Risk Review", "Enhanced Review", "Fraud Review", "Approved", "Declined", "Escalated"]


def _filter_error(rows_all, product, branch, status) -> dict | None:
    """A filter value that matches nothing is almost always a misreading ("requested" is not a status) — say so,
    with the valid values, so the model corrects itself instead of reporting that nothing exists."""
    for name, val, valid in (("product", product, seed.FINANCING), ("branch", branch, seed.BRANCHES),
                             ("status", status, STATUSES)):
        if val and not any(val.lower() in v.lower() for v in valid):
            return {"error": f"{name} '{val}' is not a valid {name}; valid values: {', '.join(valid)}. "
                             f"Leave {name} out to include everything."}
    return None


def _t_portfolio_breakdown(user, group_by="branch", metric="amount", product="", branch="", status=""):
    key = GROUPS.get(group_by, "branch")
    out = {}
    all_rows = _rows()
    err = _filter_error(all_rows, product, branch, status)
    if err:
        return err
    rows = [r for r in all_rows if (not product or product.lower() in r["product"].lower())
            and (not branch or branch.lower() in r["branch"].lower())
            and (not status or status.lower() in r["status"].lower())]
    for r in rows:
        d = out.setdefault(r[key] or "—", {"count": 0, "amount": 0.0, "pd_w": 0.0, "dsr": 0.0})
        d["count"] += 1; d["amount"] += r["amount"]; d["pd_w"] += r["pd"] * r["amount"]; d["dsr"] += r["dsr"]
    table = {k: {"cases": v["count"], "amount_rm": round(v["amount"]), "pd_pct": round(v["pd_w"] / max(1, v["amount"]) * 100, 2),
                 "avg_dsr_pct": round(v["dsr"] / v["count"], 1)} for k, v in out.items()}
    mkey = {"count": "cases", "amount": "amount_rm", "pd": "pd_pct", "dsr": "avg_dsr_pct"}.get(metric, "amount_rm")
    items = sorted(table.items(), key=lambda kv: -kv[1][mkey])
    flt = ", ".join(f"{k} = {v}" for k, v in (("product", product), ("branch", branch), ("status", status)) if v)
    chart = {"type": "bar", "title": f"{mkey.replace('_', ' ')} by {key}" + (f" ({flt})" if flt else ""),
             "labels": [k for k, _ in items], "values": [v[mkey] for _, v in items],
             "unit": "RM" if mkey == "amount_rm" else "%" if "pct" in mkey else ""}
    return {"group_by": key, "filter": flt or "none — all live applications", "table": dict(items),
            "total": {"cases": len(rows), "amount_rm": round(sum(r["amount"] for r in rows))}}, chart


def _t_get_case(user, application_id=""):
    c = domain.build_case(application_id.strip().upper())
    if not c:
        return {"error": f"no case {application_id}"}
    return {"context": case_context(c)}


def _find_member(q: str):
    q = (q or "").strip().lower()
    if q in domain.MEMBERS:
        return domain.MEMBERS[q]
    hits = [m for m in domain.MEMBERS.values() if q and (q in m["name"].lower() or q in m["full_name"].lower())]
    return hits[0] if hits else None


def _t_get_member(user, member=""):
    m = _find_member(member)
    if not m:
        return {"error": f"no member matching '{member}'"}
    a = lmi_engine.analyse(m)
    out = dict(id=m["id"], name=m["name"], service=m["service_label"], unit=m["unit"], branch=m["branch"],
               since=m["since"], savings=m["savings"], share_capital=m["share_capital"], outstanding=m["outstanding"],
               monthly_deduction=m["deduction"], external_deductions=m["external_deductions"],
               gross_monthly=m["gross_monthly"], reliability=m["reliability"],
               early_warning_state=a["state"]["state"], why_now=a["why_now"],
               retirement=m.get("retirement_date"))
    if user["role"] in auth.DISTRESS_ROLES:
        s = distress.MODEL.score(m)
        out["financial_distress"] = dict(band=s["band"], probability_12m=s["probability_12m"],
                                         drivers=[d["label"] for d in s["drivers"]], actions=s["actions"][:3])
    if user["role"] in auth.CROSSSELL_ROLES:
        out["cross_sell"] = [dict(product=o["product"], why=o["chain"]) for o in crosssell.offers(m)[:2]]
    return out


def _t_search_members(user, query="", branch="", service="", state=""):
    rows = []
    for m in domain.MEMBERS.values():
        if query and query.lower() not in m["name"].lower():
            continue
        if branch and branch.lower() not in m["branch"].lower():
            continue
        if service and service.lower() not in (m["service"] + m["service_label"]).lower():
            continue
        st = lmi_engine.analyse(m)["state"]["state"]
        if state and state.upper() != st:
            continue
        rows.append(dict(id=m["id"], name=m["name"], branch=m["branch"], service=m["service_label"],
                         outstanding=m["outstanding"], state=st))
    return {"count": len(rows), "rows": rows[:20]}


def _t_early_warning(user, limit=10):
    rows = []
    for m in domain.MEMBERS.values():
        a = lmi_engine.analyse(m)
        if a["state"]["state"] != "STABLE":
            rows.append(dict(id=m["id"], name=m["name"], branch=m["branch"], state=a["state"]["state"],
                             p_late_30d=a["forecast"]["p_late_30d"], why_now=a["why_now"][:160]))
    rows.sort(key=lambda r: -r["p_late_30d"])
    return {"count": len(rows), "rows": rows[:limit]}


def _t_collections_summary(user):
    rows = []
    for c in seed.COLLECTIONS:
        m = domain.MEMBERS[c["member_id"]]
        rows.append(dict(id=c["id"], member=m["name"], branch=m["branch"], balance=c["balance"], dpd=c["dpd"],
                         stage=c["stage"], priority=c["priority"]))
    return {"cases": len(rows), "total_balance": sum(r["balance"] for r in rows), "rows": rows}


def _t_policy_lookup(user, query=""):
    q = query.lower()
    scored = sorted(seed.POLICY_LIBRARY, key=lambda p: -sum(w in (p["title"] + " " + p["text"]).lower()
                                                            for w in re.findall(r"[a-z0-9%]{3,}", q)))
    return {"policies": [dict(id=p["id"], title=p["title"], text=p["text"]) for p in scored[:3]]}


def _t_ledger_search(user, case_id="", text="", limit=10):
    rows = store.ledger_read(case_id.strip().upper() or None, 200)
    if text:
        rows = [r for r in rows if text.lower() in (r["summary"] + r["stage"]).lower()]
    return {"rows": [dict(seq=r["seq"], at=r["at"], case=r["case_id"], stage=r["stage"], actor=r["actor"],
                          summary=r["summary"][:200]) for r in rows[:limit]]}


def _t_application_trend(user):
    t = seed.TREND
    chart = {"type": "line", "title": "Applications, approvals and declines — last 16 days",
             "labels": [x["d"] for x in t], "series": {"Applications": [x["a"] for x in t],
                                                     "Approved": [x["ap"] for x in t], "Declined": [x["de"] for x in t]}}
    return {"days": [dict(date=x["date"], applications=x["a"], approved=x["ap"], declined=x["de"]) for x in t],
            "totals": dict(applications=sum(x["a"] for x in t), approved=sum(x["ap"] for x in t),
                           declined=sum(x["de"] for x in t))}, chart


def _t_distress_overview(user):
    p = distress.portfolio(list(domain.MEMBERS.values()))
    chart = {"type": "bar", "title": "Members by financial-distress band", "labels": list(p["bands"]),
             "values": list(p["bands"].values()), "unit": ""}
    return {"bands": p["bands"], "by_branch": p["by_branch"], "expected_cases_12m": p["expected_cases_12m"],
            "national_context": p["context"]["headline"]}, chart


def _t_crosssell_overview(user, kind=""):
    p = crosssell.portfolio(list(domain.MEMBERS.values()), store.get("crosssell_feedback", {}))
    rows = [r for r in p["rows"] if not kind or kind.lower() in (r["kind"] + r["identifies"]).lower()]
    return {"summary": p["summary"], "top": [dict(member=r["name"], branch=r["branch"], offer=r["product"],
                                                  why=r["chain"], contactable=r["contactable"]) for r in rows[:10]]}


def _t_affordability_check(user, member="", product="Personal Financing-i", amount=None, term=60):
    """Maximum supportable financing for a member, product and tenure — and, if an amount is given, whether
    that amount fits. Without an amount it reports the maximum and the position at that maximum."""
    m = _find_member(member)
    if not m:
        return {"error": f"no member matching '{member}'"}
    if product not in seed.FINANCING:
        product = "Personal Financing-i"
    prod = seed.PRODUCTS[product]
    term = max(prod["min_term"], min(prod["max_term"], int(term or 60)))
    base = dict(product=product, term=term, existing_commitments=m["financing_deductions"])
    probe = policy_engine.assess(dict(base, amount=float(prod["min"])), m, {})
    mx = probe["max_financing"]
    out = dict(member=m["name"], member_id=m["id"], product=product, term_months=term, profit_rate_flat=prod["rate"],
               max_financing=mx, binding_limit=probe["max_financing_binding_label"],
               explanation=policy_engine.max_financing_explanation(probe, None),
               existing_monthly_financing=m["financing_deductions"], gross_monthly=m["gross_monthly"])
    if mx > 0:
        at = policy_engine.assess(dict(base, amount=float(mx)), m, {})
        out.update(instalment_at_max=at["instalment"], dsr_at_max=at["dsr"], dsr_ceiling=at["dsr_ceiling"],
                   deduction_ratio_at_max=at["deduction_ratio"])
    if amount:
        req = policy_engine.assess(dict(base, amount=float(amount)), m, {})
        out.update(requested_amount=float(amount), requested_instalment=req["instalment"], requested_result=req["result"],
                   requested_failures=req["failures"], requested_dsr=req["dsr"])
    return out


def _fn(name, desc, props=None, req=None):
    return {"type": "function", "function": {"name": name, "description": desc,
                                             "parameters": {"type": "object", "properties": props or {},
                                                            "required": req or []}}}


TOOLS = {
    "list_applications": (_t_list_applications, ("applications",), _fn(
        "list_applications", "List live financing applications, optionally filtered.",
        {"status": {"type": "string", "enum": STATUSES}, "branch": {"type": "string", "enum": seed.BRANCHES},
         "product": {"type": "string", "enum": seed.FINANCING},
         "missing_docs": {"type": "boolean", "description": "true = only cases still waiting on documents"},
         "risk": {"type": "string", "enum": ["Low", "Moderate", "Elevated", "High"]}})),
    "portfolio_breakdown": (_t_portfolio_breakdown, ("overview", "cockpit", "applications"), _fn(
        "portfolio_breakdown", "Aggregate ALL live applications (every one is a financing request) by a dimension, "
        "optionally for one product or branch; returns a table and a chart. For questions about statuses use "
        "group_by='status'.",
        {"group_by": {"type": "string", "enum": list(GROUPS)},
         "metric": {"type": "string", "enum": ["count", "amount", "pd", "dsr"]},
         "product": {"type": "string", "enum": seed.FINANCING, "description": "only if the user names a product"},
         "branch": {"type": "string", "enum": seed.BRANCHES, "description": "only if the user names a branch"}},
        ["group_by"])),
    "get_case": (_t_get_case, ("applications", "workbench"), _fn(
        "get_case", "Full deterministic facts for one application (policy, affordability, risk, documents).",
        {"application_id": {"type": "string", "description": "e.g. APP-104310"}}, ["application_id"])),
    "get_member": (_t_get_member, ("members",), _fn(
        "get_member", "Profile of one member by member number or name.",
        {"member": {"type": "string"}}, ["member"])),
    "search_members": (_t_search_members, ("members",), _fn(
        "search_members", "Find members by name, branch, service (TD/TLDM/TUDM/MINDEF/Pesara) or early-warning state.",
        {"query": {"type": "string"}, "branch": {"type": "string"}, "service": {"type": "string"},
         "state": {"type": "string", "enum": ["STABLE", "WATCH", "ELEVATED", "AT_RISK", "RECOVERY"]}})),
    "early_warning": (_t_early_warning, ("early-warning", "overview", "members"), _fn(
        "early_warning", "Members drifting from their own repayment baseline, most at risk first.",
        {"limit": {"type": "integer"}})),
    "collections_summary": (_t_collections_summary, ("collections", "cockpit"), _fn(
        "collections_summary", "Collections cases with balances, days past due and stage.")),
    "policy_lookup": (_t_policy_lookup, ("overview", "cockpit", "applications", "governance", "sandbox", "members",
                                         "crosssell", "ledger", "collections", "early-warning"), _fn(
        "policy_lookup", "Search KT's credit policy library (v4.0).", {"query": {"type": "string"}}, ["query"])),
    "ledger_search": (_t_ledger_search, ("ledger", "governance"), _fn(
        "ledger_search", "Search the hash-chained decision ledger.",
        {"case_id": {"type": "string"}, "text": {"type": "string"}, "limit": {"type": "integer"}})),
    "application_trend": (_t_application_trend, ("overview", "cockpit"), _fn(
        "application_trend", "Daily applications, approvals and declines for the last 16 days, with a chart.")),
    "distress_overview": (_t_distress_overview, ("cockpit", "early-warning"), _fn(
        "distress_overview", "Aggregate financial-distress (possible bankruptcy) bands across the membership, by branch.")),
    "crosssell_overview": (_t_crosssell_overview, ("crosssell",), _fn(
        "crosssell_overview", "AI cross-selling suggestions: takaful, financing and retention opportunities.",
        {"kind": {"type": "string", "enum": ["takaful", "financing", "retention", "rahnu", "advice"]}})),
    "affordability_check": (_t_affordability_check, ("applications", "members"), _fn(
        "affordability_check", "How much a member could borrow: KT's affordability engine gives the maximum supportable "
        "financing for a product and tenure, the binding limit, and — if an amount is given — whether it fits. Takes a "
        "member name or number directly; no need to look the member up first.",
        {"member": {"type": "string"}, "product": {"type": "string", "enum": seed.FINANCING},
         "amount": {"type": "number", "description": "only if the user named an amount"},
         "term": {"type": "integer", "description": "months"}}, ["member"])),
}


def tools_for(user: dict) -> dict:
    allowed = {}
    for name, (fn, views, spec) in TOOLS.items():
        if not auth.can(user, *views):
            continue
        if name == "distress_overview" and user["role"] not in auth.DISTRESS_ROLES | {"board"}:
            continue
        allowed[name] = (fn, spec)
    return allowed


def mentioned_members(question: str, limit: int = 3) -> list[dict]:
    """Members named in a question, with or without rank — "Sjn Udara Nurul Huda", "Nurul Huda", "104402"."""
    q = f" {question.lower()} "
    hits = []
    for m in domain.MEMBERS.values():
        full = m["full_name"].lower().replace("dato' ", "").replace("hj. ", "")
        given = m["given_name"].lower()
        if f" {m['id']} " in q or full in q or (len(given.split()) >= 2 and given in q) or \
                (len(given) >= 5 and f" {given} " in q and m["full_name"].split()[-1].lower() in q):
            hits.append(m)
    hits.sort(key=lambda m: -len(m["given_name"]))
    return hits[:limit]


def _staff_system(user: dict, lng: str, case: dict | None) -> str:
    base = (f"You are KT Assistant, the analyst inside KT Credit Intelligence for Koperasi Tentera (Koperasi Angkatan "
            f"Tentera Malaysia Berhad), a credit co-operative for Armed Forces personnel, MINDEF civil servants and "
            f"veterans. You are helping {user['name']}, {user['role_label']}. Today is {fdate(TODAY)}. "
            "For ANY question about counts, amounts, members, cases, branches, products, trends or policy you MUST call a "
            "tool first — answering such a question without a tool call is an error, and every figure you write must "
            "appear in a tool result. KT's branches are Kuala Lumpur, Sungai Besi, Lumut, Kuantan, Kota Kinabalu and Kok "
            "Lanas. When the user names a member, call the tools with that name or number straight away — never ask "
            "for the member number first. Islamic financing vocabulary: 'financing' not 'loan', 'profit rate' not 'interest', 'takaful' "
            "not 'insurance'. Amounts as RM12,345. Lead with the direct answer in one or two sentences; when listing "
            "more than three items use a compact markdown table; finish with one line starting 'Source:' naming the "
            "data you used. Never add up or calculate figures yourself — quote the totals the tools return. You support decisions — officers decide; never state a final credit decision. ")
    if user["role"] == "board":
        base += "This user is on the Board: report aggregates, not individual members. "
    base += ("Reply in Bahasa Malaysia. " + L.STYLE_MS) if lng == "ms" else "Reply in English."
    if case:
        base += "\n\nThe user is looking at this case right now:\n" + case_context(case)
    return base


def grounding(answer: str, sources: list[str]) -> dict:
    src = set()
    for s in sources:
        for n in numbers(s):
            try:
                src.add(float(n.replace(",", "")))
            except ValueError:
                pass
    checked, missing = 0, []
    body = re.sub(r"(?m)^\s*\d+[.)]\s", "", answer or "")          # list numbering is not a figure
    body = re.sub(r"\(\d{1,2}\)", "", body)                          # nor is an inline "(3)"
    for raw in numbers(body):
        try:
            v = float(raw.replace(",", ""))
        except ValueError:
            continue
        if 2000 <= v <= 2100 and float(v).is_integer():
            continue                                  # years
        checked += 1
        d = len(raw.split(".")[1]) if "." in raw else 0
        if not any(abs(s - v) <= 0.5 * 10 ** -d + 1e-9 or round(s, d) == v or abs(s * 100 - v) < 0.06 for s in src):
            missing.append(raw)
    return {"figures": checked, "verified": checked - len(missing), "unverified": missing[:6]}


async def staff_agent(user: dict, question: str, history: list | None = None, case_id: str | None = None,
                      lang_hint: str = "en"):
    """Async generator of (event, data) for SSE: meta, tool, chart, token, done."""
    lng = L.detect(question, default=lang_hint if lang_hint in ("ms", "en") else "en")
    case = domain.build_case(case_id) if case_id else None
    tools = tools_for(user)
    yield "meta", {"model": llm.status().get("model"), "lang": lng, "tools": list(tools), "case": case_id}
    sources = [case_context(case)] if case else []
    if not llm.status().get("available"):
        text = _fallback(user, question, case, tools)
        yield "token", {"t": text}
        yield "done", {"grounding": grounding(text, [text]), "source": "deterministic"}
        return
    msgs = [{"role": "system", "content": _staff_system(user, lng, case)}]
    for h in (history or [])[-6:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            msgs.append({"role": h["role"], "content": str(h["content"])[:1200]})
    named = mentioned_members(question) if "get_member" in tools or "affordability_check" in tools else []
    hint = ("\n\n(Members named in this question: " + "; ".join(f"{m['name']} — member no. {m['id']}" for m in named)
            + ". Pass the member number to the tools; do not ask the user for it.)") if named else ""
    msgs.append({"role": "user", "content": question + hint})
    specs = [spec for _, spec in tools.values()]
    sources.append(question)
    answer, called, corrections, last_result = "", [], 0, None
    try:
        for _round in range(7):
            calls, text, streamed = [], "", False
            live = bool(called) or case is not None              # data already in hand: show the answer as it forms
            async for kind, val in llm.chat(msgs, tools=specs, temperature=0.15, num_predict=900):
                if kind == "tool_calls":
                    calls += val
                else:
                    text += val
                    if live and not calls:
                        streamed = True
                        yield "token", {"t": val}
            if calls and streamed:
                yield "replace", {"t": ""}                    # a preamble before a tool call is not the answer
            if not calls:
                # nothing reaches the person until its figures trace back to tool output or the case file
                g = grounding(text, sources)
                # with a case file loaded the context itself is the source, so it counts as a lookup
                looked_up = bool(called) or case is not None
                # a small derived number may pass; an amount the data does not contain never does
                big = [x for x in g["unverified"] if float(x.replace(",", "")) >= 100]
                bad = g["unverified"] and (not looked_up or big or len(g["unverified"]) > max(1, g["figures"] // 5))
                if bad and corrections < 2:
                    corrections += 1
                    yield "check", {"unverified": g["unverified"], "retry": corrections}
                    if streamed:
                        yield "replace", {"t": ""}
                    msgs += [{"role": "assistant", "content": text},
                             {"role": "user", "content": ("Jawapan itu mengandungi angka yang tiada dalam data alat: " if lng == "ms"
                              else "That answer contains figures that are not in any tool result: ") + ", ".join(g["unverified"])
                              + (". Panggil alat yang sesuai dan jawab hanya daripada outputnya." if lng == "ms"
                                 else ". Call the appropriate tool and answer only from its output.")}]
                    continue
                if bad:
                    text = (_from_tool(last_result, lng) if last_result else
                            tt_(lng, "I could not verify figures for that question against the data. Please ask more specifically "
                                     "(for example, by branch, product or case number).",
                                "Saya tidak dapat mengesahkan angka bagi soalan itu dengan data. Sila tanya dengan lebih khusus "
                                "(contohnya mengikut cawangan, produk atau nombor kes)."))
                answer = text
                if streamed and not bad:
                    if lng == "ms" and L.indonesian_hits(answer):
                        yield "replace", {"t": L.normalise_ms(answer)}
                    yield "done", {"grounding": grounding(answer, sources), "source": "llm", "tools": called,
                                   "corrections": corrections}
                    return
                if streamed:
                    yield "replace", {"t": ""}
                break
            msgs.append({"role": "assistant", "content": text, "tool_calls": calls})
            for call in calls[:4]:
                name = call["function"]["name"]
                args = call["function"].get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except ValueError:
                        args = {}
                if name not in tools:
                    result, chart = {"error": f"tool {name} is not available to the {user['role_label']} role"}, None
                else:
                    try:
                        res = tools[name][0](user, **{k: v for k, v in args.items() if v not in (None, "")})
                    except TypeError as e:
                        res = {"error": f"bad arguments: {e}"}
                    result, chart = res if isinstance(res, tuple) else (res, None)
                called.append(name)
                last_result = (name, result)
                payload = json.dumps(result, default=str)[:6000]
                sources.append(payload)
                yield "tool", {"name": name, "args": args, "ok": "error" not in result,
                               "summary": _summarise(name, result)}
                if chart:
                    yield "chart", chart
                msgs.append({"role": "tool", "content": payload, "tool_name": name})
        else:
            answer = answer or tt_(lng, "I could not complete that request — please narrow the question.",
                                   "Saya tidak dapat melengkapkan permintaan itu — sila perincikan soalan.")
    except Exception as e:                                              # noqa: BLE001
        text = _fallback(user, question, case, tools) + f"\n\n(The local model failed: {str(e)[:80]})"
        yield "token", {"t": text}
        yield "done", {"grounding": grounding(text, [text]), "source": "deterministic"}
        return
    if lng == "ms" and L.indonesian_hits(answer):
        answer = L.normalise_ms(answer)
    for i in range(0, len(answer), 48):                                # stream the checked answer
        yield "token", {"t": answer[i:i + 48]}
    yield "done", {"grounding": grounding(answer, sources), "source": "llm", "tools": called, "corrections": corrections}


def tt_(lng: str, en: str, ms: str) -> str:
    return ms if lng == "ms" else en


def _from_tool(last: tuple, lng: str) -> str:
    """When the model cannot state figures faithfully, show the tool's own data instead."""
    name, r = last
    head = tt_(lng, "Here is the data I retrieved:", "Berikut ialah data yang diperoleh:")
    if "table" in r:
        cols = list(next(iter(r["table"].values())).keys())
        rows = "\n".join(f"| {k} | " + " | ".join(f"{v[c]:,}" if isinstance(v[c], (int, float)) else str(v[c]) for c in cols) + " |"
                         for k, v in r["table"].items())
        return f"{head}\n\n| {r['group_by']} | " + " | ".join(c.replace('_', ' ') for c in cols) + " |\n|" + "---|" * (len(cols) + 1) + f"\n{rows}\n\nSource: {name}"
    if "rows" in r:
        keys = [k for k in r["rows"][0].keys()][:6] if r["rows"] else []
        body = "\n".join("| " + " | ".join(str(x.get(k, "")) for k in keys) + " |" for x in r["rows"][:15])
        return f"{head}\n\n| " + " | ".join(keys) + " |\n|" + "---|" * len(keys) + f"\n{body}\n\nSource: {name}"
    return f"{head} {json.dumps(r, default=str)[:600]}\n\nSource: {name}"


def _summarise(name: str, result: dict) -> str:
    if "error" in result:
        return result["error"]
    if name == "affordability_check":
        return f"{result['member']}: maximum {rm(result['max_financing'])} over {result['term_months']} months ({result['binding_limit']})"
    if name == "get_member":
        return f"{result.get('name')} — {result.get('service', '')}, {result.get('branch', '')}"
    if "count" in result:
        return f"{result['count']} result(s)"
    if "table" in result:
        return f"{len(result['table'])} groups"
    if "context" in result:
        return "case facts loaded"
    if "rows" in result:
        return f"{len(result['rows'])} row(s)"
    if "bands" in result:
        return ", ".join(f"{k} {v}" for k, v in result["bands"].items())
    return "done"


def _fallback(user, question, case, tools) -> str:
    if case:
        return "The local model is unavailable, so here are the grounded facts for this case:\n\n" + case_context(case)
    p = domain.portfolio()
    k = p["kpis"]
    return (f"The local model is unavailable. Portfolio: {k['pipeline']} live applications, {rm(k['exposure'])} requested, "
            f"approval rate {k['approval_rate']}%, predicted delinquency {k['predicted_delinquency']}%, "
            f"{k['early_warnings']} members in early warning.")
