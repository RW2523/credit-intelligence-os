"""Synthetic demo data for KT Credit Intelligence — Koperasi Tentera (Koperasi Angkatan Tentera
Malaysia Berhad). Every person, figure and document here is fictional and generated; branch names
and product names follow KT's public information. Amounts are Ringgit Malaysia, dates are laid out
relative to the demo day (clock.TODAY) and every timestamp is Malaysia time (UTC+8).
"""
from __future__ import annotations
import random, datetime as dt
from clock import TODAY, at, add_months, months_between

INSTITUTION = "Koperasi Angkatan Tentera Malaysia Berhad"
SHORT_NAME = "Koperasi Tentera"
DEDUCTION_CAP_PCT = 60          # government rule: total salary deductions <= 60% of gross pay
MIN_GROSS_SALARY = 2000         # KT personal financing eligibility
PAYDAY = 25                     # salary-deduction (Biro ANGKASA) remittance day

# ---------------------------------------------------------------- branches
BRANCH_INFO = {
    "Kuala Lumpur": dict(code="KUL", name="Cawangan Utama Kuala Lumpur",
                         address="Pusat Bandar Wangsa Maju, 53300 Kuala Lumpur", state="W.P. Kuala Lumpur"),
    "Sungai Besi": dict(code="SGB", name="Kiosk Kem KEMENTAH, Sungai Besi",
                        address="Medan Niaga Tasik Damai, 57000 Sungai Besi", state="W.P. Kuala Lumpur"),
    "Lumut": dict(code="LMT", name="Cawangan Lumut",
                  address="Persiaran Sultan Yusuf Izzudin Shah, 32200 Lumut", state="Perak"),
    "Kuantan": dict(code="KTN", name="Cawangan Kuantan",
                    address="Perkampungan Seri Damai Aman, 25150 Kuantan", state="Pahang"),
    "Kota Kinabalu": dict(code="BKI", name="Cawangan Kota Kinabalu",
                          address="Putatan Platinum Plaza, 88200 Kota Kinabalu", state="Sabah"),
    "Kok Lanas": dict(code="KLN", name="Cawangan Kem Desa Pahlawan",
                      address="Kem Desa Pahlawan, 16500 Kok Lanas", state="Kelantan"),
}
BRANCHES = list(BRANCH_INFO)

# ---------------------------------------------------------------- products
# Profit rates are FLAT per annum (the convention for cooperative personal financing in Malaysia).
# Figures are illustrative placeholders until KT confirms its current terms.
_SAL = ["Identity Card", "Payslip", "Bank Statement", "Service Confirmation", "Salary Deduction Mandate",
        "Payment History"]
PRODUCTS = {
    "Personal Financing-i": dict(
        code="PF-i", ms="Pembiayaan Peribadi-i", kind="financing", contract="Tawarruq",
        min=1000, max=200000, min_term=6, max_term=120, rate=3.65, max_dti=40, min_tenure_m=6,
        salary_deduction=True, docs=_SAL,
        desc="General-purpose financing repaid by salary or pension deduction."),
    "Express Financing-i": dict(
        code="EF-i", ms="Pembiayaan Ekspres-i", kind="financing", contract="Tawarruq",
        min=1000, max=20000, min_term=6, max_term=36, rate=4.50, max_dti=40, min_tenure_m=6,
        salary_deduction=True, docs=["Identity Card", "Payslip", "Salary Deduction Mandate", "Payment History"],
        desc="Fast, smaller financing for urgent needs with a reduced evidence set."),
    "Fees Financing-i": dict(
        code="FF-i", ms="Pembiayaan Yuran-i", kind="financing", contract="Tawarruq",
        min=1000, max=50000, min_term=6, max_term=60, rate=3.90, max_dti=40, min_tenure_m=6,
        salary_deduction=True,
        docs=["Identity Card", "Payslip", "Bank Statement", "Fee Statement", "Salary Deduction Mandate"],
        desc="Education fees for the member or dependants."),
    "Term Financing-i": dict(
        code="TF-i", ms="Pembiayaan Berjangka-i", kind="financing", contract="Tawarruq",
        min=5000, max=150000, min_term=12, max_term=120, rate=4.20, max_dti=40, min_tenure_m=12,
        salary_deduction=True,
        docs=["Identity Card", "Payslip", "Bank Statement", "Service Confirmation", "Quotation",
              "Salary Deduction Mandate"],
        desc="Longer-tenure financing for a defined purchase such as a vehicle."),
    "SME Financing-i": dict(
        code="SME-i", ms="Pembiayaan PKS-i", kind="financing", contract="Murabahah",
        min=10000, max=300000, min_term=12, max_term=84, rate=5.00, max_dti=45, min_tenure_m=24,
        salary_deduction=False,
        docs=["Identity Card", "SSM Registration", "Income Statement", "Bank Statement", "Tax Return",
              "Quotation"],
        desc="Working capital and equipment for member-owned small businesses."),
    "Contract Financing-i": dict(
        code="CF-i", ms="Pembiayaan Kontrak-i", kind="financing", contract="Murabahah",
        min=10000, max=500000, min_term=3, max_term=36, rate=5.50, max_dti=45, min_tenure_m=24,
        salary_deduction=False,
        docs=["Identity Card", "SSM Registration", "Contract Award Letter", "Bank Statement",
              "Income Statement", "Tax Return"],
        desc="Financing to perform an awarded contract, repaid from contract proceeds."),
    "Ar-Rahnu KT": dict(
        code="AR", ms="Ar-Rahnu KT", kind="rahnu", contract="Qard + Rahn + Ujrah",
        min=100, max=100000, min_term=6, max_term=6, rate=0.0, max_dti=None, min_tenure_m=0,
        salary_deduction=False, docs=["Identity Card"], margin=70,
        desc="Shariah-compliant pawn: cash against gold, up to 70% of the gold's value, renewable."),
    "Motor Takaful": dict(
        code="MT", ms="Takaful Motor", kind="takaful", contract="Wakalah",
        min=0, max=0, min_term=12, max_term=12, rate=0.0, max_dti=None, min_tenure_m=0,
        salary_deduction=False, docs=["Identity Card"],
        desc="Motor cover; contributions can be deducted from salary."),
    "General Takaful": dict(
        code="GT", ms="Takaful Am", kind="takaful", contract="Wakalah",
        min=0, max=0, min_term=12, max_term=12, rate=0.0, max_dti=None, min_tenure_m=0,
        salary_deduction=False, docs=["Identity Card"],
        desc="Household and personal-accident cover."),
}
FINANCING = [k for k, v in PRODUCTS.items() if v["kind"] == "financing"]
CODE = {v["code"]: k for k, v in PRODUCTS.items()}

DOC_MS = {
    "Identity Card": "Kad Pengenalan", "Payslip": "Slip Gaji", "Pension Slip": "Slip Pencen",
    "Bank Statement": "Penyata Bank", "Service Confirmation": "Surat Pengesahan Perkhidmatan",
    "Salary Deduction Mandate": "Jadual Potongan Gaji (ANGKASA)", "Payment History": "Sejarah Bayaran",
    "SSM Registration": "Sijil Pendaftaran SSM", "Income Statement": "Penyata Pendapatan",
    "Tax Return": "Borang B (LHDN)", "Quotation": "Sebut Harga", "Fee Statement": "Penyata Yuran",
    "Contract Award Letter": "Surat Setuju Terima",
}

# ---------------------------------------------------------------- staff
STAFF = {
    "officer": "Noraini binti Hashim", "officer2": "Muhammad Firdaus bin Salleh",
    "senior": "Aisha binti Abdul Rahman", "collections": "Mohd Azlan bin Yusof",
    "risk": "Priya a/p Nair", "compliance": "Lee Siew Ling", "manager": "Kamarul Ariffin bin Said",
    "board": "Dato' Hj. Zulkifli bin Ahmad", "board2": "Datin Rohana binti Mahmud",
    "marketing": "Farah Nadia binti Ismail",
}

