"""Financial-distress outlook — "Possible Bankruptcy" in Member 360.

Context (as cited in KT's brief): 4,194 civil servants were declared bankrupt between 2020 and June 2025,
about 0.3% of 1.6 million civil servants (Deputy Finance Minister's reply in Parliament, Malay Mail,
13 Aug 2025); 3,602 between 2020 and September 2024 — 1,009 in 2020, 678 in 2021, 621 in 2022, 628 in
2023 and 666 in January–September 2024 (Minister Azalina's written reply, Malay Mail, 7 Nov 2024).

The model is a calibrated logistic regression trained at start-up on a synthetic cohort whose base rate
matches that ~0.3% figure, with additive reason codes. It is decision support only (POL-013): it never
triggers an adverse action; it routes the member to early, supportive help (rescheduling, AKPK
counselling) long before a creditor would petition. Since the Insolvency (Amendment) Act 2020 a
bankruptcy petition needs a debt of at least RM100,000, so total debt against that threshold is a feature.
"""
from __future__ import annotations
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from connectors import ccris

FEATURES = [
    ("deduction_ratio", "Salary deductions vs gross pay"),
    ("debt_to_income", "Total debt vs annual income"),
    ("arrears_recent", "Recent KT deduction arrears"),
    ("ext_arrears", "Arrears at other lenders (CCRIS)"),
    ("facilities", "Number of financing facilities"),
    ("savings_drawdown", "Savings (Simpanan) drawdown"),
    ("retirement_cliff", "Pay drop at retirement within 24 months"),
    ("legal", "Legal action on record"),
    ("engagement_drop", "Declining engagement with KT"),
    ("threshold_proximity", "Debt against the RM100,000 petition threshold"),
]
_KEYS = [k for k, _ in FEATURES]
_LABEL = dict(FEATURES)
# generative weights in natural units (per % of gross, per day of arrears, per facility ...)
_W = np.array([0.035, 0.35, 0.012, 0.010, 0.12, 0.008, 0.50, 1.20, 0.006, 0.90])
_CENTER = np.array([40, 0, 0, 0, 0, 0, 0, 0, 0, 0], dtype=float)

BASE_RATE_CITED = 0.003
CONTEXT = {
    "headline": "About 0.3% of Malaysia's 1.6 million civil servants were declared bankrupt between 2020 and June 2025.",
    "series": [{"year": "2020", "n": 1009}, {"year": "2021", "n": 678}, {"year": "2022", "n": 621},
               {"year": "2023", "n": 628}, {"year": "Jan–Sep 2024", "n": 666}],
    "sources": [
        "Deputy Finance Minister, reply in Parliament — Malay Mail, 13 Aug 2025 (4,194 civil servants, 2020–Jun 2025)",
        "Minister Azalina Othman Said, written reply — Malay Mail, 7 Nov 2024 (3,602 civil servants, 2020–Sep 2024)",
    ],
    "threshold": "Minimum debt for a bankruptcy petition: RM100,000 (Insolvency (Amendment) Act 2020).",
}


