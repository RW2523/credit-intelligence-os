"""Sign-in, sessions and the role hierarchy — enforced on the server, not just hidden in the UI.

Staff sign in with a staff ID and password; members sign in with their KT member number and PIN, as
on KT Online. Passwords are PBKDF2-hashed, sessions are HMAC-signed cookies, and repeated failures from
one address are rate-limited. No new dependencies: everything here is the standard library.

CIOS_DEMO=1 (default) lists the demo accounts on the sign-in page. Set CIOS_DEMO=0 to hide them.
CIOS_DEMO_PASSWORD / CIOS_MEMBER_PIN change the demo credentials; CIOS_SECRET fixes the signing key.
"""
from __future__ import annotations
import base64, hashlib, hmac, json, os, secrets, time

import seed, store

DEMO = os.environ.get("CIOS_DEMO", "1") == "1"
STAFF_PASSWORD = os.environ.get("CIOS_DEMO_PASSWORD", "KT-demo-2026")
MEMBER_PIN = os.environ.get("CIOS_MEMBER_PIN", "123456")
COOKIE = "kt_session"
TTL = 12 * 3600

# level drives the sensitive surfaces: >= 2 may see financial-distress outlooks and cross-selling
ROLES = {
    "officer": dict(label="Credit Officer", role_ms="Pegawai Kredit", level=1, authority=30000,
                    views=["overview", "applications", "intake", "workbench", "documents", "members", "assistant"]),
    "senior": dict(label="Senior Credit Officer", role_ms="Pegawai Kredit Kanan", level=2, authority=100000,
                   views=["overview", "applications", "intake", "workbench", "documents", "members",
                          "early-warning", "crosssell", "assistant"]),
    "collections": dict(label="Collections Officer", role_ms="Pegawai Kutipan", level=2, authority=0,
                        views=["overview", "early-warning", "collections", "members", "assistant"]),
    "risk": dict(label="Risk Manager", role_ms="Pengurus Risiko", level=4, authority=0,
                 views=["overview", "applications", "workbench", "members", "early-warning", "governance",
                        "sandbox", "assistant"]),
    "compliance": dict(label="Compliance Officer", role_ms="Pegawai Pematuhan", level=4, authority=0,
                       views=["overview", "applications", "workbench", "documents", "members", "ledger",
                              "governance", "assistant"]),
    "manager": dict(label="Branch Manager", role_ms="Pengurus Cawangan", level=3, authority=250000,
                    views=["overview", "cockpit", "applications", "workbench", "documents", "members",
                           "early-warning", "collections", "crosssell", "sandbox", "governance", "assistant"]),
    "board": dict(label="Board / Governance", role_ms="Lembaga Pengarah", level=5, authority=0,
                  views=["cockpit", "sandbox", "governance", "ledger", "assistant"]),
    "marketing": dict(label="Marketing & Member Growth", role_ms="Pemasaran & Pertumbuhan Ahli", level=2,
                      authority=0, views=["crosssell", "members", "assistant"]),
    "member": dict(label="Member", role_ms="Ahli", level=0, authority=0, views=["member-portal", "check"]),
}
DISTRESS_ROLES = {"senior", "collections", "risk", "compliance", "manager"}
CROSSSELL_ROLES = {"senior", "manager", "marketing"}

STAFF = {
    "noraini": ("officer", seed.STAFF["officer"]), "aisha": ("senior", seed.STAFF["senior"]),
    "azlan": ("collections", seed.STAFF["collections"]), "priya": ("risk", seed.STAFF["risk"]),
    "siewling": ("compliance", seed.STAFF["compliance"]), "kamarul": ("manager", seed.STAFF["manager"]),
    "zulkifli": ("board", seed.STAFF["board"]), "rohana": ("board", seed.STAFF["board2"]),
    "farah": ("marketing", seed.STAFF["marketing"]),
}


def _hash(pw: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 120_000).hex()


_SALT = hashlib.sha256(b"kt-demo-salt").digest()
_STAFF_HASH = _hash(STAFF_PASSWORD, _SALT)
_MEMBER_HASH = _hash(MEMBER_PIN, _SALT)


def _secret() -> bytes:
    env = os.environ.get("CIOS_SECRET")
    if env:
        return env.encode()
    s = store.get("session_secret")
    if not s:
        s = secrets.token_hex(32)
        store.put("session_secret", s)
    return s.encode()


def initials(name: str) -> str:
    w = [x for x in name.replace("Dato' ", "").replace("Datin ", "").replace("Hj. ", "").split()
         if x not in ("bin", "binti", "a/l", "a/p", "anak")]
    return (w[0][0] + w[-1][0]).upper() if len(w) > 1 else w[0][:2].upper()


def user_record(username: str, members: dict) -> dict | None:
    u = username.strip().lower()
    if u in STAFF:
        role, name = STAFF[u]
        r = ROLES[role]
        return dict(username=u, role=role, role_label=r["label"], role_ms=r["role_ms"], level=r["level"],
                    authority=r["authority"], views=r["views"], name=name, initials=initials(name))
    if u in members:
        m = members[u]
        r = ROLES["member"]
        return dict(username=u, role="member", role_label=r["label"], role_ms=r["role_ms"], level=0, authority=0,
                    views=r["views"], name=m["name"], initials=m["initials"], member_id=u)
    return None


def verify(username: str, password: str, members: dict) -> dict | None:
    rec = user_record(username, members)
    if not rec:
        _hash(password, _SALT)                         # same work either way
        return None
    want = _MEMBER_HASH if rec["role"] == "member" else _STAFF_HASH
    return rec if hmac.compare_digest(_hash(password, _SALT), want) else None


def issue(rec: dict) -> str:
    body = base64.urlsafe_b64encode(json.dumps({"u": rec["username"], "exp": int(time.time()) + TTL}).encode()).decode()
    sig = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def read(token: str | None, members: dict) -> dict | None:
    if not token or "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest(), sig):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(body.encode()))
    except Exception:                                  # noqa: BLE001
        return None
    if data.get("exp", 0) < time.time():
        return None
    return user_record(data["u"], members)


# ------------------------------------------------------------ rate limiting
_FAILS: dict[str, list[float]] = {}


def throttled(ip: str) -> bool:
    now = time.time()
    hits = [t for t in _FAILS.get(ip, []) if now - t < 300]
    _FAILS[ip] = hits
    return len(hits) >= 10


def failed(ip: str):
    _FAILS.setdefault(ip, []).append(time.time())


def demo_accounts(members: dict) -> list[dict]:
    if not DEMO:
        return []
    staff = [dict(username=u, name=n, role=ROLES[r]["label"], role_ms=ROLES[r]["role_ms"], kind="staff")
             for u, (r, n) in STAFF.items() if u != "rohana"]
    mem = [dict(username=mid, name=members[mid]["name"], role="Member", role_ms="Ahli", kind="member")
           for mid in ("104328", "104310", "104415") if mid in members]
    return staff + mem


def can(user: dict, *views: str) -> bool:
    return any(v in user["views"] for v in views)
