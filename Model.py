#!/usr/bin/env python3
"""
Legacy facade for meta models. Kept for backward compatibility.
"""

from dataclasses import dataclass
from typing import Optional

from meta import XmlMetaModel as XmlModel
from meta import UmlMetaModel as UmlModel
from meta import DEFAULT_META


@dataclass
class DiagramModel:
    """Model bundle for diagram generation, compatible with legacy imports."""
    xml: Optional[XmlModel] = None
    uml: Optional[UmlModel] = None

    def __post_init__(self) -> None:
        if self.xml is None:
            self.xml = XmlModel()
        if self.uml is None:
            self.uml = UmlModel()


# Default model instance (backed by meta)
DEFAULT_MODEL = DiagramModel()
