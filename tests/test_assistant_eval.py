"""Live evaluation of the Member Assistant against the local model (BM and EN).

    CIOS_EVAL_LLM=1 .venv/bin/python -m pytest tests/test_assistant_eval.py -s

Each question lists the facts the answer must contain and the things it must never say. The table at
the end is the measure KT asked for: Malay answers that are correct, Malaysian (not Indonesian), and
never confuse the outstanding balance with a pending application.
"""
import os, re, asyncio
import pytest

pytestmark = pytest.mark.skipif(os.environ.get("CIOS_EVAL_LLM") != "1", reason="set CIOS_EVAL_LLM=1 to run")

INDO = re.compile(r"\b(karena|kabar|informasi|bisa|uang|angsuran|rekening|kantor|butuh|silakan|Asisten|kebijakan|simpangan)\b", re.I)
DECISION = re.compile(r"\b(will be approved|you qualify|guaranteed|akan diluluskan|layak mendapat|pasti lulus)\b", re.I)

# (member, question, must contain, must not contain)
EVAL = [
    ("104328", "Berapa baki pinjaman saya dan bila bayaran seterusnya?", ["18,250", "650", "25"], ["25,000"]),
    ("104328", "How much is my loan balance and when is the next payment?", ["18,250", "650"], ["25,000"]),
    ("104328", "What's my outstanding balance?", ["18,250"], []),
    ("104328", "Berapa baki hutang saya dengan KT?", ["18,250"], ["25,000"]),
    ("104328", "Bila potongan gaji seterusnya?", ["650", "25"], []),
    ("104328", "When is my next deduction?", ["650"], []),
    ("104328", "Apa status permohonan saya?", ["Semakan Pegawai"], []),
    ("104328", "What's happening with my application?", ["Officer Review"], []),
    ("104328", "Dokumen apa yang masih diperlukan?", [], []),
    ("104328", "Which documents do you still need?", [], []),
    ("104328", "Berapa simpanan dan modal syer saya?", ["12,420", "8,200"], []),
    ("104328", "What are my savings and share capital?", ["12,420", "8,200"], []),
    ("104328", "Bolehkah saya memohon RM50,000?", ["Semak Sebelum Memohon"], []),
    ("104328", "Can I borrow RM50,000?", ["Check Before You Borrow"], []),
    ("104310", "Berapa baki pembiayaan saya?", ["14,200"], ["15,000"]),
    ("104310", "Bila bayaran seterusnya dan berapa?", ["310"], []),
    ("104310", "What is my balance and what's the status of my application?", ["14,200", "Enhanced Review"], []),
    ("104291", "Dokumen apa lagi yang perlu saya hantar?", ["Penyata Bank", "Sejarah Bayaran"], []),
    ("104291", "Which documents are still missing?", ["Bank Statement", "Payment History"], []),
    ("104415", "Berapa baki pembiayaan saya?", ["RM0"], []),
    ("104402", "Berapa ansuran bulanan saya?", ["520"], []),
    ("104402", "How much are my savings?", ["16,800"], []),
    ("104298", "Apa status permohonan yuran saya?", ["Dalam Pengesahan"], []),
    ("104298", "What is the status of my fees financing application?", ["In Verification"], []),
]


def test_member_assistant_eval():
    import assistant, llm
    asyncio.run(llm.probe())
    assert llm.status()["available"], "local model not available"
    rows, fails = [], []
    for mid, q, must, never in EVAL:
        r = asyncio.run(assistant.member_answer(mid, q, "ms"))
        a = r["answer"]
        problems = [f"missing {x}" for x in must if x.replace(",", "").lower() not in a.replace(",", "").lower()]
        problems += [f"said {x}" for x in never if x in a]
        if INDO.search(a):
            problems.append("Indonesian: " + INDO.search(a).group(0))
        if DECISION.search(a):
            problems.append("decision language")
        rows.append((r["lang"], r["source"], "PASS" if not problems else "FAIL", q[:52], a[:110].replace("\n", " ")))
        if problems:
            fails.append((q, problems, a))
    print("\nlang source   result  question / answer")
    for row in rows:
        print(f"{row[0]:4} {row[1]:8} {row[2]:5}  {row[3]}\n{'':20}→ {row[4]}")
    by_lang = {}
    for row in rows:
        by_lang.setdefault(row[0], []).append(row[2] == "PASS")
    print({k: f"{sum(v)}/{len(v)}" for k, v in by_lang.items()}, "llm-authored:", sum(1 for r in rows if r[1] == "llm"))
    assert not fails, fails
