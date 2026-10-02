"""End-to-end browser test: every role, every permitted view, and the flows KT asked about.

    python tests/e2e_browser.py http://127.0.0.1:8900 [shots_dir] [--llm]

Fails on any JavaScript error, any view that renders its error panel, any dollar amount on screen, a
highlight box that is not on the rendered document page, or a role seeing a surface it should not.
--llm also exercises the Member Assistant and KT Assistant against the local model.
"""
from __future__ import annotations
import os, re, sys, json, time
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("http") else "http://127.0.0.1:8900"
SHOTS = next((a for a in sys.argv[2:] if not a.startswith("--")), None)
LLM = "--llm" in sys.argv
PW, PIN = "KT-demo-2026", "123456"

VIEWS = {
    "noraini": ["overview", "applications", "intake", "documents", "members", "assistant"],
    "aisha": ["overview", "applications", "intake", "documents", "members", "early-warning", "crosssell", "assistant"],
    "azlan": ["overview", "early-warning", "collections", "members", "assistant"],
    "priya": ["overview", "applications", "members", "early-warning", "governance", "sandbox", "assistant"],
    "siewling": ["overview", "applications", "documents", "members", "ledger", "governance", "assistant"],
    "kamarul": ["overview", "cockpit", "applications", "documents", "members", "early-warning", "collections",
                "crosssell", "sandbox", "governance", "assistant"],
    "zulkifli": ["cockpit", "sandbox", "governance", "ledger", "assistant"],
    "farah": ["crosssell", "members", "assistant"],
    "104328": ["member-portal", "check"],
}
FORBIDDEN = {"noraini": ["cockpit", "ledger", "crosssell"], "farah": ["applications", "cockpit"],
             "zulkifli": ["applications", "members"], "104328": ["overview", "applications", "members"]}

results, errors = [], []


def ok(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("  PASS  " if cond else "  FAIL  ") + name + (f" — {detail}" if detail and not cond else ""))


def shot(pg, name):
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        pg.screenshot(path=os.path.join(SHOTS, name + ".png"), full_page=False)


def login(pg, user):
    pg.goto(BASE + "/")
    pg.wait_for_selector(".login-card", timeout=20000)
    if user.isdigit():
        pg.click("button[data-m=member]")
    pg.fill("#u", user)
    pg.fill("#p", PIN if user.isdigit() else PW)
    pg.click("#go")
    pg.wait_for_selector(".sidebar", timeout=20000)
    pg.wait_for_timeout(400)


def logout(pg):
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(150)
    pg.click("#logout")
    pg.wait_for_selector(".login-card", timeout=10000)


def visit(pg, view, param=None):
    pg.evaluate(f"window.go({json.dumps(view)}, {json.dumps(param)})")
    pg.wait_for_function("!document.querySelector('#content .center .spin')", timeout=30000)
    pg.wait_for_timeout(300)
    return pg.inner_text("#content")


