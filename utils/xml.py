from __future__ import annotations

from uml_types import XmlValue


def xml_text(v: XmlValue) -> str:
    return "" if v is None else str(v)


__all__ = ["xml_text"]


