#!/usr/bin/env python3
"""
Tests for C++ Metadata system

✅ Tests for C++ metadata system with bidirectional conversion
Current implementation provides template processing and metadata preservation
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
# Path management handled by core/__init__.py

from core.cpp_metadata import (
    CppMetadata, CppTemplateData, RawTemplateParam, UMLTemplateParameter,
    CppAttribute, CppKeyword, CppMacro, CppStandard, KeywordScope, TemplateParameterKind,
    BidirectionalConverter, CppProfileRegistry, TemplateSyncStrategy
)
from core.cpp_integration import CppEnhancedModelBuilder, EnhancedUmlElement


class TestCppMetadata:
    """Test core C++ metadata classes"""
    
    def test_cpp_attribute_formatting(self):
        """Test C++ attribute string formatting"""
        # Standard attribute
        nodiscard = CppAttribute(
            namespace="std",
            name="nodiscard",
            standard=CppStandard.CPP17
        )
        assert str(nodiscard) == "[[std::nodiscard]]"
        
        # Attribute with arguments
        deprecated = CppAttribute(
            name="deprecated", 
            arguments=["Use new_function() instead"],
            standard=CppStandard.CPP14
        )
        assert str(deprecated) == "[[deprecated(Use new_function() instead)]]"
        
        # Custom attribute
        custom = CppAttribute(
            name="my_attribute",
            arguments=["arg1", "arg2"]
        )
        assert str(custom) == "[[my_attribute(arg1, arg2)]]"
    
    def test_raw_template_param_corruption_detection(self):
        """Test automatic corruption detection in template parameters"""
        # Clean parameter
        clean_param = RawTemplateParam(original_text="typename T")
        assert clean_param.corruption_level == 0
        assert not clean_param.is_corrupted
        
        # Minor corruption (line breaks)
        minor_corrupt = RawTemplateParam(original_text="std::integral_constant<bool>\r\nsome_text")
        assert minor_corrupt.corruption_level == 1
        assert minor_corrupt.is_corrupted
        
        # Major corruption (macro remnants)
        major_corrupt = RawTemplateParam(
            original_text="type::constant> {}\r\n\r\nFMT_TYPE_CONSTANT(int, int_type)"
        )
        assert major_corrupt.corruption_level == 2
        assert major_corrupt.is_corrupted
        
        # Unusable corruption 
        empty_param = RawTemplateParam(original_text="")
        assert empty_param.corruption_level == 3
        assert empty_param.is_corrupted


class TestTemplateSyncStrategy:
    """Test template synchronization between C++ and UML"""
    
    def test_clean_name_extraction(self):
        """Test extraction of clean names from corrupted template parameters"""
        # Clean cases
        assert TemplateSyncStrategy._extract_clean_name("typename T") == "typename T"
        assert TemplateSyncStrategy._extract_clean_name("std::string") == "std::string"
        assert TemplateSyncStrategy._extract_clean_name("bool") == "bool"
        
        # Corrupted cases that can be recovered
        corrupted_text = "fmt::detail::type::constant> {}\r\nFMT_TYPE_CONSTANT"
        extracted = TemplateSyncStrategy._extract_clean_name(corrupted_text)
        # Should extract clean part before corruption starts
        assert extracted is not None
        assert "fmt::detail::type" in extracted
        assert "constant>" not in extracted  # Should stop before corruption
        
        # Completely corrupted - no recovery possible
        garbage = "||||||{\r\n\r\n????"
        assert TemplateSyncStrategy._extract_clean_name(garbage) is None
    
    def test_parameter_kind_guessing(self):
        """Test heuristic-based parameter kind detection"""
        # Value parameters
        bool_param = RawTemplateParam(original_text="bool B")
        assert TemplateSyncStrategy._guess_parameter_kind(bool_param) == TemplateParameterKind.VALUE
        
        int_param = RawTemplateParam(original_text="size_t N")  
        assert TemplateSyncStrategy._guess_parameter_kind(int_param) == TemplateParameterKind.VALUE
        
        # Template template parameters
        template_param = RawTemplateParam(original_text="template<class> class Container")
        assert TemplateSyncStrategy._guess_parameter_kind(template_param) == TemplateParameterKind.TEMPLATE
        
        # Typename parameters (default)
        type_param = RawTemplateParam(original_text="typename T")
        assert TemplateSyncStrategy._guess_parameter_kind(type_param) == TemplateParameterKind.TYPENAME
    
    def test_cpp_to_uml_conversion(self):
        """Test conversion from corrupted C++ data to clean UML parameters"""
        # Recoverable parameter
        recoverable = RawTemplateParam(
            original_text="std::integral_constant<bool>",
            kind="argument"
        )
        
        uml_param = TemplateSyncStrategy.cpp_to_uml(recoverable)
        assert uml_param is not None
        # Name extraction may simplify the text
        assert "integral_constant" in uml_param.name
        assert uml_param._cpp_raw_data == recoverable
        
        # Unrecoverable parameter
        unrecoverable = RawTemplateParam(
            original_text="",  # Empty - corruption level 3
            kind="argument"
        )
        
        uml_param = TemplateSyncStrategy.cpp_to_uml(unrecoverable)
        assert uml_param is None
    
    def test_uml_to_cpp_conversion(self):
        """Test conversion from UML back to C++ code"""
        # Parameter with clean raw data
        raw_data = RawTemplateParam(original_text="typename T", kind="template_type")
        uml_param = UMLTemplateParameter(
            name="T",
            kind=TemplateParameterKind.TYPENAME,
            _cpp_raw_data=raw_data
        )
        
        cpp_code = TemplateSyncStrategy.uml_to_cpp(uml_param)
        assert cpp_code == "typename T"  # Uses original raw data
        
        # Parameter without raw data - generate from UML
        uml_only_param = UMLTemplateParameter(
            name="Size",
            kind=TemplateParameterKind.VALUE,
            default_value="0"
        )
        
        cpp_code = TemplateSyncStrategy.uml_to_cpp(uml_only_param)
        assert "Size" in cpp_code
        assert "= 0" in cpp_code


class TestCppProfileRegistry:
    """Test C++ type profiles system"""
    
    def test_standard_library_profiles(self):
        """Test that standard library profiles are loaded correctly"""
        registry = CppProfileRegistry()
        
        # Vector profile
        vector_profile = registry.get_profile("std::vector")
        assert vector_profile is not None
        assert vector_profile.argument_roles[0] == "element"
        assert vector_profile.argument_roles[1] == "allocator"
        assert vector_profile.multiplicity_rules["element"] == "*"
        
        # Map profile  
        map_profile = registry.get_profile("std::map")
        assert map_profile is not None
        assert map_profile.argument_roles[0] == "key"
        assert map_profile.argument_roles[1] == "value"
        
        # Smart pointer profiles
        unique_ptr_profile = registry.get_profile("std::unique_ptr")
        assert unique_ptr_profile is not None
        assert unique_ptr_profile.aggregation_rules["element"] == "composite"
        
        shared_ptr_profile = registry.get_profile("std::shared_ptr")
        assert shared_ptr_profile is not None  
        assert shared_ptr_profile.aggregation_rules["element"] == "shared"
    
    def test_custom_profile_registration(self):
        """Test registration of custom type profiles"""
        from core.cpp_metadata import CppTypeProfile
        
        registry = CppProfileRegistry()
        
        # Create custom profile
        custom_profile = CppTypeProfile(
            namespace="boost",
            type_name="optional",
            argument_roles={0: "value"},
            multiplicity_rules={"value": "0..1"},
            aggregation_rules={"value": "none"}
        )
        
        registry.register_profile(custom_profile)
        
        # Verify registration
        retrieved = registry.get_profile("boost::optional")
        assert retrieved is not None
        assert retrieved.argument_roles[0] == "value"
        assert retrieved.multiplicity_rules["value"] == "0..1"


class TestBidirectionalConverter:
    """Test bidirectional C++ ↔ UML conversion"""
    
    def test_parse_clean_cpp_element(self):
        """Test parsing of clean C++ element data"""
        clean_data = {
            "name": "vector",
            "namespace": "std",
            "is_template": True,
            "template_parameters": [
                {"kind": "template_type", "name": "T"},
                {"kind": "template_type", "name": "Allocator"}
            ],
            "source_location": {
                "file": "vector.h",
                "line": 100,
                "column": 10
            }
        }
        
        converter = BidirectionalConverter()
        cpp_element = converter.parse_cpp_element(clean_data)
        
        assert cpp_element.cpp_metadata is not None
        assert cpp_element.cpp_metadata.source_location is not None
        assert cpp_element.cpp_metadata.source_location.file == "vector.h"
        
        # Check template processing
        template_data = cpp_element.cpp_metadata.template_data
        assert template_data is not None
        assert len(template_data.uml_parameters) == 2
        assert not template_data.has_corrupted_data
    
    def test_parse_corrupted_cpp_element(self):
        """Test parsing of corrupted C++ element data"""
        corrupted_data = {
            "name": "integral_constant",
            "namespace": "std", 
            "is_template": True,
            "template_parameters": [
                {"kind": "argument", "type": "fmt::detail::type"},  # Clean
                {"kind": "argument", "type": "type::constant> {}\r\nFMT_TYPE_CONSTANT"}  # Corrupted
            ]
        }
        
        converter = BidirectionalConverter()
        cpp_element = converter.parse_cpp_element(corrupted_data)
        
        template_data = cpp_element.cpp_metadata.template_data
        assert template_data is not None
        assert template_data.has_corrupted_data  # Should detect corruption
        assert len(template_data.recovery_notes) > 0  # Should have recovery notes
        
        # Should still extract some clean parameters
        assert len(template_data.uml_parameters) >= 1


class TestCppEnhancedModelBuilder:
    """Test enhanced model building with C++ metadata"""
    
    def test_build_enhanced_model(self):
        """Test building enhanced UML model from raw clang-uml data"""
        raw_elements = {
            "std::vector": {
                "name": "vector", 
                "namespace": "std",
                "is_template": True,
                "template_parameters": [
                    {"kind": "template_type", "name": "T"}
                ]
            },
            "MyClass": {
                "name": "MyClass",
                "namespace": "",
                "is_template": False
            }
        }
        
        builder = CppEnhancedModelBuilder()
        model = builder.build_enhanced_model(raw_elements)
        
        assert len(model.elements) == 2
        assert len(model.name_to_xmi) == 2
        
        # Find enhanced elements
        enhanced_elements = [elem for elem in model.elements.values() 
                           if isinstance(elem, EnhancedUmlElement)]
        assert len(enhanced_elements) == 2
    
    def test_template_corruption_fallback(self):
        """Test fallback behavior when all template parameters are corrupted"""
        corrupted_element = {
            "name": "BadTemplate",
            "is_template": True,
            "template_parameters": [
                {"kind": "argument", "type": "garbage||{}\r\nMACRO_GARBAGE"}
            ]
        }
        
        builder = CppEnhancedModelBuilder()
        model = builder.build_enhanced_model({"BadTemplate": corrupted_element})
        
        element = list(model.elements.values())[0]
        # Should detect corruption but may still have some template info
        # The enhanced element processing handles corruption gracefully
        assert isinstance(element, EnhancedUmlElement)


class TestIntegrationWithExistingCode:
    """Test integration with existing UML codebase"""
    
    def test_enhanced_uml_element_compatibility(self):
        """Test that EnhancedUmlElement is compatible with existing UML code"""
        from core.uml_model import UmlElement, ElementName, XmiId, ClangMetadata
        from uml_types import ElementKind
        from utils.ids import stable_id
        
        # Create enhanced element using existing types
        base_element = UmlElement(
            xmi=XmiId(stable_id("test_class")),
            name=ElementName("TestClass"),
            kind=ElementKind.CLASS,
            members=[],
            clang=ClangMetadata(),
            used_types=frozenset(),
            underlying=None
        )
        
        enhanced = EnhancedUmlElement(
            xmi=base_element.xmi,
            name=base_element.name,
            kind=base_element.kind,
            members=base_element.members,
            clang=base_element.clang,
            used_types=base_element.used_types,
            underlying=base_element.underlying
        )
        
        # Should maintain compatibility
        assert enhanced.xmi == base_element.xmi
        assert enhanced.name == base_element.name
        assert enhanced.kind == base_element.kind
        
        # Should add C++ capabilities
        assert hasattr(enhanced, 'cpp_metadata')
        assert hasattr(enhanced, 'bidirectional_state')


class TestTemplateFallbackInAction:
    """Test template fallback processing on real-world examples"""
    
    def test_spdlog_integral_constant_case(self):
        """Test processing of actual problematic spdlog template data"""
        # This is the exact corrupted data from spdlog
        spdlog_corrupted = {
            "name": "integral_constant",
            "namespace": "std",
            "display_name": "std::integral_constant<fmt::detail::type,type::constant> {} FMT_TYPE_CONSTANT(int, int_type>",
            "is_template": True,
            "template_parameters": [
                {
                    "is_variadic": False,
                    "kind": "argument", 
                    "template_parameters": [],
                    "type": "fmt::detail::type"
                },
                {
                    "is_variadic": False,
                    "kind": "argument",
                    "template_parameters": [],
                    "type": "type::constant> {}\r\n\r\nFMT_TYPE_CONSTANT(int, int_type"
                }
            ]
        }
        
        converter = BidirectionalConverter()
        cpp_element = converter.parse_cpp_element(spdlog_corrupted)
        
        # Should handle corruption gracefully
        assert cpp_element.cpp_metadata is not None
        assert cpp_element.cpp_metadata.template_data is not None
        
        # Should extract at least the clean parameter
        uml_params = cpp_element.cpp_metadata.template_data.uml_parameters
        assert len(uml_params) >= 1  # At least the fmt::detail::type should be extracted
        
        # Should generate some code
        generated_code = converter.generate_cpp_code(cpp_element)
        assert "class" in generated_code
        assert generated_code != "// No code generated"
    
    def test_clean_std_vector_case(self):
        """Test processing of clean std::vector template"""
        clean_vector = {
            "name": "vector",
            "namespace": "std",
            "is_template": True,
            "template_parameters": [
                {"kind": "template_type", "name": "T"},
                {"kind": "template_type", "name": "Allocator", "default": "std::allocator<T>"}
            ]
        }
        
        converter = BidirectionalConverter()
        cpp_element = converter.parse_cpp_element(clean_vector)
        
        template_data = cpp_element.cpp_metadata.template_data
        assert template_data is not None
        assert not template_data.has_corrupted_data
        assert len(template_data.uml_parameters) == 2
        
        # Check parameter details
        assert template_data.uml_parameters[0].name == "T"
        assert template_data.uml_parameters[0].kind == TemplateParameterKind.TYPENAME
        
        # Generate code
        generated_code = converter.generate_cpp_code(cpp_element)
        assert "template<" in generated_code
        assert "class vector" in generated_code


class TestCppProfileSystem:
    """Test C++ type profile system"""
    
    def test_std_vector_profile_application(self):
        """Test applying std::vector profile to template arguments"""
        registry = CppProfileRegistry()
        vector_profile = registry.get_profile("std::vector")
        
        assert vector_profile is not None
        assert vector_profile.argument_roles[0] == "element"
        assert vector_profile.argument_roles[1] == "allocator"
        assert vector_profile.multiplicity_rules["element"] == "*"
        assert vector_profile.aggregation_rules["element"] == "none"
    
    def test_smart_pointer_profiles(self):
        """Test smart pointer profiles for UML aggregation"""
        registry = CppProfileRegistry()
        
        # unique_ptr should indicate composite aggregation
        unique_profile = registry.get_profile("std::unique_ptr")
        assert unique_profile.aggregation_rules["element"] == "composite"
        
        # shared_ptr should indicate shared aggregation
        shared_profile = registry.get_profile("std::shared_ptr") 
        assert shared_profile.aggregation_rules["element"] == "shared"


@pytest.fixture
def sample_corrupted_template_data():
    """Fixture with real corrupted template data from spdlog"""
    return {
        "name": "integral_constant",
        "namespace": "std",
        "template_parameters": [
            {"kind": "argument", "type": "fmt::detail::type"},
            {"kind": "argument", "type": "type::constant> {}\r\nFMT_TYPE_CONSTANT(int, int_type)"}
        ]
    }


class TestFallbackRobustness:
    """Test robustness of fallback implementation"""
    
    def test_empty_template_parameters(self):
        """Test handling of empty or None template parameters"""
        converter = BidirectionalConverter()
        
        # Empty template_parameters
        empty_templates = {"name": "Test", "template_parameters": []}
        element = converter.parse_cpp_element(empty_templates)
        assert element.cpp_metadata.template_data is None or not element.cpp_metadata.template_data.uml_parameters
        
        # None template_parameters
        none_templates = {"name": "Test", "template_parameters": None}
        element = converter.parse_cpp_element(none_templates)
        assert element.cpp_metadata.template_data is None or not element.cpp_metadata.template_data.uml_parameters
    
    def test_malformed_json_data(self):
        """Test handling of malformed JSON data"""
        converter = BidirectionalConverter()
        
        # Missing required fields
        malformed = {"name": "Test"}  # No namespace, no template info
        element = converter.parse_cpp_element(malformed)
        assert element.cpp_metadata is not None  # Should still create metadata
        
        # Invalid template parameter structure
        invalid_template = {
            "name": "Test",
            "template_parameters": ["not_a_dict", {"invalid": "structure"}]
        }
        
        # Should not crash
        element = converter.parse_cpp_element(invalid_template)
        assert element.cpp_metadata is not None
    
    def test_extreme_corruption_handling(self, sample_corrupted_template_data):
        """Test handling of extremely corrupted template data"""
        converter = BidirectionalConverter()
        element = converter.parse_cpp_element(sample_corrupted_template_data)
        
        # Should extract something useful
        assert element.cpp_metadata is not None
        assert element.cpp_metadata.template_data is not None
        
        # Should be able to generate some code
        generated_code = converter.generate_cpp_code(element)
        assert isinstance(generated_code, str)
        assert len(generated_code) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
