"""Independent check: for every PDF field, the text that pypdf finds inside the recorded box is the drawn value."""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from pypdf import PdfReader

def runs(path):
    r = PdfReader(path); page = r.pages[0]
    W, H = float(page.mediabox.width), float(page.mediabox.height)
    out = []
    def v(text, cm, tm, fd, fs):
        if text.strip():
            x = tm[4] * cm[0] + cm[4]; y = tm[5] * cm[3] + cm[5]
            out.append((text.strip(), x / W * 100, (H - y) / H * 100))
    page.extract_text(visitor_text=v)
    return out

def check(docs, base):
    bad, n = [], 0
    for d in docs:
        if not d["file"].endswith(".pdf"):
            continue
        rs = runs(os.path.join(base, d["file"]))
        for f in d["fields"]:
            n += 1
            x, y, w, h = f["bbox"]
            inside = [t for t, rx, ry in rs if x - 0.5 <= rx <= x + w + 0.5 and y - 0.5 <= ry <= y + h + 0.5]
            if f["src"] not in inside:
                bad.append((d["file"], f["k"], f["src"], inside[:3]))
    return n, bad

if __name__ == "__main__":
    base = sys.argv[1]
    man = json.load(open(os.path.join(base, "manifest.json")))
    n, bad = check(man["docs"], base)
    print(f"{len(man['docs'])} documents, {n} PDF fields checked, {len(bad)} misplaced")
    for b in bad[:20]: print("  BAD", b)
    sys.exit(1 if bad else 0)
