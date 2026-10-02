"""SOLA salary-deduction eligibility — simulated from the member's payslip position."""
from __future__ import annotations
from seed import DEDUCTION_CAP_PCT


def eligibility(m: dict) -> dict:
    gross = m.get("gross_monthly") or 0
    used = (m.get("other_deductions") or 0) + (m.get("financing_deductions") or 0)
    room = round(gross * DEDUCTION_CAP_PCT / 100 - used, 2) if gross else 0.0
    return dict(source="SOLA", simulated=True, gross_monthly=gross, deductions_used=used,
                deduction_ratio=round(used / gross * 100, 1) if gross else None,
                cap_pct=DEDUCTION_CAP_PCT, monthly_headroom=max(0.0, room),
                eligible=room > 0 and m.get("member_type") != "retiree",
                channel=m.get("repayment_channel"))
