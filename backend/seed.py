"""Synthetic demo data for the Credit Intelligence OS. All names/figures are fictional."""
import random, datetime as dt

random.seed(7)

TODAY = dt.date(2024, 4, 16)

BRANCHES = ["Makati", "Cebu", "Davao"]
PRODUCTS = {
    "Personal Loan":  {"max": 60000,  "min_tenure_m": 6,  "max_dti": 40, "rate": 12.5, "max_term": 60,
                       "docs": ["Government ID", "Payslip", "Bank Statement", "Employment Letter", "Salary Deduction", "Payment History"]},
    "Auto Loan":      {"max": 90000,  "min_tenure_m": 12, "max_dti": 42, "rate": 9.8,  "max_term": 84,
                       "docs": ["Government ID", "Payslip", "Bank Statement", "Employment Letter", "Vehicle Quote", "Payment History"]},
    "Car Loan":       {"max": 90000,  "min_tenure_m": 12, "max_dti": 42, "rate": 9.8,  "max_term": 84,
                       "docs": ["Government ID", "Payslip", "Bank Statement", "Employment Letter", "Vehicle Quote", "Payment History"]},
    "Business Loan":  {"max": 150000, "min_tenure_m": 24, "max_dti": 45, "rate": 14.0, "max_term": 60,
                       "docs": ["Government ID", "Business Permit", "Income Statement", "Bank Statement", "Tax Return", "Equipment Quote"]},
    "Home Loan":      {"max": 400000, "min_tenure_m": 24, "max_dti": 38, "rate": 7.4,  "max_term": 240,
                       "docs": ["Government ID", "Payslip", "Bank Statement", "Employment Letter", "Property Valuation", "Tax Return"]},
    "Education Loan": {"max": 40000,  "min_tenure_m": 6,  "max_dti": 40, "rate": 8.5,  "max_term": 72,
                       "docs": ["Government ID", "Payslip", "Bank Statement", "Enrollment Letter", "Employment Letter", "Payment History"]},
}

# ---------------------------------------------------------------- members
def _month_starts(n):
    """The n consecutive month-5ths ending with the current month."""
    months = []
    y, m = TODAY.year, TODAY.month
    for _ in range(n):
        months.append(dt.date(y, m, 5))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(months))


def _payments(pattern, n=18):
    """Return list of {month, days_late, amount_due, amount_paid, channel}."""
    out = []
    for i, m in enumerate(_month_starts(n)):
        late = pattern(i, n)
        out.append({
            "month": m.isoformat(),
            "days_late": late,
            "amount_due": 650,
            "amount_paid": 650 if late < 25 else 0,
            "channel": "Salary Deduction" if i % 7 != 6 else "Bank Transfer",
        })
    return out

def _drift(i, n):           # perfect payer that starts slipping
    if i < n - 4: return 0
    return [0, 3, 8, 11][max(0, i - (n - 4))]
def _stable(i, n):  return 0 if i % 9 else 1
def _bad(i, n):     return 0 if i < n - 6 else min(120, 10 * (i - (n - 7)) + 20)
def _recovering(i, n):
    if i < n - 7: return 0
    seq = [14, 22, 9, 2, 0, 0, 0]
    return seq[min(len(seq) - 1, i - (n - 7))]

