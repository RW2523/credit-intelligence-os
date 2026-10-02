import lang as L


def test_detects_malay_and_english():
    assert L.detect("Berapa baki pinjaman saya dan bila bayaran seterusnya?") == "ms"
    assert L.detect("How much is my loan balance and when is the next payment?") == "en"


def test_flags_indonesian():
    txt = "Saya tidak dapat memberikan informasi tentang pinjaman Anda. Anda dapat menghubungi Officer Review."
    hits = L.indonesian_hits(txt)
    assert "informasi" in hits and "Anda" in hits


def test_normalises_to_malaysian():
    out = L.normalise_ms("Saya tidak bisa memberikan informasi karena kabar Anda belum diterima.")
    assert "boleh" in out and "maklumat" in out and "kerana" in out and "khabar" in out
    assert not L.indonesian_hits(out)
