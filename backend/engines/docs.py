"""Document intelligence: classification, extraction with evidence bounding
boxes, forensics, cross-source reconciliation and exception detection."""
from __future__ import annotations
import re, hashlib, datetime as dt

MONEY = re.compile(r"(?:RM|\$)?\s*([\d,]+(?:\.\d{1,2})?)")

# file-name hints in Malay and English; order matters (most specific first)
CLASSIFIER_HINTS = [
    ("Payslip", ["slip_gaji", "slipgaji", "penyata_gaji", "payslip", "pay_slip", "salary_slip", "paystub"]),
    ("Pension Slip", ["pencen", "pension"]),
    ("Salary Deduction Mandate", ["potongan", "angkasa", "deduction", "remittance"]),
    ("Payment History", ["sejarah_bayaran", "payment_history", "history"]),
    ("Bank Statement", ["penyata_bank", "bank", "statement", "penyata_akaun"]),
    ("Service Confirmation", ["pengesahan", "perkhidmatan", "service", "employment", "majikan"]),
    ("Identity Card", ["kad_pengenalan", "mykad", "ic_", "identity", "national_id", "passport"]),
    ("SSM Registration", ["ssm", "pendaftaran", "business_reg"]),
    ("Income Statement", ["penyata_pendapatan", "income_statement", "untung_rugi", "p&l", "profit"]),
    ("Tax Return", ["borang_b", "borang_be", "lhdn", "tax", "cukai"]),
    ("Fee Statement", ["yuran", "fee", "tuition", "tawaran"]),
    ("Contract Award Letter", ["setuju_terima", "sst", "kontrak", "contract", "award"]),
    ("Quotation", ["sebut_harga", "quotation", "quote", "invoice", "proforma"]),
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
        t = d["doc_type"]
        if t == "Payslip":
            gross, other = _num(f.get("Gross Monthly")), _num(f.get("Other Deductions"))
            if gross:
                out["gross_payslip"] = gross
                out["other_payslip"] = other or 0
                # income available for financing: gross pay less statutory and other non-financing deductions
                out["payslip_income"] = round((gross - (other or 0)) * 12, 2)
            out["employer_payslip"] = f.get("Employer")
            out["deduction_payslip"] = _num(f.get("KT Deduction"))
            out["financing_payslip"] = _num(f.get("Financing Deductions"))
            out["name_payslip"] = f.get("Employee Name")
            out["net_pay"] = _num(f.get("Net Pay"))
        if t == "Bank Statement":
            if f.get("Avg Monthly Salary Credit"):
                out["bank_credit_annual"] = round((_num(f["Avg Monthly Salary Credit"]) or 0) * 12, 2)
                out["bank_credit_kind"] = "salary"
                out["name_bank"] = f.get("Account Holder")
            elif f.get("Avg Monthly Business Credit"):
                out["bank_credit_annual"] = round((_num(f["Avg Monthly Business Credit"]) or 0) * 12, 2)
                out["bank_credit_kind"] = "business"
            out["returned_items"] = f.get("Returned Items (90d)")
        if t == "Service Confirmation":
            out["employer_letter"] = f.get("Employer")
            out["service_status"] = f.get("Service Status")
            out["name_letter"] = f.get("Employee Name")
            out["retirement_letter"] = f.get("Retirement Date")
        if t == "Identity Card":
            out["name_id"] = f.get("Full Name")
            out["id_number"] = f.get("MyKad No.")
        if t == "Salary Deduction Mandate":
            out["deduction_feed"] = _num(f.get("Deduction Amount"))
            out["deduction_regularity"] = f.get("Remittance Regularity")
        if t == "Income Statement":
            out["statement_net"] = _num(f.get("Net Profit"))
        if t == "Tax Return":
            out["tax_income"] = _num(f.get("Total Income"))
    return out


def bank_income(extract: dict, member: dict) -> float | None:
    """Annual income evidenced by the bank account. Salary credits are take-home pay, so the payroll
    financing deductions (from the payslip, else the member record) are added back."""
    credits = extract.get("bank_credit_annual")
    if not credits:
        return None
    if extract.get("bank_credit_kind") == "salary":
        fin = extract.get("financing_payslip")
        fin = member.get("financing_deductions", 0) if fin is None else fin
        return round(credits + 12 * fin, 2)
    return credits


def _canon_status(v):
    v = str(v).lower()
    if any(w in v for w in ("tetap", "permanent", "confirmed")):
        return "permanent & confirmed"
    if any(w in v for w in ("pencen", "retired", "pension")):
        return "pensioner"
    return v.strip()


def _row(attr, values, tolerance=0.0, unit="", canon=None):
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
    vals = {(canon(v) if canon else str(v).strip().lower()) for _, v in present}
    ok = len(vals) == 1
    return dict(attribute=attr, values={s: v for s, v in values}, result="Match" if ok else "Mismatch",
                detail="All sources agree" if ok else "Sources disagree",
                severity="info" if ok else "high")


def reconcile(application: dict, member: dict, documents: list[dict]) -> dict:
    e = extract_summary(documents)
    bank = bank_income(e, member)
    rows = [
        _row("Annual income (before financing)", [("Application", member["declared_income"]),
                                                 ("Payslip", e.get("payslip_income")),
                                                 ("Bank Statement", bank),
                                                 ("Income Statement", e.get("statement_net")),
                                                 ("KT Core", member.get("payslip_income") or member.get("bank_income"))],
             tolerance=10),
        _row("Employer", [("Application", member["employer"]),
                          ("Payslip", e.get("employer_payslip")),
                          ("Service Letter", e.get("employer_letter"))]),
        _row("Name", [("Application", member.get("full_name", member["name"])),
                      ("MyKad", e.get("name_id")),
                      ("Payslip", e.get("name_payslip")),
                      ("Bank Statement", e.get("name_bank"))]),
        _row("KT salary deduction", [("KT Core", member.get("deduction") or None),
                                     ("Payslip", e.get("deduction_payslip")),
                                     ("ANGKASA Schedule", e.get("deduction_feed"))], tolerance=2),
        _row("Service status", [("Application", member["employment"]),
                                ("Service Letter", e.get("service_status"))], canon=_canon_status),
    ]
    exceptions = []
    for r in rows:
        if r["result"] in ("Review", "Mismatch"):
            exceptions.append(dict(
                title=f"{r['attribute']} discrepancy", severity=r["severity"], attribute=r["attribute"],
                detail=r["detail"], policy="POL-003",
                resolution="Request unit/employer confirmation or one further month of bank statements",
                classification="Discrepancy requiring verification — not an allegation of fraud"))
    if e.get("deduction_regularity") and "delay" in str(e["deduction_regularity"]).lower():
        exceptions.append(dict(title="Irregular ANGKASA deduction remittance", severity="medium",
                               attribute="Salary deduction", detail=e["deduction_regularity"],
                               policy="POL-007", resolution="Monitor next two cycles; flag to servicing",
                               classification="Servicing signal"))
    return {"rows": rows, "exceptions": exceptions, "extract": e,
            "sources": ["Application", "Payslip", "Bank Statement", "Service Letter",
                        "ANGKASA Schedule", "MyKad", "Income Statement", "KT Core"]}


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
        out.append(dict(doc=d["label"], doc_id=d["id"], hash=d.get("sha256") or sha(d["file"]),
                        producer=f.get("producer", "unknown"),
                        font_consistency=f.get("font_consistency", 100),
                        verdict="Clean" if not flags else "Attention", flags=flags))
    return out