# ------------------------------------------------------------- calendar
def cycle_dates(n: int) -> list[dt.date]:
    """The n most recent salary-deduction dates (the 25th) on or before today."""
    last = dt.date(TODAY.year, TODAY.month, PAYDAY)
    if last > TODAY:
        last = add_months(last, -1, PAYDAY)
    return [add_months(last, -i, PAYDAY) for i in range(n - 1, -1, -1)]


def next_deduction_date() -> dt.date:
    d = dt.date(TODAY.year, TODAY.month, PAYDAY)
    return d if d > TODAY else add_months(d, 1, PAYDAY)


def _ago_months(n: int, day: int = 1) -> str:
    return add_months(TODAY, -n, day).isoformat()


# -------------------------------------------------------------- patterns
def _drift(i, n):           # a perfect payer who has started slipping
    if i < n - 4: return 0
    return [0, 3, 8, 11][max(0, i - (n - 4))]
def _stable(i, n):  return 0 if i % 9 else 1
def _perfect(i, n): return 0
def _bad(i, n):     return 0 if i < n - 6 else min(120, 10 * (i - (n - 7)) + 20)
def _recovering(i, n):
    if i < n - 7: return 0
    seq = [14, 22, 9, 2, 0, 0, 0]
    return seq[min(len(seq) - 1, i - (n - 7))]
def _slipping(i, n):        # mild, recent
    return 0 if i < n - 3 else [2, 6, 9][i - (n - 3)]

PATTERNS = dict(drift=_drift, stable=_stable, perfect=_perfect, bad=_bad, recovering=_recovering,
                slipping=_slipping)


def _payments(pattern, amount, channel, n=18):
    out = []
    for i, d in enumerate(cycle_dates(n)):
        late = PATTERNS[pattern](i, n)
        out.append({
            "month": d.isoformat(),
            "days_late": late,
            "amount_due": amount,
            "amount_paid": amount if late < 25 else 0,
            "channel": channel if i % 7 != 6 or channel != "Biro ANGKASA" else "Bank Transfer",
        })
    return out


# ------------------------------------------------------------ identities
_STATE_CODE = {"Johor": "01", "Kedah": "02", "Kelantan": "03", "Melaka": "04", "Negeri Sembilan": "05",
               "Pahang": "06", "Pulau Pinang": "07", "Perak": "08", "Perlis": "09", "Selangor": "10",
               "Terengganu": "11", "Sabah": "12", "Sarawak": "13", "W.P. Kuala Lumpur": "14"}


def mykad(dob: dt.date, state: str, male: bool, k: int) -> str:
    last = (k * 2 + (1 if male else 0)) % 10
    return f"{dob:%y%m%d}-{_STATE_CODE.get(state, '14')}-{(k * 37) % 900 + 100:03d}{last}"


SERVICE_LABEL = {"TD": "Tentera Darat", "TLDM": "Tentera Laut Diraja Malaysia",
                 "TUDM": "Tentera Udara Diraja Malaysia", "MINDEF": "Kementerian Pertahanan",
                 "VET": "Pesara ATM"}


# =============================================================== members
# The twelve case-study members carry the demo's stories; the generator below adds the rest of the
# membership so the queues, branch views, early warning, bankruptcy and cross-sell lists are full.
def _m(**kw):
    """Fill derived pay fields. Amounts are monthly RM unless named *_income (annual)."""
    gross, other = kw["gross_monthly"], kw["other_deductions"]
    kt, ext = kw.get("deduction", 0), kw.get("external_deductions", 0)
    kw.setdefault("payslip_income", (gross - other) * 12 if kw.get("salaried", True) else 0)
    kw.setdefault("declared_income", kw["payslip_income"] or kw.get("bank_income", 0))
    kw.setdefault("bank_income", kw["payslip_income"])
    kw["take_home"] = round(gross - other - kt - ext, 2)
    kw["financing_deductions"] = kt + ext
    return kw


def _given(full: str) -> str:
    """The name a member is addressed by: given names before bin/binti/a/l/a/p/anak; Chinese given name."""
    n = full.replace("Dato' ", "").replace("Datin ", "").replace("Hj. ", "").replace("Hjh. ", "")
    for sep in (" bin ", " binti ", " a/l ", " a/p ", " anak "):
        if sep in n:
            return n.split(sep)[0]
    parts = n.split()
    return " ".join(parts[1:]) if len(parts) == 3 and parts[0] in _CN_SUR else parts[0]


