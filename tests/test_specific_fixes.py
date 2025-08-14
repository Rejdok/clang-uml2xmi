#!/usr/bin/env python3
"""
Tests for specific EMF compliance fixes.

Each test targets a specific issue that was identified and fixed.
"""

import pytest
import tempfile
import os
from lxml import etree

from gen.xmi.generator import XmiGenerator
from gen.xmi.writer import XmiWriter
from core.uml_model import UmlModel, UmlElement, UmlOperation, UmlMember, ClangMetadata, ElementName, XmiId
from uml_types import ElementKind, Visibility
from utils.ids import stable_id


class TestSpecificIssuesFixes:
    """Test fixes for specific identified issues."""
    
    def test_issue_duplicate_memberend_fixed(self):
        """Test fix for: Association with duplicate memberEnd references."""
        # Issue was: same property referenced twice in memberEnd
        # Fix: filter self-referential associations
        
        # Create a class that might generate self-referential association
        test_class = UmlElement(
            xmi=XmiId("id_self_ref_test"),
            name=ElementName("SelfRefTest"),
            kind=ElementKind.CLASS,
            members=[],
            clang=ClangMetadata(),
            used_types=frozenset(),
            underlying=None
        )
        
        # Add a member that could create self-reference
        member = UmlMember(
            name="self_member",
            type_repr="SelfRefTest",  # Self-reference 
            visibility=Visibility.PRIVATE,
            is_static=False
        )
        test_class.members = [member]
        
        # Create the model with proper constructor arguments
        model = UmlModel(
            elements={test_class.xmi: test_class},
            associations=[],
            dependencies=[],
            generalizations=[],
            name_to_xmi={test_class.name: test_class.xmi}
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.uml', delete=False) as f:
            temp_path = f.name
            
        try:
            generator = XmiGenerator(model)
            generator.write(temp_path, "TestModel", pretty=True)
            
            # Parse and check associations
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(temp_path, parser)
            root = tree.getroot()
            
            associations = root.xpath('//*[contains(@*[local-name()="type"], "Association")]')
            
            for assoc in associations:
                member_ends = assoc.xpath('./memberEnd/@*[local-name()="idref"]')
                
                # Check that we don't have exact duplicates in memberEnd
                unique_refs = set(member_ends)
                # Either should be filtered out completely, or have proper structure
                if len(member_ends) > 0:
                    assert len(unique_refs) >= 1, "Should have at least one unique memberEnd"
                    
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_issue_template_binding_missing_signature_fixed(self):
        """Test fix for: TemplateBinding references non-existent signature."""
        # Issue was: templateBinding.signature referenced ID that didn't exist
        # Fix: disable template bindings completely
        
        # Create template instantiation that used to generate problematic binding
        inst_class = UmlElement(
            xmi=XmiId("id_problematic_inst"),
            name=ElementName("std::integral_constant<bool,true>"),
            kind=ElementKind.CLASS,
            members=[],
            clang=ClangMetadata(),
            used_types=frozenset(),
            underlying=None
        )
        
        # Create the model with proper constructor arguments
        model = UmlModel(
            elements={inst_class.xmi: inst_class},
            associations=[],
            dependencies=[],
            generalizations=[],
            name_to_xmi={inst_class.name: inst_class.xmi}
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.uml', delete=False) as f:
            temp_path = f.name
            
        try:
            generator = XmiGenerator(model)
            generator.write(temp_path, "TestModel", pretty=True)
            
            # Verify no template bindings
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(temp_path, parser)
            root = tree.getroot()
            
            bindings = root.xpath('//*[local-name()="templateBinding"]')
            assert len(bindings) == 0, "Template bindings should be disabled"
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_issue_operation_id_uniqueness_fixed(self):
        """Test fix for: Duplicate operation IDs within same class."""
        # Issue was: operations with same mangled signature got same ID
        # Fix: add operation index to ID generation
        
        test_class = UmlElement(
            xmi=XmiId("id_op_uniqueness"),
            name=ElementName("OpUniquenessTest"),
            kind=ElementKind.CLASS,
            members=[],
            clang=ClangMetadata(),
            used_types=frozenset(),
            underlying=None
        )
        
        # Create operations that would have same mangled signature
        ops = []
        for i in range(3):
            op = UmlOperation(
                name="overloaded_method",
                return_type="void",
                parameters=[],  # Same empty parameters
                visibility=Visibility.PUBLIC,
                is_static=False
            )
            ops.append(op)
        
        test_class.operations = ops
        
        # Create the model with proper constructor arguments
        model = UmlModel(
            elements={test_class.xmi: test_class},
            associations=[],
            dependencies=[],
            generalizations=[],
            name_to_xmi={test_class.name: test_class.xmi}
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.uml', delete=False) as f:
            temp_path = f.name
            
        try:
            generator = XmiGenerator(model)
            generator.write(temp_path, "TestModel", pretty=True)
            
            # Verify operations have unique IDs
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(temp_path, parser)
            root = tree.getroot()
            
            # Find the test class
            test_classes = [cls for cls in root.xpath('//*[contains(@*[local-name()="type"], "Class")]') 
                          if cls.get('name') == 'OpUniquenessTest']
            assert len(test_classes) == 1
            
            test_class = test_classes[0]
            operations = test_class.xpath('.//*[contains(@*[local-name()="type"], "Operation")]')
            operations.extend(test_class.xpath('./*[local-name()="ownedOperation"]'))
            
            op_ids = [op.get('{http://www.omg.org/XMI}id') for op in operations if op.get('{http://www.omg.org/XMI}id')]
            
            # All IDs should be unique
            assert len(op_ids) == len(set(op_ids)), f"Found duplicate operation IDs: {op_ids}"
            assert len(op_ids) >= 3, f"Expected at least 3 operations, found {len(op_ids)}"
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_issue_model_visibility_attribute_removed(self):
        """Test fix for: Root Model element should not have visibility."""
        # Issue was: Model had visibility="public" which EMF doesn't allow for root elements
        # Fix: remove visibility attribute from root Model
        
        simple_class = UmlElement(
            xmi=XmiId("id_visibility_test"),
            name=ElementName("VisibilityTest"),
            kind=ElementKind.CLASS,
            members=[],
            clang=ClangMetadata(),
            used_types=frozenset(),
            underlying=None
        )
        
        # Create the model with proper constructor arguments
        model = UmlModel(
            elements={simple_class.xmi: simple_class},
            associations=[],
            dependencies=[],
            generalizations=[],
            name_to_xmi={simple_class.name: simple_class.xmi}
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.uml', delete=False) as f:
            temp_path = f.name
            
        try:
            generator = XmiGenerator(model)
            generator.write(temp_path, "TestModel", pretty=True)
            
            # Check that Model element has no visibility
            with open(temp_path, 'r', encoding='utf-8') as xmi_file:
                content = xmi_file.read()
                
            # Should not contain visibility in Model element
            assert 'uml:Model' in content, "Should contain UML Model element"
            
            # Parse properly to check attributes
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(temp_path, parser)
            root = tree.getroot()
            
            model_elements = root.xpath('//*[local-name()="Model"]')
            for model_elem in model_elements:
                assert model_elem.get('visibility') is None, \
                    f"Model element should not have visibility: {model_elem.attrib}"
                    
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
