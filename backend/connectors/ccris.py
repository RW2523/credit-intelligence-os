"""Experian CCRIS / blacklist screening — simulated, deterministic per member."""
from __future__ import annotations
import random
from clock import TODAY

LENDERS = ["Bank Setia Perwira Berhad", "Koperasi Guru Malaysia (contoh)", "Bank Amanah Rakyat (contoh)",
           "Syarikat Kredit Kenderaan (contoh)", "PTPTN (pinjaman pendidikan)"]
INQUIRIES = {"104328": 3, "104310": 5, "104265": 4, "104436": 6}
LEGAL = {"104436": "Notice of demand from a bank (pre-litigation)"}


def report(m: dict) -> dict:
    rnd = random.Random(int(m["id"]) * 31)
    fac = []
    if m.get("outstanding"):
        fac.append(dict(lender="Koperasi Tentera", type="Personal Financing-i", outstanding=m["outstanding"],
                        instalment=m.get("deduction", 0), conduct="0 missed" if m.get("reliability", 100) >= 90
                        else "salary deduction delays"))
    ext = m.get("external_deductions", 0)
    if ext:
        n = 1 + (ext > 500) + (ext > 1000)
        for i in range(n):
            share = ext / n
            fac.append(dict(lender=LENDERS[(int(m["id"]) + i) % len(LENDERS)],
                            type=["Personal financing", "Hire purchase", "Credit card"][i % 3],
                            outstanding=round(share * rnd.randint(24, 60), -2), instalment=round(share, 2),
                            conduct="current" if m.get("pattern") not in ("bad", "drift") else
                            f"{rnd.choice([30, 60, 90])} days past due"))
    worst = 0
    for f in fac:
        if "days past due" in f["conduct"]:
            worst = max(worst, int(f["conduct"].split()[0]))
    return dict(
        source="Experian CCRIS", simulated=True, as_of=TODAY.isoformat(),
        facilities=fac, facility_count=len(fac),
        total_outstanding=round(sum(f["outstanding"] for f in fac), 2),
        external_outstanding=round(sum(f["outstanding"] for f in fac if f["lender"] != "Koperasi Tentera"), 2),
        max_dpd_12m=worst,
        recent_inquiries=INQUIRIES.get(m["id"], 1 + (int(m["id"]) % 3 == 0)),
        legal_status=LEGAL.get(m["id"], "None on record"),
        blacklisted=False,
        special_attention=m["id"] in LEGAL or worst >= 90,
    )
