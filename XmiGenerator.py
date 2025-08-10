#!/usr/bin/env python3
"""
XMI Generator for UML2Papyrus project.
Generates XMI files from UML model data.
"""

import logging
from typing import Dict, Any, List, Set, Optional, Union, cast
from lxml import etree
from UmlModel import (
    UmlModel, UmlElement, UmlAssociation, ElementKind, 
    ClangMetadata, XmiId, ElementName, TypeName
)
from XmiWriter import XmiWriter
from Utils import stable_id, xml_text
from Model import DEFAULT_MODEL

from uml_types import TypedDict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Type aliases for better readability
class NamespaceTree(TypedDict):
    __annotations__: Dict[str, Union[UmlElement, Dict[str, Any]]]

class NamespaceNode(TypedDict):
    __annotations__: Dict[str, Union[bool, Dict[str, Any], UmlElement]]

# ---------- Visitor Pattern for XMI Generation ----------
class XmiElementVisitor:
    """Abstract visitor for XMI element generation."""
    
    def visit_class(self, info: UmlElement) -> None:
        raise NotImplementedError
    
    def visit_enum(self, info: UmlElement) -> None:
        raise NotImplementedError
    
    def visit_datatype(self, info: UmlElement) -> None:
        raise NotImplementedError

class UmlXmiWritingVisitor(XmiElementVisitor):
    """Concrete visitor that writes UML elements to an XMI file."""
    
    def __init__(self, writer: XmiWriter, name_to_xmi: Dict[ElementName, XmiId]) -> None:
        self.writer: XmiWriter = writer
        self.name_to_xmi: Dict[ElementName, XmiId] = name_to_xmi

    def visit_class(self, info: UmlElement) -> None:
        name: ElementName = info.name
        xmi: XmiId = info.xmi
        is_abstract: bool = bool(info.clang.is_abstract)
        
        # Check if this is a template class
        extra_attrs: Optional[Dict[str, str]] = None
        if hasattr(info, 'templates') and info.templates:
            extra_attrs = {"isTemplate": "true"}
        
        # Extract short name from qualified name (e.g., "MyNamespace::MyClass" -> "MyClass")
        short_name = str(name).split('::')[-1] if '::' in str(name) else str(name)
        
        # Use UML model for element type
        uml_model = DEFAULT_MODEL.uml
        self.writer.start_packaged_element(xmi, uml_model.class_type, short_name, is_abstract=is_abstract, extra_attrs=extra_attrs)
        
        # Write template parameters if this is a template class
        if hasattr(info, 'templates') and info.templates:
            for i, template_param in enumerate(info.templates):
                template_id: str = stable_id(xmi + ":template:" + str(i))
                self.writer.write_template_parameter(template_id, template_param)
        
        for m in info.members:
            aid: str = stable_id(xmi + ":attr:" + m.name)
            tref: Optional[XmiId] = self.name_to_xmi.get(ElementName(m.type_repr)) if m.type_repr else None
            self.writer.write_owned_attribute(
                aid, m.name, visibility=m.visibility.value, 
                type_ref=tref, is_static=m.is_static
            )
        
        for op in info.operations:
            # Handle operations if they exist
            op_id: str = stable_id(xmi + ":op:" + op.name)
            return_type_ref: Optional[XmiId] = self.name_to_xmi.get(ElementName(op.return_type)) if op.return_type else None
            
            # Start operation
            self.writer.start_owned_operation(op_id, op.name, visibility=op.visibility.value, is_static=op.is_static)
            
            # Add return type if exists
            if return_type_ref:
                self.writer.write_operation_return_type(return_type_ref)
            
            # Add parameters
            for param_name, param_type in op.parameters:
                param_id: str = stable_id(op_id + ":param:" + param_name)
                param_type_ref: Optional[XmiId] = self.name_to_xmi.get(ElementName(param_type)) if param_type else None
                self.writer.write_owned_parameter(param_id, param_name, param_type_ref)
            
            self.writer.end_owned_operation()
        
        self.writer.end_packaged_element()

    def visit_enum(self, info: UmlElement) -> None:
        name: ElementName = info.name
        xmi: XmiId = info.xmi
        is_abstract: bool = bool(info.clang.is_abstract)
        
        # Extract short name from qualified name (e.g., "MyNamespace::MyEnum" -> "MyEnum")
        short_name = str(name).split('::')[-1] if '::' in str(name) else str(name)
        
        # Use UML model for element type
        uml_model = DEFAULT_MODEL.uml
        self.writer.start_packaged_element(xmi, uml_model.enum_type, short_name, is_abstract=is_abstract)
        
        # Handle literals if they exist
        if hasattr(info, 'literals') and info.literals:
            for lit in info.literals:
                lit_id: str = stable_id(xmi + ":literal:" + lit)
                self.writer.write_enum_literal(lit_id, lit)
        
        self.writer.end_packaged_element()

    def visit_datatype(self, info: UmlElement) -> None:
        name: ElementName = info.name
        xmi: XmiId = info.xmi
        is_abstract: bool = bool(info.clang.is_abstract)
        
        # Extract short name from qualified name (e.g., "MyNamespace::MyType" -> "MyType")
        short_name = str(name).split('::')[-1] if '::' in str(name) else str(name)
        
        # Use UML model for element type
        uml_model = DEFAULT_MODEL.uml
        self.writer.start_packaged_element(xmi, uml_model.datatype_type, short_name, is_abstract=is_abstract)
        if info.underlying:
            tref: Optional[XmiId] = self.name_to_xmi.get(ElementName(info.underlying))
            if tref:
                self.writer.write_generalization(stable_id(xmi + ":gen"), tref)
        self.writer.end_packaged_element()

