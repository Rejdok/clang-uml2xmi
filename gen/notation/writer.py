from __future__ import annotations

from typing import Any, Dict, Optional
from lxml import etree

from app.config import LayoutConfig, DiagramConfig, DEFAULT_CONFIG
from meta import DEFAULT_META as NEW_DEFAULT_META
from meta.uml_meta import UmlMetaModel as UmlModel
from meta.default_model import MetaBundle as DiagramModel
from utils.ids import stable_id
from core.uml_model import UmlElement
from uml_types import ElementKind

from uml_types import ElementAttributes

ElementDict = Dict[Any, UmlElement]

class NotationWriter:
    def __init__(self, created: ElementDict, out_notation: str,
                 config: Optional[DiagramConfig] = None, model: Optional[DiagramModel] = None) -> None:
        self.created: ElementDict = created
        self.out_notation: str = out_notation
        if config is None:
            config = DEFAULT_CONFIG.diagram
        self.config: DiagramConfig = config
        if model is None:
            model = NEW_DEFAULT_META  # type: ignore[assignment]
        self.model: DiagramModel = model
        self.layout: LayoutConfig = config.layout
        self.xml = model.xml
        self.uml = model.uml

    @staticmethod
    def kind_to_node_type(kind: ElementKind, uml_model: UmlModel) -> str:
        if kind == ElementKind.ENUM:
            return "Enumeration"
        if kind in (ElementKind.DATATYPE, ElementKind.TYPEDEF):
            return "DataType"
        return "Class"

    def write(self) -> None:
        root_attrs: ElementAttributes = {
            self.xml.xmi_version: self.config.diagram_version,
            self.xml.xmi_id: stable_id("notation"),
            "name": self.config.diagram_name,
        }
        diagram_el: etree._Element = etree.Element(
            f"{{{self.xml.notation_ns}}}Diagram",
            nsmap=self.xml.notation_nsmap,
            attrib=root_attrs,
        )
        for idx, (_, info) in enumerate(self.created.items()):
            x, y = self.layout.calculate_position(idx)
            node_type = self.kind_to_node_type(info.kind, self.uml)
            node_attrs: ElementAttributes = {
                "type": node_type,
                self.xml.xmi_id: stable_id(str(info.xmi) + ":node"),
                "elementRef": str(info.xmi),
                "x": str(x),
                "y": str(y),
                "width": str(self.layout.width),
                "height": str(self.layout.height),
            }
            etree.SubElement(diagram_el, "children", attrib=node_attrs)
        tree: etree.ElementTree = etree.ElementTree(diagram_el)
        tree.write(self.out_notation, pretty_print=True, xml_declaration=True, encoding="UTF-8")

__all__ = ["NotationWriter"]


