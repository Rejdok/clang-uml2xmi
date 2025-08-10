#!/usr/bin/env python3
"""
XMI Generator for UML2Papyrus project.
Generates XMI files from UML model data.
"""

from typing import Dict, Any, List
from lxml import etree
from UmlModel import UmlModel, UmlElement, UmlAssociation, ElementKind
from XmiWriter import XmiWriter
from Utils import stable_id, xml_text
from Model import DEFAULT_MODEL
from UmlModel import ClangMetadata

# ---------- Visitor Pattern for XMI Generation ----------
class XmiElementVisitor:
    """Abstract visitor for XMI element generation."""
    
    def visit_class(self, info: UmlElement):
        raise NotImplementedError
    
    def visit_enum(self, info: UmlElement):
        raise NotImplementedError
    
    def visit_datatype(self, info: UmlElement):
        raise NotImplementedError

class UmlXmiWritingVisitor(XmiElementVisitor):
    """Concrete visitor that writes UML elements to an XMI file."""
    
    def __init__(self, writer: XmiWriter, name_to_xmi: Dict[str, str]):
        self.writer = writer
        self.name_to_xmi = name_to_xmi

    def visit_class(self, info: UmlElement):
        name = info.name
        xmi = info.xmi
        is_abstract = bool(info.clang.is_abstract)
        
        # Use UML model for element type
        uml_model = DEFAULT_MODEL.uml
        self.writer.start_packaged_element(xmi, uml_model.class_type, name, is_abstract=is_abstract)
        
        for m in info.members:
            aid = stable_id(xmi + ":attr:" + m.name)
            tref = self.name_to_xmi.get(m.type_repr)
            self.writer.write_owned_attribute(
                aid, m.name, visibility=m.visibility.value, 
                type_ref=tref, is_static=m.is_static
            )
        
        for op in info.operations:
            # Handle operations if they exist
            pass
        
        self.writer.end_packaged_element()

    def visit_enum(self, info: UmlElement):
        name = info.name
        xmi = info.xmi
        is_abstract = bool(info.clang.is_abstract)
        
        # Use UML model for element type
        uml_model = DEFAULT_MODEL.uml
        self.writer.start_packaged_element(xmi, uml_model.enum_type, name, is_abstract=is_abstract)
        
        # Handle literals if they exist
        if hasattr(info, 'literals'):
            for lit in info.literals:
                # Handle enum literals
                pass
        
        self.writer.end_packaged_element()

    def visit_datatype(self, info: UmlElement):
        name = info.name
        xmi = info.xmi
        is_abstract = bool(info.clang.is_abstract)
        
        # Use UML model for element type
        uml_model = DEFAULT_MODEL.uml
        self.writer.start_packaged_element(xmi, uml_model.datatype_type, name, is_abstract=is_abstract)
        if info.underlying:
            tref = self.name_to_xmi.get(info.underlying)
            if tref:
                self.writer.write_generalization(stable_id(xmi + ":gen"), tref)
        self.writer.end_packaged_element()

