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
from CppParser import CppTypeParser

from uml_types import TypedDict

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
    """Concrete visitor that writes UML elements to XMI 2.1 compliant format."""
    
    def __init__(self, writer: XmiWriter, name_to_xmi: Dict[ElementName, XmiId], model: UmlModel) -> None:
        self.writer: XmiWriter = writer
        self.name_to_xmi: Dict[ElementName, XmiId] = name_to_xmi
        self.model: UmlModel = model

    def visit_class(self, info: UmlElement) -> None:
        """Visit class element - XMI 2.1 compliant."""
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
        
        # Write template parameters if this is a template class - XMI 2.1 compliant
        if hasattr(info, 'templates') and info.templates:
            signature_id: str = stable_id(xmi + ":templateSignature")
            self.writer.start_template_signature(signature_id)
            for i, template_param in enumerate(info.templates):
                template_id: str = stable_id(xmi + ":template:" + str(i))
                self.writer.write_template_parameter(template_id, template_param)
            self.writer.end_template_signature()

        # Write template binding for instantiation elements (guarded)
        inst_of = getattr(info, 'instantiation_of', None)
        inst_args = getattr(info, 'instantiation_args', []) or []
        if inst_of and isinstance(inst_args, list) and inst_args and all(arg is not None for arg in inst_args):
            # Verify base template has a signature (i.e., base element is a template)
            base_elem = None
            try:
                base_elem = self.model.elements.get(inst_of)  # type: ignore[attr-defined]
            except Exception:
                base_elem = None
            has_signature = bool(base_elem and getattr(base_elem, 'templates', None))
            if has_signature:
                signature_ref: XmiId = XmiId(stable_id(str(inst_of) + ":templateSignature"))
                try:
                    self.writer.write_template_binding(stable_id(xmi + ":binding"), signature_ref, inst_args)  # type: ignore[arg-type]
                except Exception as e:
                    logger.warning(f"Skip templateBinding for '{name}': {e}")
        
        # Write generalizations as owned elements - XMI 2.1 compliant
        generalizations = getattr(self.model, "generalizations", []) or []
        for gen in generalizations:
            if gen.child_id == xmi:  # This generalization belongs to this class
                self.writer.write_generalization(
                    stable_id(str(gen.child_id) + ":gen"), 
                    gen.parent_id,
                    inheritance_type=gen.inheritance_type.value if gen.inheritance_type else "public",
                    is_virtual=gen.is_virtual,
                    is_final=gen.is_final
                )
        
        # Write owned attributes - XMI 2.1 compliant
        for m in info.members:
            aid: str = stable_id(xmi + ":attr:" + m.name)
            tref: Optional[XmiId] = self.name_to_xmi.get(ElementName(m.type_repr)) if m.type_repr else None
            self.writer.write_owned_attribute(
                aid, m.name, visibility=m.visibility.value, 
                type_ref=tref, is_static=m.is_static
            )
        
        # Write owned operations - XMI 2.1 compliant
        for op in info.operations:
            # Handle operations if they exist
            op_id: str = stable_id(xmi + ":op:" + op.name)
            return_type_ref: Optional[XmiId] = self.name_to_xmi.get(ElementName(op.return_type)) if op.return_type else None
            
            # Start operation
            self.writer.start_owned_operation(op_id, op.name, visibility=op.visibility.value, is_static=op.is_static)
            
            # Add return type if exists
            if return_type_ref:
                self.writer.write_operation_return_type(op_id, return_type_ref)
            
            # Add parameters - XMI 2.1 compliant
            for param_name, param_type in op.parameters:
                # Validate parameter data to prevent invalid direction values
                if not isinstance(param_name, str) or not isinstance(param_type, str):
                    import logging
                    logging.warning(f"Skipping invalid parameter data: name={param_name}, type={param_type}")
                    continue
                    
                # Ensure parameter name is not an ID
                if param_name.startswith("id_"):
                    import logging
                    logging.warning(f"Parameter name appears to be an ID, using 'unnamed_param': {param_name}")
                    param_name = "unnamed_param"
                
                param_id: str = stable_id(op_id + ":param:" + param_name)
                param_type_ref: Optional[XmiId] = self.name_to_xmi.get(ElementName(param_type)) if param_type else None
                self.writer.write_owned_parameter(param_id, param_name, "in", param_type_ref)
            
            self.writer.end_owned_operation()
        
        self.writer.end_packaged_element()

    def visit_enum(self, info: UmlElement) -> None:
        """Visit enum element - XMI 2.1 compliant."""
        name: ElementName = info.name
        xmi: XmiId = info.xmi
        is_abstract: bool = bool(info.clang.is_abstract)
        
        # Extract short name from qualified name (e.g., "MyNamespace::MyEnum" -> "MyEnum")
        short_name = str(name).split('::')[-1] if '::' in str(name) else str(name)
        
        # Use UML model for element type
        uml_model = DEFAULT_MODEL.uml
        self.writer.start_packaged_element(xmi, uml_model.enum_type, short_name, is_abstract=is_abstract)
        
        # Handle literals if they exist - XMI 2.1 compliant
        if hasattr(info, 'literals') and info.literals:
            for lit in info.literals:
                lit_id: str = stable_id(xmi + ":literal:" + lit)
                self.writer.write_enum_literal(lit_id, lit)
        
        self.writer.end_packaged_element()

    def visit_datatype(self, info: UmlElement) -> None:
        """Visit datatype element - XMI 2.1 compliant."""
        name: ElementName = info.name
        xmi: XmiId = info.xmi
        is_abstract: bool = bool(info.clang.is_abstract)
        
        # Extract short name from qualified name (e.g., "MyNamespace::MyType" -> "MyType")
        short_name = str(name).split('::')[-1] if '::' in str(name) else str(name)
        
        # Use UML model for element type
        uml_model = DEFAULT_MODEL.uml
        self.writer.start_packaged_element(xmi, uml_model.datatype_type, short_name, is_abstract=is_abstract)
        
        # Add generalization if underlying type exists - XMI 2.1 compliant
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
        
        # Resolve association targets to use the correct stub element IDs
        self._resolve_association_targets()
        
        # Clean up invalid associations
        self._cleanup_invalid_associations()
        
        # Update namespace tree with stubs
        self.namespace_tree = self._build_namespace_tree(self.created)
        
        # Validate the model before generation
        self._validate_model()

    def _build_namespace_tree(self, elements: Dict[ElementName, UmlElement]) -> NamespaceTree:
        """Build namespace hierarchy tree from elements."""
        tree: NamespaceTree = {}
        logger.info(f"Building namespace tree for {len(elements)} elements")
        
        # First, add pre-created namespace packages from UmlModel
        if hasattr(self.model, 'namespace_packages') and self.model.namespace_packages:
            for namespace_name, namespace_xmi in self.model.namespace_packages.items():
                tree[namespace_name] = {'__namespace__': True, '__children__': {}, '__xmi_id__': namespace_xmi}
                logger.debug(f"Added pre-created namespace: {namespace_name} -> {namespace_xmi}")
        
        for q_name, info in elements.items():
            try:
                # Convert ElementName to string for processing
                name_str = str(q_name)
                
                if '::' not in name_str:
                    # Root level element
                    tree[name_str] = info
                    logger.debug(f"Added root element: {name_str}")
                else:
                    # Namespaced element - simple namespace splitting
                    parts = name_str.split('::')
                    
                    if len(parts) == 1:
                        # No namespace separator found
                        tree[name_str] = info
                        logger.debug(f"Added element without namespace: {name_str}")
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
        
        # Also collect from associations that reference undefined types
        for assoc in self.model.associations:
            # Check if target is a valid XMI ID that exists in created elements
            if assoc.tgt not in [info.xmi for info in self.created.values()]:
                # This association references an undefined type - we need to create a stub for it
                # The target might be a type name that needs to be resolved
                # For now, we'll skip this as we'll handle it in _resolve_association_targets
                pass
        
        return all_referenced_type_names

    def _create_stub_elements(self) -> None:
        """Create stub elements for referenced but undefined types."""
        logger.info(f"Creating stub elements for {len(self.all_referenced_type_names)} referenced types")
        stub_count = 0
        
        # Clean up extremely long type names to avoid issues
        cleaned_type_names = set()
        for type_name in self.all_referenced_type_names:
            if len(type_name) > 200:
                # Truncate very long names
                cleaned_name = type_name[:200] + "..."
                logger.warning(f"Type name too long ({len(type_name)} chars), truncating: {cleaned_name}")
                cleaned_type_names.add(cleaned_name)
            else:
                cleaned_type_names.add(type_name)
        
        for type_name in cleaned_type_names:
            # Skip if already created or if it's a primitive type
            if type_name in self.created or ElementName(type_name) in self.name_to_xmi:
                continue
                
            # Skip primitive types that don't need stubs
            if type_name in ['int', 'char', 'bool', 'float', 'double', 'void', 'string', 'std::string']:
                continue
                
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

    def _resolve_association_targets(self) -> None:
        """Resolve association targets to use the correct stub element IDs."""
        logger.info(f"Resolving association targets for {len(self.model.associations)} associations")
        resolved_count = 0
        
        for assoc in self.model.associations:
            # Check if target is a valid XMI ID that exists in created elements
            if assoc.tgt not in [info.xmi for info in self.created.values()]:
                # This association references an undefined type
                # Try to find a stub element that might match this target
                target_found = False
                
                # Look for a stub element that might match this target
                for name, info in self.created.items():
                    if info.xmi == assoc.tgt:
                        # This is already a valid reference
                        target_found = True
                        break
                
                if not target_found:
                    # Try to find by name in the name_to_xmi mapping
                    # This handles cases where the target might be a type name that was converted to an ElementName
                    for name, xmi_id in self.name_to_xmi.items():
                        if xmi_id == assoc.tgt:
                            # Found the name, check if it exists in created elements
                            if name in self.created:
                                target_found = True
                                break
                
                if not target_found:
                    logger.warning(f"Association '{assoc.name}' has unresolved target: {assoc.tgt}")
        
        logger.info(f"Resolved {resolved_count} association targets")

    def _cleanup_invalid_associations(self) -> None:
        """Removes associations that reference undefined elements."""
        logger.info(f"Cleaning up invalid associations for {len(self.model.associations)} total associations")
        valid_associations: List[UmlAssociation] = []
        removed_count = 0
        
        # Get all valid XMI IDs from created elements
        valid_xmi_ids = {element.xmi for element in self.created.values()}
        
        for assoc in self.model.associations:
            if assoc.src in valid_xmi_ids and assoc.tgt in valid_xmi_ids:
                valid_associations.append(assoc)
            else:
                logger.warning(f"Association '{assoc.name}' references undefined elements. Removing.")
                logger.debug(f"Association '{assoc.name}' src: {assoc.src}, tgt: {assoc.tgt}")
                removed_count += 1
        
        self.model.associations = valid_associations
        logger.info(f"Removed {removed_count} invalid associations. {len(self.model.associations)} associations remain.")

    def _validate_model(self) -> None:
        """Validate the model before XMI generation."""
        logger.info("Validating model...")
        
        validation_errors: List[str] = []
        
        # Create reverse mapping from XMI ID to ElementName for validation
        xmi_to_name: Dict[XmiId, ElementName] = {xmi_id: name for name, xmi_id in self.name_to_xmi.items()}
        
        # Check for elements without names
        for name, element in self.created.items():
            if not element.name:
                validation_errors.append(f"Element {name} has no name")
            
            # Check for elements without XMI IDs
            if not element.xmi:
                validation_errors.append(f"Element {name} has no XMI ID")
            
            # Check for members with invalid types
            for member in element.members:
                if member.type_repr:
                    # Skip primitive types that don't need UML elements
                    if member.type_repr in ['int', 'char', 'bool', 'float', 'double', 'void', 'string', 'std::string', 'long', 'short', 'unsigned', 'signed']:
                        continue
                    if ElementName(member.type_repr) not in self.name_to_xmi:
                        validation_errors.append(f"Member {member.name} in {name} references undefined type: {member.type_repr}")
        
        # Check for associations with undefined source or target elements
        association_errors = 0
        # Get all valid XMI IDs from created elements
        valid_xmi_ids = {element.xmi for element in self.created.values()}
        
        for assoc in self.model.associations:
            if assoc.src not in valid_xmi_ids:
                validation_errors.append(f"Association '{assoc.name}' references undefined source element: {assoc.src}")
                association_errors += 1
            if assoc.tgt not in valid_xmi_ids:
                validation_errors.append(f"Association '{assoc.name}' references undefined target element: {assoc.tgt}")
                association_errors += 1
        
        if association_errors > 0:
            logger.warning(f"Found {association_errors} association reference issues")
        
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
                    
                    # Use pre-created XMI ID if available, otherwise generate new one
                    if '__xmi_id__' in item:
                        package_id: str = str(item['__xmi_id__'])
                        logger.debug(f"Using pre-created package ID: {package_id} for {package_name}")
                    else:
                        package_id: str = stable_id(f"package:{package_name}")
                        logger.debug(f"Generated new package ID: {package_id} for {package_name}")
                    
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
                
                visitor: UmlXmiWritingVisitor = UmlXmiWritingVisitor(writer, self.name_to_xmi, self.model)
                
                # Write packaged elements (including stubs in their namespaces)
                self._write_package_contents(visitor, namespace_tree)
                
                # Associations, Dependencies, and Generalizations are written at the root level
                logger.info(f"Writing {len(self.model.associations)} associations")
                for assoc in self.model.associations:
                    writer.write_association(assoc, uml_model=DEFAULT_MODEL.uml)

                logger.info(f"Writing {len(self.model.dependencies)} dependencies")
                for owner_q_name, typ in self.model.dependencies:
                    # Debug: log the actual structure of dependencies
                    logger.debug(f"Dependency: owner={owner_q_name} (type: {type(owner_q_name)}), typ={typ} (type: {type(typ)})")
                    
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
                        # Debug: log more details about what's missing
                        if not client_id:
                            logger.debug(f"Client ID missing for: {owner_q_name}")
                        if not supplier_id:
                            logger.debug(f"Supplier ID missing for: {typ} (searched as: {ElementName(typ)})")
                            logger.debug(f"Available names in name_to_xmi: {list(self.name_to_xmi.keys())[:10]}...")

                generalizations = getattr(self.model, "generalizations", []) or []
                logger.info(f"Writing {len(generalizations)} generalizations as owned elements of classes")
                # Generalizations are now written as owned elements of classes in visit_class method
                # No need to write them here at the root level

                writer.end_doc()
                logger.info("XMI file generated successfully")
                
        except Exception as e:
            logger.error(f"Error generating XMI file: {e}")
            raise