STORY = [
    # A — the portal member: a perfect payer who has started slipping (ELEVATED)
    _m(id="104328", name="Ahmad Faizal bin Rosli", rank="Sjn", service="TD", member_type="serving",
       unit="Batalion Ke-7 Rejimen Askar Melayu Diraja", camp="Kem Perdana Sungai Besi", branch="Sungai Besi",
       gender="M", dob="1990-06-12", birth_state="Negeri Sembilan", service_no="1123457", enlisted="2010-06-01",
       since="2020-03-01", savings=12420, share_capital=8200, outstanding=18250, prior_financings=3,
       reliability=96, gross_monthly=4680, other_deductions=1097, deduction=650, external_deductions=0,
       declared_income=52000, bank_income=45200, tenure_years=16, state="ELEVATED", pattern="drift",
       savings_trend=[300, 310, 320, 320, 310, 330, 340, 340, 345, 350, 350, 340, 320, 280, 240, 210],
       takaful=[], vehicle="Proton Saga 2019", dependants=[9, 6], gold_grams=0,
       engagement=[9, 9, 8, 9, 10, 9, 8, 9, 8, 7, 6, 5], marketing_consent=True,
       email="ahmad.faizal@contoh.example", phone="+60 12-345 0134",
       declared_note="Declared income includes an operations allowance (Elaun Operasi) that ended in July."),
    # B — retired major running a catering business (SME Financing-i, documents pending)
    _m(id="104188", name="Hj. Rosli bin Kamarudin", rank="Mej (B)", service="VET", member_type="retiree",
       unit="Rosli Katering Enterprise", camp="Wangsa Maju", branch="Kuala Lumpur", gender="M",
       dob="1968-02-14", birth_state="Selangor", service_no="201845", enlisted="1988-01-04",
       since="2009-07-14", savings=24100, share_capital=15400, outstanding=32000, prior_financings=2,
       reliability=93, gross_monthly=3900, other_deductions=120, deduction=600, external_deductions=0,
       salaried=False, declared_income=85000, bank_income=82000, payslip_income=0, tenure_years=5,
       business="Rosli Katering Enterprise", state="STABLE", pattern="stable", repayment_channel="Standing instruction",
       savings_trend=[900] * 10 + [950, 940, 980, 990, 1000, 1010], takaful=["General Takaful"],
       vehicle="Toyota Hilux 2020", dependants=[24, 21], gold_grams=60,
       engagement=[7, 7, 8, 7, 7, 8, 7, 8, 8, 7, 8, 8], marketing_consent=True,
       email="rosli.katering@contoh.example", phone="+60 13-288 0198"),
    # C — new recruit, fraud review (shared device, velocity), fails tenure and exposure
    _m(id="104265", name="Muhammad Aiman bin Zulkifli", rank="Prebet", service="TD", member_type="serving",
       unit="Pusat Latihan Asas Tentera Darat", camp="Kem Desa Pahlawan", branch="Kok Lanas", gender="M",
       dob="2003-11-02", birth_state="Kelantan", service_no="1198766", enlisted=_ago_months(20),
       since=_ago_months(5, 2), savings=1450, share_capital=900, outstanding=0, prior_financings=0,
       reliability=0, gross_monthly=2750, other_deductions=310, deduction=0, external_deductions=450,
       declared_income=31000, bank_income=22500, tenure_years=1, state="WATCH", pattern="stable",
       savings_trend=[160, 150, 140, 135, 130, 120, 110, 100, 95, 90, 80, 70, 60, 55, 50, 40],
       takaful=[], vehicle=None, dependants=[], gold_grams=0,
       engagement=[2, 3, 2, 4, 6, 9, 12, 14, 15, 16, 18, 20], marketing_consent=False,
       email="aiman.z@contoh.example", phone="+60 19-555 0112"),
    # D — retired captain, logistics company, recovering payment pattern (SME Financing-i)
    _m(id="104241", name="Wong Kah Seng", rank="Kapt (B)", service="VET", member_type="retiree",
       unit="WKS Logistik Sdn Bhd", camp="Putatan", branch="Kota Kinabalu", gender="M", dob="1971-08-20",
       birth_state="Sabah", service_no="203317", enlisted="1993-05-03", since="2008-01-20", savings=18900,
       share_capital=11200, outstanding=41500, prior_financings=4, reliability=88, gross_monthly=3400,
       other_deductions=90, deduction=900, external_deductions=0, salaried=False, declared_income=97000,
       bank_income=91800, payslip_income=0, tenure_years=8, business="WKS Logistik Sdn Bhd",
       state="ELEVATED", pattern="recovering", repayment_channel="Standing instruction",
       savings_trend=[800, 790, 780, 750, 720, 700, 680, 650, 620, 600, 590, 570, 600, 650, 710, 750],
       takaful=["Motor Takaful", "General Takaful"], vehicle="Isuzu D-Max 2022", dependants=[17],
       gold_grams=0, engagement=[8, 8, 7, 7, 6, 6, 6, 7, 7, 8, 8, 9], marketing_consent=True,
       email="wong.ks@contoh.example", phone="+60 16-822 0177"),
    # E — the clean approval case (Term Financing-i, vehicle)
    _m(id="104172", name="Tan Boon Keat", rank="Mej", service="TUDM", member_type="serving",
       unit="Skuadron No. 6, Pangkalan Udara Kuantan", camp="Pangkalan Udara Kuantan", branch="Kuantan",
       gender="M", dob="1984-05-09", birth_state="Pahang", service_no="U203456", enlisted="2006-07-10",
       since="2011-05-09", savings=41200, share_capital=22800, outstanding=9800, prior_financings=5,
       reliability=99, gross_monthly=9200, other_deductions=1330, deduction=1100, external_deductions=0,
       declared_income=94000, tenure_years=20, state="STABLE", pattern="perfect",
       savings_trend=[1700] * 8 + [1750, 1760, 1800, 1820, 1850, 1860, 1900, 1920],
       takaful=["Motor Takaful"], vehicle="Honda Civic 2018", dependants=[14, 11, 7], gold_grams=0,
       engagement=[8, 8, 9, 8, 8, 9, 8, 8, 9, 8, 9, 9], marketing_consent=True,
       email="tan.bk@contoh.example", phone="+60 17-555 0155"),
    # F — the reported "-200" case: DSR, exposure and the 60% deduction cap all fail
    _m(id="104310", name="Mohd Ridzuan bin Hamzah", rank="Kpl", service="TD", member_type="serving",
       unit="Batalion Ke-5 Rejimen Renjer Diraja", camp="Kem Lok Kawi", branch="Kota Kinabalu", gender="M",
       dob="1994-02-11", birth_state="Sabah", service_no="1167120", enlisted="2014-02-03",
       since="2022-02-11", savings=2100, share_capital=1400, outstanding=14200, prior_financings=1,
       reliability=71, gross_monthly=3900, other_deductions=550, deduction=310, external_deductions=1210,
       declared_income=41000, bank_income=32600, tenure_years=12, state="AT_RISK", pattern="bad",
       savings_trend=[250, 240, 230, 215, 200, 190, 170, 150, 140, 120, 105, 90, 75, 60, 45, 30],
       takaful=[], vehicle="Perodua Axia 2017", dependants=[5, 3, 1], gold_grams=15,
       engagement=[6, 6, 5, 5, 5, 4, 4, 3, 3, 2, 2, 1], marketing_consent=True,
       email="ridzuan.h@contoh.example", phone="+60 14-818 0165"),
    # G — strong naval officer (Term Financing-i, ready to approve)
    _m(id="104233", name="Nurul Izzah binti Kamaruddin", rank="Lt Kdr", service="TLDM",
       member_type="serving", unit="KD Pelandok", camp="Pangkalan TLDM Lumut", branch="Lumut", gender="F",
       dob="1985-09-30", birth_state="Perak", service_no="N3012783", enlisted="2007-01-15", since="2012-09-30",
       savings=33800, share_capital=19600, outstanding=4300, prior_financings=4, reliability=98,
       gross_monthly=8400, other_deductions=1150, deduction=980, external_deductions=0,
       declared_income=87000, tenure_years=19, state="STABLE", pattern="perfect",
       savings_trend=[1500] * 16, takaful=["General Takaful"], vehicle="Mazda CX-5 2017", dependants=[10],
       gold_grams=40, engagement=[9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9], marketing_consent=True,
       email="nurul.izzah@contoh.example", phone="+60 12-555 0188"),
    # H — MINDEF civil servant, postgraduate fees (Fees Financing-i)
    _m(id="104298", name="Lim Mei Ying", rank="N41", service="MINDEF", member_type="civil",
       unit="Bahagian Dasar dan Perancangan Strategik", camp="Wisma Pertahanan", branch="Kuala Lumpur",
       gender="F", dob="1991-06-18", birth_state="Pulau Pinang", service_no="KP41-20877", enlisted="2016-03-01",
       since="2017-06-18", savings=8600, share_capital=5200, outstanding=6100, prior_financings=1,
       reliability=94, gross_monthly=5200, other_deductions=420, deduction=540, external_deductions=0,
       declared_income=57000, tenure_years=10, state="STABLE", pattern="stable",
       savings_trend=[420, 425, 430, 435, 440, 445, 450, 455, 460, 465, 470, 475, 480, 485, 490, 495],
       takaful=[], vehicle="Perodua Bezza 2021", dependants=[], gold_grams=0,
       engagement=[7, 7, 8, 8, 8, 8, 9, 9, 9, 9, 9, 9], marketing_consent=True,
       email="lim.meiying@contoh.example", phone="+60 19-555 0121"),
    # I — MINDEF clerk with an approved payment arrangement (signal suppressed)
    _m(id="104291", name="Siti Khadijah binti Omar", rank="N19", service="MINDEF", member_type="civil",
       unit="Unit Pentadbiran Kem Desa Pahlawan", camp="Kem Desa Pahlawan", branch="Kok Lanas", gender="F",
       dob="1987-12-04", birth_state="Kelantan", service_no="KP19-11843", enlisted="2011-01-03",
       since="2014-12-04", savings=5300, share_capital=3100, outstanding=3900, prior_financings=1,
       reliability=90, gross_monthly=2950, other_deductions=300, deduction=430, external_deductions=170,
       declared_income=32000, tenure_years=15, state="WATCH", pattern="slipping",
       savings_trend=[300, 295, 290, 285, 280, 270, 265, 260, 250, 245, 235, 230, 225, 215, 210, 205],
       takaful=[], vehicle=None, dependants=[12, 8, 4], gold_grams=25,
       engagement=[8, 8, 7, 7, 7, 6, 6, 6, 5, 5, 5, 4], marketing_consent=True,
       email="siti.khadijah@contoh.example", phone="+60 18-555 0143"),
    # J — retired lieutenant colonel, contractor (Contract Financing-i, credit committee)
    _m(id="104276", name="Dato' Ramli bin Yusof", rank="Lt Kol (B)", service="VET",
       member_type="retiree", unit="Ramli Bina Sdn Bhd", camp="Setapak", branch="Kuala Lumpur", gender="M",
       dob="1964-08-25", birth_state="Johor", service_no="198812", enlisted="1984-06-01", since="2005-08-25",
       savings=68400, share_capital=39200, outstanding=52000, prior_financings=6, reliability=97,
       gross_monthly=6100, other_deductions=380, deduction=2900, external_deductions=0, salaried=False,
       declared_income=220000, bank_income=214000, payslip_income=0, tenure_years=11,
       business="Ramli Bina Sdn Bhd", state="STABLE", pattern="stable",
       repayment_channel="Standing instruction",
       savings_trend=[2700] * 16, takaful=["Motor Takaful", "General Takaful"], vehicle="Toyota Camry 2021",
       dependants=[], gold_grams=120, engagement=[6, 6, 6, 7, 6, 6, 7, 6, 6, 7, 6, 6], marketing_consent=True,
       email="ramli.bina@contoh.example", phone="+60 12-290 0190"),
    # K — air force corporal, express financing
    _m(id="104201", name="Chong Wei Ming", rank="Kpl Udara", service="TUDM", member_type="serving",
       unit="Skuadron No. 17, Pangkalan Udara Kuantan", camp="Pangkalan Udara Kuantan", branch="Kuantan",
       gender="M", dob="1996-10-10", birth_state="Pahang", service_no="U718842", enlisted="2016-10-03",
       since="2019-10-10", savings=3900, share_capital=2400, outstanding=2200, prior_financings=1,
       reliability=92, gross_monthly=3900, other_deductions=420, deduction=470, external_deductions=0,
       declared_income=42000, tenure_years=10, state="STABLE", pattern="stable",
       savings_trend=[200, 205, 210, 205, 215, 220, 218, 225, 230, 225, 235, 240, 238, 242, 245, 250],
       takaful=[], vehicle="Honda City 2020", dependants=[2], gold_grams=0,
       engagement=[7, 7, 7, 8, 8, 7, 8, 8, 8, 8, 8, 8], marketing_consent=True,
       email="chong.wm@contoh.example", phone="+60 19-555 0176"),
    # L — warrant officer buying a car on Personal Financing-i (documents pending)
    _m(id="104317", name="Rajesh a/l Subramaniam", rank="PW II", service="TD", member_type="serving",
       unit="Rejimen Ke-2 Jurutera Diraja", camp="Kem Sultan Azlan Shah", branch="Lumut", gender="M",
       dob="1983-09-02", birth_state="Perak", service_no="1078813", enlisted="2002-09-02", since="2012-09-02",
       savings=15600, share_capital=9100, outstanding=21400, prior_financings=2, reliability=91,
       gross_monthly=6300, other_deductions=820, deduction=880, external_deductions=300,
       declared_income=69000, tenure_years=24, state="STABLE", pattern="stable",
       savings_trend=[650, 660, 655, 670, 675, 665, 680, 690, 685, 695, 700, 710, 705, 715, 720, 725],
       takaful=[], vehicle="Proton X50 2022", dependants=[16, 13], gold_grams=0,
       engagement=[8, 8, 8, 8, 7, 8, 8, 8, 8, 7, 8, 8], marketing_consent=True,
       email="rajesh.s@contoh.example", phone="+60 17-555 0129"),
    # M — the 60%-of-gross case: DSR passes, total salary deductions do not
    _m(id="104355", name="Jeffrey anak Nyalau", rank="Kpl", service="TD", member_type="serving",
       unit="Batalion Ke-9 Rejimen Renjer Diraja", camp="Kem Lok Kawi", branch="Kota Kinabalu", gender="M",
       dob="1992-03-15", birth_state="Sarawak", service_no="1159034", enlisted="2012-03-05",
       since="2016-03-15", savings=4200, share_capital=2600, outstanding=3100, prior_financings=2,
       reliability=93, gross_monthly=3500, other_deductions=1250, deduction=300, external_deductions=220,
       declared_income=27000, tenure_years=14, state="STABLE", pattern="stable",
       other_note="Other deductions include LTAT, quarters rent, takaful and a court maintenance order.",
       savings_trend=[220] * 16, takaful=["General Takaful"], vehicle="Yamaha Y15ZR", dependants=[8, 6],
       gold_grams=0, engagement=[7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7], marketing_consent=True,
       email="jeffrey.n@contoh.example", phone="+60 13-881 0355"),
    # N — cross-sell A: financing, spotless conduct, a vehicle and no takaful
    _m(id="104402", name="Nurul Huda binti Zakaria", rank="Sjn Udara", service="TUDM",
       member_type="serving", unit="Skuadron No. 6, Pangkalan Udara Kuantan", camp="Pangkalan Udara Kuantan",
       branch="Kuantan", gender="F", dob="1989-04-21", birth_state="Terengganu", service_no="U709921",
       enlisted="2009-04-06", since="2013-04-21", savings=16800, share_capital=9400, outstanding=11800,
       prior_financings=2, reliability=100, gross_monthly=5100, other_deductions=640, deduction=520,
       external_deductions=0, tenure_years=17, state="STABLE", pattern="perfect",
       savings_trend=[600] * 16, takaful=[], vehicle="Perodua Ativa 2023", dependants=[7, 4], gold_grams=10,
       engagement=[8, 8, 8, 9, 8, 8, 9, 8, 8, 9, 8, 9], marketing_consent=True,
       email="nurul.huda@contoh.example", phone="+60 11-2345 0402"),
    # O — cross-sell B: strong salary and savings, no personal financing, large headroom
    _m(id="104415", name="Muhammad Hafiz bin Ismail", rank="Lt", service="TLDM", member_type="serving",
       unit="KD Sultan Idris I", camp="Pangkalan TLDM Lumut", branch="Lumut", gender="M", dob="1995-01-08",
       birth_state="Johor", service_no="N4012299", enlisted="2017-06-12", since="2018-01-08", savings=28600,
       share_capital=12500, outstanding=0, prior_financings=0, reliability=100, gross_monthly=6200,
       other_deductions=780, deduction=0, external_deductions=0, tenure_years=9, state="STABLE",
       pattern="perfect", savings_trend=[900] * 8 + [950, 980, 1000, 1000, 1050, 1050, 1100, 1100],
       takaful=["Motor Takaful"], vehicle="Honda HR-V 2022", dependants=[], gold_grams=30,
       engagement=[7, 8, 8, 8, 8, 9, 9, 9, 9, 9, 9, 9], marketing_consent=True,
       email="hafiz.ismail@contoh.example", phone="+60 12-345 0415"),
    # P — cross-sell C: declining engagement, retention intervention
    _m(id="104428", name="Siti Aminah binti Daud", rank="N29", service="MINDEF", member_type="civil",
       unit="Pejabat Rekod Tentera Darat", camp="Kem Batu Kentonmen", branch="Kuala Lumpur", gender="F",
       dob="1980-07-07", birth_state="Selangor", service_no="KP29-08821", enlisted="2004-02-02",
       since="2006-07-07", savings=21400, share_capital=12800, outstanding=0, prior_financings=3,
       reliability=97, gross_monthly=4300, other_deductions=360, deduction=0, external_deductions=0,
       tenure_years=22, state="STABLE", pattern="perfect",
       savings_trend=[600, 600, 580, 560, 520, 480, 450, 400, 360, 300, 250, 200, 150, 100, 50, 0],
       takaful=[], vehicle="Proton Persona 2016", dependants=[19, 17], gold_grams=45,
       engagement=[10, 10, 9, 9, 8, 7, 6, 5, 4, 3, 2, 1], marketing_consent=True,
       email="siti.aminah@contoh.example", phone="+60 17-555 0428"),
    # Q — retired warrant officer, heavy external debt, worsening arrears (bankruptcy watch)
    _m(id="104436", name="Ramasamy a/l Muthu", rank="Mej (B)", service="VET", member_type="retiree",
       unit="Pesara ATM — Jabatan Hal Ehwal Veteran", camp="Ampang", branch="Kuala Lumpur", gender="M",
       dob="1966-03-03", birth_state="Selangor", service_no="197731", enlisted="1986-01-06",
       since="2001-03-03", savings=1900, share_capital=3200, outstanding=38600, prior_financings=5,
       reliability=78, gross_monthly=4200, other_deductions=160, deduction=1180, external_deductions=1350,
       tenure_years=0, state="AT_RISK", pattern="bad", repayment_channel="Pension deduction (JHEV)",
       savings_trend=[200, 190, 180, 160, 140, 120, 100, 80, 60, 40, 30, 20, 10, 0, 0, 0],
       takaful=[], vehicle="Proton Inspira 2014", dependants=[], gold_grams=0,
       engagement=[6, 6, 6, 5, 5, 5, 4, 4, 3, 3, 2, 2], marketing_consent=True,
       email="ramasamy.m@contoh.example", phone="+60 16-555 0436"),
]

