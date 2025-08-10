from typing import Any, Dict, Optional
from lxml import etree

from Utils import stable_id, xml_text
from Model import XmlModel, UmlModel, DEFAULT_MODEL
from UmlModel import UmlAssociation

class XmiWriter:
    def __init__(self, xf: etree.xmlfile, xml_model: XmlModel = None):
        self.xf = xf
        self._ctx_stack = []
        
        # Use provided model or default
        if xml_model is None:
            xml_model = DEFAULT_MODEL.xml
        self.config = xml_model

    def start_doc(self, model_name: str, model_id: str = "model_1"):
        self.xf.write_declaration()
        xmi_ctx = self.xf.element(
            f"{{{self.config.xmi_ns}}}XMI",
            nsmap=self.config.uml_nsmap,
            **{self.config.xmi_version: "2.1"}
        )
        xmi_ctx.__enter__()
        self._ctx_stack.append(xmi_ctx)

        model_ctx = self.xf.element(
            f"{{{self.config.uml_ns}}}Model",
            **{
                self.config.xmi_id: model_id,
                "name": model_name
            }
        )
        model_ctx.__enter__()
        self._ctx_stack.append(model_ctx)

    def end_doc(self):
        # Pop and exit all remaining contexts
        while self._ctx_stack:
            ctx = self._ctx_stack.pop()
            ctx.__exit__(None, None, None)

    def start_packaged_element(self, xmi_id: str, xmi_type: str, name: str,
                               is_abstract: bool=False, extra_attrs: Optional[Dict[str,str]] = None):
        # гарантируем, что тип будет в формате "uml:Class"
        if not xmi_type.startswith("uml:"):
            xmi_type = f"uml:{xmi_type}"
        attrs = {self.config.xmi_type: xmi_type, self.config.xmi_id: xmi_id, "name": xml_text(name)}
        if is_abstract:
            attrs["isAbstract"] = "true"
        # добавляем дополнительные атрибуты (например: {"templateParameter": "<id>"} )
        if extra_attrs:
            for k, v in extra_attrs.items():
                attrs[k] = v
        ctx = self.xf.element("packagedElement", nsmap=self.config.uml_nsmap, **attrs)
        ctx.__enter__()
        self._ctx_stack.append(ctx)

    def end_packaged_element(self):
        ctx = self._ctx_stack.pop()
        ctx.__exit__(None, None, None)

    def start_package(self, package_id: str, name: str):
        """Start a package element."""
        ctx = self.xf.element("packagedElement", nsmap=self.config.uml_nsmap, **{
            self.config.xmi_type: "uml:Package",
            self.config.xmi_id: package_id,
            "name": xml_text(name)
        })
        ctx.__enter__()
        self._ctx_stack.append(ctx)

    def end_package(self):
        """End a package element."""
        ctx = self._ctx_stack.pop()
        ctx.__exit__(None, None, None)

    def write_owned_attribute(self, aid: str, name: str, visibility: str="private", type_ref: Optional[str]=None, is_static: bool=False):
        # NOTE: use attribute `type` to reference the classifier by xmi:id
        attrs = {self.config.xmi_id: aid, "name": xml_text(name), "visibility": xml_text(visibility)}
        if is_static:
            attrs["isStatic"] = "true"
        if type_ref:
            attrs["type"] = type_ref
        el = etree.Element("ownedAttribute", attrib=attrs, nsmap=self.config.uml_nsmap)
        self.xf.write(el)

    def start_owned_operation(self, oid: str, name: str, visibility: str="public", is_static: bool=False, is_abstract: bool=False):
        attrs = {self.config.xmi_id: oid, "name": xml_text(name)}
        if visibility:
            attrs["visibility"] = xml_text(visibility)
        if is_static:
            attrs["isStatic"] = "true"
        if is_abstract:
            attrs["isAbstract"] = "true"
        ctx = self.xf.element("ownedOperation", nsmap=self.config.uml_nsmap, **attrs)
        ctx.__enter__()
        self._ctx_stack.append(ctx)

    def end_owned_operation(self):
        ctx = self._ctx_stack.pop()
        ctx.__exit__(None, None, None)

    def write_owned_parameter(self, pid: str, name: str, direction: str="in", type_ref: Optional[str]=None, default_value: Optional[str]=None, is_ordered: bool=True, is_unique: bool=True):
        # NOTE: use attribute `type` to reference parameter type by xmi:id
        attrs = {self.config.xmi_id: pid, "name": xml_text(name), "direction": xml_text(direction)}
        attrs["isOrdered"] = "true" if is_ordered else "false"
        attrs["isUnique"] = "true" if is_unique else "false"
        if type_ref:
            attrs["type"] = type_ref
        el = etree.Element("ownedParameter", attrib=attrs, nsmap=self.config.uml_nsmap)
        self.xf.write(el)
        if default_value is not None:
            dv = etree.Element("defaultValue", attrib={self.config.xmi_id: stable_id(pid + ":default"), "value": xml_text(default_value)}, nsmap=self.config.uml_nsmap)
            self.xf.write(dv)

    def write_literal(self, lid: str, name: str):
        el = etree.Element("ownedLiteral", attrib={self.config.xmi_id: lid, "name": xml_text(name)}, nsmap=self.config.uml_nsmap)
        self.xf.write(el)

    def write_generalization(self, gid: str, general_ref: str):
        # use attribute 'general' to reference parent classifier by id
        el = etree.Element("generalization", attrib={self.config.xmi_id: gid, "general": general_ref}, nsmap=self.config.uml_nsmap)
        self.xf.write(el)

    def write_association(self, assoc: UmlAssociation, uml_model: UmlModel = None):
        # Get UML model for type information
        if uml_model is None:
            uml_model = DEFAULT_MODEL.uml
        
        # Prefer precomputed stable ids (set earlier in XmiGenerator.write)
        aid = assoc._assoc_id or stable_id(f"assoc:{assoc.src}:{assoc.tgt}:{assoc.name}")
        assoc_el = etree.Element(
            "packagedElement",
            attrib={
                self.config.xmi_type: uml_model.association_type,
                self.config.xmi_id: aid,
                "name": xml_text(assoc.name or "")
            },
            nsmap=self.config.uml_nsmap
        )

        # compute end ids (use precomputed if available)
        end1_id = assoc._end1_id or stable_id(aid + ":end1")
        end2_id = assoc._end2_id or stable_id(aid + ":end2")

        def add_bound_value(parent, tag, value):
            """Добавляет lowerValue/upperValue с правильным xmi:type используя модель."""
            if value == "-1" or value == "*" or value.strip() == "*":
                literal_type = uml_model.literal_unlimited_natural_type
                literal_value = uml_model.unlimited_multiplicity
            else:
                literal_type = uml_model.literal_integer_type
                literal_value = str(value)
            etree.SubElement(
                parent, tag,
                attrib={
                    self.config.xmi_type: literal_type,
                    self.config.xmi_id: stable_id(parent.get(self.config.xmi_id) + ":" + tag),
                    "value": literal_value
                },
                nsmap=self.config.uml_nsmap
            )

        # end1 (reference the type via attribute `type`)
        end1_id = stable_id(aid + ":end1")
        end1 = etree.SubElement(
            assoc_el, "ownedEnd",
            attrib={
                self.config.xmi_id: end1_id, 
                "type": assoc.src, 
                "aggregation": assoc.aggregation.value
            },
            nsmap=self.config.uml_nsmap
        )
        add_bound_value(end1, "lowerValue", uml_model.default_multiplicity_lower)
        add_bound_value(end1, "upperValue", uml_model.default_multiplicity_upper)

        # end2
        end2_id = stable_id(aid + ":end2")
        end2 = etree.SubElement(
            assoc_el, "ownedEnd",
            attrib={
                self.config.xmi_id: end2_id, 
                "type": assoc.tgt, 
                "aggregation": uml_model.default_aggregation
            },
            nsmap=self.config.uml_nsmap
        )
        if assoc.multiplicity == uml_model.unlimited_multiplicity:
            add_bound_value(end2, "lowerValue", "0")
            add_bound_value(end2, "upperValue", uml_model.unlimited_multiplicity)
        else:
            add_bound_value(end2, "lowerValue", uml_model.default_multiplicity_lower)
            add_bound_value(end2, "upperValue", uml_model.default_multiplicity_upper)

        self.xf.write(assoc_el)

    def write_packaged_element_raw(self, element: etree._Element):
        self.xf.write(element)
