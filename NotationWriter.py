
# ---------- Notation writer (Papyrus minimal) ----------
class NotationWriter:
    def __init__(self, created: Dict[str, Any], out_notation: str, row_wrap: int = 10,
                 step_x: int = 300, step_y: int = 200, width: int = 180, height: int = 100):
        self.created = created
        self.out_notation = out_notation
        self.row_wrap = row_wrap
        self.step_x = step_x
        self.step_y = step_y
        self.width = width
        self.height = height

    @staticmethod
    def kind_to_node_type(kind: str) -> str:
        if kind == "enum":
            return "Enumeration"
        if kind in ("datatype", "typedef"):
            return "DataType"
        return "Class"

    def write(self):
        NSMAP_LOCAL = {
            "notation": "http://www.eclipse.org/papyrus/notation/1.0",
            "xmi": "http://www.omg.org/XMI"
        }
        root_attrs = {
            f"{{{XMI_NS}}}version": "2.0",
            f"{{{XMI_NS}}}id": stable_id("notation"),
            "name": "ClassDiagram"
        }
        diagram_el = etree.Element(f"{{{NSMAP_LOCAL['notation']}}}Diagram", nsmap=NSMAP_LOCAL, attrib=root_attrs)

        idx = 0
        for key, info in self.created.items():
            x = 40 + (idx % self.row_wrap) * self.step_x
            y = 40 + (idx // self.row_wrap) * self.step_y
            node_type = self.kind_to_node_type(info.get("kind", "class"))
            node_attrs = {
                "type": node_type,
                f"{{{XMI_NS}}}id": stable_id(info["xmi"] + ":node"),
                "elementRef": info["xmi"],
                "x": str(x),
                "y": str(y),
                "width": str(self.width),
                "height": str(self.height)
            }
            etree.SubElement(diagram_el, "children", attrib=node_attrs)
            idx += 1

        tree = etree.ElementTree(diagram_el)
        tree.write(self.out_notation, pretty_print=True, xml_declaration=True, encoding="UTF-8")