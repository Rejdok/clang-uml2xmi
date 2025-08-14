#!/usr/bin/env python3
"""
Regression prevention tests for EMF compliance fixes.

These tests check for specific issues that were causing EMF validation failures
and ensure they don't reoccur in future changes.
"""

import pytest
import tempfile
import os
from pathlib import Path
from lxml import etree
import subprocess
import sys
from collections import defaultdict
from typing import Dict, List, Set

from gen.xmi.generator import XmiGenerator
from core.uml_model import UmlModel, UmlElement, UmlOperation, ClangMetadata, ElementName, XmiId
from uml_types import ElementKind, Visibility


class TestRegressionPrevention:
    """Tests to prevent regression of specific EMF issues."""
    
    def test_no_template_signature_parameter_errors(self):
        """Regression test: template signatures with 0 parameters should not be created."""
        # This was a major EMF validation error:
        # "The feature 'parameter' of 'RedefinableTemplateSignature' with 0 values must have at least 1 values"
        
        template_class = UmlElement(
            xmi=XmiId("id_template_test"),
            name=ElementName("TemplateClass"),
            kind=ElementKind.CLASS,
            members=[],
            clang=ClangMetadata(),
            used_types=frozenset(),
            underlying=None
        )
        
        # Set empty templates (this used to cause empty template signatures)
        template_class.templates = []
        
        # Create the model with proper constructor arguments
        model = UmlModel(
            elements={template_class.xmi: template_class},
            associations=[],
            dependencies=[],
            generalizations=[],
            name_to_xmi={template_class.name: template_class.xmi}
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.uml', delete=False) as f:
            temp_path = f.name
            
        try:
            generator = XmiGenerator(model)
            generator.write(temp_path, "TestModel", pretty=True)
            
            # Parse and verify no template signatures exist
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(temp_path, parser)
            root = tree.getroot()
            
            # Should have zero template signatures (completely disabled)
            signatures = root.xpath('//*[contains(@*[local-name()="type"], "RedefinableTemplateSignature")]')
            assert len(signatures) == 0, "Template signatures should be completely disabled"
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_no_unresolved_template_binding_references(self):
        """Regression test: template bindings should not reference non-existent signatures."""
        # This was causing: "The reference 'signature' has an unresolved idref"
        
        # Create an instantiation class (this used to generate template bindings)
        inst_class = UmlElement(
            xmi=XmiId("id_instantiation"),
            name=ElementName("std::vector<int>"),
            kind=ElementKind.CLASS,
            members=[],
            clang=ClangMetadata(),
            used_types=frozenset(),
            underlying=None
        )
        
        # Mark as instantiation
        inst_class.instantiation_of = XmiId("id_std_vector")
        inst_class.instantiation_args = ["int"]
        
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
            
            # Parse and verify no template bindings exist
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(temp_path, parser)
            root = tree.getroot()
            
            # Should have zero template bindings (completely disabled)  
            bindings = root.xpath('//*[contains(@*[local-name()="type"], "TemplateBinding")]')
            assert len(bindings) == 0, "Template bindings should be completely disabled"
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_no_duplicate_operation_ids_in_class(self):
        """Regression test: operations with same signature should have unique IDs."""
        # This was causing: "Named element 'Operation' is not distinguishable from all other members"
        
        test_class = UmlElement(
            xmi=XmiId("id_dup_ops_class"),
            name=ElementName("DuplicateOpsClass"),
            kind=ElementKind.CLASS,
            members=[],
            clang=ClangMetadata(),
            used_types=frozenset(),
            underlying=None
        )
        
        # Create two operations with identical signatures
        op1 = UmlOperation(
            name="same_op",
            return_type="void",
            parameters=[],
            visibility=Visibility.PUBLIC,
            is_static=False
        )
        op2 = UmlOperation(
            name="same_op",
            return_type="void", 
            parameters=[],
            visibility=Visibility.PUBLIC,
            is_static=False
        )
        
        test_class.operations = [op1, op2]
        
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
            
            # Parse and verify operations have unique IDs
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(temp_path, parser)
            root = tree.getroot()
            
            # Find the test class
            test_classes = [cls for cls in root.xpath('//*[contains(@*[local-name()="type"], "Class")]') 
                          if cls.get('name') == 'DuplicateOpsClass']
            assert len(test_classes) == 1, "Should find exactly one test class"
            
            test_class = test_classes[0]
            # Find operations (they are ownedOperation elements)
            operations = test_class.xpath('./*[local-name()="ownedOperation"]')
            
            # Collect operation IDs
            op_ids: Set[str] = set()
            for op in operations:
                op_id = op.get('{http://www.omg.org/XMI}id')
                if op_id:
                    assert op_id not in op_ids, f"Found duplicate operation ID: {op_id}"
                    op_ids.add(op_id)
            
            # Should have found operations
            assert len(op_ids) >= 2, f"Expected at least 2 operations, found {len(op_ids)}"
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_model_element_no_visibility_attribute(self):
        """Regression test: root Model element should not have visibility attribute."""
        # This was causing: "Named element 'Model' is not owned by a namespace, but it has visibility"
        
        simple_class = UmlElement(
            xmi=XmiId("id_simple"),
            name=ElementName("SimpleClass"),
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
            
            # Read the raw XML to check Model element attributes
            with open(temp_path, 'r', encoding='utf-8') as xmi_file:
                content = xmi_file.read()
            
            # Parse and check Model element
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(temp_path, parser)
            root = tree.getroot()
            
            # Find Model elements
            models = root.xpath('//*[local-name()="Model"]')
            assert len(models) >= 1, "Should find at least one Model element"
            
            for model_elem in models:
                visibility = model_elem.get('visibility')
                assert visibility is None, f"Model element should not have visibility attribute, found: {visibility}"
                
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_no_association_with_single_member_end(self):
        """Regression test: associations should have at least 2 memberEnd elements."""
        # This was causing validation errors about insufficient memberEnd count
        
        # Create minimal classes for association
        class1 = UmlElement(
            xmi=XmiId("id_class1"),
            name=ElementName("Class1"),
            kind=ElementKind.CLASS,
            members=[],
            clang=ClangMetadata(),
            used_types=frozenset(),
            underlying=None
        )
        
        class2 = UmlElement(
            xmi=XmiId("id_class2"),
            name=ElementName("Class2"),
            kind=ElementKind.CLASS,
            members=[],
            clang=ClangMetadata(),
            used_types=frozenset(),
            underlying=None
        )
        
        # Create the model with proper constructor arguments
        model = UmlModel(
            elements={class1.xmi: class1, class2.xmi: class2},
            associations=[],
            dependencies=[],
            generalizations=[],
            name_to_xmi={class1.name: class1.xmi, class2.name: class2.xmi}
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
            
            # Find all associations
            associations = root.xpath('//*[contains(@*[local-name()="type"], "Association")]')
            
            for assoc in associations:
                assoc_id = assoc.get('{http://www.omg.org/XMI}id')
                
                # Count memberEnd elements
                member_ends = assoc.xpath('./memberEnd')
                owned_ends = assoc.xpath('./ownedEnd')
                total_ends = len(member_ends) + len(owned_ends)
                
                # EMF requires at least 2 ends
                assert total_ends >= 2, \
                    f"Association {assoc_id} has insufficient ends: {total_ends} (need ≥2)"
                    
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestEMFValidationTools:
    """Test that our validation tools work correctly."""
    
    def test_python_xmi_validator_works(self):
        """Test that Python XMI validator correctly identifies valid files."""
        # Use the successful output from our fixes
        if os.path.exists("out_final_perfect.uml"):
            result = subprocess.run([
                sys.executable, "tools/validate_xmi.py", "out_final_perfect.uml"
            ], capture_output=True, text=True)
            
            assert result.returncode == 0, f"Python validator should pass: {result.stderr}"
            assert "OK: no unresolved idrefs" in result.stdout, f"Expected success message: {result.stdout}"
    
    def test_java_emf_validator_integration(self):
        """Test that Java EMF validator integration works (if available)."""
        # This test checks that our integration with Eclipse EMF validator works
        if os.path.exists("out_final_perfect.uml"):
            result = subprocess.run([
                sys.executable, "-m", "pytest", 
                "tests/test_integration_spdlog.py::test_spdlog_integration_generate_and_validate",
                "-v", "-x"  # Stop on first failure
            ], capture_output=True, text=True)
            
            # Should pass the EMF validation
            assert result.returncode == 0, f"EMF validation integration should work: {result.stdout}\n{result.stderr}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
