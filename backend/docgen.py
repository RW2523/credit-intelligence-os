"""Demo evidence generator.

Builds the documents behind every seeded case — payslips, bank statements, service letters, identity
cards, ANGKASA deduction schedules, SSM records, income statements, quotations — in Malaysian form,
and records the exact position of every value it draws. The viewer reads those positions, so a
highlighted field always lands on the value it came from, and the extracted value always matches the
document text.

Every document carries a SPECIMEN watermark and is synthetic. Files are written to data/docs and
regenerated whenever the demo day changes, so pay periods and statement dates stay current.
"""
from __future__ import annotations
import os, io, csv, json, hashlib, datetime as dt

from clock import TODAY, add_months
import fmt
import seed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "docs")
MANIFEST = os.path.join(OUT, "manifest.json")
VERSION = "kt-docs-5"

BANK = "Bank Setia Perwira Berhad"          # fictional
SPECIMEN = "SPECIMEN · DATA SINTETIK"
FOOT = "Dokumen sintetik untuk demonstrasi KT Credit Intelligence sahaja · Synthetic demo document"


def _rm(x, d=2):
    return fmt.rm(x, d)


# =================================================================== PDFs
class Page:
    """A single A4 page that records the bounding box of every value it draws (as % of the page)."""

    def __init__(self, path: str, title: str):
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        self.c = canvas.Canvas(path, pagesize=A4, pageCompression=1)
        self.c.setTitle(title)
        self.c.setAuthor("KT Credit Intelligence demo generator")
        self.c.setSubject(SPECIMEN)
        self.W, self.H = A4
        self.fields: list[dict] = []

    def _w(self, s, size, bold=False):
        from reportlab.pdfbase.pdfmetrics import stringWidth
        return stringWidth(str(s), "Helvetica-Bold" if bold else "Helvetica", size)

    def text(self, x, y, s, size=9.5, bold=False, align="left", color=(0.12, 0.14, 0.18)):
        self.c.setFillColorRGB(*color)
        self.c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        s = str(s)
        if align == "right":
            self.c.drawRightString(x, y, s)
        elif align == "center":
            self.c.drawCentredString(x, y, s)
        else:
            self.c.drawString(x, y, s)

    def value(self, key, x, y, s, size=9.5, bold=False, align="left", conf=97, shown=None):
        """Draw a value and record where it is. `shown` lets the extracted value differ in format."""
        s = str(s)
        self.text(x, y, s, size, bold, align)
        w = self._w(s, size, bold)
        x0 = x - w if align == "right" else (x - w / 2 if align == "center" else x)
        pad = 2.5
        top = self.H - (y + size * 0.80) - pad
        h = size * 1.05 + 2 * pad
        self.fields.append(dict(k=key, v=shown if shown is not None else s, src=s, c=conf, page=1,
                                bbox=[round((x0 - pad) / self.W * 100, 2), round(top / self.H * 100, 2),
                                      round((w + 2 * pad) / self.W * 100, 2), round(h / self.H * 100, 2)]))

    def rule(self, y, x0=40, x1=None, wgt=0.6, grey=0.75):
        self.c.setStrokeColorRGB(grey, grey, grey)
        self.c.setLineWidth(wgt)
        self.c.line(x0, y, x1 or self.W - 40, y)

    def band(self, y, h, rgb=(0.11, 0.30, 0.23)):
        self.c.setFillColorRGB(*rgb)
        self.c.rect(0, y, self.W, h, stroke=0, fill=1)

    def box(self, x, y, w, h, grey=0.95):
        self.c.setFillColorRGB(grey, grey, grey)
        self.c.setStrokeColorRGB(0.82, 0.82, 0.82)
        self.c.rect(x, y, w, h, stroke=1, fill=1)

    def finish(self):
        c = self.c
        c.saveState()
        c.setFillColorRGB(0.85, 0.20, 0.20, alpha=0.10)
        c.setFont("Helvetica-Bold", 54)
        c.translate(self.W / 2, self.H / 2)
        c.rotate(32)
        c.drawCentredString(0, 0, "SPECIMEN")
        c.restoreState()
        self.text(self.W / 2, 22, FOOT, size=7, align="center", color=(0.45, 0.45, 0.45))
        c.showPage()
        c.save()
        return self.fields


def _header(p: Page, l1: str, l2: str, l3: str = ""):
    p.band(p.H - 74, 74)
    p.text(40, p.H - 34, l1, 13, True, color=(1, 1, 1))
    p.text(40, p.H - 52, l2, 9.5, color=(0.86, 0.92, 0.88))
    if l3:
        p.text(p.W - 40, p.H - 34, l3, 8.5, align="right", color=(0.95, 0.85, 0.55))
    p.text(p.W - 40, p.H - 52, SPECIMEN, 8, True, align="right", color=(0.95, 0.85, 0.55))