# ----------------------------------------------------------- generator
_MALAY_M = ["Ahmad", "Muhammad", "Mohd", "Hafiz", "Faizal", "Azman", "Khairul", "Shahrul", "Izzat", "Amirul",
            "Hakim", "Firdaus", "Syafiq", "Zulkarnain", "Rizal", "Fadzli", "Nazri", "Hairul", "Aziz", "Haziq"]
_MALAY_F = ["Nurul", "Siti", "Nor", "Aisyah", "Farah", "Nadia", "Hidayah", "Syazwani", "Aminah", "Rohana",
            "Fatimah", "Liyana", "Hani", "Zawiyah"]
_MALAY_FATHER = ["Abdullah", "Ismail", "Hassan", "Ibrahim", "Yusof", "Osman", "Ahmad", "Rahman", "Hamid",
                 "Salleh", "Zainal", "Razak", "Kassim", "Mansor", "Jaafar", "Daud", "Sulaiman", "Ali", "Rashid"]
_CN_SUR = ["Tan", "Lim", "Lee", "Wong", "Ng", "Chong", "Chan", "Ong", "Teoh", "Goh"]
_CN_GIVEN = ["Wei Ming", "Chee Keong", "Jun Hao", "Zhi Wei", "Kok Leong", "Mei Ling", "Hui Min", "Li Ying"]
_IN_M = ["Suresh", "Kumar", "Ganesh", "Vijay", "Ravi", "Prakash", "Saravanan"]
_IN_F = ["Kavitha", "Devi", "Shanti", "Malar"]
_IN_FATHER = ["Krishnan", "Raman", "Murugan", "Arumugam", "Muniandy", "Gopal"]
_IBAN_M = ["Mathew", "Justin", "Robert", "Kenny", "Dennis", "Edward", "Felix"]
_IBAN_F = ["Linda", "Mary", "Juliana", "Rita"]
_IBAN_FATHER = ["Jugah", "Ngelai", "Sumbang", "Nyalau", "Unting", "Belaja", "Lang", "Ensali"]
_KDZ_M = ["Albert", "Stanley", "Jimmy", "Raymond", "Benedict", "Junaidi", "Roslan"]
_KDZ_F = ["Florence", "Agnes", "Rosnah", "Jenny"]
_KDZ_SUR = ["Gimbang", "Majakil", "Lojingki", "Gunsalam", "Sintong", "Lakim", "Majimbun", "Gani"]

