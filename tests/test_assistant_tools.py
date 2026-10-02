"""KT Assistant tools: member recognition, affordability without an amount, filtered breakdowns, clean text."""
import assistant, auth, domain, llm


def officer():
    return auth.user_record("noraini", domain.MEMBERS)


def test_members_named_in_either_language_are_recognised():
    for q, want in [("How much could Sjn Udara Nurul Huda borrow over 60 months?", "104402"),
                    ("Berapa boleh Sjn Udara Nurul Huda pinjam untuk 60 bulan?", "104402"),
                    ("Why did Kpl Mohd Ridzuan fail policy?", "104310"),
                    ("profile for 104436", "104436")]:
        assert [m["id"] for m in assistant.mentioned_members(q)][:1] == [want], q
    assert assistant.mentioned_members("Jumlah pembiayaan mengikut cawangan") == []


def test_affordability_without_an_amount_reports_the_maximum():
    r = assistant._t_affordability_check(officer(), member="Sjn Udara Nurul Huda", term=60)
    assert r["max_financing"] == 64100 and r["binding_limit"] == "debt service ratio ceiling"
    assert "requested_result" not in r and r["dsr_at_max"] <= r["dsr_ceiling"]
    r = assistant._t_affordability_check(officer(), member="104402", amount=80000, term=60)
    assert r["requested_result"] == "FAIL" and "Debt service ratio" in r["requested_failures"]


def test_breakdown_respects_the_product_filter():
    res, chart = assistant._t_portfolio_breakdown(officer(), group_by="branch", metric="amount", product="Personal Financing-i")
    truth = {}
    for a in domain.applications():
        if a["product"] == "Personal Financing-i":
            truth[a["branch"]] = truth.get(a["branch"], 0) + a["amount"]
    assert {k: v["amount_rm"] for k, v in res["table"].items()} == truth
    assert "Personal Financing-i" in res["filter"] and "Personal Financing-i" in chart["title"]


def test_grounding_flags_invented_figures():
    src = ['{"table": {"Kuala Lumpur": {"amount_rm": 188000, "cases": 3}}}']
    assert assistant.grounding("Kuala Lumpur RM188,000 across 3 cases", src)["unverified"] == []
    assert assistant.grounding("Penang RM1,420,000 across 32 cases", src)["unverified"]


def test_cyrillic_lookalikes_are_cleaned():
    assert llm.clean("a DSР of 39.98%") == "a DSR of 39.98%"


def test_breakdown_hands_the_model_its_totals():
    res, _ = assistant._t_portfolio_breakdown(officer(), group_by="branch", metric="amount")
    assert res["total"]["amount_rm"] == round(sum(a["amount"] for a in domain.applications()))
    assert res["total"]["cases"] == len(domain.applications())