def _kv(p: Page, y, label, key, value, x=40, vx=190, conf=97, bold=False, shown=None):
    p.text(x, y, label, 9, color=(0.40, 0.42, 0.46))
    if key:
        p.value(key, vx, y, value, 9.5, bold=bold, conf=conf, shown=shown)
    else:
        p.text(vx, y, value, 9.5, bold)


# ---------------------------------------------------------------- payslip
def _pay_lines(m: dict) -> tuple[list, list, list]:
    gross, other = m["gross_monthly"], m["other_deductions"]
    basic = round(gross * 0.68 - (gross * 0.68) % 10, 2)
    itp, itka, cola = 300.0, 160.0, 300.0
    allow = round(gross - basic - itp - itka - cola, 2)
    earn = [("Gaji Pokok", basic), ("Imbuhan Tetap Perumahan (ITP)", itp),
            ("Imbuhan Tetap Khidmat Awam (ITKA)", itka), ("Bantuan Sara Hidup (COLA)", cola),
            ("Elaun Perkhidmatan", allow)]
    muslim = any(t in m["full_name"] for t in (" bin ", " binti "))
    serving_or = m["member_type"] == "serving" and not any(m["rank"].startswith(r) for r in ("Lt", "Kapt", "Mej"))
    # statutory first, at realistic levels; the member's remaining non-financing deductions are the
    # voluntary and household items a government payslip typically carries
    parts = [("Potongan Cukai Bulanan (PCB)", round(max(0.0, gross * 12 - 42000) * 0.045 / 12, 2))]
    if serving_or:
        parts.append(("Caruman LTAT", round(basic * 0.10, 2)))
    if muslim:
        parts.append(("Zakat", round(min(120.0, gross * 0.015), 2)))
    parts.append(("Khairat Kematian", 15.0))
    fill = ([("Perintah Nafkah Mahkamah", 500.0)] if m.get("other_note") else []) + \
        ([("Sewa Kuarters", 280.0)] if m["member_type"] == "serving" else []) + \
        ([("Tabung Haji", 200.0)] if muslim else []) + [("Takaful Keluarga", 180.0)]
    left = round(other - sum(v for _, v in parts), 2)
    for k, cap in fill:
        if left <= 0:
            break
        take = round(min(cap, left), 2)
        parts.append((k, take)); left = round(left - take, 2)
    if left > 0:
        parts.append(("Potongan lain (persatuan, kebajikan)", left))
    elif left < 0:                                       # small payslips: scale statutory items to fit
        scale = other / max(1.0, sum(v for _, v in parts))
        parts = [(k, round(v * scale, 2)) for k, v in parts]
        parts[-1] = (parts[-1][0], round(other - sum(v for _, v in parts[:-1]), 2))
    fin = [("Koperasi Tentera (KT)", float(m["deduction"]))] if m["deduction"] else []
    if m["external_deductions"]:
        fin.append(("Biro ANGKASA — pembiayaan lain", float(m["external_deductions"])))
    return earn, parts, fin


