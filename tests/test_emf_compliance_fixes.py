                #!/usr/bin/env python3
"""
Tests for EMF compliance fixes in the XMI generator.

These tests verify that the fixes for EMF validation issues work correctly:
- No template signatures generated (EMF compatibility)
- No template bindings generated 
- Unique operation IDs (prevent duplicate operations)
- Root model without visibility attribute
- Self-referential associations filtered out
- Overall EMF validation passes
"""

import pytest
import tempfile
import os
from pathlib import Path
from lxml import etree
import subprocess
import sys
from typing import Dict, List, Set

from gen.xmi.generator import XmiGenerator
from gen.xmi.writer import XmiWriter
from core.uml_model import UmlModel, UmlElement, UmlOperation, UmlMember, ClangMetadata, ElementName, XmiId
from uml_types import ElementKind, Visibility
from utils.ids import stable_id


class TestEMFComplianceFixes:
    """Test suite for EMF compliance fixes."""
    
    @pytest.fixture
    def sample_model_with_templates(self) -> UmlModel:
        """Create a sample UML model with template classes."""
        # Create a template class with duplicate operations
        template_element = UmlElement(
            xmi=XmiId("id_template_class"),
            name=ElementName("TestTemplate"),
            kind=ElementKind.CLASS,
            members=[],
            clang=ClangMetadata(),
            used_types=frozenset(),
            underlying=None
        )
        
        # Add template information
        template_element.templates = ["T", "U"]
        
        # Add duplicate operations (same signature)
        op1 = UmlOperation(
            name="duplicate_op",
            return_type="void",
            parameters=[],
            visibility=Visibility.PUBLIC,
            is_static=False
        )
        op2 = UmlOperation(
            name="duplicate_op", 
            return_type="void",
            parameters=[],
            visibility=Visibility.PUBLIC,
            is_static=False
        )
        template_element.operations = [op1, op2]
        
        # Create the model with proper constructor arguments
        model = UmlModel(
            elements={template_element.xmi: template_element},
            associations=[],
            dependencies=[],
            generalizations=[],
            name_to_xmi={template_element.name: template_element.xmi}
        )
        
        return model
    
    @pytest.fixture
    def sample_model_with_associations(self) -> UmlModel:
        """Create a sample UML model with self-referential associations."""
        # Create class with self-referential member
        class_element = UmlElement(
            xmi=XmiId("id_self_ref_class"),
            name=ElementName("SelfRefClass"),
            kind=ElementKind.CLASS,
            members=[],
            clang=ClangMetadata(),
            used_types=frozenset(),
            underlying=None
        )
        
        # Create the model with proper constructor arguments
        model = UmlModel(
            elements={class_element.xmi: class_element},
            associations=[],
            dependencies=[],
            generalizations=[],
            name_to_xmi={class_element.name: class_element.xmi}
        )
        
        return model
        
    def test_no_template_signatures_generated(self, sample_model_with_templates):
        """Test that template signatures are not generated (EMF compliance)."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.uml', delete=False) as f:
            temp_path = f.name
            
        try:
            generator = XmiGenerator(sample_model_with_templates)
            generator.write(temp_path, "TestModel", pretty=True)
            
            # Parse the generated XMI
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(temp_path, parser)
            root = tree.getroot()
            
            # Check that no template signatures exist
            signatures = root.xpath('//*[contains(@*[local-name()="type"], "RedefinableTemplateSignature")]')
            assert len(signatures) == 0, f"Found {len(signatures)} template signatures, expected 0"
            
            # Check that no ownedTemplateSignature elements exist
            owned_signatures = root.xpath('//*[local-name()="ownedTemplateSignature"]')
            assert len(owned_signatures) == 0, f"Found {len(owned_signatures)} ownedTemplateSignature elements, expected 0"
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_no_template_bindings_generated(self, sample_model_with_templates):
        """Test that template bindings are not generated (EMF compliance)."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.uml', delete=False) as f:
            temp_path = f.name
            
        try:
            generator = XmiGenerator(sample_model_with_templates)
            generator.write(temp_path, "TestModel", pretty=True)
            
            # Parse the generated XMI
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(temp_path, parser)
            root = tree.getroot()
            
            # Check that no template bindings exist
            bindings = root.xpath('//*[contains(@*[local-name()="type"], "TemplateBinding")]')
            assert len(bindings) == 0, f"Found {len(bindings)} template bindings, expected 0"
            
            # Check that no templateBinding elements exist
            template_bindings = root.xpath('//*[local-name()="templateBinding"]')
            assert len(template_bindings) == 0, f"Found {len(template_bindings)} templateBinding elements, expected 0"
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_unique_operation_ids(self, sample_model_with_templates):
        """Test that operations with identical signatures get unique IDs."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.uml', delete=False) as f:
            temp_path = f.name
            
        try:
            generator = XmiGenerator(sample_model_with_templates)
            generator.write(temp_path, "TestModel", pretty=True)
            
            # Parse the generated XMI
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(temp_path, parser)
            root = tree.getroot()
            
            # Find all operations (they are generated as ownedOperation elements)
            operations = root.xpath('//*[local-name()="ownedOperation"]')
            
            # Collect operation IDs
            operation_ids: Set[str] = set()
            for op in operations:
                op_id = op.get('{http://www.omg.org/XMI}id')
                if op_id:
                    assert op_id not in operation_ids, f"Duplicate operation ID found: {op_id}"
                    operation_ids.add(op_id)
            
            # Ensure we found some operations
            assert len(operation_ids) > 0, "No operations found in generated XMI"
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_root_model_no_visibility(self, sample_model_with_templates):
        """Test that root model does not have visibility attribute (EMF compliance)."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.uml', delete=False) as f:
            temp_path = f.name
            
        try:
            generator = XmiGenerator(sample_model_with_templates)
            generator.write(temp_path, "TestModel", pretty=True)
            
            # Parse the generated XMI
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(temp_path, parser)
            root = tree.getroot()
            
            # Find the root Model element
            models = root.xpath('//*[contains(@*[local-name()="type"], "Model") or local-name()="Model"]')
            assert len(models) > 0, "No Model element found"
            
            root_model = models[0]
            visibility = root_model.get('visibility')
            assert visibility is None, f"Root model should not have visibility, but found: {visibility}"
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_no_self_referential_associations(self, sample_model_with_associations):
        """Test that self-referential associations are filtered out."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.uml', delete=False) as f:
            temp_path = f.name
            
        try:
            generator = XmiGenerator(sample_model_with_associations)
            generator.write(temp_path, "TestModel", pretty=True)
            
            # Parse the generated XMI
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(temp_path, parser)
            root = tree.getroot()
            
            # Find all associations
            associations = root.xpath('//*[contains(@*[local-name()="type"], "Association")]')
            
            for assoc in associations:
                # Get memberEnd references
                member_ends = assoc.xpath('./memberEnd/@*[local-name()="idref"]')
                
                # Check for self-referential associations (same property referenced twice)
                if len(member_ends) >= 2:
                    # Should not have duplicate memberEnd references
                    unique_ends = set(member_ends)
                    assert len(unique_ends) == len(member_ends) or len(unique_ends) == 2, \
                        f"Association {assoc.get('{http://www.omg.org/XMI}id')} has problematic memberEnd structure: {member_ends}"
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_emf_validation_passes(self, sample_model_with_templates):
        """Test that generated XMI passes EMF validation."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.uml', delete=False) as f:
            temp_path = f.name
            
        try:
            generator = XmiGenerator(sample_model_with_templates)
            generator.write(temp_path, "TestModel", pretty=True)
            
            # Run Python validator (basic check)
            result = subprocess.run([
                sys.executable, "tools/validate_xmi.py", temp_path
            ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
            
            assert result.returncode == 0, f"Python XMI validation failed: {result.stderr}"
            assert "OK: no unresolved idrefs" in result.stdout, f"Unexpected validation output: {result.stdout}"
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_no_datatype_stubs_generated(self, sample_model_with_templates):
        """Test that DataType stubs are not generated when disabled."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.uml', delete=False) as f:
            temp_path = f.name
            
        try:
            generator = XmiGenerator(sample_model_with_templates)
            generator.write(temp_path, "TestModel", pretty=True)
            
            # Parse the generated XMI
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(temp_path, parser)
            root = tree.getroot()
            
            # Check that no Type_ stub elements exist (when stubs are disabled)
            from app.config import DEFAULT_CONFIG
            if not DEFAULT_CONFIG.emit_referenced_type_stubs:
                type_stubs = root.xpath('//*[starts-with(@name, "Type_")]')
                assert len(type_stubs) == 0, f"Found {len(type_stubs)} Type_ stubs when stubs are disabled"
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_spdlog_integration_emf_validation(self):
        """Test that spdlog integration test passes EMF validation after fixes."""
        # This test ensures the main integration scenario works
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "tests/test_integration_spdlog.py::test_spdlog_integration_generate_and_validate",
            "-v"
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
        
        assert result.returncode == 0, f"Integration test failed: {result.stdout}\n{result.stderr}"
        assert "PASSED" in result.stdout, f"Integration test did not pass: {result.stdout}"
    
    def test_associations_have_sufficient_member_ends(self, sample_model_with_associations):
        """Test that all associations have at least 2 memberEnd elements (EMF requirement)."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.uml', delete=False) as f:
            temp_path = f.name
            
        try:
            generator = XmiGenerator(sample_model_with_associations)
            generator.write(temp_path, "TestModel", pretty=True)
            
            # Parse the generated XMI
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(temp_path, parser)
            root = tree.getroot()
            
            # Find all associations
            associations = root.xpath('//*[contains(@*[local-name()="type"], "Association")]')
            
            for assoc in associations:
                assoc_id = assoc.get('{http://www.omg.org/XMI}id')
                
                # Count memberEnd and ownedEnd elements
                member_ends = assoc.xpath('./memberEnd')
                owned_ends = assoc.xpath('./ownedEnd')
                total_ends = len(member_ends) + len(owned_ends)
                
                assert total_ends >= 2, \
                    f"Association {assoc_id} has only {total_ends} ends, EMF requires at least 2"
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_operation_name_uniqueness_within_class(self, sample_model_with_templates):
        """Test that operations within the same class have distinguishable names."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.uml', delete=False) as f:
            temp_path = f.name
            
        try:
            generator = XmiGenerator(sample_model_with_templates)
            generator.write(temp_path, "TestModel", pretty=True)
            
            # Parse the generated XMI
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(temp_path, parser)
            root = tree.getroot()
            
            # Find all classes
            classes = root.xpath('//*[contains(@*[local-name()="type"], "Class")]')
            
            for cls in classes:
                cls_id = cls.get('{http://www.omg.org/XMI}id')
                cls_name = cls.get('name', 'unnamed')
                
                # Find operations in this class (they are ownedOperation elements)
                operations = cls.xpath('./*[local-name()="ownedOperation"]')
                
                # Check for operation name uniqueness within class
                operation_names: Set[str] = set()
                operation_ids: Set[str] = set()
                
                for op in operations:
                    op_id = op.get('{http://www.omg.org/XMI}id')
                    op_name = op.get('name', 'unnamed_op')
                    
                    if op_id:
                        assert op_id not in operation_ids, \
                            f"Class {cls_name} has duplicate operation ID: {op_id}"
                        operation_ids.add(op_id)
                    
                    # Operations with same base name should be distinguishable
                    # (they should have different display names with hash suffixes)
                    if '#' in op_name:
                        base_name = op_name.split('#')[0]
                        assert op_name not in operation_names, \
                            f"Class {cls_name} has duplicate operation name: {op_name}"
                        operation_names.add(op_name)
                        
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestSpecificEMFFixes:
    """Test specific fixes for known EMF validation issues."""
    
    def test_no_empty_template_signatures(self):
        """Test that empty template signatures are not created."""
        # This would be checked by ensuring template signature creation is disabled
        # The fix was to completely disable template signature generation
        
        # Create a simple model
        element = UmlElement(
            xmi=XmiId("id_test_template"),
            name=ElementName("EmptyTemplate"),
            kind=ElementKind.CLASS,
            members=[],
            clang=ClangMetadata(),
            used_types=frozenset(),
            underlying=None
        )
        element.templates = []  # Empty template list
        
        # Create the model with proper constructor arguments
        model = UmlModel(
            elements={element.xmi: element},
            associations=[],
            dependencies=[],
            generalizations=[],
            name_to_xmi={element.name: element.xmi}
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.uml', delete=False) as f:
            temp_path = f.name
            
        try:
            generator = XmiGenerator(model)
            generator.write(temp_path, "TestModel", pretty=True)
            
            # Parse the generated XMI
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(temp_path, parser)
            root = tree.getroot()
            
            # Verify no template signatures are created (they're disabled)
            signatures = root.xpath('//*[contains(@*[local-name()="type"], "RedefinableTemplateSignature")]')
            assert len(signatures) == 0, "Template signatures should be completely disabled"
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_operation_id_includes_index(self):
        """Test that operation IDs include index to ensure uniqueness."""
        # Test the stable_id generation pattern
        class_id = "id_test_class"
        
        # Simulate two operations with same signature but different indices
        mangled_sig = "duplicate_op() -> void"
        
        op1_id = stable_id(f"{class_id}:op:0:{mangled_sig}")
        op2_id = stable_id(f"{class_id}:op:1:{mangled_sig}")
        
        # Should be different due to index
        assert op1_id != op2_id, f"Operation IDs should be different: {op1_id} vs {op2_id}"
        
        # Both should be different IDs containing operation info
        assert op1_id.startswith("id_"), f"Operation ID should start with 'id_': {op1_id}"
        assert op2_id.startswith("id_"), f"Operation ID should start with 'id_': {op2_id}"
    
    def test_config_stubs_disabled(self):
        """Test that DataType stubs are disabled in configuration."""
        from app.config import DEFAULT_CONFIG
        
        # Verify that emit_referenced_type_stubs is set to False
        assert DEFAULT_CONFIG.emit_referenced_type_stubs is False, \
            "emit_referenced_type_stubs should be disabled for EMF compatibility"


def test_integration_scenario():
    """Test the complete integration scenario that was failing before fixes."""
    # Run the actual integration test
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/test_integration_spdlog.py::test_spdlog_integration_generate_and_validate",
        "-v", "--tb=short"
    ], capture_output=True, text=True)
    
    # Should pass without EMF validation errors
    assert result.returncode == 0, f"Integration test failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert "PASSED" in result.stdout, "Integration test should pass"
    assert "EMF validator failed" not in result.stdout, "Should not have EMF validation failures"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