# -------------------- XMI Generator (Refactored) --------------------
class XmiGenerator:
    """Generates XMI files from UML model data."""
    
    def __init__(self, model: UmlModel):
        self.model = model
        self.created = model.elements
        self.name_to_xmi = model.name_to_xmi
        
        # Build namespace tree for real elements only
        self.namespace_tree = self._build_namespace_tree(self.created)
        
        # Collect all referenced type names
        self.all_referenced_type_names = self._collect_referenced_types()
        
        # Create stub elements for referenced but undefined types
        self._create_stub_elements()
        
        # Update namespace tree with stubs
        self.namespace_tree = self._build_namespace_tree(self.created)

    def _build_namespace_tree(self, elements: Dict[str, UmlElement]) -> Dict[str, Any]:
        """Build namespace hierarchy tree from elements."""
        tree = {}
        
        for q_name, info in elements.items():
            if '::' not in q_name:
                # Root level element
                tree[q_name] = info
            else:
                # Namespaced element
                parts = q_name.split('::')
                current = tree
                
                # Navigate/create namespace path
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {'__namespace__': True, '__children__': {}}
                    elif not isinstance(current[part], dict) or '__namespace__' not in current[part]:
                        # If this node is not a namespace (e.g., it's a UmlElement), 
                        # we need to convert it to a namespace
                        existing_element = current[part]
                        current[part] = {'__namespace__': True, '__children__': {}}
                        # Move the existing element to a child with a default name
                        current[part]['__children__']['__root__'] = existing_element
                    current = current[part]['__children__']
                
                # Add the actual element
                current[parts[-1]] = info
        
        return tree

    def _collect_referenced_types(self) -> set:
        """Collect all type names referenced in the model."""
        all_referenced_type_names = set()
        
        for name, info in self.created.items():
            # Collect from members
            for m in info.members:
                if m.type_repr:
                    all_referenced_type_names.add(m.type_repr)
            
            # Collect from operations
            if hasattr(info, 'operations'):
                for op in info.operations:
                    if op.get("return"):
                        all_referenced_type_names.add(op["return"])
                    for p in op.get("params", []):
                        if p.get("type"):
                            all_referenced_type_names.add(p["type"])
            
            # Collect from templates
            if hasattr(info, 'templates'):
                for t in info.templates:
                    all_referenced_type_names.add(t)
            
            # Collect from associations
            for assoc in self.model.associations:
                if assoc.name:
                    all_referenced_type_names.add(assoc.name)
        
        return all_referenced_type_names

    def _create_stub_elements(self):
        """Create stub elements for referenced but undefined types."""
        for type_name in self.all_referenced_type_names:
            if type_name not in self.created and type_name not in self.name_to_xmi:
                # Create stub element
                stub_id = stable_id(f"stub:{type_name}")
                self.name_to_xmi[type_name] = stub_id
                
                # Create stub UmlElement
                stub_element = UmlElement(
                    xmi=stub_id,
                    name=type_name,
                    kind=ElementKind.DATATYPE,
                    members=[],
                    clang=ClangMetadata(),
                    used_types=set(),
                    underlying=None
                )
                
                self.created[type_name] = stub_element

    def _write_package_contents(self, visitor: UmlXmiWritingVisitor, tree: Dict[str, Any], parent_name: str = ""):
        """Recursively write package contents."""
        for name, item in tree.items():
            if isinstance(item, dict) and item.get('__namespace__'):
                # This is a namespace
                package_name = f"{parent_name}::{name}" if parent_name else name
                package_id = stable_id(f"package:{package_name}")
                
                # Start package using the visitor's writer
                visitor.writer.start_package(package_id, name)
                
                # Write namespace contents
                self._write_package_contents(visitor, item['__children__'], package_name)
                
                # End package using the visitor's writer
                visitor.writer.end_package()
            else:
                # This is an actual element
                if hasattr(item, 'kind'):
                    # Use visitor pattern to handle different element types
                    if item.kind == ElementKind.CLASS:
                        visitor.visit_class(item)
                    elif item.kind == ElementKind.ENUM:
                        visitor.visit_enum(item)
                    elif item.kind == ElementKind.DATATYPE:
                        visitor.visit_datatype(item)
                    else:
                        # Default to class for unknown types
                        visitor.visit_class(item)

    def write(self, out_path: str, project_name: str):
        """Write the complete XMI file."""
        from Model import DEFAULT_MODEL
        
        # Separate real elements from stubs
        real_elements = {k: v for k, v in self.created.items() if v.kind != ElementKind.DATATYPE}
        stub_elements = {k: v for k, v in self.created.items() if v.kind == ElementKind.DATATYPE}

        # Step 3: Build namespace tree for real elements only
        namespace_tree = self._build_namespace_tree(real_elements)

        # Step 4: Write the document
        with etree.xmlfile(out_path, encoding="utf-8") as xf:
            writer = XmiWriter(xf, xml_model=DEFAULT_MODEL.xml)
            writer.start_doc(project_name, model_id="model_1")
            
            visitor = UmlXmiWritingVisitor(writer, self.name_to_xmi)
            
            # Write packaged elements
            self._write_package_contents(visitor, namespace_tree)
            
            # Write all stubs at the root level
            for q_name, stub_info in stub_elements.items():
                # Pass the original qualified name to the visitor
                stub_info.name = q_name
                visitor.visit_datatype(stub_info)
            
            # Associations, Dependencies, and Generalizations are written at the root level
            for assoc in self.model.associations:
                writer.write_association(assoc, uml_model=DEFAULT_MODEL.uml)

            for owner_q_name, typ in self.model.dependencies:
                client_info = self.created.get(owner_q_name)
                if not client_info:
                    continue
                client_id = client_info.xmi
                supplier_id = self.name_to_xmi.get(typ)
                
                if client_id and supplier_id:
                    dep_id = stable_id(f"dep:{owner_q_name}:{typ}")
                    
                    # Use model for dependency attributes
                    uml_model = DEFAULT_MODEL.uml
                    xml_model = DEFAULT_MODEL.xml
                    
                    attribs = {
                        xml_model.xmi_type: "uml:Dependency", 
                        xml_model.xmi_id: dep_id,
                        "name": f"dep_{xml_text(owner_q_name)}_to_{xml_text(typ)}",
                        "client": client_id, 
                        "supplier": supplier_id
                    }
                    dep_el = etree.Element("packagedElement", attrib=attribs, nsmap=xml_model.uml_nsmap)
                    xf.write(dep_el)

            for child_id, parent_id in getattr(self.model, "generalizations", []) or []:
                writer.write_generalization(stable_id(child_id + ":gen"), parent_id)

            writer.end_doc()
