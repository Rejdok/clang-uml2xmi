
# ---------- Utilities ----------
import hashlib
import uuid
from typing import Union, Any

from uml_types import IdString, HashString, XmlValue

def xid() -> IdString:
    """Generate a unique identifier with 'id_' prefix."""
    return "id_" + uuid.uuid4().hex


def stable_id(s: str) -> HashString:
    """Generate a stable identifier based on input string hash."""
    return "id_" + hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


def xml_text(v: XmlValue) -> str:
    """Convert value to XML-safe string representation."""
    return "" if v is None else str(v)


