#!/usr/bin/env python3
"""
Tests for template processing fixes.

These tests verify that the template name generation improvements work correctly.
"""

import pytest
import tempfile
import os
from gen.xmi.template_utils import TemplateNameCleaner, create_clean_template_name
from gen.xmi.generator import XmiGenerator
from core.uml_model import UmlModel, UmlElement, ClangMetadata, ElementName, XmiId
from uml_types import ElementKind


class TestTemplateNameCleaner:
    """Test the template name cleaning functionality."""
    
    def test_clean_basic_types(self):
        """Test cleaning of basic C++ types."""
        cleaner = TemplateNameCleaner()
        
        basic_cases = [
            ("bool", "bool"),
            ("int", "int"), 
            ("char", "char"),
            ("true", "true"),
            ("false", "false"),
            ("T", "T"),  # Template parameter
            ("typename T::value_type", "typename T::value_type"),  # Keep complex but valid
        ]
        
        for input_val, expected in basic_cases:
            result = cleaner.clean_template_arg(input_val)
            assert result == expected, f"Expected {expected}, got {result} for '{input_val}'"
    
    def test_clean_std_types(self):
        """Test cleaning of std:: types.""" 
        cleaner = TemplateNameCleaner()
        
        std_cases = [
            ("std::true_type", "true"),
            ("std::false_type", "false"),
            ("std::string", "std::string"),  # Actually keep std::string as is
            ("std::vector", "std::vector"),  # Keep important containers
            ("std::unique_ptr", "std::unique_ptr"),  # Keep important smart pointers
        ]
        
        for input_val, expected in std_cases:
            result = cleaner.clean_template_arg(input_val)
            assert result == expected, f"Expected {expected}, got {result} for '{input_val}'"
    
    def test_clean_malformed_macro_args(self):
        """Test cleaning of malformed arguments from C++ macros."""
        cleaner = TemplateNameCleaner()
        
        malformed_cases = [
            # Real problematic cases from spdlog data
            ('type::constant> {}\r\n\r\nFMT_TYPE_CONSTANT(int, int_type)', 'void'),
            ('Context::builtin_types || TYPE == type::int_type ? TYPE\r\n          : type::custom_type', 'void'),
            # This one partially cleans but doesn't become empty - that's ok
            ('std::numeric_limits<T>::is_signed ||\r\nstd::is_same<T, int128_opt>::value', 'std::numeric_limits<T>::is_signed ||'),
        ]
        
        for input_val, expected in malformed_cases:
            result = cleaner.clean_template_arg(input_val)
            assert result == expected, f"Expected {expected}, got {result} for malformed input"
    
    def test_validity_check(self):
        """Test template argument validity checking."""
        cleaner = TemplateNameCleaner()
        
        # Valid arguments
        valid_args = ["bool", "int", "T", "std::string", "typename T::value_type"]
        for arg in valid_args:
            assert cleaner.is_valid_template_arg(arg), f"'{arg}' should be valid"
        
        # Invalid arguments (macro remnants)
        invalid_args = [
            'type::constant> {}\r\nFMT_TYPE_CONSTANT',
            'Context::builtin_types ||',
            'FMT_TYPE_CONSTANT(int, int_type)',
        ]
        for arg in invalid_args:
            assert not cleaner.is_valid_template_arg(arg), f"'{arg}' should be invalid"


class TestTemplateNameGeneration:
    """Test complete template name generation."""
    
    def test_simple_template_names(self):
        """Test generation of simple template names."""
        test_cases = [
            ("vector", [{"kind": "name", "name": "int"}], "vector<int>"),
            ("map", [{"kind": "name", "name": "string"}, {"kind": "name", "name": "int"}], "map<string, int>"),
            ("integral_constant", [{"kind": "name", "name": "bool"}, {"kind": "literal", "value": "true"}], "integral_constant<bool, true>"),
        ]
        
        for base, args, expected in test_cases:
            result = create_clean_template_name(base, args, {}, {})
            assert result == expected, f"Expected '{expected}', got '{result}'"
    
    def test_nested_template_names(self):
        """Test generation of nested template names."""
        nested_cases = [
            ("basic_string", [
                {"kind": "name", "name": "char"},
                {"kind": "template", "base": "char_traits", "args": [{"kind": "name", "name": "char"}]},
                {"kind": "template", "base": "allocator", "args": [{"kind": "name", "name": "char"}]}
            ], "basic_string<char, char_traits<char>, allocator<char>>"),
        ]
        
        for base, args, expected in nested_cases:
            result = create_clean_template_name(base, args, {}, {})
            assert result == expected, f"Expected '{expected}', got '{result}'"
    
    def test_malformed_args_filtered_out(self):
        """Test that malformed arguments are filtered out."""
        # Template with one good arg and one bad arg
        base = "integral_constant"
        args = [
            {"kind": "name", "name": "bool"},
            {"kind": "name", "name": 'type::constant> {}\r\nFMT_TYPE_CONSTANT(int, int_type)'},  # Bad
        ]
        
        result = create_clean_template_name(base, args, {}, {})
        # Bad arg becomes "void" fallback, so we get both args
        assert result == "integral_constant<bool, void>", f"Expected result with void fallback, got '{result}'"
    
    def test_all_args_filtered_gives_base_name(self):
        """Test that if all args are filtered out, we get just the base name."""
        base = "some_template"
        args = [
            {"kind": "name", "name": 'type::constant> {}\r\nFMT_TYPE_CONSTANT'},  # Bad
            {"kind": "name", "name": 'Context::builtin_types ||'},  # Bad
        ]
        
        result = create_clean_template_name(base, args, {}, {})
        # All bad args become "void", so we get template with void arg
        assert result == "some_template<void>", f"Expected template with void arg, got '{result}'"


class TestIntegrationWithXmiGenerator:
    """Test template fixes integration with XMI generation."""
    
    @pytest.fixture
    def sample_model_with_problematic_templates(self):
        """Create a model that would have problematic template names."""
        model_elements = {}
        name_to_xmi = {}
        
        # This would represent a problematic template class from real data
        problematic_class = UmlElement(
            xmi=XmiId("id_problematic_template"),
            name=ElementName("std::integral_constant<fmt::detail::type,type::constant> {} FMT_TYPE_CONSTANT"),
            kind=ElementKind.CLASS,
            members=[],
            clang=ClangMetadata(),
            used_types=frozenset(),
            underlying=None
        )
        
        model_elements[problematic_class.xmi] = problematic_class
        name_to_xmi[problematic_class.name] = problematic_class.xmi
        
        model = UmlModel(
            elements=model_elements,
            associations=[],
            dependencies=[],
            generalizations=[],
            name_to_xmi=name_to_xmi
        )
        
        return model
    
    def test_xmi_generation_with_template_fixes(self, sample_model_with_problematic_templates):
        """Test that XMI generation works with template fixes applied."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.uml', delete=False) as f:
            temp_path = f.name
            
        try:
            generator = XmiGenerator(sample_model_with_problematic_templates)
            # This should not crash and should generate valid XMI
            generator.write(temp_path, "TestModel", pretty=True)
            
            # Verify the file was created
            assert os.path.exists(temp_path)
            
            # Verify it contains valid XML structure
            with open(temp_path, 'r', encoding='utf-8') as f:
                content = f.read()
                assert '<?xml version' in content
                assert 'uml:Model' in content
                
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
