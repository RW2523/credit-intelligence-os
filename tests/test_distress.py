import domain
from engines import distress, crosssell


def test_cohort_matches_cited_civil_service_rate():
    assert abs(distress.MODEL.base_rate - 0.003) < 0.0006


def test_troubled_members_score_high_and_clean_members_low():
    hi = distress.MODEL.score(domain.MEMBERS["104436"])
    lo = distress.MODEL.score(domain.MEMBERS["104172"])
    assert hi["band"] == "High" and lo["band"] == "Low"
    assert hi["drivers"] and hi["actions"]
    assert 0 < hi["probability_12m"] < 0.8


def test_cross_sell_patterns_from_the_brief():
    a = [o["pattern"] for o in crosssell.offers(domain.MEMBERS["104402"])]
    b = [o["pattern"] for o in crosssell.offers(domain.MEMBERS["104415"])]
    c = [o["pattern"] for o in crosssell.offers(domain.MEMBERS["104428"])]
    assert "A" in a and "B" in b and "C" in c


def test_no_financing_offers_to_members_in_distress():
    for m in domain.MEMBERS.values():
        if distress.MODEL.score(m)["band"] in ("Elevated", "High"):
            assert not [o for o in crosssell.offers(m) if o["kind"] == "financing"], m["id"]