_CAMPS = {
    "Kuala Lumpur": [("TD", "Kem Batu Kentonmen"), ("MINDEF", "Wisma Pertahanan"), ("TUDM", "Pangkalan Udara Subang"),
                     ("TD", "Kem Wardieburn")],
    "Sungai Besi": [("TD", "Kem Perdana Sungai Besi"), ("TD", "Kem Desa Tasik"), ("MINDEF", "Kem Perdana Sungai Besi")],
    "Lumut": [("TLDM", "Pangkalan TLDM Lumut"), ("TLDM", "KD Pelandok"), ("TD", "Kem Sultan Azlan Shah")],
    "Kuantan": [("TUDM", "Pangkalan Udara Kuantan"), ("TD", "Kem Inderapura"), ("MINDEF", "Pangkalan Udara Kuantan")],
    "Kota Kinabalu": [("TD", "Kem Lok Kawi"), ("TLDM", "Pangkalan TLDM Teluk Sepanggar"), ("TD", "Kem Kepayan")],
    "Kok Lanas": [("TD", "Kem Desa Pahlawan"), ("TD", "Kem Pengkalan Chepa"), ("MINDEF", "Kem Desa Pahlawan")],
}
_UNITS = {"TD": ["Rejimen Askar Melayu Diraja", "Rejimen Renjer Diraja", "Kor Armor Diraja",
                 "Rejimen Artileri Diraja", "Kor Jurutera Diraja", "Kor Perkhidmatan Diraja",
                 "Kor Kesihatan Diraja", "Kor Polis Tentera Diraja", "Kor Isyarat Diraja"],
          "TLDM": ["Armada Barat", "Markas Wilayah Laut", "Pusat Latihan TLDM", "Skuadron Kapal Peronda"],
          "TUDM": ["Skuadron Pengangkutan", "Skuadron Pertahanan Udara", "Unit Penyelenggaraan Pesawat"],
          "MINDEF": ["Bahagian Kewangan", "Bahagian Perolehan", "Unit Pentadbiran Kem", "Bahagian Sumber Manusia"]}
_RANKS = {"TD": [("Prebet", 2900, 6), ("L/Kpl", 3250, 6), ("Kpl", 3800, 9), ("Sjn", 4800, 8), ("S/Sjn", 5300, 4),
                 ("PW II", 6000, 3), ("Lt", 5100, 2), ("Kapt", 6300, 2), ("Mej", 8500, 1)],
          "TLDM": [("Kelasi", 2900, 4), ("Laskar Kanan", 3700, 5), ("Bintara Muda", 4700, 4),
                   ("Bintara Kanan", 5300, 2), ("Lt", 5100, 1), ("Lt Kdr", 8300, 1)],
          "TUDM": [("Prebet Udara", 2900, 4), ("Kpl Udara", 3800, 5), ("Sjn Udara", 4800, 4),
                   ("Fl Sjn", 5300, 2), ("Kapt", 6300, 1), ("Mej", 8500, 1)],
          "MINDEF": [("N19", 2800, 5), ("N29", 3800, 4), ("J29", 3900, 2), ("N41", 5200, 3), ("N44", 7400, 1)]}
_VEHICLES = ["Perodua Myvi 2021", "Perodua Bezza 2020", "Proton Saga 2019", "Proton X50 2023", "Honda City 2019",
             "Toyota Vios 2018", "Perodua Axia 2022", "Yamaha Y15ZR", "Honda Wave 125", None, None]


