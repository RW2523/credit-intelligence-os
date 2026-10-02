"""Language handling for Bahasa Malaysia and English.

Detects which language a member wrote in, and keeps replies in *Malaysian* Malay: small models drift
into Indonesian ("Anda", "karena", "kabar", "informasi", "Asisten Kebijakan"), which KT's members read
as foreign. The style guide goes into every Malay prompt; indonesian_hits() checks the reply; and
normalise_ms() is the last-resort repair.
"""
from __future__ import annotations
import re

_MS = {"saya", "berapa", "bila", "apa", "baki", "bayaran", "pinjaman", "pembiayaan", "ansuran", "dan", "yang",
       "untuk", "boleh", "tak", "tidak", "ke", "di", "dengan", "ada", "sudah", "belum", "gaji", "potongan",
       "permohonan", "dokumen", "mohon", "nak", "macam", "mana", "bagaimana", "kenapa", "mengapa", "terima",
       "kasih", "tolong", "encik", "puan", "tuan", "hilang", "kerja", "risau", "sakit", "bulan", "depan",
       "seterusnya", "simpanan", "saham", "dividen", "masih", "perlu", "hutang", "akaun", "sila", "boleh",
       "berkenaan", "tentang", "ini", "itu", "kami", "kita", "anda", "awak", "bayar", "jumlah", "lagi", "sahaja",
       "layak", "kelayakan", "cawangan", "bank", "berapakah", "bilakah", "adakah", "mengikut", "senarai",
       "tunjuk", "ahli", "permohonan", "kes", "kenapa", "tertunggak", "lewat", "risiko", "minggu", "hari"}
_EN = {"what", "when", "how", "my", "is", "the", "balance", "payment", "next", "application", "documents",
       "need", "can", "i", "much", "loan", "financing", "of", "and", "to", "do", "you", "still", "lost",
       "job", "worried", "show", "me", "which", "why", "are", "by", "list", "who", "there", "have", "for",
       "please", "will", "about", "does", "status", "members", "cases", "branch", "this", "month", "in"}

STYLE_MS = (
    "Tulis dalam Bahasa Malaysia standard (BUKAN Bahasa Indonesia). Gunakan: 'anda' (huruf kecil di tengah "
    "ayat), 'kerana' (bukan 'karena'), 'khabar' (bukan 'kabar'), 'maklumat' (bukan 'informasi'), 'boleh' "
    "(bukan 'bisa'), 'wang' (bukan 'uang'), 'ansuran' (bukan 'angsuran'), 'akaun' (bukan 'rekening'), "
    "'pejabat' (bukan 'kantor'), 'perlu' (bukan 'butuh'), 'sila' (bukan 'silakan'), 'Pembantu' (bukan "
    "'Asisten'). Untuk produk KT gunakan 'pembiayaan' (bukan 'pinjaman') dan 'kadar keuntungan' (bukan "
    "'bunga'). Tulis amaun sebagai RM18,250 dan tarikh sebagai 25 Okt 2026."
)

# Indonesian marker -> Malaysian replacement
_INDO = {
    "karena": "kerana", "kabar": "khabar", "informasi": "maklumat", "bisa": "boleh", "uang": "wang",
    "angsuran": "ansuran", "rekening": "akaun", "kantor": "pejabat", "butuh": "perlu", "silakan": "sila",
    "asisten": "pembantu", "kebijakan": "dasar", "terimakasih": "terima kasih", "saat ini": "pada masa ini",
    "dapat menghubungi": "boleh menghubungi", "tidak dapat": "tidak boleh", "mohon maaf": "harap maaf",
    "bagaimanapun juga": "walau bagaimanapun", "berhubungan": "berkaitan", "pinjaman anda": "pembiayaan anda",
    "sedangkan": "manakala", "kapan": "bila", "sudah": "sudah", "nanti": "nanti", "segera": "segera",
    # not Indonesian, but a frequent model slip: "simpangan" is a junction, "simpanan" is savings
    "simpangan": "simpanan",
}
_INDO_STRICT = [k for k in _INDO if k not in ("sudah", "nanti", "segera", "pinjaman anda")]


def detect(text: str, default: str = "en") -> str:
    words = re.findall(r"[a-zA-Z']+", (text or "").lower())
    ms = sum(1 for w in words if w in _MS)
    en = sum(1 for w in words if w in _EN)
    if ms == en:
        return default
    return "ms" if ms > en else "en"


def indonesian_hits(text: str) -> list[str]:
    low = (text or "").lower()
    hits = [k for k in _INDO_STRICT if re.search(rf"\b{re.escape(k)}\b", low)]
    # Indonesian style capitalises "Anda" mid-sentence; Malaysian writes "anda"
    if re.search(r"[a-z,]\s+Anda\b", text or ""):
        hits.append("Anda")
    return hits


def normalise_ms(text: str) -> str:
    out = text
    for k, v in _INDO.items():
        if k in _INDO_STRICT:
            out = re.sub(rf"\b{re.escape(k)}\b", v, out)
            out = re.sub(rf"\b{re.escape(k.capitalize())}\b", v.capitalize(), out)
    out = re.sub(r"([a-z,]\s+)Anda\b", r"\1anda", out)
    return out


STATUS_MS = {
    "Officer Review": "Semakan Pegawai", "Documents Pending": "Menunggu Dokumen", "In Verification": "Dalam Pengesahan",
    "Ready to Approve": "Sedia untuk Keputusan", "Credit Analysis": "Analisis Kredit", "Risk Review": "Semakan Risiko",
    "Enhanced Review": "Semakan Terperinci", "Fraud Review": "Semakan Integriti", "Approved": "Diluluskan",
    "Declined": "Tidak Diluluskan", "Escalated": "Dirujuk kepada Pegawai Kanan",
}