MEMBERS = [
    dict(id="104328", name="David Carter", initials="DC", since="2020-03-01", branch="Makati",
         savings=12420, share_capital=8200, outstanding=18250, prior_loans=3, reliability=96,
         dti=28, employer="TechCorp Inc.", employment="Employed", tenure_years=6,
         declared_income=52000, payslip_income=43000, bank_income=45200, deduction=620,
         email="d.carter@example.com", phone="+63 917 555 0134", state="ELEVATED",
         pattern=_drift, savings_trend=[1200,1250,1300,1310,1290,1330,1350,1360,1380,1400,1410,1380,1300,1150,980,860]),
    dict(id="104188", name="Maria Torres", initials="MT", since="2019-07-14", branch="Makati",
         savings=24100, share_capital=15400, outstanding=32000, prior_loans=2, reliability=93,
         dti=32, employer="Torres Catering (self)", employment="Self-Employed", tenure_years=5,
         declared_income=65000, payslip_income=0, bank_income=62000, deduction=0,
         email="m.torres@example.com", phone="+63 918 555 0198", state="STABLE",
         pattern=_stable, savings_trend=[2000]*10+[2100,2050,2200,2150,2300,2250]),
    dict(id="104265", name="Sarah Lim", initials="SL", since="2023-11-02", branch="Cebu",
         savings=1450, share_capital=900, outstanding=0, prior_loans=0, reliability=0,
         dti=46, employer="Bright Retail Co.", employment="Employed", tenure_years=1,
         declared_income=39000, payslip_income=38400, bank_income=28700, deduction=0,
         email="s.lim@example.com", phone="+63 919 555 0112", state="WATCH",
         pattern=_stable, savings_trend=[300,280,260,255,240,220,200,190,180,160,150,140,130,120,110,90]),
    dict(id="104241", name="Daniel Brooks", initials="DB", since="2018-01-20", branch="Davao",
         savings=18900, share_capital=11200, outstanding=41500, prior_loans=4, reliability=88,
         dti=39, employer="Brooks Logistics", employment="Self-Employed", tenure_years=8,
         declared_income=97000, payslip_income=0, bank_income=91800, deduction=0,
         email="d.brooks@example.com", phone="+63 917 555 0177", state="ELEVATED",
         pattern=_recovering, savings_trend=[1600,1580,1550,1500,1450,1400,1350,1300,1250,1200,1180,1150,1200,1300,1420,1500]),
    dict(id="104172", name="James Lee", initials="JL", since="2016-05-09", branch="Cebu",
         savings=41200, share_capital=22800, outstanding=9800, prior_loans=5, reliability=99,
         dti=26, employer="Northwind Systems", employment="Employed", tenure_years=9,
         declared_income=83000, payslip_income=82400, bank_income=82400, deduction=1100,
         email="j.lee@example.com", phone="+63 917 555 0155", state="STABLE",
         pattern=_stable, savings_trend=[3400]*8+[3500,3520,3600,3650,3700,3720,3800,3850]),
    dict(id="104310", name="Robert James", initials="RJ", since="2022-02-11", branch="Davao",
         savings=2100, share_capital=1400, outstanding=14200, prior_loans=1, reliability=71,
         dti=48, employer="Delta Freight", employment="Employed", tenure_years=2,
         declared_income=41000, payslip_income=40200, bank_income=32600, deduction=310,
         email="r.james@example.com", phone="+63 918 555 0165", state="AT_RISK",
         pattern=_bad, savings_trend=[500,480,460,430,400,380,340,300,280,240,210,180,150,120,90,60]),
    dict(id="104233", name="Elena Garcia", initials="EG", since="2017-09-30", branch="Makati",
         savings=33800, share_capital=19600, outstanding=4300, prior_loans=4, reliability=98,
         dti=24, employer="Garcia Dental Group", employment="Employed", tenure_years=7,
         declared_income=78000, payslip_income=77600, bank_income=77600, deduction=980,
         email="e.garcia@example.com", phone="+63 917 555 0188", state="STABLE",
         pattern=_stable, savings_trend=[2800]*16),
    dict(id="104298", name="Mei Ying", initials="MY", since="2021-06-18", branch="Makati",
         savings=8600, share_capital=5200, outstanding=6100, prior_loans=1, reliability=94,
         dti=31, employer="Lumen Analytics", employment="Employed", tenure_years=3,
         declared_income=48000, payslip_income=47600, bank_income=47600, deduction=540,
         email="m.ying@example.com", phone="+63 919 555 0121", state="STABLE",
         pattern=_stable, savings_trend=[900,910,920,930,940,950,960,970,980,990,1000,1010,1020,1030,1040,1050]),
    dict(id="104291", name="Siti Khadijah", initials="SK", since="2021-12-04", branch="Cebu",
         savings=5300, share_capital=3100, outstanding=3900, prior_loans=1, reliability=90,
         dti=35, employer="Harborline Retail", employment="Employed", tenure_years=3,
         declared_income=36000, payslip_income=35800, bank_income=35800, deduction=430,
         email="s.khadijah@example.com", phone="+63 918 555 0143", state="WATCH",
         pattern=_stable, savings_trend=[600,590,580,570,560,540,530,520,500,490,470,460,450,430,420,410]),
    dict(id="104276", name="Antonio Cruz", initials="AC", since="2015-08-25", branch="Makati",
         savings=68400, share_capital=39200, outstanding=52000, prior_loans=6, reliability=97,
         dti=29, employer="Cruz & Partners", employment="Employed", tenure_years=11,
         declared_income=135000, payslip_income=134800, bank_income=134800, deduction=2200,
         email="a.cruz@example.com", phone="+63 917 555 0190", state="STABLE",
         pattern=_stable, savings_trend=[5400]*16),
    dict(id="104201", name="Kevin Wu", initials="KW", since="2022-10-10", branch="Cebu",
         savings=3900, share_capital=2400, outstanding=2200, prior_loans=1, reliability=92,
         dti=33, employer="Wu Interiors", employment="Employed", tenure_years=2,
         declared_income=42000, payslip_income=40500, bank_income=40500, deduction=470,
         email="k.wu@example.com", phone="+63 919 555 0176", state="STABLE",
         pattern=_stable, savings_trend=[420,430,440,430,450,460,455,470,480,470,490,500,495,505,510,520]),
    dict(id="104317", name="Lisa Tan", initials="LT", since="2020-09-02", branch="Cebu",
         savings=15600, share_capital=9100, outstanding=21400, prior_loans=2, reliability=91,
         dti=37, employer="Tan Media House", employment="Employed", tenure_years=4,
         declared_income=69000, payslip_income=68800, bank_income=68800, deduction=820,
         email="l.tan@example.com", phone="+63 917 555 0129", state="STABLE",
         pattern=_stable, savings_trend=[1300,1320,1310,1340,1350,1330,1360,1380,1370,1390,1400,1420,1410,1430,1440,1450]),
]