def payslip(path: str, m: dict) -> list[dict]:
    period = add_months(TODAY, -1 if TODAY.day < seed.PAYDAY else 0, 1)
    employer = m["employer"]
    p = Page(path, f"Slip Gaji {fmt.month(period, 'ms')}")
    _header(p, "ANGKATAN TENTERA MALAYSIA" if m["member_type"] == "serving" else "KEMENTERIAN PERTAHANAN MALAYSIA",
            "Penyata Gaji Bulanan · Monthly Pay Statement", m["service_label"])
    p.value("Employer", 40, p.H - 96, employer, 9, True, conf=96)
    y = p.H - 124
    _kv(p, y, "Nama", "Employee Name", m["full_name"].upper(), conf=98, bold=True); y -= 16
    _kv(p, y, "No. Kad Pengenalan", None, m["mykad"]); y -= 16
    _kv(p, y, "No. Tentera / Pekerja", "Service No", m["service_no"], conf=99); y -= 16
    _kv(p, y, "Pangkat / Gred", "Rank / Grade", m["rank"], conf=97); y -= 16
    _kv(p, y, "Pasukan / Jabatan", None, m["unit"]); y -= 16
    _kv(p, y, "Bulan Gaji", "Pay Period", fmt.month(period, "ms"), conf=99); y -= 26
    earn, other, fin = _pay_lines(m)
    p.rule(y + 10)
    p.text(40, y - 4, "PENDAPATAN", 8.5, True); p.text(300, y - 4, "POTONGAN", 8.5, True)
    p.text(270, y - 4, "RM", 8, True, align="right"); p.text(p.W - 40, y - 4, "RM", 8, True, align="right")
    y -= 20
    ye = y
    for k, v in earn:
        p.text(40, ye, k, 9); p.text(270, ye, f"{v:,.2f}", 9, align="right"); ye -= 15
    yd = y
    for k, v in other:
        p.text(300, yd, k, 9); p.text(p.W - 40, yd, f"{v:,.2f}", 9, align="right"); yd -= 15
    p.text(300, yd, "Jumlah potongan statutori & lain-lain", 8.5, True)
    p.value("Other Deductions", p.W - 40, yd, f"{m['other_deductions']:,.2f}", 9, True, "right", conf=96,
            shown=_rm(m["other_deductions"]))
    yd -= 20
    p.text(300, yd, "Potongan pembiayaan", 8.5, True, color=(0.40, 0.42, 0.46)); yd -= 15
    for k, v in fin:
        p.text(300, yd, k, 9)
        if k.startswith("Koperasi"):
            p.value("KT Deduction", p.W - 40, yd, f"{v:,.2f}", 9, False, "right", conf=99, shown=_rm(v))
        else:
            p.text(p.W - 40, yd, f"{v:,.2f}", 9, align="right")
        yd -= 15
    p.text(300, yd, "Jumlah potongan pembiayaan", 8.5, True)
    p.value("Financing Deductions", p.W - 40, yd, f"{m['financing_deductions']:,.2f}", 9, True, "right",
            conf=98, shown=_rm(m["financing_deductions"]))
    ye = min(ye, yd) - 18
    p.rule(ye + 10)
    p.text(40, ye - 4, "JUMLAH PENDAPATAN KASAR", 9, True)
    p.value("Gross Monthly", 270, ye - 4, f"{m['gross_monthly']:,.2f}", 9.5, True, "right", conf=97,
            shown=_rm(m["gross_monthly"]))
    p.text(300, ye - 4, "JUMLAH POTONGAN", 9, True)
    p.text(p.W - 40, ye - 4, f"{m['other_deductions'] + m['financing_deductions']:,.2f}", 9.5, True, "right")
    ye -= 34
    p.box(40, ye - 10, p.W - 80, 30)
    p.text(52, ye, "GAJI BERSIH (NET PAY)", 11, True)
    p.value("Net Pay", p.W - 52, ye, f"RM {m['take_home']:,.2f}", 12, True, "right", conf=98,
            shown=_rm(m["take_home"]))
    p.text(40, ye - 34, f"Kredit ke akaun: {BANK} · ****{m['id'][-4:]}", 8.5, color=(0.40, 0.42, 0.46))
    p.text(40, ye - 48, f"Potongan pembiayaan diremit melalui {m['repayment_channel']}.", 8.5,
           color=(0.40, 0.42, 0.46))
    return p.finish()


# ------------------------------------------------------------ bank statement
def bank_statement(path: str, m: dict, business: bool) -> list[dict]:
    months = [add_months(TODAY, -i, 1) for i in (3, 2, 1)]
    start, end = months[0], add_months(months[-1], 1, 1) - dt.timedelta(days=1)
    if business:
        credit = round(m["bank_income"] / 12, 2)
        label, key = "Kredit perniagaan", "Avg Monthly Business Credit"
    else:
        credit = round(m["bank_income"] / 12 - m["financing_deductions"], 2)
        label, key = "Kredit gaji", "Avg Monthly Salary Credit"
    p = Page(path, "Penyata Akaun")
    _header(p, BANK.upper(), "Penyata Akaun Semasa-i · Current Account-i Statement", "Fiktif / Fictional bank")
    y = p.H - 104
    _kv(p, y, "Pemegang akaun", "Account Holder", (m.get("business") if business else m["full_name"]).upper(),
        conf=98, bold=True); y -= 16
    _kv(p, y, "No. akaun", "Account Number", f"5621 0{m['id'][:2]} ****{m['id'][-4:]}", conf=99,
        shown=f"****{m['id'][-4:]}"); y -= 16
    _kv(p, y, "Tempoh penyata", "Statement Period", f"{fmt.date(start, 'ms')} – {fmt.date(end, 'ms')}", conf=99); y -= 26
    p.text(40, y, "TARIKH", 8, True); p.text(110, y, "BUTIRAN", 8, True)
    p.text(390, y, "DEBIT", 8, True, align="right"); p.text(470, y, "KREDIT", 8, True, align="right")
    p.text(p.W - 40, y, "BAKI", 8, True, align="right")
    p.rule(y - 5); y -= 18
    bal = round(credit * 0.9 + 850, 2)                    # an account that never dips into overdraft
    lowest = bal
    rows = []
    for mo in months:
        pay = dt.date(mo.year, mo.month, seed.PAYDAY)
        rows += [(dt.date(mo.year, mo.month, 3), "Bil utiliti TNB / Air", -round(credit * 0.06, 2)),
                 (dt.date(mo.year, mo.month, 8), "Pemindahan DuitNow", -round(credit * 0.22, 2)),
                 (dt.date(mo.year, mo.month, 15), "Pembelian kad debit", -round(credit * 0.31, 2)),
                 (pay, f"{label} — {'ATM/JANM' if not business else 'pelanggan'}", credit),
                 (dt.date(mo.year, mo.month, 27), "Pengeluaran ATM", -round(credit * 0.28, 2))]
    for d, desc, amt in rows:
        bal = round(bal + amt, 2)
        lowest = min(lowest, bal)
        p.text(40, y, fmt.date(d, "ms"), 8.5); p.text(110, y, desc, 8.5)
        if amt < 0:
            p.text(390, y, f"{-amt:,.2f}", 8.5, align="right")
        else:
            p.text(470, y, f"{amt:,.2f}", 8.5, align="right")
        p.text(p.W - 40, y, f"{bal:,.2f}", 8.5, align="right")
        y -= 13.5
    y -= 12
    p.box(40, y - 64, p.W - 80, 74)
    p.text(52, y - 6, "RINGKASAN 90 HARI · 90-DAY SUMMARY", 8.5, True)
    p.text(52, y - 24, f"Purata {label.lower()} bulanan", 9)
    p.value(key, 300, y - 24, f"RM {credit:,.2f}", 9.5, True, conf=95, shown=_rm(credit))
    p.text(52, y - 40, "Baki terendah", 9)
    p.value("Lowest Balance", 300, y - 40, f"RM {lowest:,.2f}", 9.5, conf=94, shown=_rm(lowest))
    p.text(52, y - 56, "Cek / debit dipulangkan", 9)
    returned = "0" if m["reliability"] >= 85 or business else "2"
    p.value("Returned Items (90d)", 300, y - 56, returned, 9.5, conf=99)
    return p.finish()


