from typing import Any, Dict, Optional, List, Union, Protocol
from lxml import etree

from Utils import stable_id, xml_text
from Model import XmlModel, UmlModel, DEFAULT_MODEL
from UmlModel import UmlAssociation, XmiId

from uml_types import (
    ContextStack, ElementAttributes, XmlElement,
    ModelName, ModelId
)

class XmiWriter:
    def __init__(self, xf: etree.xmlfile, xml_model: Optional[XmlModel] = None) -> None:
        self.xf: etree.xmlfile = xf
        self._ctx_stack: ContextStack = []
        
        # Use provided model or default
        if xml_model is None:
            xml_model = DEFAULT_MODEL.xml
        self.config: XmlModel = xml_model

    def start_doc(self, model_name: str, model_id: str = "model_1") -> None:
        self.xf.write_declaration()
        xmi_ctx: etree._Element = self.xf.element(
            f"{{{self.config.xmi_ns}}}XMI",
            nsmap=self.config.uml_nsmap,
            **{self.config.xmi_version: "2.1"}
        )
        xmi_ctx.__enter__()
        self._ctx_stack.append(xmi_ctx)

        model_ctx: etree._Element = self.xf.element(
            f"{{{self.config.uml_ns}}}Model",
            **{
                self.config.xmi_id: model_id,
                "name": model_name
            }
        )
        model_ctx.__enter__()
        self._ctx_stack.append(model_ctx)

    def end_doc(self) -> None:
        # Pop and exit all remaining contexts
        while self._ctx_stack:
            ctx: etree._Element = self._ctx_stack.pop()
            ctx.__exit__(None, None, None)

    def start_packaged_element(self, xmi_id: XmiId, xmi_type: str, name: str,
                               is_abstract: bool = False, extra_attrs: Optional[ElementAttributes] = None) -> None:
        # гарантируем, что тип будет в формате "uml:Class"
        if not xmi_type.startswith("uml:"):
            xmi_type = f"uml:{xmi_type}"
        attrs: ElementAttributes = {self.config.xmi_type: xmi_type, self.config.xmi_id: str(xmi_id), "name": xml_text(name)}
        if is_abstract:
            attrs["isAbstract"] = "true"
        # добавляем дополнительные атрибуты (например: {"templateParameter": "<id>"} )
        if extra_attrs:
            for k, v in extra_attrs.items():
                attrs[k] = v
        ctx: etree._Element = self.xf.element("packagedElement", nsmap=self.config.uml_nsmap, **attrs)
        ctx.__enter__()
        self._ctx_stack.append(ctx)

    def end_packaged_element(self) -> None:
        ctx: etree._Element = self._ctx_stack.pop()
        ctx.__exit__(None, None, None)

    def start_package(self, package_id: XmiId, name: str) -> None:
        """Start a package element."""
        ctx: etree._Element = self.xf.element("packagedElement", nsmap=self.config.uml_nsmap, **{
            self.config.xmi_type: "uml:Package",
            self.config.xmi_id: str(package_id),
            "name": xml_text(name)
        })
        ctx.__enter__()
        self._ctx_stack.append(ctx)

    def end_package(self) -> None:
        """End a package element."""
        ctx: etree._Element = self._ctx_stack.pop()
        ctx.__exit__(None, None, None)

    def write_owned_attribute(self, aid: str, name: str, visibility: str = "private", type_ref: Optional[XmiId] = None, is_static: bool = False) -> None:
        # NOTE: use attribute `type` to reference the classifier by xmi:id
        attrs: ElementAttributes = {self.config.xmi_id: aid, "name": xml_text(name), "visibility": xml_text(visibility)}
        if is_static:
            attrs["isStatic"] = "true"
        if type_ref:
            attrs["type"] = str(type_ref)
        el: etree._Element = etree.Element("ownedAttribute", attrib=attrs, nsmap=self.config.uml_nsmap)
        self.xf.write(el)

    def start_owned_operation(self, oid: str, name: str, visibility: str = "public", is_static: bool = False, is_abstract: bool = False) -> None:
        attrs: ElementAttributes = {self.config.xmi_id: oid, "name": xml_text(name)}
        if visibility:
            attrs["visibility"] = xml_text(visibility)
        if is_static:
            attrs["isStatic"] = "true"
        if is_abstract:
            attrs["isAbstract"] = "true"
        ctx: etree._Element = self.xf.element("ownedOperation", nsmap=self.config.uml_nsmap, **attrs)
        ctx.__enter__()
        self._ctx_stack.append(ctx)

    def end_owned_operation(self) -> None:
        ctx: etree._Element = self._ctx_stack.pop()
        ctx.__exit__(None, None, None)

    def write_owned_parameter(self, pid: str, name: str, direction: str = "in", type_ref: Optional[XmiId] = None, default_value: Optional[str] = None, is_ordered: bool = True, is_unique: bool = True) -> None:
        # Debug logging to help identify invalid direction values
        import logging
        if direction.startswith("id_"):
            logging.error(f"CRITICAL: Parameter direction appears to be an ID: {direction} for parameter '{name}' with ID {pid}")
        
        # Validate direction parameter to prevent IllegalValueException
        valid_directions = {"in", "out", "inout", "return"}
        if direction not in valid_directions:
            # Log warning and use default direction
            logging.warning(f"Invalid parameter direction '{direction}' for parameter '{name}', using 'in' instead")
            direction = "in"
        
        # NOTE: use attribute `type` to reference parameter type by xmi:id
        attrs: ElementAttributes = {self.config.xmi_id: pid, "name": xml_text(name), "direction": xml_text(direction)}
        attrs["isOrdered"] = "true" if is_ordered else "false"
        attrs["isUnique"] = "true" if is_unique else "false"
        if type_ref:
            attrs["type"] = str(type_ref)
        el: etree._Element = etree.Element("ownedParameter", attrib=attrs, nsmap=self.config.uml_nsmap)
        self.xf.write(el)
        if default_value is not None:
            dv: etree._Element = etree.Element("defaultValue", attrib={self.config.xmi_id: stable_id(pid + ":default"), "value": xml_text(default_value)}, nsmap=self.config.uml_nsmap)
            self.xf.write(dv)

    def write_literal(self, lid: str, name: str) -> None:
        el: etree._Element = etree.Element("ownedLiteral", attrib={self.config.xmi_id: lid, "name": xml_text(name)}, nsmap=self.config.uml_nsmap)
        self.xf.write(el)
    
    def write_enum_literal(self, lid: str, name: str) -> None:
        """Write an enum literal element."""
        el: etree._Element = etree.Element("ownedLiteral", attrib={self.config.xmi_id: lid, "name": xml_text(name)}, nsmap=self.config.uml_nsmap)
        self.xf.write(el)
    
    def write_operation_return_type(self, type_ref: XmiId) -> None:
        """Write the return type for an operation."""
        # Validate direction value to prevent IllegalValueException
        direction = "return"
        valid_directions = {"in", "out", "inout", "return"}
        if direction not in valid_directions:
            # This should never happen, but add validation just in case
            import logging
            logging.error(f"Invalid return parameter direction '{direction}', using 'return' instead")
            direction = "return"
            
        el: etree._Element = etree.Element("ownedParameter", attrib={
            self.config.xmi_id: stable_id("return_param"),
            "direction": direction,
            "type": str(type_ref)
        }, nsmap=self.config.uml_nsmap)
        self.xf.write(el)
    
    def start_template_signature(self, signature_id: str) -> None:
        """Start a template signature element that contains template parameters."""
        ctx: etree._Element = self.xf.element("ownedTemplateSignature", attrib={
            self.config.xmi_id: signature_id,
            self.config.xmi_type: "uml:RedefinableTemplateSignature"
        }, nsmap=self.config.uml_nsmap)
        ctx.__enter__()
        self._ctx_stack.append(ctx)

    def end_template_signature(self) -> None:
        """End a template signature element."""
        ctx: etree._Element = self._ctx_stack.pop()
        ctx.__exit__(None, None, None)

    def write_template_parameter(self, template_id: str, parameter_name: str) -> None:
        """Write a template parameter element within a template signature."""
        el: etree._Element = etree.Element("ownedTemplateParameter", attrib={
            self.config.xmi_id: template_id,
            self.config.xmi_type: "uml:TemplateParameter",
            "name": xml_text(parameter_name)
        }, nsmap=self.config.uml_nsmap)
        self.xf.write(el)

    def write_generalization(self, gid: str, general_ref: XmiId, inheritance_type: str = "public", is_virtual: bool = False, is_final: bool = False) -> None:
        """Write generalization element with inheritance attributes.
        
        Args:
            gid: Generalization element ID
            general_ref: Reference to parent classifier
            inheritance_type: Type of inheritance (public/private/protected)
            is_virtual: Whether inheritance is virtual
            is_final: Whether class is final
        """
        # use attribute 'general' to reference parent classifier by id
        attrs = {self.config.xmi_id: gid, "general": str(general_ref)}
        
        # Add inheritance type if specified
        if inheritance_type and inheritance_type != "public":
            attrs["visibility"] = inheritance_type
            
        # Add virtual inheritance marker if applicable
        if is_virtual:
            attrs["isVirtual"] = "true"
            
        # Add final class marker if applicable
        if is_final:
            attrs["isFinalSpecialization"] = "true"
            
        el: etree._Element = etree.Element("generalization", attrib=attrs, nsmap=self.config.uml_nsmap)
        self.xf.write(el)

    def write_association(self, assoc: UmlAssociation, uml_model: Optional[UmlModel] = None) -> None:
        # Get UML model for type information
        if uml_model is None:
            uml_model = DEFAULT_MODEL.uml
        
        # Prefer precomputed stable ids (set earlier in XmiGenerator.write)
        aid: str = assoc._assoc_id or stable_id(f"assoc:{assoc.src}:{assoc.tgt}:{assoc.name}")
        assoc_el: etree._Element = etree.Element(
            "packagedElement",
            attrib={
                self.config.xmi_type: uml_model.association_type,
                self.config.xmi_id: aid,
                "name": xml_text(assoc.name or "")
            },
            nsmap=self.config.uml_nsmap
        )

        # compute end ids (use precomputed if available)
        end1_id: str = assoc._end1_id or stable_id(aid + ":end1")
        end2_id: str = assoc._end2_id or stable_id(aid + ":end2")

        def add_bound_value(parent: etree._Element, tag: str, value: str) -> None:
            """Добавляет lowerValue/upperValue с правильным xmi:type используя модель."""
            if value == "-1" or value == "*" or value.strip() == "*":
                literal_type: str = uml_model.literal_unlimited_natural_type
                literal_value: str = uml_model.unlimited_multiplicity
            else:
                literal_type: str = uml_model.literal_integer_type
                literal_value: str = str(value)
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
        end1: etree._Element = etree.SubElement(
            assoc_el, "ownedEnd",
            attrib={
                self.config.xmi_id: end1_id, 
                "type": str(assoc.src), 
                "aggregation": assoc.aggregation.value
            },
            nsmap=self.config.uml_nsmap
        )
        add_bound_value(end1, "lowerValue", uml_model.default_multiplicity_lower)
        add_bound_value(end1, "upperValue", uml_model.default_multiplicity_upper)

        # end2
        end2_id = stable_id(aid + ":end2")
        end2: etree._Element = etree.SubElement(
            assoc_el, "ownedEnd",
            attrib={
                self.config.xmi_id: end2_id, 
                "type": str(assoc.tgt), 
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

    def write_packaged_element_raw(self, element: etree._Element) -> None:
        self.xf.write(element)
