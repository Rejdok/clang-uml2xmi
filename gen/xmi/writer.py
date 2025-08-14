from typing import Any, Dict, Optional, List, Union, Protocol
import logging
from lxml import etree

from utils.ids import stable_id
from utils.xml import xml_text
from meta import XmlMetaModel as NewXmlModel, UmlMetaModel as NewUmlModel, DEFAULT_META
from core.uml_model import UmlAssociation, XmiId

from uml_types import ContextStack, ElementAttributes

# Setup logger
logger = logging.getLogger(__name__)

class XmiWriter:
    def __init__(self, xf: etree.xmlfile, xml_model: Optional[NewXmlModel] = None) -> None:
        self.xf: etree.xmlfile = xf
        self._ctx_stack: ContextStack = []
        self._referenced_type_ids: set[str] = set()
        self._referenced_idrefs: set[str] = set()
        self._emitted_ids: set[str] = set()
        self._emitted_property_ids: set[str] = set()
        
        # Use provided model or default
        if xml_model is None:
            xml_model = DEFAULT_META.xml  # type: ignore[assignment]
        self.config: NewXmlModel = xml_model  # type: ignore[assignment]

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
        # Root model should not have visibility (EMF requirement)
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
        try:
            self._emitted_ids.add(str(xmi_id))
        except Exception:
            pass

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
        try:
            self._emitted_ids.add(str(package_id))
        except Exception:
            pass

    def end_package(self) -> None:
        """End a package element."""
        ctx: etree._Element = self._ctx_stack.pop()
        ctx.__exit__(None, None, None)

    def write_owned_attribute(self, aid: str, name: str, visibility: str = "private", type_ref: Optional[XmiId] = None, is_static: bool = False, association_ref: Optional[XmiId] = None, opposite_ref: Optional[XmiId] = None) -> None:
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
            try:
                self._referenced_type_ids.add(str(type_ref))
                self._referenced_idrefs.add(str(type_ref))
            except Exception:
                pass
        if association_ref:
            attrs["association"] = str(association_ref)
            try:
                self._referenced_idrefs.add(str(association_ref))
            except Exception:
                pass
        if opposite_ref:
            attrs["opposite"] = str(opposite_ref)
            try:
                self._referenced_idrefs.add(str(opposite_ref))
            except Exception:
                pass
            
        el: etree._Element = etree.Element("ownedAttribute", attrib=attrs, nsmap=self.config.uml_nsmap)
        self.xf.write(el)
        try:
            if aid:
                self._emitted_property_ids.add(str(aid))
        except Exception:
            pass

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
        try:
            self._emitted_ids.add(str(oid))
        except Exception:
            pass

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
        try:
            self._emitted_ids.add(str(pid))
        except Exception:
            pass

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
        ctx: etree._Element = self.xf.element(
            "ownedTemplateSignature",
            nsmap=self.config.uml_nsmap,
            **{
                self.config.xmi_id: signature_id,
                self.config.xmi_type: "uml:RedefinableTemplateSignature",
            },
        )
        ctx.__enter__()
        self._ctx_stack.append(ctx)

    def end_template_signature(self) -> None:
        """End template signature."""
        ctx: etree._Element = self._ctx_stack.pop()
        ctx.__exit__(None, None, None)

    def write_template_parameter(self, template_id: str, parameter_name: str) -> None:
        """Write template parameter - XMI 2.1 compliant."""
        el: etree._Element = etree.Element(
            "ownedTemplateParameter",
            nsmap=self.config.uml_nsmap,
            **{
                self.config.xmi_id: template_id,
                self.config.xmi_type: "uml:TemplateParameter",
                "name": xml_text(parameter_name),
            },
        )
        self.xf.write(el)

    def write_template_binding(self, binding_id: str, signature_ref: Optional[XmiId], arg_ids: List[XmiId]) -> None:
        """Write templateBinding with parameterSubstitution entries as a child of current element.
        If signature_ref is None, omit the 'signature' child (permissive mode).
        """
        # Nest within current open packagedElement using xmlfile contexts
        with self.xf.element(
            "templateBinding",
            nsmap=self.config.uml_nsmap,
            **{
                self.config.xmi_id: binding_id,
                self.config.xmi_type: "uml:TemplateBinding",
            },
        ):
            # signature reference (optional)
            if signature_ref is not None:
                with self.xf.element(
                    "signature",
                    nsmap=self.config.uml_nsmap,
                    **{self.config.xmi_idref: str(signature_ref)},
                ):
                    pass

            # substitutions
            for i, aid in enumerate(arg_ids):
                with self.xf.element(
                    "parameterSubstitution",
                    nsmap=self.config.uml_nsmap,
                    **{self.config.xmi_id: stable_id(binding_id + f":sub:{i}")},
                ):
                    with self.xf.element(
                        "actual",
                        nsmap=self.config.uml_nsmap,
                        **{self.config.xmi_idref: str(aid)},
                    ):
                        pass

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
        try:
            self._referenced_idrefs.add(str(general_ref))
            self._emitted_ids.add(str(gid))
        except Exception:
            pass

    def write_association(self, assoc: UmlAssociation, uml_model: Optional[NewUmlModel] = None) -> None:
        """Write association - XMI 2.1 compliant."""
        # Get UML model for type information
        if uml_model is None:
            uml_model = DEFAULT_META.uml  # type: ignore[assignment]
        
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
        try:
            self._emitted_ids.add(aid)
        except Exception:
            pass

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

        # For UML2 5.x: Prefer class-owned Property ids when provided.
        # If not provided, create ownedEnd Properties under the Association and reference them
        # only when allowed by configuration.
        from app.config import DEFAULT_CONFIG
        allow_owned = True
        try:
            allow_owned = DEFAULT_CONFIG.allow_owned_end
        except Exception:
            pass
        create_owned_end1: bool = False
        create_owned_end2: bool = False
        if not assoc._end1_id:
            if allow_owned:
                create_owned_end1 = True
            end1_id = stable_id(aid + ":end1")
        if not assoc._end2_id:
            if allow_owned:
                create_owned_end2 = True
            end2_id = stable_id(aid + ":end2")
            
        # For self-referential associations (same end IDs), always create ownedEnd to avoid duplicate memberEnd
        if end1_id == end2_id:
            create_owned_end1 = True
            create_owned_end2 = True
            # Generate unique IDs for the ownedEnd properties
            end1_id = stable_id(aid + ":ownedEnd1")
            end2_id = stable_id(aid + ":ownedEnd2")

        if create_owned_end1:
            # ownedEnd 1 -> type = src
            end1_el = etree.SubElement(
                assoc_el,
                "ownedEnd",
                attrib={
                    self.config.xmi_type: "uml:Property",
                    self.config.xmi_id: end1_id,
                    "name": f"end1_{assoc.src}",
                    "visibility": "public",
                    "isOrdered": "false",
                    "isUnique": "true",
                    "isReadOnly": "false",
                    "aggregation": "none",
                    "type": str(assoc.src),
                    "association": aid,
                },
                nsmap=self.config.uml_nsmap,
            )
            add_bound_value(end1_el, "lowerValue", "1")
            add_bound_value(end1_el, "upperValue", "1")
            try:
                if end1_id:
                    self._emitted_property_ids.add(str(end1_id))
                    self._emitted_ids.add(str(end1_id))
            except Exception:
                pass

        if create_owned_end2:
            # ownedEnd 2 -> type = tgt
            end2_el = etree.SubElement(
                assoc_el,
                "ownedEnd",
                attrib={
                    self.config.xmi_type: "uml:Property",
                    self.config.xmi_id: end2_id,
                    "name": f"end2_{assoc.tgt}",
                    "visibility": "public",
                    "isOrdered": "false",
                    "isUnique": "true",
                    "isReadOnly": "false",
                    "aggregation": "none",
                    "type": str(assoc.tgt),
                    "association": aid,
                },
                nsmap=self.config.uml_nsmap,
            )
            add_bound_value(end2_el, "lowerValue", "1")
            add_bound_value(end2_el, "upperValue", "1")
            try:
                if end2_id:
                    self._emitted_property_ids.add(str(end2_id))
                    self._emitted_ids.add(str(end2_id))
            except Exception:
                pass

        # Do not set 'opposite' attributes on ends to avoid conflicts during EMF load

        # If any ownedEnd was created (i.e., конец не у класса), помечаем ассоциацию eAnnotation как стереотип
        from app.config import DEFAULT_CONFIG
        cfg_annotate = True
        try:
            cfg_annotate = DEFAULT_CONFIG.annotate_owned_end
        except Exception:
            pass
        if cfg_annotate and (create_owned_end1 or create_owned_end2):
            try:
                ann = etree.SubElement(
                    assoc_el,
                    "eAnnotations",
                    attrib={
                        "source": "cpp",
                    },
                    nsmap=self.config.uml_nsmap,
                )
                etree.SubElement(
                    ann,
                    "details",
                    attrib={
                        "key": "stereotype",
                        "value": "OwnedEnd",
                    },
                    nsmap=self.config.uml_nsmap,
                )
                etree.SubElement(
                    ann,
                    "details",
                    attrib={
                        "key": "end1",
                        "value": "owned" if create_owned_end1 else "class",
                    },
                    nsmap=self.config.uml_nsmap,
                )
                etree.SubElement(
                    ann,
                    "details",
                    attrib={
                        "key": "end2",
                        "value": "owned" if create_owned_end2 else "class",
                    },
                    nsmap=self.config.uml_nsmap,
                )
            except Exception:
                pass

        # Always declare memberEnd idrefs (either class-owned or the ownedEnd we just created)
        # EMF requires exactly 2 memberEnd for valid association
        # Ensure both end IDs are valid before creating memberEnd
        if end1_id and end2_id:
            etree.SubElement(assoc_el, "memberEnd", attrib={self.config.xmi_idref: end1_id}, nsmap=self.config.uml_nsmap)
            etree.SubElement(assoc_el, "memberEnd", attrib={self.config.xmi_idref: end2_id}, nsmap=self.config.uml_nsmap)
        else:
            logger.warning(f"Skipping association {aid} due to invalid end IDs: end1={end1_id}, end2={end2_id}")
            return  # Don't create invalid association
        try:
            self._referenced_idrefs.add(str(end1_id))
            self._referenced_idrefs.add(str(end2_id))
        except Exception:
            pass

        # Write the complete association
        self.xf.write(assoc_el)
        # Track referenced type ids for post-materialization
        try:
            if assoc.src:
                self._referenced_type_ids.add(str(assoc.src))
            if assoc.tgt:
                self._referenced_type_ids.add(str(assoc.tgt))
        except Exception:
            pass

    def get_referenced_type_ids(self) -> set[str]:
        return set(self._referenced_type_ids)

    def get_referenced_idrefs(self) -> set[str]:
        return set(self._referenced_idrefs)

    def get_emitted_property_ids(self) -> set[str]:
        return set(self._emitted_property_ids)

    def get_emitted_ids(self) -> set[str]:
        return set(self._emitted_ids)

    def write_packaged_element_raw(self, element: etree._Element) -> None:
        """Write raw packaged element - XMI 2.1 compliant."""
        self.xf.write(element)
    
    def write_comment(self, text: str) -> None:
        """Write XML comment (for file writers, we'll skip this)."""
        # Skip comments for file writers as they don't support append
        pass

__all__ = ["XmiWriter"]


