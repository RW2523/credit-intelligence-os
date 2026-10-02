"""External data adapters.

KT's lending platform (Digibanc, per the Codebase Technologies case study) integrates Experian's
Central Credit Reference Information System (CCRIS) for credit history and blacklist screening, SOLA
for salary-deduction eligibility, and eKYC. These adapters expose the same shapes the real feeds would,
but return deterministic SIMULATED data until KT provides sandbox credentials. Every response carries
`simulated: True` and the UI labels it as such.
"""
from connectors import ccris, sola, ekyc  # noqa: F401

SIMULATED = True
