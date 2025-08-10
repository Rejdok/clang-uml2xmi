
# ---------- Notation writer (Papyrus minimal) ----------
from typing import Any, Dict, Optional
from lxml import etree

from Config import LayoutConfig, DiagramConfig, DEFAULT_CONFIG
from Model import DiagramModel, UmlModel, DEFAULT_MODEL
from Utils import stable_id
from UmlModel import UmlElement, ElementKind, ElementName

from uml_types import ElementAttributes

# Type aliases for better readability
ElementDict = Dict[ElementName, UmlElement]

class NotationWriter:
    def __init__(self, created: ElementDict, out_notation: str, 
                 config: Optional[DiagramConfig] = None, model: Optional[DiagramModel] = None) -> None:
        self.created: ElementDict = created
        self.out_notation: str = out_notation
        
        # Use provided config or default
        if config is None:
            config = DEFAULT_CONFIG.diagram
        self.config: DiagramConfig = config
        
        # Use provided model or default
        if model is None:
            model = DEFAULT_MODEL
        self.model: DiagramModel = model
        
        # Extract configurations and models for convenience
        self.layout: LayoutConfig = config.layout
        self.xml = model.xml
        self.uml = model.uml

    @staticmethod
    def kind_to_node_type(kind: ElementKind, uml_model: UmlModel) -> str:
        """Convert element kind to UML node type using configuration."""
        if kind == ElementKind.ENUM:
            return "Enumeration"
        if kind in (ElementKind.DATATYPE, ElementKind.TYPEDEF):
            return "DataType"
        return "Class"

    def write(self) -> None:
        """Write notation file using configuration-based approach."""
        # Use configuration for namespaces
        root_attrs: ElementAttributes = {
            self.xml.xmi_version: self.config.diagram_version,
            self.xml.xmi_id: stable_id("notation"),
            "name": self.config.diagram_name
        }
        
        diagram_el: etree._Element = etree.Element(
            f"{{{self.xml.notation_ns}}}Diagram", 
            nsmap=self.xml.notation_nsmap, 
            attrib=root_attrs
        )

        idx: int = 0
        for key, info in self.created.items():
            # Use layout configuration to calculate position
            x: int
            y: int
            x, y = self.layout.calculate_position(idx)
            
            node_type: str = self.kind_to_node_type(info.kind, self.uml)
            
            node_attrs: ElementAttributes = {
                "type": node_type,
                self.xml.xmi_id: stable_id(str(info.xmi) + ":node"),
                "elementRef": str(info.xmi),
                "x": str(x),
                "y": str(y),
                "width": str(self.layout.width),
                "height": str(self.layout.height)
            }
            
            etree.SubElement(diagram_el, "children", attrib=node_attrs)
            idx += 1

        tree: etree.ElementTree = etree.ElementTree(diagram_el)
        tree.write(self.out_notation, pretty_print=True, xml_declaration=True, encoding="UTF-8")