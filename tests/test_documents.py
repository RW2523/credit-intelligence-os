"""Every highlight box sits on its value in the generated document, and every value is what is printed."""
import os, sys
import domain, docgen
sys.path.insert(0, os.path.dirname(__file__))
from bbox_check import check


def test_documents_exist():
    docs = domain.seeded_documents()
    assert len(docs) >= 100
    for d in docs:
        assert os.path.exists(os.path.join(docgen.OUT, d["file"])), d["file"]


def test_every_pdf_box_contains_its_value():
    n, bad = check(domain.seeded_documents(), docgen.OUT)
    assert n > 400 and not bad, bad[:5]


def test_csv_fields_point_at_real_rows():
    for d in domain.seeded_documents():
        if d["file"].endswith(".csv"):
            rows = open(os.path.join(docgen.OUT, d["file"])).read().strip().splitlines()
            for f in d["fields"]:
                assert all(1 <= r < len(rows) for r in f["rows"]), (d["file"], f["k"])


def test_no_dollar_values_in_documents():
    for d in domain.seeded_documents():
        for f in d["fields"]:
            assert "$" not in str(f["v"])