def members():
    out = []
    for m in MEMBERS:
        d = {k: v for k, v in m.items() if k != "pattern"}
        d["payments"] = _payments(m["pattern"])
        out.append(d)
    return out

# ------------------------------------------------------------ applications
APPLICATIONS = [
    dict(id="APP-104328", member_id="104328", product="Personal Loan", amount=25000, term=36,
         purpose="Home improvement", submitted="2024-04-15T10:24:00", branch="Makati",
         status="Officer Review", officer="Sarah Kim", channel="Branch",
         guarantor=None, existing_commitments=450, case_type="origination"),
    dict(id="APP-104188", member_id="104188", product="Business Loan", amount=50000, term=48,
         purpose="Kitchen equipment expansion", submitted="2024-04-10T08:20:00", branch="Makati",
         status="Documents Pending", officer="Sarah Kim", channel="Online",
         guarantor="Antonio Cruz", existing_commitments=600, case_type="origination"),
    dict(id="APP-104172", member_id="104172", product="Auto Loan", amount=28000, term=60,
         purpose="Vehicle purchase", submitted="2024-04-10T04:10:00", branch="Cebu",
         status="Ready to Approve", officer="Marco Diaz", channel="Online",
         guarantor=None, existing_commitments=420, case_type="origination"),
    dict(id="APP-104265", member_id="104265", product="Personal Loan", amount=10000, term=24,
         purpose="Debt consolidation", submitted="2024-04-13T09:05:00", branch="Cebu",
         status="Fraud Review", officer="Marco Diaz", channel="Online",
         guarantor=None, existing_commitments=450, case_type="origination"),
    dict(id="APP-104241", member_id="104241", product="Business Loan", amount=75000, term=60,
         purpose="Fleet refinancing", submitted="2024-04-12T14:40:00", branch="Davao",
         status="Risk Review", officer="Aisha Rahman", channel="Branch",
         guarantor="Elena Garcia", existing_commitments=900, case_type="origination"),
    dict(id="APP-104310", member_id="104310", product="Personal Loan", amount=15000, term=36,
         purpose="Medical expenses", submitted="2024-04-14T11:15:00", branch="Davao",
         status="Enhanced Review", officer="Aisha Rahman", channel="Branch",
         guarantor=None, existing_commitments=1520, case_type="origination"),
    dict(id="APP-104233", member_id="104233", product="Auto Loan", amount=22000, term=48,
         purpose="Vehicle purchase", submitted="2024-04-12T06:00:00", branch="Makati",
         status="Ready to Approve", officer="Sarah Kim", channel="Online",
         guarantor=None, existing_commitments=310, case_type="origination"),
    dict(id="APP-104298", member_id="104298", product="Education Loan", amount=18000, term=48,
         purpose="Postgraduate tuition", submitted="2024-04-14T13:30:00", branch="Makati",
         status="In Verification", officer="Sarah Kim", channel="Online",
         guarantor=None, existing_commitments=640, case_type="origination"),
    dict(id="APP-104291", member_id="104291", product="Personal Loan", amount=10000, term=24,
         purpose="Family emergency", submitted="2024-04-14T16:05:00", branch="Cebu",
         status="Documents Pending", officer="Marco Diaz", channel="Branch",
         guarantor=None, existing_commitments=720, case_type="origination"),
    dict(id="APP-104276", member_id="104276", product="Home Loan", amount=120000, term=180,
         purpose="Property purchase", submitted="2024-04-13T09:45:00", branch="Makati",
         status="Credit Analysis", officer="Aisha Rahman", channel="Branch",
         guarantor=None, existing_commitments=2900, case_type="origination"),
    dict(id="APP-104201", member_id="104201", product="Personal Loan", amount=8500, term=24,
         purpose="Working capital", submitted="2024-04-11T15:20:00", branch="Cebu",
         status="Officer Review", officer="Marco Diaz", channel="Online",
         guarantor=None, existing_commitments=560, case_type="origination"),
    dict(id="APP-104317", member_id="104317", product="Car Loan", amount=32000, term=60,
         purpose="Vehicle purchase", submitted="2024-04-15T07:00:00", branch="Cebu",
         status="Documents Pending", officer="Marco Diaz", channel="Online",
         guarantor=None, existing_commitments=1180, case_type="origination"),
]

