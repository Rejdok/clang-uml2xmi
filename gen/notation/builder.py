from __future__ import annotations

from typing import Dict, Any, Optional, List, Tuple
from core.uml_model import UmlElement
from uml_types import ElementKind
from app.config import DiagramConfig, LayoutConfig, DEFAULT_CONFIG


class NotationLayoutBuilder:
    """
    Builds a simple layout model (list of positioned nodes) from UML elements.
    """
    def __init__(self, config: Optional[DiagramConfig] = None) -> None:
        self.config = config or DEFAULT_CONFIG.diagram
        self.layout: LayoutConfig = self.config.layout

    def build_nodes(self, elements: Dict[Any, UmlElement]) -> List[Tuple[UmlElement, Tuple[int, int]]]:
        nodes: List[Tuple[UmlElement, Tuple[int, int]]] = []
        for idx, (_, el) in enumerate(elements.items()):
            x, y = self.layout.calculate_position(idx)
            nodes.append((el, (x, y)))
        return nodes