class DistressModel:
    def __init__(self, n=160000, seed=17):
        rng = np.random.default_rng(seed)
        X = np.column_stack([
            rng.normal(42, 10, n).clip(5, 90),           # deduction ratio %
            rng.gamma(2.0, 0.45, n).clip(0, 6),          # debt / annual income
            rng.gamma(0.6, 6, n).clip(0, 120),           # recent arrears (days)
            rng.gamma(0.35, 12, n).clip(0, 120),         # external arrears (days)
            rng.poisson(1.6, n).clip(0, 8),              # facilities
            rng.gamma(1.2, 12, n).clip(0, 100),          # savings drawdown %
            (rng.random(n) < 0.08).astype(float),        # retirement cliff
            (rng.random(n) < 0.012).astype(float),       # legal action
            rng.gamma(1.0, 12, n).clip(0, 100),          # engagement drop %
            rng.beta(1.3, 6, n),                         # proximity to RM100k
        ])
        raw = (X - _CENTER) @ _W + rng.normal(0, 0.35, n)
        # solve the intercept so the cohort's annual rate matches the cited ~0.3% for civil servants
        lo, hi = -20.0, 0.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if (1 / (1 + np.exp(-(mid + raw)))).mean() > BASE_RATE_CITED:
                hi = mid
            else:
                lo = mid
        y = (rng.random(n) < 1 / (1 + np.exp(-(lo + raw)))).astype(int)
        self.scaler = StandardScaler().fit(X)
        self.lr = LogisticRegression(max_iter=4000).fit(self.scaler.transform(X), y)
        self.base_rate = float(y.mean())
        self.trained_on = n
        self.positives = int(y.sum())
        self.version = "distress-v1.1.0"

    def features_for(self, m: dict) -> dict:
        r = ccris.report(m)
        gross = m.get("gross_monthly") or 1
        pays = m.get("payments") or []
        recent = [p["days_late"] for p in pays[-6:]] or [0]
        trend = m.get("savings_trend") or [0]
        prior = sum(trend[:6]) / 6 if len(trend) >= 6 else (trend[0] or 1)
        drawdown = max(0.0, (prior - trend[-1]) / prior * 100) if prior else 0.0
        eng = m.get("engagement") or [0]
        e0 = sum(eng[:4]) / 4 if len(eng) >= 4 else eng[0]
        e1 = sum(eng[-4:]) / 4 if len(eng) >= 4 else eng[-1]
        engagement_drop = max(0.0, (e0 - e1) / e0 * 100) if e0 else 0.0
        total_debt = r["total_outstanding"]
        mtr = m.get("months_to_retirement")
        return {
            "deduction_ratio": round(((m.get("other_deductions") or 0) + (m.get("financing_deductions") or 0)) / gross * 100, 1),
            "debt_to_income": round(total_debt / max(1, gross * 12), 2),
            "arrears_recent": max(recent),
            "ext_arrears": r["max_dpd_12m"],
            "facilities": r["facility_count"],
            "savings_drawdown": round(drawdown, 1),
            "retirement_cliff": 1.0 if (mtr is not None and mtr <= 24 and m.get("outstanding", 0) > 0) else 0.0,
            "legal": 1.0 if r["legal_status"] != "None on record" else 0.0,
            "engagement_drop": round(engagement_drop, 1),
            "threshold_proximity": round(min(1.0, total_debt / 100000), 3),
        }

    def score(self, m: dict) -> dict:
        feats = self.features_for(m)
        x = np.array([[feats[k] for k in _KEYS]], dtype=float)
        z = self.scaler.transform(x)
        p = float(self.lr.predict_proba(z)[0, 1])
        contrib = self.lr.coef_[0] * z[0]
        order = np.argsort(-contrib)
        drivers = [dict(feature=_KEYS[i], label=_LABEL[_KEYS[i]], value=feats[_KEYS[i]],
                        contribution=round(float(contrib[i]), 3)) for i in order if contrib[i] > 0.15][:5]
        band = "Low" if p < 0.005 else "Watch" if p < 0.02 else "Elevated" if p < 0.08 else "High"
        r = ccris.report(m)
        return {
            "member_id": m["id"], "probability_12m": round(p, 4), "band": band,
            "multiple_of_base": round(p / BASE_RATE_CITED, 1),
            "drivers": drivers, "features": feats, "actions": _actions(band, feats),
            "total_debt": r["total_outstanding"], "ccris": r,
            "model_version": self.version, "trained_on": self.trained_on,
            "cohort_base_rate": round(self.base_rate, 4),
            "guardrail": "Decision support only — never an automatic adverse action (POL-013).",
        }


def _actions(band: str, f: dict) -> list[str]:
    a = []
    if band == "High":
        a += ["Senior officer review within 5 working days",
              "Offer rescheduling or restructuring under POL-007 before any further arrears",
              "Refer to AKPK (Agensi Kaunseling dan Pengurusan Kredit) for free debt counselling",
              "Pause new financing and cross-selling offers to this member"]
    elif band == "Elevated":
        a += ["Early, supportive contact by the branch officer",
              "Review total salary deductions against the 60% cap; consider a longer tenure",
              "Share AKPK counselling information"]
    elif band == "Watch":
        a += ["Monitor the next two deduction cycles", "Include in financial-literacy outreach"]
    else:
        a.append("No action — routine monitoring")
    if f["retirement_cliff"] and band != "Low":
        a.append("Plan the switch from salary to pension deduction before retirement")
    if f["threshold_proximity"] >= 0.7 and band in ("Elevated", "High"):
        a.append("Total debt is approaching the RM100,000 petition threshold — prioritise consolidation advice")
    return a


MODEL = DistressModel()


def portfolio(members: list[dict]) -> dict:
    scores = [MODEL.score(m) for m in members]
    bands = {b: 0 for b in ("Low", "Watch", "Elevated", "High")}
    by_branch: dict = {}
    for m, s in zip(members, scores):
        bands[s["band"]] += 1
        d = by_branch.setdefault(m["branch"], {b: 0 for b in bands})
        d[s["band"]] += 1
    expected = round(sum(s["probability_12m"] for s in scores), 2)
    return {"bands": bands, "by_branch": by_branch, "expected_cases_12m": expected, "members": len(members),
            "portfolio_rate": round(expected / max(1, len(members)), 4), "context": CONTEXT}