# -------------------------------------------------------------- documents
# bbox = [x, y, w, h] as % of page — drives evidence highlighting in the viewer
DOCUMENTS = [
    dict(id="DOC-1001", app_id="APP-104328", member_id="104328", file="payslip_david_carter_mar_2024.pdf",
         label="payslip_mar2024.pdf", doc_type="Payslip", status="Verified", confidence=98,
         uploaded="2024-04-15T10:24:00", pages=1,
         forensics=dict(tampering=False, font_consistency=99, metadata_ok=True, duplicate_hash=False, producer="Payroll Suite 4.2"),
         fields=[
            dict(k="Employee Name", v="David Carter", c=98, bbox=[8, 22, 40, 5], page=1),
            dict(k="Employer", v="TechCorp Inc.", c=96, bbox=[8, 12, 44, 6], page=1),
            dict(k="Pay Period", v="March 2024", c=99, bbox=[58, 22, 34, 5], page=1),
            dict(k="Gross Monthly", v="$4,333", c=97, bbox=[8, 46, 60, 6], page=1),
            dict(k="Net Monthly", v="$3,583", c=98, bbox=[8, 58, 60, 6], page=1),
            dict(k="Salary Deduction (Coop)", v="$620", c=99, bbox=[8, 68, 60, 5], page=1),
            dict(k="Annualised Net", v="$43,000", c=97, bbox=[8, 78, 60, 5], page=1)]),
    dict(id="DOC-1002", app_id="APP-104328", member_id="104328", file="bank_statement_david_carter_q1_2024.pdf",
         label="bank_statement_q1.pdf", doc_type="Bank Statement", status="Verified", confidence=96,
         uploaded="2024-04-15T10:25:00", pages=1,
         forensics=dict(tampering=False, font_consistency=97, metadata_ok=True, duplicate_hash=False, producer="CoreBank Export"),
         fields=[
            dict(k="Account Holder", v="David Carter", c=98, bbox=[8, 14, 44, 5], page=1),
            dict(k="Account Number", v="****4821", c=99, bbox=[58, 14, 34, 5], page=1),
            dict(k="Avg Monthly Credit", v="$3,766", c=94, bbox=[8, 42, 62, 6], page=1),
            dict(k="Annualised Deposits", v="$45,200", c=95, bbox=[8, 52, 62, 6], page=1),
            dict(k="Recurring Debits", v="$1,100", c=93, bbox=[8, 62, 62, 6], page=1),
            dict(k="Lowest Balance", v="$412", c=92, bbox=[8, 72, 62, 5], page=1),
            dict(k="NSF Events (90d)", v="0", c=99, bbox=[8, 82, 62, 5], page=1)]),
    dict(id="DOC-1003", app_id="APP-104328", member_id="104328", file="employment_letter_david_carter.pdf",
         label="employment_letter.pdf", doc_type="Employment Letter", status="Verified", confidence=97,
         uploaded="2024-04-15T10:27:00", pages=1,
         forensics=dict(tampering=False, font_consistency=98, metadata_ok=True, duplicate_hash=False, producer="Word"),
         fields=[
            dict(k="Employee Name", v="David Carter", c=98, bbox=[8, 26, 44, 5], page=1),
            dict(k="Employer", v="TechCorp Inc.", c=97, bbox=[8, 12, 44, 6], page=1),
            dict(k="Position", v="Senior Systems Engineer", c=95, bbox=[8, 36, 56, 5], page=1),
            dict(k="Employment Status", v="Employed — Permanent", c=97, bbox=[8, 46, 56, 5], page=1),
            dict(k="Start Date", v="2018-02-01", c=96, bbox=[8, 56, 40, 5], page=1)]),
    dict(id="DOC-1004", app_id="APP-104328", member_id="104328", file="national_id_david_carter.png",
         label="national_id.png", doc_type="Government ID", status="Verified", confidence=99,
         uploaded="2024-04-15T10:30:00", pages=1,
         forensics=dict(tampering=False, font_consistency=99, metadata_ok=True, duplicate_hash=False, producer="Scanner"),
         fields=[
            dict(k="Full Name", v="David Carter", c=99, bbox=[34, 30, 50, 10], page=1),
            dict(k="ID Number", v="NID-8842-1190", c=98, bbox=[34, 44, 50, 9], page=1),
            dict(k="Date of Birth", v="1988-06-12", c=97, bbox=[34, 58, 40, 9], page=1),
            dict(k="Expiry", v="2029-06-11", c=98, bbox=[34, 72, 40, 9], page=1)]),
    dict(id="DOC-1005", app_id="APP-104328", member_id="104328", file="salary_deduction_david_carter.csv",
         label="salary_deduction_march.csv", doc_type="Salary Deduction", status="Verified", confidence=100,
         uploaded="2024-04-15T10:32:00", pages=1,
         forensics=dict(tampering=False, font_consistency=100, metadata_ok=True, duplicate_hash=False, producer="HR Feed"),
         fields=[
            dict(k="Member", v="David Carter", c=100, bbox=[4, 10, 40, 6], page=1),
            dict(k="Deduction Amount", v="$620", c=100, bbox=[4, 22, 40, 6], page=1),
            dict(k="Remittance Regularity", v="2 delays in last 2 cycles", c=100, bbox=[4, 34, 62, 6], page=1)]),
    dict(id="DOC-1006", app_id="APP-104328", member_id="104328", file="member_payment_history_david_carter.csv",
         label="payment_history.csv", doc_type="Payment History", status="Verified", confidence=100,
         uploaded="2024-04-15T10:33:00", pages=1,
         forensics=dict(tampering=False, font_consistency=100, metadata_ok=True, duplicate_hash=False, producer="Core System"),
         fields=[
            dict(k="Records", v="16 months", c=100, bbox=[4, 10, 40, 6], page=1),
            dict(k="On-time Rate", v="87.5%", c=100, bbox=[4, 22, 40, 6], page=1),
            dict(k="Max Days Late", v="8", c=100, bbox=[4, 34, 40, 6], page=1)]),
    dict(id="DOC-1007", app_id="APP-104188", member_id="104188", file="business_permit_maria_torres.pdf",
         label="business_permit.pdf", doc_type="Business Permit", status="Verified", confidence=97,
         uploaded="2024-04-10T08:25:00", pages=1,
         forensics=dict(tampering=False, font_consistency=96, metadata_ok=True, duplicate_hash=False, producer="LGU Portal"),
         fields=[
            dict(k="Business Name", v="Torres Catering Services", c=97, bbox=[8, 20, 56, 6], page=1),
            dict(k="Owner", v="Maria Torres", c=98, bbox=[8, 32, 44, 5], page=1),
            dict(k="Permit Number", v="BP-2024-77410", c=96, bbox=[8, 44, 44, 5], page=1),
            dict(k="Valid Until", v="2024-12-31", c=97, bbox=[8, 56, 40, 5], page=1)]),
    dict(id="DOC-1008", app_id="APP-104188", member_id="104188", file="income_statement_maria_torres_q1.pdf",
         label="income_statement_q1.pdf", doc_type="Income Statement", status="Needs Review", confidence=92,
         uploaded="2024-04-10T08:27:00", pages=1,
         forensics=dict(tampering=False, font_consistency=88, metadata_ok=True, duplicate_hash=False, producer="Excel"),
         fields=[
            dict(k="Entity", v="Torres Catering Services", c=95, bbox=[8, 16, 56, 6], page=1),
            dict(k="Period", v="Q1 2024", c=97, bbox=[64, 16, 28, 6], page=1),
            dict(k="Revenue", v="$41,200", c=93, bbox=[8, 40, 60, 6], page=1),
            dict(k="Net Income", v="$15,500", c=88, bbox=[8, 52, 60, 6], page=1),
            dict(k="Annualised Net", v="$62,000", c=86, bbox=[8, 64, 60, 6], page=1)]),
]

