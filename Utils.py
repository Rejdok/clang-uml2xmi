
# ---------- Utilities ----------
import hashlib
import uuid


def xid() -> str:
    return "id_" + uuid.uuid4().hex


def stable_id(s: str) -> str:
    return "id_" + hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


def xml_text(v) -> str:
    return "" if v is None else str(v)


