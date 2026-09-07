"""Document intelligence: classification, extraction with evidence bounding
boxes, forensics, cross-source reconciliation and exception detection."""
from __future__ import annotations
import re, hashlib, datetime as dt

MONEY = re.compile(r"\$?\s*([\d,]+(?:\.\d{2})?)")

CLASSIFIER_HINTS = [
    ("Payslip", ["payslip", "pay_slip", "salary_slip", "pay-stub", "paystub"]),
    ("Bank Statement", ["bank", "statement", "account_statement"]),
    ("Employment Letter", ["employment", "employer", "certificate_of_employment"]),
    ("Government ID", ["id", "national_id", "passport", "licence", "license"]),
    ("Salary Deduction", ["deduction", "remittance"]),
    ("Payment History", ["payment_history", "history", "ledger"]),
    ("Business Permit", ["permit", "business_permit", "dti"]),
    ("Income Statement", ["income_statement", "p&l", "profit"]),
    ("Tax Return", ["tax", "itr", "return"]),
    ("Equipment Quote", ["quote", "quotation", "invoice", "proforma"]),
    ("Vehicle Quote", ["vehicle", "car", "auto_quote"]),
    ("Property Valuation", ["valuation", "appraisal"]),
    ("Enrollment Letter", ["enrollment", "enrolment", "tuition"]),
]

PIPELINE = ["Upload", "Malware scan", "Classification", "OCR", "Layout understanding",
            "Field extraction", "Confidence scoring", "Forensics", "Cross-document comparison",
            "Exception detection", "Evidence registration"]


def classify(filename: str) -> tuple[str, int]:
    low = filename.lower()
    for label, keys in CLASSIFIER_HINTS:
        for k in keys:
            if k in low:
                return label, 94
    return "Supporting Document", 61


def sha(name: str) -> str:
    return "sha256:" + hashlib.sha256(name.encode()).hexdigest()[:24]


def _num(v: str) -> float | None:
    if v is None:
        return None
    m = MONEY.search(str(v))
    return float(m.group(1).replace(",", "")) if m else None


def extract_summary(documents: list[dict]) -> dict:
    """Roll the per-document fields up into the values the policy engine consumes."""
    out = {}
    for d in documents:
        f = {x["k"]: x["v"] for x in d.get("fields", [])}
        if d["doc_type"] == "Payslip":
            out["payslip_income"] = _num(f.get("Annualised Net"))
            out["employer_payslip"] = f.get("Employer")
            out["deduction_payslip"] = _num(f.get("Salary Deduction (Coop)"))
            out["name_payslip"] = f.get("Employee Name")
        if d["doc_type"] == "Bank Statement":
            out["bank_income"] = _num(f.get("Annualised Deposits"))
            out["recurring_debits"] = _num(f.get("Recurring Debits"))
            out["name_bank"] = f.get("Account Holder")
            out["nsf"] = f.get("NSF Events (90d)")
        if d["doc_type"] == "Employment Letter":
            out["employer_letter"] = f.get("Employer")
            out["employment_status"] = f.get("Employment Status")
            out["name_letter"] = f.get("Employee Name")
        if d["doc_type"] == "Government ID":
            out["name_id"] = f.get("Full Name")
            out["id_number"] = f.get("ID Number")
        if d["doc_type"] == "Salary Deduction":
            out["deduction_feed"] = _num(f.get("Deduction Amount"))
            out["deduction_regularity"] = f.get("Remittance Regularity")
        if d["doc_type"] == "Income Statement":
            out["bank_income"] = out.get("bank_income") or _num(f.get("Annualised Net"))
            out["statement_net"] = _num(f.get("Annualised Net"))
    return out