def _gen_members(n: int) -> list[dict]:
    rnd = random.Random(7)
    _used = {m["name"] for m in STORY}
    out, ids = [], 104440
    weights = {"TD": 46, "TLDM": 14, "TUDM": 14, "MINDEF": 16, "VET": 10}
    plan = [BRANCHES[i % len(BRANCHES)] for i in range(n)]
    patterns = (["stable"] * 38 + ["perfect"] * 18 + ["slipping"] * 5 + ["drift"] * 3 + ["bad"] * 3
                + ["recovering"] * 3)
    rnd.shuffle(patterns)
    for k, branch in enumerate(plan):
        ids += rnd.choice([3, 7, 11, 13])
        # a branch only serves the services that have a base near it (no navy in Kok Lanas)
        here = {c[0] for c in _CAMPS[branch]} | {"VET"}
        opts = [k_ for k_ in weights if k_ in here]
        svc = rnd.choices(opts, [weights[k_] for k_ in opts])[0]
        eth = rnd.choices(["malay", "borneo", "indian", "chinese"], [74, 14, 6, 6])[0]
        if branch == "Kota Kinabalu" and rnd.random() < .5:
            eth = "borneo"
        male = rnd.random() < (0.82 if svc != "MINDEF" else 0.45)
        if eth == "malay":
            first = rnd.choice(_MALAY_M if male else _MALAY_F)
            name = f"{first} {rnd.choice(_MALAY_M[1:] if male else _MALAY_F)} {'bin' if male else 'binti'} {rnd.choice(_MALAY_FATHER)}" \
                if first in ("Muhammad", "Mohd", "Nurul", "Siti", "Nor") else \
                f"{first} {'bin' if male else 'binti'} {rnd.choice(_MALAY_FATHER)}"
            bstate = rnd.choice(["Kelantan", "Terengganu", "Kedah", "Perak", "Johor", "Pahang", "Selangor"])
        elif eth == "borneo":
            if rnd.random() < 0.5:
                name = f"{rnd.choice(_IBAN_M if male else _IBAN_F)} anak {rnd.choice(_IBAN_FATHER)}"
                bstate = "Sarawak"
            else:
                first = rnd.choice(_KDZ_M if male else _KDZ_F)
                sur = rnd.choice(_KDZ_SUR)
                name = f"{first} {'bin' if male else 'binti'} {sur}" if first in ("Junaidi", "Roslan", "Rosnah") \
                    else f"{first} {sur}"
                bstate = "Sabah"
        elif eth == "indian":
            name = f"{rnd.choice(_IN_M if male else _IN_F)} {'a/l' if male else 'a/p'} {rnd.choice(_IN_FATHER)}"
            bstate = rnd.choice(["Perak", "Selangor", "Negeri Sembilan", "Johor"])
        else:
            name = f"{rnd.choice(_CN_SUR)} {rnd.choice(_CN_GIVEN)}"
            bstate = rnd.choice(["Pulau Pinang", "Perak", "Johor", "Selangor"])
        if name in _used:                      # keep every member's name distinct
            for sep in (" bin ", " binti ", " a/l ", " a/p ", " anak "):
                if sep in name:
                    name = name.replace(sep, f" {rnd.choice(_MALAY_M[3:] if male else _MALAY_F[3:])}{sep}", 1)
                    break
            else:
                name = f"{name} {rnd.choice(['Jr', 'Ah Kow', 'Boon'])}"
        _used.add(name)
        if svc == "VET":
            rank, base = rnd.choice([("PW I (B)", 3100), ("Sjn (B)", 2300), ("Kapt (B)", 3300), ("Kpl (B)", 1900)])
            gross, mtype = base + rnd.randint(-200, 400), "retiree"
            camp, unit = rnd.choice(["Ampang", "Gombak", "Seremban", "Kuantan", "Kota Bharu", "Penampang"]), \
                "Pesara ATM — Jabatan Hal Ehwal Veteran"
            age = rnd.randint(52, 66)
        else:
            camps = [c for c in _CAMPS[branch] if c[0] == svc] or _CAMPS[branch]
            camp = rnd.choice(camps)[1]
            age = rnd.randint(22, 52)
            # seniority follows age: a 45-year-old is a warrant officer or an officer, not a private
            ranks = sorted(_RANKS[svc], key=lambda r: r[1])
            pos = (age - 22) / 30 * (len(ranks) - 1) + rnd.uniform(-1.2, 1.2)
            rank, base, _ = ranks[max(0, min(len(ranks) - 1, round(pos)))]
            gross = base + rnd.randint(-250, 650)
            unit = rnd.choice(_UNITS[svc])
            mtype = "civil" if svc == "MINDEF" else "serving"
        dob = dt.date(TODAY.year - age, rnd.randint(1, 12), rnd.randint(1, 28))
        enlisted = dt.date(dob.year + rnd.randint(18, 24), rnd.randint(1, 12), rnd.randint(1, 28))
        enlisted = min(enlisted, TODAY - dt.timedelta(days=400))
        since = max(enlisted, dt.date(2004, 1, 1)) + dt.timedelta(days=rnd.randint(60, 2200))
        since = min(since, TODAY - dt.timedelta(days=240))
        other = round(gross * rnd.uniform(0.08, 0.17))
        pat = patterns[k % len(patterns)]
        has_fin = rnd.random() < 0.72 or pat in ("bad", "drift", "slipping", "recovering")
        ded = rnd.choice([0, 250, 320, 410, 480, 560, 650, 720, 850]) if has_fin else 0
        ded = ded or (rnd.choice([280, 390, 460]) if has_fin else 0)
        ext = rnd.choice([0, 0, 0, 180, 300, 450, 600])
        if pat == "bad":
            ext += rnd.choice([400, 650, 900])
        outstanding = round(ded * rnd.randint(14, 70), -2) if ded else 0
        savings = round(rnd.uniform(0.6, 6.0) * gross * (1.6 if pat == "perfect" else 1), -1)
        if pat in ("bad", "drift"):
            savings = round(savings * 0.35, -1)
        share = round(savings * rnd.uniform(0.35, 0.7), -1)
        state = {"bad": "AT_RISK", "drift": "ELEVATED", "slipping": "WATCH", "recovering": "ELEVATED"}.get(pat, "STABLE")
        mo = round(rnd.uniform(0.02, 0.08) * gross, -1)
        trend = [round(mo * (1 + (0.05 * rnd.random()) - (0.06 * i if pat in ("bad", "drift") else 0)), 0)
                 for i in range(16)]
        engage_decline = rnd.random() < 0.12
        engagement = [max(0, 9 - (i if engage_decline else 0) + rnd.randint(-1, 1)) for i in range(12)]
        deps = sorted([rnd.randint(1, 23) for _ in range(rnd.choice([0, 1, 2, 2, 3, 4]))], reverse=True)
        sno = (f"U7{rnd.randint(10000, 99999)}" if svc == "TUDM" else f"N4{rnd.randint(100000, 999999)}"
               if svc == "TLDM" else f"KP{rank[1:3]}-{rnd.randint(10000, 99999)}" if svc == "MINDEF"
               else f"{rnd.randint(1050000, 1199999)}")
        out.append(_m(
            id=str(ids), name=name, rank=rank, service=svc, member_type=mtype, unit=unit, camp=camp,
            branch=branch, gender="M" if male else "F", dob=dob.isoformat(), birth_state=bstate,
            service_no=sno, enlisted=enlisted.isoformat(), since=since.isoformat(), savings=savings,
            share_capital=share, outstanding=outstanding, prior_financings=rnd.randint(0, 5),
            reliability={"perfect": 100, "stable": rnd.randint(90, 98), "slipping": rnd.randint(86, 93),
                         "drift": rnd.randint(88, 95), "bad": rnd.randint(62, 78),
                         "recovering": rnd.randint(80, 88)}[pat],
            gross_monthly=gross, other_deductions=other, deduction=ded, external_deductions=ext,
            tenure_years=max(1, TODAY.year - enlisted.year) if svc != "VET" else 0, state=state, pattern=pat,
            repayment_channel="Pension deduction (JHEV)" if svc == "VET" else "Biro ANGKASA",
            savings_trend=trend, takaful=rnd.sample(["Motor Takaful", "General Takaful"], k=rnd.choice([0, 0, 1, 1, 2])),
            vehicle=rnd.choice(_VEHICLES), dependants=deps, gold_grams=rnd.choice([0, 0, 0, 10, 20, 35, 50]),
            engagement=engagement, marketing_consent=rnd.random() < 0.9, dnc=rnd.random() < 0.04,
            email=f"{name.split()[0].lower()}.{ids % 1000}@contoh.example",
            phone=f"+60 1{rnd.randint(1, 9)}-{rnd.randint(200, 899)} {rnd.randint(1000, 9999)}"))
    return out


