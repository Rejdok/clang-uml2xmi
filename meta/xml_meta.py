from dataclasses import dataclass
from typing import Dict

Namespace = str
AttributeName = str


@dataclass
class XmlMetaModel:
    xmi_ns: Namespace = "http://www.omg.org/XMI"
    uml_ns: Namespace = "http://www.eclipse.org/uml2/5.0.0/UML"
    notation_ns: Namespace = "http://www.eclipse.org/papyrus/notation/1.0"

    @property
    def xmi_id(self) -> AttributeName:
        return f"{{{self.xmi_ns}}}id"

    @property
    def xmi_idref(self) -> AttributeName:
        return f"{{{self.xmi_ns}}}idref"

    @property
    def xmi_type(self) -> AttributeName:
        return f"{{{self.xmi_ns}}}type"

    @property
    def xmi_version(self) -> AttributeName:
        return f"{{{self.xmi_ns}}}version"

    @property
    def uml_nsmap(self) -> Dict[str, Namespace]:
        return {"xmi": self.xmi_ns, "uml": self.uml_ns}

    @property
    def notation_nsmap(self) -> Dict[str, Namespace]:
        return {"notation": self.notation_ns, "xmi": self.xmi_ns}


