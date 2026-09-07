"""Credit risk model: logistic regression + gradient boosting, probability
calibration, and additive reason codes. Trained at startup on a synthetic
population so the demo runs entirely offline on this machine."""
from __future__ import annotations
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.preprocessing import StandardScaler

FEATURES = [
    ("dsr", "Debt service ratio"),
    ("reliability", "Historical payment reliability"),
    ("tenure_years", "Employment tenure"),
    ("membership_years", "Membership tenure"),
    ("equity_ratio", "Savings & share capital vs exposure"),
    ("income_variance", "Declared vs verified income variance"),
    ("recent_inquiries", "Recent credit inquiries"),
    ("prior_loans", "Successfully repaid facilities"),
    ("max_days_late", "Worst historical delinquency"),
    ("utilisation", "Facility utilisation"),
]
_KEYS = [k for k, _ in FEATURES]
_LABEL = dict(FEATURES)

# true generative weights for the synthetic population (log-odds per z-unit)
_W = np.array([1.15, -1.05, -0.35, -0.45, -0.60, 0.55, 0.50, -0.40, 0.85, 0.65])
_BIAS = -3.5


class RiskModel:
    def __init__(self, n=6000, seed=11):
        rng = np.random.default_rng(seed)
        X = np.column_stack([
            rng.normal(33, 8, n).clip(5, 65),            # dsr
            rng.normal(92, 9, n).clip(40, 100),          # reliability
            rng.gamma(3, 2, n).clip(0, 30),              # employment tenure
            rng.gamma(2.4, 2, n).clip(0, 25),            # membership years
            rng.gamma(2, 0.5, n).clip(0.02, 6),          # equity ratio
            rng.gamma(1.4, 4, n).clip(0, 45),            # income variance %
            rng.poisson(1.3, n).clip(0, 9),              # inquiries
            rng.poisson(2.2, n).clip(0, 10),             # prior loans
            rng.gamma(1.1, 7, n).clip(0, 120),           # max days late
            rng.normal(48, 20, n).clip(0, 100),          # utilisation
        ])
        self.scaler = StandardScaler().fit(X)
        Z = self.scaler.transform(X)
        logit = _BIAS + Z @ _W + rng.normal(0, 0.45, n)
        y = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)

        self.lr = LogisticRegression(max_iter=2000).fit(Z, y)
        gb = GradientBoostingClassifier(n_estimators=120, max_depth=3, learning_rate=0.08, random_state=3)
        self.gb = CalibratedClassifierCV(gb, method="isotonic", cv=3).fit(Z, y)
        self.base_rate = float(y.mean())
        self.trained_on = n
        self.version = "risk-v3.4.1"

    # ------------------------------------------------------------------
    def features_for(self, member: dict, application: dict, policy: dict, history: dict) -> dict:
        equity = member["savings"] + member["share_capital"]
        exposure = max(1.0, member["outstanding"] + application["amount"])
        return {
            "dsr": policy["dsr"],
            "reliability": member["reliability"] or 75,
            "tenure_years": member["tenure_years"],
            "membership_years": policy["tenure_months"] / 12,
            "equity_ratio": equity / exposure,
            "income_variance": policy["income"]["variance_pct"],
            "recent_inquiries": history.get("recent_inquiries", 1),
            "prior_loans": member["prior_loans"],
            "max_days_late": history.get("max_days_late", 0),
            "utilisation": history.get("utilisation", 45),
        }

    def score(self, feats: dict) -> dict:
        x = np.array([[feats[k] for k in _KEYS]], dtype=float)
        z = self.scaler.transform(x)
        p_lr = float(self.lr.predict_proba(z)[0, 1])
        p_gb = float(self.gb.predict_proba(z)[0, 1])
        # blend, then shrink towards the population base rate so a single
        # extreme tree path cannot produce a 0% or 100% claim
        blended = 0.55 * p_lr + 0.45 * p_gb
        pd = round(float(np.clip(0.82 * blended + 0.18 * self.base_rate, 0.004, 0.65)), 4)

        # additive contributions in log-odds (locally faithful, LR-based)
        coef = self.lr.coef_[0]
        contrib = coef * z[0]
        order = np.argsort(-np.abs(contrib))
        drivers = []
        for i in order:
            drivers.append({
                "feature": _KEYS[i],
                "label": _LABEL[_KEYS[i]],
                "value": round(float(x[0, i]), 2),
                "contribution": round(float(contrib[i]), 3),
                "direction": "increases risk" if contrib[i] > 0 else "reduces risk",
            })
        grade, band = self._grade(pd)
        return {
            "pd": pd, "pd_lr": round(p_lr, 4), "pd_gb": round(p_gb, 4),
            "grade": grade, "band": band,
            "score": int(round(850 - 600 * min(1.0, pd ** 0.42), 0)),
            "drivers": drivers,
            "positive": [d for d in drivers if d["contribution"] < 0][:4],
            "negative": [d for d in drivers if d["contribution"] > 0][:4],
            "reason_codes": [self._code(d) for d in drivers if d["contribution"] > 0][:3],
            "model_version": self.version,
            "base_rate": round(self.base_rate, 4),
            "calibration": "isotonic, 3-fold",
        }

    @staticmethod
    def _grade(pd: float):
        if pd < 0.025: return "Low", "A"
        if pd < 0.06:  return "Low", "B"
        if pd < 0.12:  return "Moderate", "C"
        if pd < 0.20:  return "Elevated", "D"
        return "High", "E"

    @staticmethod
    def _code(d: dict) -> str:
        return {
            "dsr": "R01 — Debt service ratio elevated relative to verified income",
            "reliability": "R02 — Payment reliability below product benchmark",
            "tenure_years": "R03 — Limited employment tenure",
            "membership_years": "R04 — Short membership relationship",
            "equity_ratio": "R05 — Low savings and share capital relative to exposure",
            "income_variance": "R06 — Declared income not fully corroborated",
            "recent_inquiries": "R07 — Recent credit-seeking activity",
            "prior_loans": "R08 — Limited repayment track record",
            "max_days_late": "R09 — Historical delinquency present",
            "utilisation": "R10 — High facility utilisation",
        }[d["feature"]]


MODEL = RiskModel()