REQUIRED_BY_APP = {
    "APP-104328": ["Government ID", "Payslip", "Bank Statement", "Employment Letter", "Salary Deduction", "Payment History"],
    "APP-104188": ["Government ID", "Business Permit", "Income Statement", "Bank Statement", "Tax Return", "Equipment Quote"],
}

# ------------------------------------------------------------- collections
COLLECTIONS = [
    dict(id="COL-1001", member_id="104310", balance=4850, dpd=120, response=72, priority="P1",
         last_payment="2024-01-12", intervention="Phone call + hardship options", promise=None,
         expected_value=3492, stage="Late Stage"),
    dict(id="COL-1002", member_id="104291", balance=2340, dpd=90, response=65, priority="P1",
         last_payment="2024-01-30", intervention="SMS with payment link", promise="2024-04-26",
         expected_value=1521, stage="Mid Stage"),
    dict(id="COL-1003", member_id="104201", balance=1920, dpd=60, response=58, priority="P2",
         last_payment="2024-02-18", intervention="Call + refinance review", promise=None,
         expected_value=1113, stage="Mid Stage"),
    dict(id="COL-1004", member_id="104241", balance=3600, dpd=45, response=66, priority="P2",
         last_payment="2024-03-02", intervention="Offer hardship options", promise=None,
         expected_value=2376, stage="Early Stage"),
    dict(id="COL-1005", member_id="104317", balance=980, dpd=30, response=49, priority="P3",
         last_payment="2024-03-12", intervention="SMS + financial education", promise=None,
         expected_value=480, stage="Early Stage"),
    dict(id="COL-1006", member_id="104328", balance=5200, dpd=0, response=71, priority="P1",
         last_payment="2024-04-08", intervention="Proactive supportive outreach", promise=None,
         expected_value=3692, stage="Pre-Delinquency"),
]

