from typing import Any, Dict, Optional, List, Union, Protocol
import logging
from lxml import etree

from Utils import stable_id, xml_text
from Model import XmlModel, UmlModel, DEFAULT_MODEL
try:
    # Prefer new meta bundle if available
    from meta import XmlMetaModel as NewXmlModel, UmlMetaModel as NewUmlModel, DEFAULT_META
    _HAS_META = True
except Exception:
    _HAS_META = False
from UmlModel import UmlAssociation, XmiId

from uml_types import (
    ContextStack, ElementAttributes, XmlElement,
    ModelName, ModelId
)

# Setup logger
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class XmiWriter:
    def __init__(self, xf: etree.xmlfile, xml_model: Optional[XmlModel] = None) -> None:
        self.xf: etree.xmlfile = xf
        self._ctx_stack: ContextStack = []
        
        # Use provided model or default
        if xml_model is None:
            # If new meta exists, use it; otherwise fallback to legacy Model.DEFAULT_MODEL
            if _HAS_META:
                xml_model = DEFAULT_META.xml  # type: ignore[assignment]
            else:
                xml_model = DEFAULT_MODEL.xml
        self.config: XmlModel = xml_model

    def start_doc(self, model_name: str, model_id: str = "model_1") -> None:
        """Start XMI 2.1 document with proper namespaces."""
        self.xf.write_declaration()
        
        # XMI 2.1 compliant root element
        xmi_ctx: etree._Element = self.xf.element(
            f"{{{self.config.xmi_ns}}}XMI",
            nsmap=self.config.uml_nsmap,
            **{self.config.xmi_version: "2.1"}
        )
        xmi_ctx.__enter__()
        self._ctx_stack.append(xmi_ctx)

        # UML Model element - XMI 2.1 compliant
        model_ctx: etree._Element = self.xf.element(
            f"{{{self.config.uml_ns}}}Model",
            **{
                self.config.xmi_id: model_id,
                "name": model_name,
                "visibility": "public"
            }
        )
        model_ctx.__enter__()
        self._ctx_stack.append(model_ctx)

    def end_doc(self) -> None:
        """End XMI document properly."""
        # Pop and exit all remaining contexts
        while self._ctx_stack:
            ctx: etree._Element = self._ctx_stack.pop()
            ctx.__exit__(None, None, None)

    def start_packaged_element(self, xmi_id: XmiId, xmi_type: str, name: str,
                               is_abstract: bool = False, extra_attrs: Optional[ElementAttributes] = None) -> None:
        """Start packaged element with XMI 2.1 compliant attributes."""
        # Ensure type is in format "uml:Class"
        if not xmi_type.startswith("uml:"):
            xmi_type = f"uml:{xmi_type}"
        
        # XMI 2.1 compliant attributes
        attrs: ElementAttributes = {
            self.config.xmi_type: xmi_type, 
            self.config.xmi_id: str(xmi_id), 
            "name": xml_text(name),
            "visibility": "public"  # Default visibility for XMI 2.1
        }
        
        if is_abstract:
            attrs["isAbstract"] = "true"
            
        # Add extra attributes (e.g., {"templateParameter": "<id>"})
        if extra_attrs:
            for k, v in extra_attrs.items():
                attrs[k] = v
                
        ctx: etree._Element = self.xf.element("packagedElement", nsmap=self.config.uml_nsmap, **attrs)
        ctx.__enter__()
        self._ctx_stack.append(ctx)

    def end_packaged_element(self) -> None:
        """End packaged element."""
        ctx: etree._Element = self._ctx_stack.pop()
        ctx.__exit__(None, None, None)

    def start_package(self, package_id: XmiId, name: str) -> None:
        """Start a package element - XMI 2.1 compliant."""
        ctx: etree._Element = self.xf.element("packagedElement", nsmap=self.config.uml_nsmap, **{
            self.config.xmi_type: "uml:Package",
            self.config.xmi_id: str(package_id),
            "name": xml_text(name),
            "visibility": "public"
        })
        ctx.__enter__()
        self._ctx_stack.append(ctx)

    def end_package(self) -> None:
        """End a package element."""
        ctx: etree._Element = self._ctx_stack.pop()
        ctx.__exit__(None, None, None)

    def write_owned_attribute(self, aid: str, name: str, visibility: str = "private", type_ref: Optional[XmiId] = None, is_static: bool = False) -> None:
        """Write owned attribute - XMI 2.1 compliant."""
        # XMI 2.1 compliant attributes
        attrs: ElementAttributes = {
            self.config.xmi_id: aid, 
            "name": xml_text(name), 
            "visibility": xml_text(visibility),
            "isStatic": "false",  # Default value
            "isReadOnly": "false",  # Default value
            "isDerived": "false"   # Default value
        }
        
        if is_static:
            attrs["isStatic"] = "true"
        if type_ref:
            attrs["type"] = str(type_ref)
            
        el: etree._Element = etree.Element("ownedAttribute", attrib=attrs, nsmap=self.config.uml_nsmap)
        self.xf.write(el)

    def start_owned_operation(self, oid: str, name: str, visibility: str = "public", is_static: bool = False, is_abstract: bool = False) -> None:
        """Start owned operation - XMI 2.1 compliant."""
        # XMI 2.1 compliant attributes
        attrs: ElementAttributes = {
            self.config.xmi_id: oid, 
            "name": xml_text(name),
            "visibility": xml_text(visibility),
            "isStatic": "false",      # Default value
            "isAbstract": "false",    # Default value
            "isQuery": "false"        # Default value
        }
        
        if is_static:
            attrs["isStatic"] = "true"
        if is_abstract:
            attrs["isAbstract"] = "true"
            
        ctx: etree._Element = self.xf.element("ownedOperation", nsmap=self.config.uml_nsmap, **attrs)
        ctx.__enter__()
        self._ctx_stack.append(ctx)

    def end_owned_operation(self) -> None:
        """End owned operation."""
        ctx: etree._Element = self._ctx_stack.pop()
        ctx.__exit__(None, None, None)

    def write_owned_parameter(self, pid: str, name: str, direction: str = "in", type_ref: Optional[XmiId] = None, default_value: Optional[str] = None, is_ordered: bool = True, is_unique: bool = True) -> None:
        """Write owned parameter - XMI 2.1 compliant."""
        # Validate direction value for XMI 2.1
        valid_directions = ["in", "out", "inout", "return"]
        if direction not in valid_directions:
            logger.warning(f"Invalid parameter direction '{direction}', using 'in'")
            direction = "in"
        
        # XMI 2.1 compliant attributes
        attrs: ElementAttributes = {
            self.config.xmi_id: pid,
            "name": xml_text(name),
            "direction": direction,
            "isOrdered": str(is_ordered).lower(),
            "isUnique": str(is_unique).lower()
        }
        
        if type_ref:
            attrs["type"] = str(type_ref)
        if default_value:
            attrs["defaultValue"] = xml_text(default_value)
            
        el: etree._Element = etree.Element("ownedParameter", nsmap=self.config.uml_nsmap, **attrs)
        self.xf.write(el)

    def write_literal(self, lid: str, name: str) -> None:
        """Write literal - XMI 2.1 compliant."""
        el: etree._Element = etree.Element("ownedLiteral", nsmap=self.config.uml_nsmap, **{
            self.config.xmi_id: lid,
            "name": xml_text(name)
        })
        self.xf.write(el)

    def write_enum_literal(self, lid: str, name: str) -> None:
        """Write enum literal - XMI 2.1 compliant."""
        el: etree._Element = etree.Element("ownedLiteral", nsmap=self.config.uml_nsmap, **{
            self.config.xmi_id: lid,
            "name": xml_text(name)
        })
        self.xf.write(el)

    def write_operation_return_type(self, operation_id: XmiId, type_ref: XmiId) -> None:
        """Write operation return type - XMI 2.1 compliant.

        The return parameter must have a unique xmi:id per operation to avoid
        collisions across multiple operations.
        """
        # XMI 2.1 compliant return parameter
        return_attrs: ElementAttributes = {
            self.config.xmi_id: stable_id(str(operation_id) + ":return"),
            "name": "return",
            "direction": "return",
            "type": str(type_ref),
            "isOrdered": "true",
            "isUnique": "true"
        }

        return_el: etree._Element = etree.Element("ownedParameter", nsmap=self.config.uml_nsmap, **return_attrs)
        self.xf.write(return_el)

    def start_template_signature(self, signature_id: str) -> None:
        """Start template signature - XMI 2.1 compliant."""
        ctx: etree._Element = self.xf.element("ownedTemplateSignature", nsmap=self.config.uml_nsmap, **{
            self.config.xmi_id: signature_id
        })
        ctx.__enter__()
        self._ctx_stack.append(ctx)

    def end_template_signature(self) -> None:
        """End template signature."""
        ctx: etree._Element = self._ctx_stack.pop()
        ctx.__exit__(None, None, None)

    def write_template_parameter(self, template_id: str, parameter_name: str) -> None:
        """Write template parameter - XMI 2.1 compliant."""
        el: etree._Element = etree.Element("ownedTemplateParameter", nsmap=self.config.uml_nsmap, **{
            self.config.xmi_id: template_id,
            "name": xml_text(parameter_name)
        })
        self.xf.write(el)

    def write_template_binding(self, binding_id: str, signature_ref: XmiId, arg_ids: List[XmiId]) -> None:
        """Write templateBinding with parameterSubstitution entries as a child of current element."""
        # Nest within current open packagedElement using xmlfile contexts
        tb_ctx = self.xf.element(
            "templateBinding",
            nsmap=self.config.uml_nsmap,
            **{
                self.config.xmi_id: binding_id,
                self.config.xmi_type: "uml:TemplateBinding",
            },
        )
        tb_ctx.__enter__()
        try:
            # signature reference
            sig_ctx = self.xf.element(
                "signature",
                nsmap=self.config.uml_nsmap,
                **{self.config.xmi_idref: str(signature_ref)},
            )
            sig_ctx.__enter__()
            sig_ctx.__exit__(None, None, None)

            # substitutions
            for i, aid in enumerate(arg_ids):
                ps_ctx = self.xf.element(
                    "parameterSubstitution",
                    nsmap=self.config.uml_nsmap,
                    **{self.config.xmi_id: stable_id(binding_id + f":sub:{i}")},
                )
                ps_ctx.__enter__()
                try:
                    actual_ctx = self.xf.element(
                        "actual",
                        nsmap=self.config.uml_nsmap,
                        **{self.config.xmi_idref: str(aid)},
                    )
                    actual_ctx.__enter__()
                    actual_ctx.__exit__(None, None, None)
                finally:
                    ps_ctx.__exit__(None, None, None)
        finally:
            tb_ctx.__exit__(None, None, None)

    def write_generalization(self, gid: str, general_ref: XmiId, inheritance_type: str = "public", is_virtual: bool = False, is_final: bool = False) -> None:
        """Write generalization element - XMI 2.1 compliant."""
        # XMI 2.1 compliant attributes
        attrs = {
            self.config.xmi_id: gid, 
            self.config.xmi_type: "uml:Generalization",
            "general": str(general_ref)
        }
        
        # Add virtual inheritance marker if applicable
        if is_virtual:
            attrs["isVirtual"] = "true"
            
        # Add final class marker if applicable
        if is_final:
            attrs["isFinalSpecialization"] = "true"
            
        el: etree._Element = etree.Element("generalization", attrib=attrs, nsmap=self.config.uml_nsmap)
        self.xf.write(el)

    def write_association(self, assoc: UmlAssociation, uml_model: Optional[UmlModel] = None) -> None:
        """Write association - XMI 2.1 compliant."""
        # Get UML model for type information
        if uml_model is None:
            uml_model = DEFAULT_MODEL.uml
        
        # Prefer precomputed stable ids (set earlier in XmiGenerator.write)
        aid: str = assoc._assoc_id or stable_id(f"assoc:{assoc.src}:{assoc.tgt}:{assoc.name}")
        
        # XMI 2.1 compliant association attributes
        assoc_el: etree._Element = etree.Element(
            "packagedElement",
            attrib={
                self.config.xmi_type: uml_model.association_type,
                self.config.xmi_id: aid,
                "name": xml_text(assoc.name or ""),
                "visibility": "public"  # Default visibility for XMI 2.1
            },
            nsmap=self.config.uml_nsmap
        )

        # Compute end ids (use precomputed if available)
        end1_id: str = assoc._end1_id or stable_id(aid + ":end1")
        end2_id: str = assoc._end2_id or stable_id(aid + ":end2")

        def add_bound_value(parent: etree._Element, tag: str, value: str) -> None:
            """Add lowerValue/upperValue with proper xmi:type for XMI 2.1."""
            if value == "-1" or value == "*" or value.strip() == "*":
                literal_type: str = uml_model.literal_unlimited_natural_type
                literal_value: str = uml_model.unlimited_multiplicity
            else:
                literal_type: str = uml_model.literal_integer_type
                literal_value: str = str(value)
                
            # XMI 2.1 compliant bound value
            bound_el = etree.SubElement(
                parent, tag,
                attrib={
                    self.config.xmi_type: literal_type,
                    self.config.xmi_id: stable_id(parent.get(self.config.xmi_id) + ":" + tag),
                    "value": literal_value
                },
                nsmap=self.config.uml_nsmap
            )
            return bound_el

        # Add association ends with XMI 2.1 compliance
        # Use source element ID as name for end1
        end1_el = etree.SubElement(assoc_el, "ownedEnd", attrib={
            self.config.xmi_id: end1_id,
            "name": f"end1_{assoc.src}",  # Use source ID as name
            "visibility": "public",
            "isOrdered": "false",
            "isUnique": "true",
            "isReadOnly": "false",
            "aggregation": "none",
            "type": str(assoc.src),
            "association": aid
        }, nsmap=self.config.uml_nsmap)
        
        # Add multiplicity for end1 - use default if not specified
        add_bound_value(end1_el, "lowerValue", "1")
        add_bound_value(end1_el, "upperValue", "1")

        # Use target element ID as name for end2
        end2_el = etree.SubElement(assoc_el, "ownedEnd", attrib={
            self.config.xmi_id: end2_id,
            "name": f"end2_{assoc.tgt}",  # Use target ID as name
            "visibility": "public",
            "isOrdered": "false",
            "isUnique": "true",
            "isReadOnly": "false",
            "aggregation": "none",
            "type": str(assoc.tgt),
            "association": aid
        }, nsmap=self.config.uml_nsmap)
        
        # Add multiplicity for end2 - use association multiplicity if specified
        if assoc.multiplicity:
            if assoc.multiplicity == "*":
                add_bound_value(end2_el, "lowerValue", "0")
                add_bound_value(end2_el, "upperValue", "*")
            else:
                add_bound_value(end2_el, "lowerValue", "1")
                add_bound_value(end2_el, "upperValue", assoc.multiplicity)
        else:
            # Default multiplicity
            add_bound_value(end2_el, "lowerValue", "1")
            add_bound_value(end2_el, "upperValue", "1")

        # Add memberEnd references to the association (XMI: idref to the ends)
        etree.SubElement(assoc_el, "memberEnd", attrib={
            self.config.xmi_idref: end1_id
        }, nsmap=self.config.uml_nsmap)
        etree.SubElement(assoc_el, "memberEnd", attrib={
            self.config.xmi_idref: end2_id
        }, nsmap=self.config.uml_nsmap)

        # Write the complete association
        self.xf.write(assoc_el)

    def write_packaged_element_raw(self, element: etree._Element) -> None:
        """Write raw packaged element - XMI 2.1 compliant."""
        self.xf.write(element)