# -------------------------------------------------------- service letter
def service_letter(path: str, m: dict, ref_day: dt.date) -> list[dict]:
    p = Page(path, "Surat Pengesahan Perkhidmatan")
    civil = m["member_type"] == "civil"
    _header(p, "KEMENTERIAN PERTAHANAN MALAYSIA" if civil else f"MARKAS {m['unit'].upper()}"[:60],
            m["camp"], m["service_label"])
    p.value("Employer", 40, p.H - 96, m["employer"], 9, True, conf=97)
    y = p.H - 126
    p.text(40, y, f"Ruj. Kami: KT/SP/{m['id']}/{ref_day.year}", 9)
    p.text(p.W - 40, y, f"Tarikh: {fmt.date(ref_day, 'ms')}", 9, align="right"); y -= 30
    p.text(40, y, "Kepada: Pengurus Kredit, Koperasi Angkatan Tentera Malaysia Berhad", 9.5); y -= 26
    p.text(40, y, "SURAT PENGESAHAN PERKHIDMATAN", 11, True); y -= 22
    p.text(40, y, "Adalah disahkan bahawa anggota/pegawai di bawah berkhidmat di jabatan ini:", 9.5); y -= 24
    _kv(p, y, "Nama", "Employee Name", m["full_name"].upper(), conf=98, bold=True); y -= 17
    _kv(p, y, "No. Kad Pengenalan", None, m["mykad"]); y -= 17
    _kv(p, y, "No. Tentera / Pekerja", "Service No", m["service_no"], conf=99); y -= 17
    _kv(p, y, "Pangkat / Gred", "Rank / Grade", m["rank"], conf=97); y -= 17
    _kv(p, y, "Pasukan / Jabatan", "Unit", m["unit"], conf=95); y -= 17
    _kv(p, y, "Taraf perkhidmatan", "Service Status", "Tetap dan Disahkan", conf=97); y -= 17
    _kv(p, y, "Tarikh mula berkhidmat", "Enlistment Date", fmt.date(m["enlisted"], "ms"), conf=96); y -= 17
    _kv(p, y, "Tarikh bersara wajib", "Retirement Date", fmt.date(m["retirement_date"], "ms"), conf=95); y -= 30
    p.text(40, y, "Pihak kami tiada halangan untuk potongan gaji bagi tujuan pembiayaan melalui Biro ANGKASA.", 9.5)
    y -= 40
    p.text(40, y, "Sekian, terima kasih.", 9.5); y -= 36
    p.text(40, y, "(tandatangan)", 9, color=(0.5, 0.5, 0.5)); y -= 14
    p.text(40, y, "Pegawai Memerintah / Ketua Jabatan", 9, True)
    return p.finish()