COMMS = [
    dict(member_id="104310", type="call", title="Outbound Call", at="2024-04-24T10:15:00",
         text="Spoke with member. Discussed past-due balance and hardship options. Member requested time to review.", outcome="Contacted"),
    dict(member_id="104310", type="sms", title="SMS Sent", at="2024-04-20T14:03:00",
         text="Sent payment link and account summary.", outcome="Delivered"),
    dict(member_id="104291", type="promise", title="Promise to Pay", at="2024-04-12T11:20:00",
         text="Member promised $300 payment on Apr 26, 2024.", outcome="Open"),
    dict(member_id="104310", type="call", title="Outbound Call", at="2024-04-05T16:10:00",
         text="Left voicemail. No response.", outcome="No Answer"),
    dict(member_id="104328", type="email", title="Payment Reminder", at="2024-04-02T09:00:00",
         text="Standard reminder sent ahead of due date.", outcome="Opened"),
]

TREND = [
    {"d": "Apr 1", "a": 13, "ap": 10, "de": 4}, {"d": "Apr 2", "a": 15, "ap": 11, "de": 5},
    {"d": "Apr 3", "a": 14, "ap": 10, "de": 4}, {"d": "Apr 4", "a": 13, "ap": 9, "de": 5},
    {"d": "Apr 5", "a": 18, "ap": 13, "de": 5}, {"d": "Apr 6", "a": 20, "ap": 14, "de": 6},
    {"d": "Apr 7", "a": 17, "ap": 12, "de": 5}, {"d": "Apr 8", "a": 23, "ap": 16, "de": 7},
    {"d": "Apr 9", "a": 28, "ap": 22, "de": 6}, {"d": "Apr 10", "a": 20, "ap": 16, "de": 4},
    {"d": "Apr 11", "a": 18, "ap": 13, "de": 5}, {"d": "Apr 12", "a": 17, "ap": 12, "de": 5},
    {"d": "Apr 13", "a": 19, "ap": 14, "de": 5}, {"d": "Apr 14", "a": 25, "ap": 18, "de": 7},
    {"d": "Apr 15", "a": 28, "ap": 20, "de": 7}, {"d": "Apr 16", "a": 24, "ap": 17, "de": 6},
]

