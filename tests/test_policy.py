"""Affordability engine: the reported -200 bug, flat-rate maths and the 60% deduction cap."""
import random
import domain, seed
from engines import policy


def case(aid):
    return domain.build_case(aid)


def test_maximum_is_never_negative_for_any_seeded_case():
    for a in domain.applications():
        assert case(a["id"])["policy"]["max_financing"] >= 0, a["id"]


def test_maximum_is_never_negative_for_random_members():
    rnd = random.Random(1)
    members = list(domain.MEMBERS.values())
    for _ in range(1000):
        m = dict(rnd.choice(members))
        m["outstanding"] = rnd.choice([0, 5000, 30000, 90000])
        m["savings"], m["share_capital"] = rnd.choice([(100, 50), (2000, 1000), (40000, 20000)])
        prod = rnd.choice(seed.FINANCING)
        p = seed.PRODUCTS[prod]
        app = dict(product=prod, amount=rnd.randint(p["min"], p["max"]), term=rnd.randint(p["min_term"], p["max_term"]),
                   existing_commitments=rnd.choice([0, 300, 1500, 4000]))
        r = policy.assess(app, m, {})
        assert r["max_financing"] >= 0
        assert r["max_financing_binding"] in r["max_financing_limits"]


def test_robert_james_case_now_reads_rm0_with_an_explanation():
    c = case("APP-104310")
    p = c["policy"]
    assert p["max_financing"] == 0
    note = c["counterfactuals"]["improves"]
    joined = " ".join(note)
    assert "-RM" not in joined and "RM-" not in joined and "$" not in joined
    assert "56%" in joined and "RM433" in joined and "RM14,000" in joined and "RM50" in joined


def test_flat_rate_instalment():
    # RM25,000 over 48 months at 3.65% flat = 25,000 x (1 + 0.0365 x 4) / 48
    assert round(policy.instalment(25000, 48, 3.65), 2) == 596.88 or round(policy.instalment(25000, 48, 3.65), 2) == 596.87
    assert abs(policy.principal_for(policy.instalment(25000, 48, 3.65), 48, 3.65) - 25000) < 0.01


def test_sixty_percent_cap_binds_when_dsr_passes():
    p = case("APP-104355")["policy"]           # Kpl Jeffrey anak Nyalau
    assert p["dsr"] <= p["dsr_ceiling"]
    assert p["deduction_ratio"] > 60
    assert "Salary deduction cap (60% of gross)" in p["failures"]
    assert p["max_financing_binding"] == "deduction_cap"


def test_clean_case_passes_and_member_check_matches_workbench():
    c = case("APP-104328")
    m = domain.MEMBERS["104328"]
    app = dict(product="Personal Financing-i", amount=25000, term=48, existing_commitments=m["financing_deductions"])
    member_view = policy.assess(app, m, {})
    assert member_view["max_financing"] == c["policy"]["max_financing"] == 32800


def test_policy_gate_ids_are_unique():
    for a in domain.applications():
        ids = [g["id"] for g in case(a["id"])["policy"]["gates"] if g["name"] != "Tenure vs retirement"]
        assert len(ids) == len(set(ids)), (a["id"], ids)


def test_income_variance_case():
    p = case("APP-104328")["policy"]
    assert p["income"]["variance_pct"] == 17.3 and p["income"]["material_variance"]