# ----------------------------------------------------------- business docs
def ssm(path: str, m: dict) -> list[dict]:
    p = Page(path, "Maklumat Pendaftaran Perniagaan")
    _header(p, "MAKLUMAT PENDAFTARAN PERNIAGAAN", "Cetakan maklumat syarikat / perniagaan", "Contoh — bukan dokumen rasmi")
    reg = f"{int(m['since'][:4]) + 3}0{m['id'][-5:]}0{m['id'][2:4]}"
    y = p.H - 112
    _kv(p, y, "Nama perniagaan", "Business Name", m["business"].upper(), conf=97, bold=True); y -= 18
    _kv(p, y, "No. pendaftaran", "Registration No", reg, conf=96); y -= 18
    _kv(p, y, "Pemilik / pengarah", "Owner", m["full_name"].upper(), conf=98); y -= 18
    nature = "Katering dan bekalan makanan" if "Katering" in m["business"] else \
        "Pengangkutan dan logistik" if "Logistik" in m["business"] else "Kerja penyenggaraan bangunan"
    _kv(p, y, "Jenis perniagaan", "Nature of Business", nature, conf=95); y -= 18
    _kv(p, y, "Alamat", None, seed.BRANCH_INFO[m["branch"]]["address"]); y -= 18
    exp = add_months(TODAY, 9, 1)
    _kv(p, y, "Tarikh luput", "Expiry Date", fmt.date(exp, "ms"), conf=97)
    return p.finish()


def income_statement(path: str, m: dict) -> list[dict]:
    fy = TODAY.year - 1
    net = round(m["bank_income"] * 0.97, -2)
    rev = round(net * 3.1, -2)
    p = Page(path, f"Penyata Pendapatan {fy}")
    _header(p, "PENYATA PENDAPATAN · INCOME STATEMENT", m["business"], f"Tahun kewangan {fy}")
    y = p.H - 112
    _kv(p, y, "Entiti", "Entity", m["business"], conf=95, bold=True); y -= 18
    _kv(p, y, "Tempoh", "Period", f"FY{fy}", conf=97); y -= 30
    lines = [("Hasil (Revenue)", rev, "Revenue"), ("Kos jualan", -round(rev * 0.52, -2), None),
             ("Untung kasar", round(rev * 0.48, -2), None), ("Belanja operasi", -round(rev * 0.48 - net, -2), None)]
    for lbl, v, key in lines:
        p.text(40, y, lbl, 9.5)
        if key:
            p.value(key, 400, y, f"{v:,.2f}", 9.5, align="right", conf=93, shown=_rm(v))
        else:
            p.text(400, y, f"{v:,.2f}", 9.5, align="right")
        y -= 17
    p.rule(y + 8, 40, 410)
    p.text(40, y - 6, "UNTUNG BERSIH (Net profit)", 10, True)
    p.value("Net Profit", 400, y - 6, f"{net:,.2f}", 10, True, "right", conf=90, shown=_rm(net))
    p.text(40, y - 40, "Disediakan oleh pemilik; belum diaudit.", 8.5, color=(0.45, 0.45, 0.45))
    return p.finish()


def tax_return(path: str, m: dict) -> list[dict]:
    ya = TODAY.year - 1
    inc = round(m["bank_income"] * 0.97, -2)
    p = Page(path, f"Borang B {ya}")
    _header(p, f"BORANG B — TAHUN TAKSIRAN {ya}", "Ringkasan pendapatan (salinan pembayar cukai)", "Contoh — bukan dokumen rasmi")
    y = p.H - 112
    _kv(p, y, "Nama pembayar cukai", "Taxpayer", m["full_name"].upper(), conf=97, bold=True); y -= 18
    _kv(p, y, "Tahun taksiran", "Year of Assessment", str(ya), conf=99); y -= 18
    _kv(p, y, "Pendapatan berkanun perniagaan", "Business Income", f"RM {inc:,.2f}", conf=94, shown=_rm(inc)); y -= 18
    pension = round(m["gross_monthly"] * 12, -2)
    _kv(p, y, "Pendapatan pencen (dikecualikan)", None, f"RM {pension:,.2f}"); y -= 18
    _kv(p, y, "Jumlah pendapatan", "Total Income", f"RM {inc:,.2f}", conf=94, shown=_rm(inc))
    return p.finish()


def quotation(path: str, m: dict, a: dict) -> list[dict]:
    vehicle = a["product"] == "Term Financing-i" or "Vehicle" in a["purpose"] or "Car" in a["purpose"]
    supplier = "Perwira Motor Sdn Bhd (fiktif)" if vehicle else "Dapur Niaga Bekalan Sdn Bhd (fiktif)"
    item = ("Perodua Ativa 1.0 AV (baharu)" if a["amount"] < 40000 else "Toyota Corolla Cross 1.8V") if vehicle \
        else "Set peralatan dapur komersial (6 item)"
    price = round(a["amount"] * (1.12 if vehicle else 1.05), -2)
    qd = TODAY - dt.timedelta(days=9)
    p = Page(path, "Sebut Harga")
    _header(p, "SEBUT HARGA · QUOTATION", supplier, f"No. SH-{a['id'][-5:]}")
    y = p.H - 112
    _kv(p, y, "Pembekal", "Supplier", supplier, conf=96, bold=True); y -= 18
    _kv(p, y, "Kepada", None, m["full_name"].upper()); y -= 18
    _kv(p, y, "Tarikh", "Quotation Date", fmt.date(qd, "ms"), conf=98); y -= 30
    _kv(p, y, "Butiran", "Item", item, conf=95); y -= 18
    _kv(p, y, "Harga (termasuk SST)", "Quoted Price", f"RM {price:,.2f}", conf=97, bold=True, shown=_rm(price))
    y -= 30
    p.text(40, y, "Sah selama 30 hari dari tarikh sebut harga.", 8.5, color=(0.45, 0.45, 0.45))
    return p.finish()


