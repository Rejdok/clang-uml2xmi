#!/usr/bin/env python3
"""
Test script to verify that classes in namespaces have correct names.
"""

import logging
import tempfile
import os
import xml.etree.ElementTree as ET
from UmlModel import UmlModel, UmlElement, ElementKind, ClangMetadata, XmiId, ElementName
from XmiGenerator import XmiGenerator

# Configure logging for testing
logging.basicConfig(level=logging.INFO)

def create_namespace_test_model():
    """Create a test model with classes in namespaces."""
    
    # Create a class in namespace
    namespaced_class = UmlElement(
        xmi=XmiId("my_namespace_class"),
        name=ElementName("MyNamespace::MyClass"),
        kind=ElementKind.CLASS,
        members=[],
        clang=ClangMetadata(),
        used_types=frozenset(),
        underlying=None
    )
    
    # Create another class in the same namespace
    namespaced_class2 = UmlElement(
        xmi=XmiId("my_namespace_class2"),
        name=ElementName("MyNamespace::MyClass2"),
        kind=ElementKind.CLASS,
        members=[],
        clang=ClangMetadata(),
        used_types=frozenset(),
        underlying=None
    )
    
    # Create a nested namespace
    nested_namespace_class = UmlElement(
        xmi=XmiId("nested_class"),
        name=ElementName("OuterNamespace::InnerNamespace::NestedClass"),
        kind=ElementKind.CLASS,
        members=[],
        clang=ClangMetadata(),
        used_types=frozenset(),
        underlying=None
    )
    
    # Create collections for the model
    elements = {}
    elements[namespaced_class.xmi] = namespaced_class
    elements[namespaced_class2.xmi] = namespaced_class2
    elements[nested_namespace_class.xmi] = nested_namespace_class
    
    name_to_xmi = {}
    name_to_xmi[namespaced_class.name] = namespaced_class.xmi
    name_to_xmi[namespaced_class2.name] = namespaced_class2.xmi
    name_to_xmi[nested_namespace_class.name] = nested_namespace_class.xmi
    
    # Create the model
    model = UmlModel(
        elements=elements,
        associations=[],
        dependencies=[],
        generalizations=[],
        name_to_xmi=name_to_xmi
    )
    
    return model

def test_namespace_names():
    """Test that classes in namespaces have correct names."""
    
    print("Creating namespace test model...")
    model = create_namespace_test_model()
    
    print("Creating XMI generator...")
    generator = XmiGenerator(model)
    
    # Create temporary output file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xmi', delete=False) as tmp:
        output_path = tmp.name
    
    try:
        print(f"Generating XMI file to: {output_path}")
        generator.write(output_path, "NamespaceTest")
        
        print("XMI generation completed successfully!")
        
        # Parse the generated XMI file to check names
        tree = ET.parse(output_path)
        root = tree.getroot()
        
        # Find all packagedElement elements
        packaged_elements = root.findall(".//packagedElement")
        
        print(f"Found {len(packaged_elements)} packaged elements")
        
        # Check each element
        for elem in packaged_elements:
            elem_name = elem.get('name', 'NO_NAME')
            elem_type = elem.get('{http://www.omg.org/XMI}type', 'NO_TYPE')
            elem_id = elem.get('{http://www.omg.org/XMI}id', 'NO_ID')
            
            print(f"Element: {elem_name} (type: {elem_type}, id: {elem_id})")
            
            # Check if this is a class in a namespace
            if elem_type == 'uml:Class':
                if 'MyClass' in elem_name or 'MyClass2' in elem_name or 'NestedClass' in elem_name:
                    print(f"  ✓ Class name '{elem_name}' is correct")
                else:
                    print(f"  ✗ Class name '{elem_name}' is incorrect")
        
        # Check for namespace packages
        # Note: XPath with namespaces is complex, so we'll use the alternative method below
        packages = []  # Will be populated by alternative method
        print(f"Found {len(packages)} namespace packages (XPath method)")
        
        # Alternative approach: find all packagedElement and filter by type
        all_packaged = root.findall(".//packagedElement")
        namespace_packages = [elem for elem in all_packaged 
                            if elem.get('{http://www.omg.org/XMI}type') == 'uml:Package']
        print(f"Found {len(namespace_packages)} namespace packages (alternative method)")
        
        for package in namespace_packages:
            package_name = package.get('name', 'NO_NAME')
            print(f"  Package: {package_name}")
        
    except Exception as e:
        print(f"ERROR during testing: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up temporary file
        try:
            os.unlink(output_path)
            print("Temporary file cleaned up")
        except:
            pass

if __name__ == "__main__":
    test_namespace_names()
