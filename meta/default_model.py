from dataclasses import dataclass
from .xml_meta import XmlMetaModel
from .uml_meta import UmlMetaModel


@dataclass
class MetaBundle:
    xml: XmlMetaModel
    uml: UmlMetaModel


DEFAULT_META = MetaBundle(xml=XmlMetaModel(), uml=UmlMetaModel())