def fee_statement(path: str, m: dict, a: dict) -> list[dict]:
    inst = "Kolej Universiti Perwira (fiktif)"
    prog = "Sarjana Pengurusan Strategik" if "Master" in a["purpose"] else "Diploma Pengurusan Perniagaan"
    student = m["full_name"] if "Master" in a["purpose"] else f"Anak kepada {m['full_name']}"
    fees = round(a["amount"] * 1.04, -2)
    p = Page(path, "Penyata Yuran")
    _header(p, "PENYATA YURAN · FEE STATEMENT", inst, f"Sesi {TODAY.year}/{TODAY.year + 1}")
    y = p.H - 112
    _kv(p, y, "Pelajar", "Student", student.upper(), conf=96, bold=True); y -= 18
    _kv(p, y, "Institusi", "Institution", inst, conf=97); y -= 18
    _kv(p, y, "Program", "Programme", prog, conf=96); y -= 18
    _kv(p, y, "Jumlah yuran program", "Total Fees", f"RM {fees:,.2f}", conf=97, bold=True, shown=_rm(fees))
    return p.finish()


def contract_letter(path: str, m: dict, a: dict) -> list[dict]:
    value = round(a["amount"] * 2.6, -3)
    p = Page(path, "Surat Setuju Terima")
    _header(p, "SURAT SETUJU TERIMA (SST)", "Jabatan Kejuruteraan Kem — contoh", f"Ruj. JKK/{TODAY.year}/{a['id'][-4:]}")
    y = p.H - 112
    _kv(p, y, "Kontraktor", "Contractor", m["business"].upper(), conf=97, bold=True); y -= 18
    _kv(p, y, "No. kontrak", "Contract No", f"JKK/PK/{TODAY.year}/0{a['id'][-3:]}", conf=98); y -= 18
    _kv(p, y, "Skop", None, "Penyenggaraan berkala berek dan bangunan kem"); y -= 18
    _kv(p, y, "Nilai kontrak", "Contract Value", f"RM {value:,.2f}", conf=96, bold=True, shown=_rm(value)); y -= 18
    _kv(p, y, "Tempoh", "Duration", "24 bulan", conf=97)
    return p.finish()


# ================================================================ images
def identity_card(path: str, m: dict) -> list[dict]:
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1012, 638

    def font(sz, bold=False):
        for f in (f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
                  "/System/Library/Fonts/Supplemental/Arial.ttf"):
            if os.path.exists(f):
                return ImageFont.truetype(f, sz)
        return ImageFont.load_default(size=sz)

    img = Image.new("RGB", (W, H), (226, 238, 246))
    d = ImageDraw.Draw(img)
    for i in range(0, H, 6):
        d.line([(0, i), (W, i)], fill=(218, 231, 241))
    d.rectangle([0, 0, W, 86], fill=(24, 74, 110))
    d.text((34, 22), "KAD PENGENALAN · IDENTITY CARD", font=font(30, True), fill=(255, 255, 255))
    d.text((W - 34, 30), "SPECIMEN", font=font(24, True), fill=(250, 210, 120), anchor="ra")
    d.rectangle([40, 130, 300, 450], fill=(200, 212, 224), outline=(150, 165, 180), width=3)
    d.ellipse([110, 170, 230, 290], fill=(150, 166, 182))
    d.rectangle([95, 300, 245, 440], fill=(150, 166, 182))
    fields = []

    def put(key, x, y, text, sz=30, bold=True, conf=98):
        f = font(sz, bold)
        d.text((x, y), text, font=f, fill=(20, 30, 40))
        x0, y0, x1, y1 = d.textbbox((x, y), text, font=f)
        pad = 6
        fields.append(dict(k=key, v=text, c=conf, page=1,
                           bbox=[round((x0 - pad) / W * 100, 2), round((y0 - pad) / H * 100, 2),
                                 round((x1 - x0 + 2 * pad) / W * 100, 2), round((y1 - y0 + 2 * pad) / H * 100, 2)]))

    put("MyKad No.", 340, 140, m["mykad"], 40, True, 99)
    name = m["full_name"].upper()
    lines, cur = [], ""
    for w in name.split():
        if len(cur) + len(w) + 1 > 24:
            lines.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    lines.append(cur)
    y = 230
    d.text((340, 200), "NAMA", font=font(18), fill=(80, 90, 100))
    for i, ln in enumerate(lines):
        put("Full Name" if i == 0 else f"Full Name (line {i + 1})", 340, y, ln, 32, True, 99)
        y += 42
    if len(lines) > 1:                                  # one field, one box spanning both lines
        a_, b_ = fields[-len(lines)], fields[-1]
        top, left = a_["bbox"][1], min(a_["bbox"][0], b_["bbox"][0])
        right = max(a_["bbox"][0] + a_["bbox"][2], b_["bbox"][0] + b_["bbox"][2])
        bottom = b_["bbox"][1] + b_["bbox"][3]
        del fields[-len(lines):]
        fields.append(dict(k="Full Name", v=name, c=99, page=1,
                           bbox=[left, top, round(right - left, 2), round(bottom - top, 2)]))
    dob = dt.date.fromisoformat(m["dob"])
    d.text((340, y + 20), "TARIKH LAHIR", font=font(18), fill=(80, 90, 100))
    put("Date of Birth", 340, y + 44, fmt.date(dob, "ms").upper(), 28, False, 97)
    d.text((340, y + 100), "WARGANEGARA", font=font(24, True), fill=(20, 30, 40))
    d.text((W / 2, H - 30), "Data sintetik untuk demonstrasi · Synthetic demo data", font=font(16), fill=(90, 100, 110),
           anchor="ma")
    img.save(path, "PNG", optimize=True)
    return fields