def _finish(m: dict, k: int) -> dict:
    m["full_name"] = m["name"]
    male = m["gender"] == "M"
    if m["member_type"] == "civil":
        m["name"] = f"{'Encik' if male else 'Puan'} {m['full_name']}"
    else:
        m["name"] = f"{m['rank']} {m['full_name']}"
    m["given_name"] = _given(m["full_name"])
    words = [w for w in m["full_name"].replace("Dato' ", "").replace("Hj. ", "").split()
             if w not in ("bin", "binti", "a/l", "a/p", "anak")]
    m["initials"] = (words[0][0] + words[-1][0]).upper() if len(words) > 1 else words[0][:2].upper()
    m.setdefault("repayment_channel", "Pension deduction (JHEV)" if m["member_type"] == "retiree"
                 else "Biro ANGKASA")
    m.setdefault("dnc", False)
    m.setdefault("salaried", True)
    dob = dt.date.fromisoformat(m["dob"])
    m["mykad"] = mykad(dob, m.get("birth_state", "W.P. Kuala Lumpur"), m["gender"] == "M", k)
    m["service_label"] = SERVICE_LABEL[m["service"]]
    if m["member_type"] == "serving":
        officer = any(m["rank"].startswith(r) for r in ("Lt", "Kapt", "Mej", "Kol", "Kdr"))
        enl = dt.date.fromisoformat(m["enlisted"])
        ret = add_months(dob, 56 * 12) if officer else min(add_months(enl, 21 * 12), add_months(dob, 60 * 12))
        if ret <= TODAY:
            ret = add_months(TODAY, 18)
        m["retirement_date"] = ret.isoformat()
        m["employer"] = f"Angkatan Tentera Malaysia — {m['service_label']}"
        m["employment"] = "Serving — permanent & confirmed"
    elif m["member_type"] == "civil":
        m["retirement_date"] = add_months(dob, 60 * 12).isoformat()
        m["employer"] = "Kementerian Pertahanan Malaysia"
        m["employment"] = "Civil service — permanent"
    else:
        m["retirement_date"] = None
        m["employer"] = m.get("business") or "Pesara ATM (pencen)"
        m["employment"] = "Self-employed (business owner)" if m.get("business") else "Retired (pension)"
    m["months_to_retirement"] = (months_between(TODAY, dt.date.fromisoformat(m["retirement_date"]))
                                 if m["retirement_date"] else None)
    m["display_rank"] = m["rank"] if m["member_type"] != "civil" else f"Gred {m['rank']}"
    return m


MEMBERS = [_finish(m, i) for i, m in enumerate(STORY + _gen_members(66))]
_BY_ID = {m["id"]: m for m in MEMBERS}


def members():
    out = []
    for m in MEMBERS:
        d = dict(m)
        # only members with a KT facility have a repayment history to monitor
        d["payments"] = _payments(m["pattern"], m["deduction"], m["repayment_channel"]) if m["deduction"] else []
        out.append(d)
    return out


# ------------------------------------------------------------ applications
def clock_at(days_ago: int, hh: int, mm: int) -> str:
    return at(TODAY - dt.timedelta(days=days_ago), hh, mm)


def _app(aid, mid, product, amount, term, purpose, days, hh, mm, status, officer, channel, guarantor=None):
    m = _BY_ID[mid]
    return dict(id=aid, member_id=mid, product=product, amount=amount, term=term, purpose=purpose,
                submitted=clock_at(days, hh, mm), branch=m["branch"], status=status, officer=officer,
                channel=channel, guarantor=_BY_ID[guarantor]["name"] if guarantor else None,
                guarantor_id=guarantor,
                existing_commitments=m["deduction"] + m["external_deductions"], case_type="origination")


O1, O2, SR = STAFF["officer"], STAFF["officer2"], STAFF["senior"]
APPLICATIONS = [
    _app("APP-104328", "104328", "Personal Financing-i", 25000, 48, "Home renovation", 1, 10, 24,
         "Officer Review", O1, "Branch"),
    _app("APP-104188", "104188", "SME Financing-i", 50000, 48, "Kitchen equipment for camp catering contract",
         6, 8, 20, "Documents Pending", O1, "KT Online", guarantor="104276"),
    _app("APP-104172", "104172", "Term Financing-i", 28000, 60, "Vehicle purchase", 6, 11, 10,
         "Ready to Approve", O2, "KT Online"),
    _app("APP-104265", "104265", "Personal Financing-i", 10000, 24, "Debt consolidation", 3, 9, 5,
         "Fraud Review", O2, "KT Online"),
    _app("APP-104241", "104241", "SME Financing-i", 75000, 60, "Fleet refinancing", 4, 14, 40,
         "Risk Review", SR, "Branch", guarantor="104233"),
    _app("APP-104310", "104310", "Personal Financing-i", 15000, 36, "Medical expenses for a parent", 2, 11, 15,
         "Enhanced Review", SR, "Branch"),
    _app("APP-104233", "104233", "Term Financing-i", 22000, 48, "Vehicle purchase", 4, 9, 0,
         "Ready to Approve", O1, "KT Online"),
    _app("APP-104298", "104298", "Fees Financing-i", 18000, 48, "Master's tuition, UPNM", 2, 13, 30,
         "In Verification", O1, "KT Online"),
    _app("APP-104291", "104291", "Personal Financing-i", 10000, 24, "Family emergency", 2, 16, 5,
         "Documents Pending", O2, "Branch"),
    _app("APP-104276", "104276", "Contract Financing-i", 120000, 36, "Working capital — barracks maintenance contract",
         3, 9, 45, "Credit Analysis", SR, "Branch"),
    _app("APP-104201", "104201", "Express Financing-i", 8500, 24, "House repairs after flooding", 5, 15, 20,
         "Officer Review", O2, "KT Online"),
    _app("APP-104317", "104317", "Personal Financing-i", 32000, 60, "Car purchase", 1, 7, 0,
         "Documents Pending", O2, "KT Online"),
    _app("APP-104355", "104355", "Express Financing-i", 8000, 24, "School fees and uniforms", 1, 12, 40,
         "Officer Review", O1, "Branch"),
]


def _gen_applications():
    """A further set of live cases on generated members, spread across branches and products."""
    rnd = random.Random(19)
    pool = [m for m in MEMBERS[len(STORY):] if m["pattern"] in ("stable", "perfect", "slipping")
            and m["member_type"] != "retiree"]
    picks = rnd.sample(pool, 9)
    plan = [("Personal Financing-i", 15000, 60, "Wedding expenses"), ("Express Financing-i", 5000, 18, "Motorcycle repair"),
            ("Fees Financing-i", 9000, 36, "Diploma fees for a dependant"), ("Personal Financing-i", 30000, 84, "Home renovation"),
            ("Term Financing-i", 45000, 84, "Vehicle purchase"), ("Personal Financing-i", 12000, 48, "Hajj and umrah"),
            ("Express Financing-i", 3000, 12, "Household emergency"), ("Fees Financing-i", 14000, 48, "University fees for a dependant"),
            ("Personal Financing-i", 20000, 60, "Debt consolidation")]
    statuses = ["Officer Review", "In Verification", "Documents Pending", "Officer Review", "Credit Analysis",
                "Ready to Approve", "Officer Review", "In Verification", "Officer Review"]
    out = []
    for i, (m, (prod, amt, term, purpose)) in enumerate(zip(picks, plan)):
        cap = max(3000, round((m["gross_monthly"] - m["other_deductions"]) * 0.4 - m["deduction"] - m["external_deductions"], -1))
        amt = min(amt, PRODUCTS[prod]["max"], round(cap * term / (1 + PRODUCTS[prod]["rate"] / 100 * term / 12) * 0.85, -3) or amt)
        amt = max(PRODUCTS[prod]["min"], amt)
        out.append(_app(f"APP-{m['id']}", m["id"], prod, amt, term, purpose, rnd.randint(1, 6),
                        rnd.randint(8, 16), rnd.choice([0, 10, 20, 30, 40, 50]), statuses[i],
                        rnd.choice([O1, O2, O2, SR]), rnd.choice(["Branch", "KT Online", "KT Online"])))
    return out


APPLICATIONS += _gen_applications()

# evidence a case is deliberately still waiting for
MISSING = {
    "APP-104317": ["Service Confirmation", "Bank Statement"],
    "APP-104291": ["Bank Statement", "Payment History"],
    "APP-104241": ["Tax Return"],
    "APP-104265": ["Service Confirmation", "Payment History"],
    "APP-104201": ["Payment History"],
    "APP-104188": ["Tax Return", "Quotation"],
}
for a in APPLICATIONS[13:]:
    if a["status"] == "Documents Pending":
        MISSING[a["id"]] = ["Bank Statement"]

