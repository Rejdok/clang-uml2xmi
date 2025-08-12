from __future__ import annotations

import hashlib
import uuid

from uml_types import IdString, HashString


def xid() -> IdString:
    return "id_" + uuid.uuid4().hex


def stable_id(s: str) -> HashString:
    return "id_" + hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


__all__ = ["xid", "stable_id"]