POLICY_LIBRARY = [
    dict(id="POL-001", version="v3.4", title="Affordability — Debt Service Ratio",
         text="Total monthly obligations including the proposed instalment must not exceed the product DSR ceiling of the member's verified net monthly income. Personal Loan ceiling 40%, Auto/Car 42%, Business 45%, Home 38%, Education 40%."),
    dict(id="POL-002", version="v3.4", title="Membership Tenure",
         text="Minimum membership tenure applies per product: 6 months for Personal and Education, 12 months for Auto/Car, 24 months for Business and Home."),
    dict(id="POL-003", version="v3.4", title="Income Verification Variance",
         text="Where verified bank deposits differ from declared income by more than 10%, the lower verified figure is used for affordability and the case must be routed to officer review with the variance disclosed."),
    dict(id="POL-004", version="v3.4", title="Exposure Limit",
         text="Aggregate member exposure may not exceed 4x share capital plus savings without senior officer approval."),
    dict(id="POL-005", version="v3.4", title="Officer Authority Bands",
         text="Officer authority up to $30,000. Senior officer up to $100,000. Credit committee above $100,000. Autonomous execution only within the Board-set Autonomy Dial limits."),
    dict(id="POL-006", version="v3.4", title="Fraud Escalation",
         text="A high anomaly score is an investigation signal, not a finding of fraud. Cases with critical integrity signals route to Fraud Review and may not be auto-executed."),
    dict(id="POL-007", version="v3.4", title="Hardship and Forbearance",
         text="Members exhibiting early-warning deterioration should receive the least intrusive effective intervention. Supportive outreach precedes formal collections where prior conduct was good."),
    dict(id="POL-008", version="v3.4", title="Document Requirements",
         text="Each product defines a mandatory evidence set. A case may not be approved with mandatory evidence missing unless a documented exception is recorded by a senior officer."),
]


# ---------------------------------------------------- generated evidence
# Every other case gets a plausible evidence set so queues, reconciliation and
# the policy sandbox all behave realistically. The underlying artifacts are the
# same synthetic demo files; the extracted values come from the member record.
_FILE_FOR = {
    "Payslip": "payslip_david_carter_mar_2024.pdf",
    "Bank Statement": "bank_statement_david_carter_q1_2024.pdf",
    "Employment Letter": "employment_letter_david_carter.pdf",
    "Government ID": "national_id_david_carter.png",
    "Salary Deduction": "salary_deduction_david_carter.csv",
    "Payment History": "member_payment_history_david_carter.csv",
    "Business Permit": "business_permit_maria_torres.pdf",
    "Income Statement": "income_statement_maria_torres_q1.pdf",
    "Tax Return": "income_statement_maria_torres_q1.pdf",
    "Equipment Quote": "business_permit_maria_torres.pdf",
    "Vehicle Quote": "business_permit_maria_torres.pdf",
    "Property Valuation": "business_permit_maria_torres.pdf",
    "Enrollment Letter": "employment_letter_david_carter.pdf",
}
# cases that are deliberately still waiting on evidence
_MISSING = {
    "APP-104317": ["Vehicle Quote", "Employment Letter"],
    "APP-104291": ["Bank Statement", "Payment History"],
    "APP-104241": ["Tax Return"],
    "APP-104265": ["Employment Letter", "Payment History"],
    "APP-104201": ["Payment History"],
}