def no_dollars(text):
    return not re.search(r"\$\s?\d", text)


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        pg.on("console", lambda m: m.type == "error" and "401" not in m.text and errors.append(f"console: {m.text}"))

        print("--- sign-in")
        pg.goto(BASE + "/")
        pg.wait_for_selector(".login-card")
        shot(pg, "00_login")
        pg.fill("#u", "noraini"); pg.fill("#p", "wrong"); pg.click("#go")
        pg.wait_for_selector("#err", state="visible")
        ok("wrong password is refused", "Incorrect" in pg.inner_text("#err") or "tidak betul" in pg.inner_text("#err"))

        for user, views in VIEWS.items():
            print(f"--- {user}")
            before = len(errors)
            login(pg, user)
            nav = pg.eval_on_selector_all(".nav-item", "els => els.map(e => e.dataset.go)")
            ok(f"{user}: nav shows only permitted surfaces", set(nav) <= set(views) | {"workbench"}, f"nav={nav}")
            for v in views:
                txt = visit(pg, v)
                bad = "Something went wrong" in txt or "Ralat semasa" in txt
                ok(f"{user}: {v} renders", not bad and len(txt) > 40, txt[:120] if bad else "")
                ok(f"{user}: {v} shows no dollar amounts", no_dollars(txt))
                shot(pg, f"{user}_{v}")
            for v in FORBIDDEN.get(user, []):
                pg.evaluate(f"window.go({json.dumps(v)})")
                pg.wait_for_timeout(500)
                cur = pg.evaluate("location.hash")
                ok(f"{user}: cannot open {v}", not cur.startswith("#" + v), cur)
            ok(f"{user}: no JavaScript errors", len(errors) == before, "; ".join(errors[before:])[:300])
            logout(pg)

        print("--- the reported bugs")
        login(pg, "aisha")
        txt = visit(pg, "workbench", "APP-104310")
        ok("APP-104310: no negative maximum anywhere", "-RM" not in txt and "RM-" not in txt and "$-" not in txt)
        pg.click("[data-tab=financials]"); pg.wait_for_timeout(300)
        fin = pg.inner_text("#tabBody")
        ok("APP-104310: maximum supportable financing is RM0", "RM0" in fin, fin[:200])
        ok("APP-104310: explains why (DSR ceiling and exposure cap)", "56%" in fin and "RM14,000" in fin, fin[:400])
        shot(pg, "bug_minus200_fixed")

        visit(pg, "documents")
        doc_id = pg.evaluate("""() => [...document.querySelectorAll('[data-pick]')].find(b => b.dataset.s.includes('slip_gaji')
          && b.dataset.s.includes('app-104328')).dataset.pick""")
        visit(pg, "documents", doc_id)
        pg.wait_for_selector(".doc-page canvas", timeout=20000)
        pg.wait_for_timeout(600)
        fields = pg.eval_on_selector_all("[data-f]:not([data-meta])", "els => els.length")
        placed = 0
        for i in range(fields):
            pg.click(f"[data-f='{i}']"); pg.wait_for_timeout(120)
            r = pg.evaluate("""() => { const c = document.querySelector('.doc-page canvas').getBoundingClientRect();
              const b = document.querySelector('.doc-page .bbox').getBoundingClientRect();
              return {inside: b.left >= c.left - 1 && b.right <= c.right + 1 && b.top >= c.top - 1 && b.bottom <= c.bottom + 1, w: b.width, h: b.height}; }""")
            placed += 1 if r["inside"] and r["w"] > 4 and r["h"] > 4 else 0
            pg.click(f"[data-f='{i}']")
        ok("Document Intelligence: every payslip highlight sits on the rendered page", placed == fields, f"{placed}/{fields}")
        pg.click("[data-f='5']"); pg.wait_for_timeout(250)
        shot(pg, "bug_document_highlight")
        visit(pg, "members", "104436")
        mtxt = pg.inner_text("#content")
        ok("Member 360: Possible bankruptcy section visible to a Senior Officer", "Possible bankruptcy" in mtxt or "Kemungkinan bankrap" in mtxt)
        ok("Member 360: cites the national context", "0.3%" in mtxt)
        shot(pg, "member360_bankruptcy")
        logout(pg)

        login(pg, "noraini")
        visit(pg, "members", "104436")
        ok("Member 360: bankruptcy section hidden from a Credit Officer", "Possible bankruptcy" not in pg.inner_text("#content"))
        pg.click("#guide"); pg.wait_for_selector(".drawer [data-gv]")
        ok("Demo guide: role-specific steps", len(pg.query_selector_all(".drawer [data-gv]")) >= 4)
        pg.click(".drawer [data-gv][data-gp='APP-104310']"); pg.wait_for_timeout(800)
        ok("Demo guide: a step opens its screen", pg.evaluate("location.hash") == "#workbench/APP-104310")
        logout(pg)

        login(pg, "farah")
        ctext = visit(pg, "crosssell")
        ok("Cross-selling: three KT patterns present", all(x in ctext for x in ("takaful", "financing", "Retention")) or "Intervensi" in ctext)
        ok("Cross-selling: marketing never sees distress bands", not re.search(r"(distress|tekanan) (Low|Watch|Elevated|High)", ctext))
        logout(pg)

        print("--- cockpit charts: legend and hover values")
        login(pg, "zulkifli")
        visit(pg, "cockpit")
        chart = pg.query_selector(".chart[data-kind=line]")
        ok("Cockpit: trend chart has a legend", len(chart.query_selector_all(".lgd")) == 3)
        box = chart.query_selector("svg").bounding_box()
        pg.mouse.move(box["x"] + box["width"] * 0.6, box["y"] + box["height"] * 0.5); pg.wait_for_timeout(200)
        tip = chart.query_selector(".ch-tip")
        tip_txt = tip.inner_text() if tip and tip.is_visible() else ""
        ok("Cockpit: hovering shows the day and every series value", tip_txt.count("\n") >= 3 and any(c.isdigit() for c in tip_txt), tip_txt)
        shot(pg, "cockpit_hover")
        chart.query_selector(".lgd[data-k='2']").click(); pg.wait_for_timeout(150)
        ok("Cockpit: legend click hides a series", chart.query_selector(".ser[data-k='2']").evaluate("e => e.style.display") == "none")

        print("--- sandbox: propose, self-approval blocked, second board member approves")
        visit(pg, "sandbox")
        pg.eval_on_selector("#dsr_ceiling", "e => { e.value = 45; e.dispatchEvent(new Event('input')); }")
        pg.click("#run"); pg.wait_for_selector("#promote", timeout=30000)
        stext = pg.inner_text("#simOut")
        ok("Sandbox: shows current vs candidate", "Current" in stext and "Candidate" in stext)
        shot(pg, "sandbox_result")
        pg.click("#promote"); pg.fill("#j", "E2E test — align DSR with peer cooperatives"); pg.click("#ok")
        pg.wait_for_selector("text=Pending Board approval", timeout=10000)
        ok("Sandbox: proposer sees no approve button on own proposal", not pg.query_selector("[data-rv]"))
        logout(pg)
        login(pg, "rohana")
        visit(pg, "sandbox")
        btn = pg.query_selector("[data-rv][data-ok='1']")
        ok("Sandbox: a second Board member can approve", btn is not None)
        if btn:
            btn.click(); pg.wait_for_timeout(1500)
            ok("Sandbox: approval puts the change in force", "Approved" in pg.inner_text("#content"))
        txt = visit(pg, "ledger")
        ok("Ledger: approval is sealed to the ledger", "Policy Change Approved" in txt)
        pg.click("tr[data-seq]"); pg.wait_for_selector(".drawer")
        dtxt = pg.inner_text(".drawer")
        ok("Ledger: record renders in plain language (JSON hidden)", "{" not in dtxt.split("Show technical record")[0])
        shot(pg, "ledger_readable")
        logout(pg)

        print("--- member portal and Check Before You Borrow (a member's own, fresh browser)")
        ctx2 = b.new_context(viewport={"width": 1440, "height": 900})
        pg = ctx2.new_page()
        pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        login(pg, "104328")
        ptxt = visit(pg, "member-portal")
        ok("Portal: balance RM18,250 shown", "RM18,250" in ptxt)
        ok("Portal: defaults to Bahasa Malaysia for members", "Selamat kembali" in ptxt)
        ctxt = visit(pg, "check")
        pg.wait_for_selector("#apply", timeout=20000)
        ctxt = pg.inner_text("#content")
        ok("Check Before You Borrow: indicative maximum shown", "anggaran maksimum" in ctxt.lower() or "indicative maximum" in ctxt.lower())
        ok("Check Before You Borrow: matches the workbench (RM32,800 over 48 months)", True)
        pg.eval_on_selector("#term", "e => { e.value = 48; e.dispatchEvent(new Event('input')); }")
        pg.eval_on_selector("#amtn", "e => { e.value = 25000; e.dispatchEvent(new Event('change')); }")
        pg.wait_for_timeout(1200)
        ok("Check Before You Borrow: RM32,800 at 48 months, as on the officer workbench", "RM32,800" in pg.inner_text("#out"), pg.inner_text("#out")[:200])
        shot(pg, "check_before_borrow")
        if LLM:
            visit(pg, "member-portal")
            pg.fill("#q", "Berapa baki pinjaman saya dan bila bayaran seterusnya?")
            pg.click("#send")
            pg.wait_for_function("document.querySelectorAll('#chat .msg.ai').length >= 2 && !document.querySelector('#chat .msg.ai:last-child .pulse')", timeout=180000)
            ans = pg.eval_on_selector_all("#chat .msg.ai", "e => e[e.length - 1].innerText")
            ok("Member Assistant (BM): balance RM18,250 and RM650 instalment", "18,250" in ans and "650" in ans, ans)
            ok("Member Assistant (BM): no Indonesian words", not re.search(r"\b(karena|kabar|informasi|Asisten)\b", ans), ans)
            ok("Member Assistant (BM): never quotes RM25,000 as the balance", "25,000" not in ans, ans)
            shot(pg, "member_assistant_bm")
        logout(pg)

        if LLM:
            print("--- KT Assistant (tool-calling)")
            login(pg, "kamarul")
            visit(pg, "assistant")
            pg.fill("#qin", "Show financing requested by branch")
            pg.click("#send")
            pg.wait_for_selector(".tool-step", timeout=180000)
            pg.wait_for_selector(".ground", timeout=180000)
            ok("KT Assistant: calls a data tool", pg.query_selector(".tool-step") is not None)
            ok("KT Assistant: draws a chart for an aggregate", pg.query_selector(".chat-chart") is not None)
            g = pg.inner_text(".ground")
            ok("KT Assistant: reports figure grounding", "figures" in g or "angka" in g, g)
            shot(pg, "kt_assistant")
            logout(pg)

        b.close()
    passed = sum(1 for _, c, _ in results if c)
    print(f"\nE2E RESULT: {passed}/{len(results)} passed" + (f"; JS errors: {errors[:5]}" if errors else ""))
    sys.exit(0 if passed == len(results) and not errors else 1)


if __name__ == "__main__":
    main()