# =================================================================== CSVs
def angkasa_schedule(path: str, m: dict, payments: list[dict]) -> list[dict]:
    rows = [["bulan", "no_anggota", "nama", "amaun_potongan_rm", "tarikh_remit", "status"]]
    if not payments:                                    # first KT financing: a new mandate, no history yet
        rows.append([seed.next_deduction_date().strftime("%Y-%m"), m["id"], m["full_name"].upper(), "0.00", "",
                     "MANDAT BAHARU"])
        with open(path, "w", newline="") as fh:
            csv.writer(fh).writerows(rows)
        return [dict(k="Member", v=m["full_name"].upper(), c=100, page=1, rows=[1]),
                dict(k="Deduction Amount", v=_rm(0), c=100, page=1, rows=[1]),
                dict(k="Remittance Regularity", v="New mandate — no KT deduction history", c=100, page=1, rows=[1])]
    recent = payments[-6:]
    delays = [i for i, p in enumerate(recent) if p["days_late"] > 2]
    for p in recent:
        due = dt.date.fromisoformat(p["month"])
        rem = due + dt.timedelta(days=p["days_late"])
        rows.append([due.strftime("%Y-%m"), m["id"], m["full_name"].upper(), f"{p['amount_due']:.2f}",
                     rem.isoformat(), "LEWAT" if p["days_late"] > 2 else "DIREMIT"])
    with open(path, "w", newline="") as fh:
        csv.writer(fh).writerows(rows)
    reg = "Regular" if not delays else f"{len(delays)} delayed remittance(s) in the last {len(recent)} cycles"
    return [dict(k="Member", v=m["full_name"].upper(), c=100, page=1, rows=[1]),
            dict(k="Deduction Amount", v=_rm(m["deduction"]), c=100, page=1, rows=list(range(1, len(rows)))),
            dict(k="Remittance Regularity", v=reg, c=100, page=1,
                 rows=[i + 1 for i in delays] or list(range(1, len(rows))))]


def payment_history(path: str, m: dict, payments: list[dict]) -> list[dict]:
    rows = [["kitaran", "amaun_perlu_rm", "amaun_dibayar_rm", "hari_lewat", "saluran"]]
    if not payments:                                    # no KT financing yet — the record says so
        rows.append(["—", "0.00", "0.00", "0", "tiada pembiayaan KT"])
        with open(path, "w", newline="") as fh:
            csv.writer(fh).writerows(rows)
        return [dict(k="Records", v="No KT financing history", c=100, page=1, rows=[1])]
    for p in payments:
        rows.append([p["month"], f"{p['amount_due']:.2f}", f"{p['amount_paid']:.2f}", p["days_late"], p["channel"]])
    with open(path, "w", newline="") as fh:
        csv.writer(fh).writerows(rows)
    lates = [p["days_late"] for p in payments]
    ontime = round(sum(1 for x in lates if x <= 2) / max(1, len(lates)) * 100, 1)
    worst = max(lates) if lates else 0
    return [dict(k="Records", v=f"{len(payments)} months", c=100, page=1, rows=list(range(1, len(rows)))),
            dict(k="On-time Rate", v=f"{ontime}%", c=100, page=1,
                 rows=[i + 1 for i, x in enumerate(lates) if x <= 2]),
            dict(k="Max Days Late", v=str(worst), c=100, page=1,
                 rows=[i + 1 for i, x in enumerate(lates) if x == worst and worst > 0] or [len(rows) - 1])]


