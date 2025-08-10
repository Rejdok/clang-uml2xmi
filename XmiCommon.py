# Пространства имён XMI и UML
XMI_NS = "http://www.omg.org/XMI"
UML_NS = "http://www.eclipse.org/uml2/5.0.0/UML"


# Константы для корректных имён атрибутов
XMI_ID = f"{{{XMI_NS}}}id"
XMI_IDREF = f"{{{XMI_NS}}}idref"
XMI_TYPE = f"{{{XMI_NS}}}type"

# Карта пространств имён
NSMAP = {
    "xmi": XMI_NS,
    "uml": UML_NS
}