def _row(attr, values, tolerance=0.0, unit=""):
    """values: list of (source, value). Compares numbers within tolerance %, strings exactly."""
    present = [(s, v) for s, v in values if v not in (None, "", "—")]
    if len(present) < 2:
        return dict(attribute=attr, values=dict(values), result="Insufficient",
                    detail="Fewer than two independent sources", severity="info")
    nums = [(_num(v) if not isinstance(v, (int, float)) else float(v)) for _, v in present]
    if all(n is not None for n in nums):
        lo, hi = min(nums), max(nums)
        spread = (hi - lo) / hi * 100 if hi else 0
        ok = spread <= tolerance
        return dict(attribute=attr, values={s: v for s, v in values}, result="Match" if ok else "Review",
                    detail=f"{spread:.1f}% spread across sources (tolerance {tolerance}%)",
                    severity="info" if ok else ("high" if spread > 20 else "medium"), spread=round(spread, 1))
    vals = {str(v).strip().lower() for _, v in present}
    ok = len(vals) == 1
    return dict(attribute=attr, values={s: v for s, v in values}, result="Match" if ok else "Mismatch",
                detail="All sources agree" if ok else "Sources disagree",
                severity="info" if ok else "high")


def reconcile(application: dict, member: dict, documents: list[dict]) -> dict:
    e = extract_summary(documents)
    rows = [
        _row("Annual income", [("Application", member["declared_income"]),
                               ("Payslip", e.get("payslip_income")),
                               ("Bank Statement", e.get("bank_income")),
                               ("Core Member Data", member.get("bank_income"))], tolerance=10),
        _row("Employer", [("Application", member["employer"]),
                          ("Payslip", e.get("employer_payslip")),
                          ("Employment Letter", e.get("employer_letter"))]),
        _row("Account holder / name", [("Application", member["name"]),
                                       ("Government ID", e.get("name_id")),
                                       ("Payslip", e.get("name_payslip")),
                                       ("Bank Statement", e.get("name_bank"))]),
        _row("Salary deduction", [("Core Member Data", member.get("deduction")),
                                  ("Payslip", e.get("deduction_payslip")),
                                  ("Deduction Feed", e.get("deduction_feed"))], tolerance=2),
        _row("Employment status", [("Application", member["employment"]),
                                   ("Employment Letter", e.get("employment_status", "").split(" — ")[0] if e.get("employment_status") else None)]),
    ]
    exceptions = []
    for r in rows:
        if r["result"] in ("Review", "Mismatch"):
            exceptions.append(dict(
                title=f"{r['attribute']} discrepancy", severity=r["severity"], attribute=r["attribute"],
                detail=r["detail"], policy="POL-003",
                resolution="Request employer confirmation or one additional month of bank statements",
                classification="Discrepancy requiring verification — not an allegation of fraud"))
    if e.get("deduction_regularity") and "delay" in str(e["deduction_regularity"]).lower():
        exceptions.append(dict(title="Irregular salary deduction remittance", severity="medium",
                               attribute="Salary deduction", detail=e["deduction_regularity"],
                               policy="POL-007", resolution="Monitor next two cycles; flag to servicing",
                               classification="Servicing signal"))
    return {"rows": rows, "exceptions": exceptions, "extract": e,
            "sources": ["Application", "Payslip", "Bank Statement", "Employment Letter",
                        "Deduction Feed", "Government ID", "Core Member Data"]}


def completeness(application: dict, documents: list[dict], required: list[str]) -> dict:
    present = {d["doc_type"] for d in documents if d["status"] != "Rejected"}
    verified = {d["doc_type"] for d in documents if d["status"] == "Verified"}
    missing = [r for r in required if r not in present]
    return {"required": len(required), "present": len([r for r in required if r in present]),
            "verified": len([r for r in required if r in verified]), "missing": missing,
            "required_list": required,
            "complete": not missing}


def forensics_report(documents: list[dict]) -> list[dict]:
    out = []
    for d in documents:
        f = d.get("forensics", {})
        flags = []
        if f.get("tampering"): flags.append("Content-layer manipulation detected")
        if f.get("duplicate_hash"): flags.append("Document hash seen on another case")
        if f.get("font_consistency", 100) < 92: flags.append("Font/layout inconsistency")
        if not f.get("metadata_ok", True): flags.append("Metadata anomaly")
        out.append(dict(doc=d["label"], doc_id=d["id"], hash=sha(d["file"]),
                        producer=f.get("producer", "unknown"),
                        font_consistency=f.get("font_consistency", 100),
                        verdict="Clean" if not flags else "Attention", flags=flags))
    return out