# -------------------- XMI Generator (Refactored) --------------------
class XmiGenerator:
    """Generates XMI files from UML model data."""
    
    def __init__(self, model: UmlModel) -> None:
        self.model: UmlModel = model
        self.name_to_xmi: Dict[ElementName, XmiId] = model.name_to_xmi
        
        # Create a mapping from ElementName to UmlElement for namespace tree building
        self.created: Dict[ElementName, UmlElement] = {}
        for name, xmi_id in self.name_to_xmi.items():
            if xmi_id in model.elements:
                self.created[name] = model.elements[xmi_id]
        
        # Build namespace tree for real elements only
        self.namespace_tree: NamespaceTree = self._build_namespace_tree(self.created)
        
        # Collect all referenced type names
        self.all_referenced_type_names: Set[str] = self._collect_referenced_types()
        
        # Create stub elements for referenced but undefined types
        self._create_stub_elements()
        
        # Update namespace tree with stubs
        self.namespace_tree = self._build_namespace_tree(self.created)
        
        # Validate the model before generation
        self._validate_model()

    def _build_namespace_tree(self, elements: Dict[ElementName, UmlElement]) -> NamespaceTree:
        """Build namespace hierarchy tree from elements."""
        tree: NamespaceTree = {}
        logger.info(f"Building namespace tree for {len(elements)} elements")
        
        for q_name, info in elements.items():
            try:
                # Convert ElementName to string for processing
                name_str = str(q_name)
                
                if '::' not in name_str:
                    # Root level element
                    tree[name_str] = info
                    logger.debug(f"Added root element: {name_str}")
                else:
                    # Namespaced element - need to handle template types carefully
                    # Split by :: but be careful with template syntax like std::vector<int>
                    parts: List[str] = []
                    current_part = ""
                    bracket_count = 0
                    
                    for char in name_str:
                        if char == '<':
                            bracket_count += 1
                        elif char == '>':
                            bracket_count -= 1
                        elif char == ':' and bracket_count == 0:
                            if current_part:
                                parts.append(current_part)
                                current_part = ""
                            # Skip the second : in ::
                            continue
                        else:
                            current_part += char
                    
                    if current_part:
                        parts.append(current_part)
                    
                    if len(parts) == 1:
                        # No namespace separator found (template syntax interfered)
                        tree[name_str] = info
                        logger.debug(f"Added template element: {name_str}")
                    else:
                        # Namespaced element
                        current: NamespaceTree = tree
                        
                        # Navigate/create namespace path
                        for part in parts[:-1]:
                            if part not in current:
                                current[part] = {'__namespace__': True, '__children__': {}}
                                logger.debug(f"Created namespace: {part}")
                            elif not isinstance(current[part], dict) or '__namespace__' not in current[part]:
                                # If this node is not a namespace (e.g., it's a UmlElement), 
                                # we need to convert it to a namespace
                                existing_element: UmlElement = current[part]  # type: ignore
                                current[part] = {'__namespace__': True, '__children__': {}}
                                # Move the existing element to a child with a default name
                                current[part]['__children__']['__root__'] = existing_element  # type: ignore
                                logger.debug(f"Converted element to namespace: {part}")
                            current = current[part]['__children__']  # type: ignore
                        
                        # Add the actual element
                        current[parts[-1]] = info
                        logger.debug(f"Added namespaced element: {parts[-1]} in {'::'.join(parts[:-1])}")
            except Exception as e:
                logger.error(f"Error processing element {q_name}: {e}")
                # Fallback: add as root element
                tree[str(q_name)] = info
        
        logger.info(f"Namespace tree built successfully with {len(tree)} root nodes")
        return tree

    def _collect_referenced_types(self) -> Set[str]:
        """Collect all type names referenced in the model."""
        all_referenced_type_names: Set[str] = set()
        
        for name, info in self.created.items():
            # Collect from members
            for m in info.members:
                if m.type_repr:
                    all_referenced_type_names.add(m.type_repr)
            
            # Collect from operations
            if hasattr(info, 'operations'):
                for op in info.operations:
                    if op.return_type:
                        all_referenced_type_names.add(op.return_type)
                    for param_name, param_type in op.parameters:
                        if param_type:
                            all_referenced_type_names.add(param_type)
            
            # Collect from templates
            if hasattr(info, 'templates'):
                for t in info.templates:
                    all_referenced_type_names.add(t)
            
            # Collect from associations
            for assoc in self.model.associations:
                if assoc.name:
                    all_referenced_type_names.add(assoc.name)
        
        return all_referenced_type_names

    def _create_stub_elements(self) -> None:
        """Create stub elements for referenced but undefined types."""
        logger.info(f"Creating stub elements for {len(self.all_referenced_type_names)} referenced types")
        stub_count = 0
        
        for type_name in self.all_referenced_type_names:
            if type_name not in self.created and ElementName(type_name) not in self.name_to_xmi:
                try:
                    # Create stub element
                    stub_id: XmiId = XmiId(stable_id(f"stub:{type_name}"))
                    self.name_to_xmi[ElementName(type_name)] = stub_id
                    
                    # Create stub UmlElement
                    stub_element: UmlElement = UmlElement(
                        xmi=stub_id,
                        name=ElementName(type_name),
                        kind=ElementKind.DATATYPE,
                        members=[],
                        clang=ClangMetadata(),
                        used_types=frozenset(),
                        underlying=None
                    )
                    
                    self.created[ElementName(type_name)] = stub_element
                    stub_count += 1
                    logger.debug(f"Created stub for type: {type_name}")
                except Exception as e:
                    logger.error(f"Error creating stub for type {type_name}: {e}")
        
        logger.info(f"Created {stub_count} stub elements")

    def _validate_model(self) -> None:
        """Validate the model before XMI generation."""
        logger.info("Validating model...")
        
        validation_errors: List[str] = []
        
        # Check for elements without names
        for name, element in self.created.items():
            if not element.name:
                validation_errors.append(f"Element {name} has no name")
            
            # Check for elements without XMI IDs
            if not element.xmi:
                validation_errors.append(f"Element {name} has no XMI ID")
            
            # Check for members with invalid types
            for member in element.members:
                if member.type_repr and ElementName(member.type_repr) not in self.name_to_xmi:
                    validation_errors.append(f"Member {member.name} in {name} references undefined type: {member.type_repr}")
        
        # Check for circular dependencies in associations
        for assoc in self.model.associations:
            if assoc.src not in self.name_to_xmi or assoc.tgt not in self.name_to_xmi:
                validation_errors.append(f"Association {assoc.name} references undefined types: {assoc.src} -> {assoc.tgt}")
        
        if validation_errors:
            logger.warning(f"Model validation found {len(validation_errors)} issues:")
            for error in validation_errors:
                logger.warning(f"  - {error}")
        else:
            logger.info("Model validation passed successfully")

    def get_model_statistics(self) -> Dict[str, Any]:
        """Get statistics about the model."""
        stats = {
            'total_elements': len(self.created),
            'classes': len([e for e in self.created.values() if e.kind == ElementKind.CLASS]),
            'enums': len([e for e in self.created.values() if e.kind == ElementKind.ENUM]),
            'datatypes': len([e for e in self.created.values() if e.kind == ElementKind.DATATYPE]),
            'templates': len([e for e in self.created.values() if hasattr(e, 'templates') and e.templates]),
            'associations': len(self.model.associations),
            'dependencies': len(self.model.dependencies),
            'generalizations': len(getattr(self.model, 'generalizations', []) or []),
            'stub_elements': len([e for e in self.created.values() if str(e.xmi).startswith('stub:')])
        }
        
        logger.info("Model statistics:")
        for key, value in stats.items():
            logger.info(f"  {key}: {value}")
        
        return stats

    def _write_package_contents(self, visitor: UmlXmiWritingVisitor, tree: NamespaceTree, parent_name: str = "") -> None:
        """Recursively write package contents."""
        logger.debug(f"Writing package contents for: {parent_name or 'root'}")
        
        for name, item in tree.items():
            try:
                if isinstance(item, dict) and item.get('__namespace__'):
                    # This is a namespace
                    package_name: str = f"{parent_name}::{name}" if parent_name else name
                    package_id: str = stable_id(f"package:{package_name}")
                    
                    logger.debug(f"Starting package: {package_name}")
                    # Start package using the visitor's writer
                    visitor.writer.start_package(package_id, name)
                    
                    # Write namespace contents
                    children: Dict[str, Any] = item.get('__children__', {})  # type: ignore
                    self._write_package_contents(visitor, children, package_name)
                    
                    # End package using the visitor's writer
                    visitor.writer.end_package()
                    logger.debug(f"Ended package: {package_name}")
                else:
                    # This is an actual element
                    if hasattr(item, 'kind'):
                        logger.debug(f"Writing element: {item.name} (kind: {item.kind})")
                        # Use visitor pattern to handle different element types
                        if item.kind == ElementKind.CLASS:
                            visitor.visit_class(item)
                        elif item.kind == ElementKind.ENUM:
                            visitor.visit_enum(item)
                        elif item.kind == ElementKind.DATATYPE:
                            visitor.visit_datatype(item)
                        else:
                            # Default to class for unknown types
                            logger.warning(f"Unknown element kind '{item.kind}' for '{item.name}', treating as class")
                            visitor.visit_class(item)
                    else:
                        logger.warning(f"Element '{item.name}' has no kind attribute")
            except Exception as e:
                logger.error(f"Error writing package content '{name if isinstance(item, dict) else item.name}': {e}")
                # Continue with other elements

    def write(self, out_path: str, project_name: str) -> None:
        """Write the complete XMI file."""
        from Model import DEFAULT_MODEL
        
        logger.info(f"Starting XMI generation for project: {project_name}")
        logger.info(f"Output file: {out_path}")
        
        # Get and log model statistics
        stats = self.get_model_statistics()
        
        # Build namespace tree for ALL elements (including stubs)
        namespace_tree: NamespaceTree = self._build_namespace_tree(self.created)

        # Step 4: Write the document
        try:
            with etree.xmlfile(out_path, encoding="utf-8") as xf:
                writer: XmiWriter = XmiWriter(xf, xml_model=DEFAULT_MODEL.xml)
                writer.start_doc(project_name, model_id="model_1")
                
                visitor: UmlXmiWritingVisitor = UmlXmiWritingVisitor(writer, self.name_to_xmi)
                
                # Write packaged elements (including stubs in their namespaces)
                self._write_package_contents(visitor, namespace_tree)
                
                # Associations, Dependencies, and Generalizations are written at the root level
                logger.info(f"Writing {len(self.model.associations)} associations")
                for assoc in self.model.associations:
                    writer.write_association(assoc, uml_model=DEFAULT_MODEL.uml)

                logger.info(f"Writing {len(self.model.dependencies)} dependencies")
                for owner_q_name, typ in self.model.dependencies:
                    client_info: Optional[UmlElement] = self.created.get(ElementName(owner_q_name))
                    if not client_info:
                        logger.warning(f"Client not found for dependency: {owner_q_name} -> {typ}")
                        continue
                    client_id: XmiId = client_info.xmi
                    supplier_id: Optional[XmiId] = self.name_to_xmi.get(ElementName(typ))
                    
                    if client_id and supplier_id:
                        dep_id: str = stable_id(f"dep:{owner_q_name}:{typ}")
                        
                        # Use model for dependency attributes
                        xml_model = DEFAULT_MODEL.xml
                        
                        attribs: Dict[str, str] = {
                            xml_model.xmi_type: "uml:Dependency", 
                            xml_model.xmi_id: dep_id,
                            "name": f"dep_{xml_text(owner_q_name)}_to_{xml_text(typ)}",
                            "client": client_id, 
                            "supplier": supplier_id
                        }
                        dep_el: etree._Element = etree.Element("packagedElement", attrib=attribs, nsmap=xml_model.uml_nsmap)
                        xf.write(dep_el)
                    else:
                        logger.warning(f"Missing client or supplier for dependency: {owner_q_name} -> {typ}")

                generalizations = getattr(self.model, "generalizations", []) or []
                logger.info(f"Writing {len(generalizations)} generalizations")
                for gen in generalizations:
                    writer.write_generalization(
                        stable_id(str(gen.child_id) + ":gen"), 
                        gen.parent_id,
                        inheritance_type=gen.inheritance_type.value if gen.inheritance_type else "public",
                        is_virtual=gen.is_virtual,
                        is_final=gen.is_final
                    )

                writer.end_doc()
                logger.info("XMI file generated successfully")
                
        except Exception as e:
            logger.error(f"Error generating XMI file: {e}")
            raise