def _fields_for(kind, m, app, y):
    net = (m["payslip_income"] or m["bank_income"] or m["declared_income"])
    bank = m["bank_income"] or m["declared_income"]
    F = lambda k, v, c, i: dict(k=k, v=v, c=c, bbox=[8, 20 + 10 * i, 60, 5], page=1)
    if kind == "Payslip":
        return [F("Employee Name", m["name"], 98, 0), F("Employer", m["employer"], 96, 1),
                F("Pay Period", "March 2024", 99, 2), F("Gross Monthly", f"${net/12*1.21:,.0f}", 96, 3),
                F("Net Monthly", f"${net/12:,.0f}", 97, 4),
                F("Salary Deduction (Coop)", f"${m['deduction']:,.0f}", 98, 5),
                F("Annualised Net", f"${net:,.0f}", 97, 6)]
    if kind == "Bank Statement":
        return [F("Account Holder", m["name"], 98, 0), F("Account Number", f"****{m['id'][-4:]}", 99, 1),
                F("Avg Monthly Credit", f"${bank/12:,.0f}", 94, 2),
                F("Annualised Deposits", f"${bank:,.0f}", 95, 3),
                F("Recurring Debits", f"${app['existing_commitments']:,.0f}", 93, 4),
                F("NSF Events (90d)", "0" if m["reliability"] >= 90 else "2", 99, 5)]
    if kind == "Employment Letter":
        return [F("Employee Name", m["name"], 98, 0), F("Employer", m["employer"], 97, 1),
                F("Employment Status", f"{m['employment']} — Permanent", 96, 2),
                F("Start Date", f"{2024 - m['tenure_years']}-02-01", 95, 3)]
    if kind == "Government ID":
        return [F("Full Name", m["name"], 99, 0), F("ID Number", f"NID-{m['id']}-01", 98, 1),
                F("Expiry", "2029-06-11", 98, 2)]
    if kind == "Salary Deduction":
        return [F("Member", m["name"], 100, 0), F("Deduction Amount", f"${m['deduction']:,.0f}", 100, 1),
                F("Remittance Regularity", "Regular", 100, 2)]
    if kind == "Payment History":
        return [F("Records", "18 months", 100, 0), F("On-time Rate", f"{m['reliability']}%", 100, 1)]
    if kind in ("Income Statement", "Tax Return"):
        return [F("Entity", m["employer"], 95, 0), F("Period", "FY2023", 97, 1),
                F("Annualised Net", f"${bank:,.0f}", 90, 2)]
    return [F("Document", kind, 92, 0), F("Reference", f"REF-{app['id'][-6:]}", 90, 1),
            F("Applicant", m["name"], 95, 2)]


def generated_documents(members_by_id):
    out, n = [], 2000
    hand = {d["app_id"] for d in DOCUMENTS}
    for app in APPLICATIONS:
        if app["id"] in hand:
            continue
        m = members_by_id[app["member_id"]]
        missing = _MISSING.get(app["id"], [])
        for kind in PRODUCTS[app["product"]]["docs"]:
            if kind in missing:
                continue
            n += 1
            conf = 97 if m["reliability"] >= 90 else 94
            out.append(dict(
                id=f"DOC-{n}", app_id=app["id"], member_id=m["id"], file=_FILE_FOR.get(kind, _FILE_FOR["Government ID"]),
                label=f"{kind.lower().replace(' ', '_')}_{m['name'].split()[-1].lower()}.pdf",
                doc_type=kind, status="Verified" if conf >= 94 else "Needs Review", confidence=conf,
                uploaded=app["submitted"], pages=1,
                forensics=dict(tampering=False, font_consistency=97 if conf >= 94 else 90,
                               metadata_ok=True, duplicate_hash=False, producer="Member upload"),
                fields=_fields_for(kind, m, app, 0)))
    return out