# ------------------------------------------------------------- collections
_next = next_deduction_date()
COLLECTIONS = [
    dict(id="COL-2601", member_id="104310", balance=4850, dpd=120, response=72, priority="P1",
         last_payment=cycle_dates(6)[0].isoformat(), intervention="Call + hardship options", promise=None,
         expected_value=3492, stage="Late Stage"),
    dict(id="COL-2602", member_id="104436", balance=6200, dpd=90, response=61, priority="P1",
         last_payment=cycle_dates(5)[0].isoformat(), intervention="Pension deduction review + AKPK referral",
         promise=None, expected_value=3100, stage="Late Stage"),
    dict(id="COL-2603", member_id="104291", balance=1340, dpd=9, response=65, priority="P2",
         last_payment=cycle_dates(2)[0].isoformat(), intervention="SMS with payment link",
         promise=add_months(_next, 0, 28).isoformat(), expected_value=1120, stage="Early Stage"),
    dict(id="COL-2604", member_id="104241", balance=3600, dpd=0, response=66, priority="P3",
         last_payment=cycle_dates(1)[0].isoformat(), intervention="Confirm recovery and close", promise=None,
         expected_value=2376, stage="Recovery"),
    dict(id="COL-2605", member_id="104328", balance=5200, dpd=0, response=71, priority="P1",
         last_payment=cycle_dates(1)[0].isoformat(), intervention="Proactive supportive outreach", promise=None,
         expected_value=3692, stage="Pre-Delinquency"),
]
for i, m in enumerate([m for m in MEMBERS[len(STORY):] if m["pattern"] == "bad"][:3]):
    COLLECTIONS.append(dict(id=f"COL-26{10 + i}", member_id=m["id"], balance=round(m["deduction"] * 4.5, -1) or 1800,
                            dpd=[60, 45, 30][i], response=[58, 62, 49][i], priority=["P2", "P2", "P3"][i],
                            last_payment=cycle_dates(3)[0].isoformat(), intervention="Call + restructure review",
                            promise=None, expected_value=0, stage="Mid Stage" if i < 2 else "Early Stage"))

COMMS = [
    dict(member_id="104310", type="call", title="Outbound call", at=clock_at(3, 10, 15),
         text="Bercakap dengan ahli. Bincang baki tertunggak dan pilihan bantuan kesukaran. Ahli minta masa untuk menimbang.",
         outcome="Contacted"),
    dict(member_id="104310", type="sms", title="SMS sent", at=clock_at(7, 14, 3),
         text="Pautan bayaran dan ringkasan akaun dihantar.", outcome="Delivered"),
    dict(member_id="104291", type="promise", title="Promise to pay", at=clock_at(5, 11, 20),
         text=f"Ahli berjanji membayar RM300 pada {_next.day + 3 if _next.day < 26 else 28} haribulan ini.", outcome="Open"),
    dict(member_id="104310", type="call", title="Outbound call", at=clock_at(16, 16, 10),
         text="Tinggal mesej suara. Tiada jawapan.", outcome="No Answer"),
    dict(member_id="104328", type="email", title="Payment reminder", at=clock_at(12, 9, 0),
         text="Peringatan biasa dihantar sebelum tarikh potongan gaji.", outcome="Opened"),
    dict(member_id="104436", type="call", title="Outbound call", at=clock_at(4, 15, 30),
         text="Ahli maklumkan pencen tidak mencukupi selepas potongan bank. Dirujuk untuk semakan AKPK.",
         outcome="Contacted"),
]


# ------------------------------------------------------------------ trend
def _trend():
    rnd = random.Random(3)
    out = []
    for i in range(15, -1, -1):
        d = TODAY - dt.timedelta(days=i)
        weekend = d.weekday() >= 5
        a = rnd.randint(5, 9) if weekend else rnd.randint(14, 27)
        ap = round(a * rnd.uniform(0.66, 0.78))
        de = max(1, round(a * rnd.uniform(0.12, 0.24)))
        out.append({"d": f"{d.day} {['Jan','Feb','Mac','Apr','Mei','Jun','Jul','Ogo','Sep','Okt','Nov','Dis'][d.month-1]}",
                    "date": d.isoformat(), "a": a, "ap": ap, "de": de})
    return out


TREND = _trend()

# ---------------------------------------------------------------- policies
POLICY_LIBRARY = [
    dict(id="POL-001", version="v4.0", title="Affordability — Debt Service Ratio",
         text="Total monthly financing commitments including the proposed instalment must not exceed the product "
              "DSR ceiling of the member's verified net monthly income (gross pay less statutory and other "
              "non-financing deductions). Personal, Express, Fees and Term Financing-i 40%; SME and Contract "
              "Financing-i 45%."),
    dict(id="POL-002", version="v4.0", title="Membership Tenure",
         text="Minimum KT membership: 6 months for Personal, Express and Fees Financing-i; 12 months for Term "
              "Financing-i; 24 months for SME and Contract Financing-i."),
    dict(id="POL-003", version="v4.0", title="Income Verification Variance",
         text="Where verified income (payslip, or bank salary credits plus payroll financing deductions) differs "
              "from declared income by more than 10%, the lower verified figure is used and the case is routed to "
              "officer review with the variance disclosed."),
    dict(id="POL-004", version="v4.0", title="Exposure Limit",
         text="Aggregate member exposure to KT may not exceed 4x savings (Simpanan) plus share capital (Modal Syer) "
              "without senior officer approval."),
    dict(id="POL-005", version="v4.0", title="Approval Authority Bands",
         text="Credit Officer up to RM30,000. Senior Officer up to RM100,000. Credit Committee (chaired by the "
              "Branch Manager) up to RM250,000; Board above. Autonomous execution only within the Board-set "
              "Autonomy Dial limits."),
    dict(id="POL-006", version="v4.0", title="Integrity Escalation",
         text="A high anomaly score is an investigation signal, not a finding of fraud. Cases with critical "
              "integrity signals route to Fraud Review and may not be auto-executed."),
    dict(id="POL-007", version="v4.0", title="Hardship and Rescheduling",
         text="Members showing early deterioration receive the least intrusive effective intervention. Supportive "
              "outreach, rescheduling and AKPK counselling referral precede formal collection where prior conduct "
              "was good. Ta'widh (late-payment compensation) follows Bank Negara Malaysia guidance."),
    dict(id="POL-008", version="v4.0", title="Document Requirements",
         text="Each product defines a mandatory evidence set. A case may not be approved with mandatory evidence "
              "missing unless a documented exception is recorded by a senior officer."),
    dict(id="POL-009", version="v4.0", title="Product Amount Limits",
         text="Requested financing must lie within the product's minimum and maximum amount."),
    dict(id="POL-010", version="v4.0", title="Financing Tenure Limits",
         text="Tenure must lie within the product's term range and, for salary-deduction products, should not "
              "extend beyond the member's compulsory retirement date without a pension-deduction mandate."),
    dict(id="POL-011", version="v4.0", title="Salary Deduction Cap (60% of gross)",
         text="For salary- and pension-deduction products, total deductions (statutory, other and all financing "
              "including the new instalment) may not exceed 60% of gross monthly pay, in line with the government "
              "rule applied through Biro ANGKASA."),
    dict(id="POL-012", version="v4.0", title="Eligibility — Service Status and Minimum Income",
         text="Applicants must be permanent and confirmed ATM personnel or MINDEF civil servants, or pensioners, "
              "with gross monthly income of at least RM2,000 for Personal and Express Financing-i."),
    dict(id="POL-013", version="v4.0", title="Sensitive Analytics — Financial Distress and Cross-selling",
         text="Financial-distress (possible bankruptcy) indicators and cross-selling suggestions are decision "
              "support for authorised officers only. They never trigger automatic adverse action, every view is "
              "logged, and outreach respects the member's marketing consent."),
]