# ============================================================ orchestration
_LABEL = {
    "Payslip": lambda a: f"slip_gaji_{fmt.month(add_months(TODAY, -1 if TODAY.day < seed.PAYDAY else 0, 1), 'en')[:3].lower()}{TODAY.year}.pdf",
    "Bank Statement": lambda a: "penyata_bank_3bulan.pdf",
    "Service Confirmation": lambda a: "surat_pengesahan_perkhidmatan.pdf",
    "Identity Card": lambda a: "kad_pengenalan.png",
    "Salary Deduction Mandate": lambda a: "jadual_potongan_angkasa.csv",
    "Payment History": lambda a: "sejarah_bayaran.csv",
    "SSM Registration": lambda a: "maklumat_ssm.pdf",
    "Income Statement": lambda a: f"penyata_pendapatan_{TODAY.year - 1}.pdf",
    "Tax Return": lambda a: f"borang_b_{TODAY.year - 1}.pdf",
    "Quotation": lambda a: "sebut_harga.pdf",
    "Fee Statement": lambda a: "penyata_yuran.pdf",
    "Contract Award Letter": lambda a: "surat_setuju_terima.pdf",
}
_PRODUCER = {"Payslip": "e-Penyata Gaji export", "Bank Statement": f"{BANK} e-Statement",
             "Service Confirmation": "Microsoft Word", "Identity Card": "Scanner",
             "Salary Deduction Mandate": "Biro ANGKASA feed", "Payment History": "KT core system",
             "SSM Registration": "Portal cetakan", "Income Statement": "Microsoft Excel",
             "Tax Return": "Salinan pembayar cukai", "Quotation": "Pembekal", "Fee Statement": "Portal pelajar",
             "Contract Award Letter": "Microsoft Word"}
# documents a reviewer should look at again (the stories behind "Needs Review")
_REVIEW = {("APP-104188", "Income Statement"): (92, 88), ("APP-104265", "Bank Statement"): (91, 90)}


def _make(kind: str, path: str, m: dict, a: dict, payments: list[dict]) -> list[dict]:
    business = not seed.PRODUCTS[a["product"]]["salary_deduction"]
    return {
        "Payslip": lambda: payslip(path, m),
        "Bank Statement": lambda: bank_statement(path, m, business),
        "Service Confirmation": lambda: service_letter(path, m, TODAY - dt.timedelta(days=12)),
        "Identity Card": lambda: identity_card(path, m),
        "Salary Deduction Mandate": lambda: angkasa_schedule(path, m, payments),
        "Payment History": lambda: payment_history(path, m, payments),
        "SSM Registration": lambda: ssm(path, m),
        "Income Statement": lambda: income_statement(path, m),
        "Tax Return": lambda: tax_return(path, m),
        "Quotation": lambda: quotation(path, m, a),
        "Fee Statement": lambda: fee_statement(path, m, a),
        "Contract Award Letter": lambda: contract_letter(path, m, a),
    }[kind]()


def build(members_by_id: dict, applications: list[dict]) -> list[dict]:
    os.makedirs(OUT, exist_ok=True)
    docs, n = [], 1000
    for a in applications:
        m = members_by_id[a["member_id"]]
        missing = seed.MISSING.get(a["id"], [])
        payments = m.get("payments") or []
        sub = dt.datetime.fromisoformat(a["submitted"])
        for j, kind in enumerate(seed.PRODUCTS[a["product"]]["docs"]):
            if kind in missing:
                continue
            n += 1
            label = _LABEL[kind](a)
            fname = f"{m['id']}_{label}"
            path = os.path.join(OUT, fname)
            fields = _make(kind, path, m, a, payments)
            conf, font = _REVIEW.get((a["id"], kind), (99 if kind in ("Identity Card", "Payment History",
                                                                        "Salary Deduction Mandate") else 97, 98))
            docs.append(dict(
                id=f"DOC-{n}", app_id=a["id"], member_id=m["id"], file=fname, label=label, doc_type=kind,
                doc_type_ms=seed.DOC_MS.get(kind, kind), status="Verified" if conf >= 94 else "Needs Review",
                confidence=conf, uploaded=(sub + dt.timedelta(minutes=2 + 3 * j)).isoformat(timespec="seconds"),
                pages=1, forensics=dict(tampering=False, font_consistency=font, metadata_ok=True,
                                        duplicate_hash=False, producer=_PRODUCER[kind]),
                fields=fields, sha256=_sha(path)))
    with open(MANIFEST, "w") as fh:
        json.dump({"version": VERSION, "anchor": TODAY.isoformat(), "docs": docs}, fh, indent=1)
    return docs


def _sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return "sha256:" + h.hexdigest()[:24]


def documents(members_by_id: dict, applications: list[dict]) -> list[dict]:
    """The seeded evidence set — regenerated if the layout version or the demo day changed."""
    try:
        with open(MANIFEST) as fh:
            man = json.load(fh)
        if (man.get("version") == VERSION and man.get("anchor") == TODAY.isoformat()
                and all(os.path.exists(os.path.join(OUT, d["file"])) for d in man["docs"])):
            return man["docs"]
    except (OSError, ValueError):
        pass
    return build(members_by_id, applications)
