"""eKYC (MyKad scan, face match, liveness) — simulated. Compliant flows follow BNM's e-KYC policy."""
from __future__ import annotations


def status(m: dict) -> dict:
    flagged = m["id"] in ("104265",)
    return dict(source="Digibanc eKYC", simulated=True, mykad=m.get("mykad"),
                document_check="Passed", face_match=0.91 if flagged else 0.98,
                liveness="Passed", status="Review" if flagged else "Verified",
                note="Device shared with another member — see integrity graph" if flagged else None)
