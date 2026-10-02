"""Synthetic data integrity: KT members, branches, products, Ringgit, 2026 dates in Malaysia time."""
import json, re, datetime as dt
import seed, domain, clock


def test_today_and_current_events_are_2026():
    assert clock.TODAY.year >= 2026
    for a in seed.APPLICATIONS:
        d = dt.date.fromisoformat(a["submitted"][:10])
        assert d <= clock.TODAY and d.year == clock.TODAY.year or (clock.TODAY - d).days < 10
        assert a["submitted"].endswith("+08:00")


def test_no_future_payments_and_deductions_on_payday():
    for m in domain.MEMBERS.values():
        for p in m["payments"]:
            d = dt.date.fromisoformat(p["month"])
            assert d <= clock.TODAY and d.day == seed.PAYDAY


def test_branches_and_products_are_kt():
    assert set(seed.BRANCHES) == {"Kuala Lumpur", "Sungai Besi", "Lumut", "Kuantan", "Kota Kinabalu", "Kok Lanas"}
    for a in seed.APPLICATIONS:
        p = seed.PRODUCTS[a["product"]]
        assert p["kind"] == "financing"
        assert p["min"] <= a["amount"] <= p["max"], a["id"]
        assert a["branch"] in seed.BRANCHES
    names = set(seed.PRODUCTS)
    for k in ("Personal Financing-i", "Express Financing-i", "Fees Financing-i", "SME Financing-i", "Term Financing-i",
              "Contract Financing-i", "Motor Takaful", "General Takaful", "Ar-Rahnu KT"):
        assert k in names


def test_members_are_kt_members():
    services = {m["service"] for m in domain.MEMBERS.values()}
    assert {"TD", "TLDM", "TUDM", "MINDEF", "VET"} <= services
    assert len({m["full_name"] for m in domain.MEMBERS.values()}) == len(domain.MEMBERS)
    for m in domain.MEMBERS.values():
        assert re.fullmatch(r"\d{6}-\d{2}-\d{4}", m["mykad"])
        assert m["phone"].startswith("+60")
        assert int(m["mykad"][-1]) % 2 == (1 if m["gender"] == "M" else 0)


def test_no_dollars_or_conventional_terms_in_seed_text():
    blob = json.dumps([seed.APPLICATIONS, seed.POLICY_LIBRARY, seed.COMMS, seed.PRODUCTS], default=str)
    assert "$" not in blob
    assert not re.search(r"\b(loan|interest rate)\b", blob, re.I)
