
# ---------- Notation writer (Papyrus minimal) ----------
from typing import Any, Dict

from Config import LayoutConfig, DiagramConfig, DEFAULT_CONFIG
from Model import DiagramModel, UmlModel, DEFAULT_MODEL
from Utils import stable_id
from lxml import etree

class NotationWriter:
    def __init__(self, created: Dict[str, Any], out_notation: str, 
                 config: DiagramConfig = None, model: DiagramModel = None):
        self.created = created
        self.out_notation = out_notation
        
        # Use provided config or default
        if config is None:
            config = DEFAULT_CONFIG.diagram
        self.config = config
        
        # Use provided model or default
        if model is None:
            model = DEFAULT_MODEL
        self.model = model
        
        # Extract configurations and models for convenience
        self.layout = config.layout
        self.xml = model.xml
        self.uml = model.uml

    @staticmethod
    def kind_to_node_type(kind: str, uml_model: UmlModel) -> str:
        """Convert element kind to UML node type using configuration."""
        if kind == "enum":
            return "Enumeration"
        if kind in ("datatype", "typedef"):
            return "DataType"
        return "Class"

    def write(self):
        """Write notation file using configuration-based approach."""
        # Use configuration for namespaces
        root_attrs = {
            self.xml.xmi_version: self.config.diagram_version,
            self.xml.xmi_id: stable_id("notation"),
            "name": self.config.diagram_name
        }
        
        diagram_el = etree.Element(
            f"{{{self.xml.notation_ns}}}Diagram", 
            nsmap=self.xml.notation_nsmap, 
            attrib=root_attrs
        )

        idx = 0
        for key, info in self.created.items():
            # Use layout configuration to calculate position
            x, y = self.layout.calculate_position(idx)
            
            node_type = self.kind_to_node_type(
                info.get("kind", "class"), 
                self.uml
            )
            
            node_attrs = {
                "type": node_type,
                self.xml.xmi_id: stable_id(info["xmi"] + ":node"),
                "elementRef": info["xmi"],
                "x": str(x),
                "y": str(y),
                "width": str(self.layout.width),
                "height": str(self.layout.height)
            }
            
            etree.SubElement(diagram_el, "children", attrib=node_attrs)
            idx += 1

        tree = etree.ElementTree(diagram_el)
        tree.write(self.out_notation, pretty_print=True, xml_declaration=True, encoding="UTF-8")