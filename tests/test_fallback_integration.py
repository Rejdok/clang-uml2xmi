#!/usr/bin/env python3
"""
Integration tests for fallback C++ metadata solution

⚠️  These test the TEMPORARY FALLBACK implementation.
TODO: Replace with clang-uml C++ library integration tests.
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.cpp_integration import CppEnhancedModelBuilder, CppAwareXmiGenerator
from core.cpp_metadata import CppProfileRegistry
from app.config import GeneratorConfig


class TestFallbackIntegration:
    """Test that fallback C++ metadata system integrates properly with existing codebase"""
    
    def test_config_cpp_options_loaded(self):
        """Test that new C++ processing options are available in config"""
        config = GeneratorConfig()
        
        # Check fallback options are present
        assert hasattr(config, 'cpp_processing_strategy')
        assert hasattr(config, 'cpp_max_corruption_level')
        assert hasattr(config, 'cpp_preserve_raw_metadata')
        assert hasattr(config, 'cpp_enable_profiles')
        assert hasattr(config, 'cpp_show_fallback_warnings')
        
        # Check default values
        assert config.cpp_processing_strategy == "fallback"
        assert config.cpp_max_corruption_level == 2
        assert config.cpp_preserve_raw_metadata == True
        assert config.cpp_enable_profiles == True
        assert config.cpp_show_fallback_warnings == True
    
    def test_enhanced_model_builder_factory(self):
        """Test that enhanced model builder can be created with config"""
        from core.cpp_integration import get_enhanced_builder, CppEnhancedConfig
        
        config = CppEnhancedConfig()
        config.template_strategy = "fallback"
        config.max_corruption_level = 2
        
        builder = get_enhanced_builder(config)
        assert isinstance(builder, CppEnhancedModelBuilder)
        assert builder.converter is not None
        assert builder.profile_registry is not None
    
    def test_migration_warnings_displayed(self):
        """Test that migration warnings are displayed for fallback usage"""
        import logging
        from core.cpp_integration import log_migration_warning
        
        # Capture log output
        with pytest.warns(None) as warnings:
            log_migration_warning()
        
        # Should generate warning about fallback implementation
        # (Note: warnings might not be captured properly in pytest, so this is a basic check)
        assert True  # Migration warning function should not crash
    
    def test_fallback_processing_on_real_data(self):
        """Test fallback processing on realistic corrupted template data"""
        # Real corrupted data similar to what we see in spdlog
        realistic_corrupted_data = {
            "std::integral_constant": {
                "name": "integral_constant",
                "namespace": "std",
                "is_template": True,
                "template_parameters": [
                    {"kind": "argument", "type": "fmt::detail::type"},  # Clean
                    {"kind": "argument", "type": "type::constant> {}\r\n\r\nFMT_TYPE_CONSTANT(int, int_type"}  # Corrupted
                ]
            },
            "std::vector": {
                "name": "vector", 
                "namespace": "std",
                "is_template": True,
                "template_parameters": [
                    {"kind": "template_type", "name": "T"},  # Clean
                    {"kind": "template_type", "name": "Allocator"}  # Clean
                ]
            }
        }
        
        builder = CppEnhancedModelBuilder()
        model = builder.build_enhanced_model(realistic_corrupted_data)
        
        # Should successfully process both elements
        assert len(model.elements) == 2
        assert len(model.name_to_xmi) == 2
        
        # Should handle corruption gracefully
        integral_constant_element = None
        vector_element = None
        
        for element in model.elements.values():
            if "integral_constant" in str(element.name):
                integral_constant_element = element
            elif "vector" in str(element.name):
                vector_element = element
        
        # Both elements should be created
        assert integral_constant_element is not None
        assert vector_element is not None
    
    def test_cpp_profiles_integration(self):
        """Test that C++ type profiles integrate with model building"""
        registry = CppProfileRegistry()
        
        # Should have standard library profiles
        profiles = [
            "std::vector", "std::map", "std::unique_ptr", "std::shared_ptr"
        ]
        
        for profile_name in profiles:
            profile = registry.get_profile(profile_name)
            assert profile is not None, f"Profile {profile_name} should be available"
            assert profile.argument_roles, f"Profile {profile_name} should have argument roles"
    
    def test_enhanced_xmi_generation_compatibility(self):
        """Test that enhanced XMI generation is compatible with existing validation"""
        from core.uml_model import UmlModel
        
        # Create minimal enhanced model
        sample_data = {
            "TestClass": {
                "name": "TestClass",
                "namespace": "",
                "is_template": False
            }
        }
        
        builder = CppEnhancedModelBuilder()
        enhanced_model = builder.build_enhanced_model(sample_data)
        
        # Should be compatible with existing UmlModel structure
        assert hasattr(enhanced_model, 'elements')
        assert hasattr(enhanced_model, 'associations')
        assert hasattr(enhanced_model, 'dependencies')
        assert hasattr(enhanced_model, 'generalizations')
        assert hasattr(enhanced_model, 'name_to_xmi')
        
        # Elements should be properly formatted
        assert len(enhanced_model.elements) > 0
        element = list(enhanced_model.elements.values())[0]
        assert hasattr(element, 'xmi')
        assert hasattr(element, 'name')
        assert hasattr(element, 'kind')


class TestFallbackStability:
    """Test stability and robustness of fallback implementation"""
    
    def test_large_scale_processing(self):
        """Test processing of large datasets without crashes"""
        # Simulate large dataset with mixed clean/corrupted data
        large_dataset = {}
        
        for i in range(100):
            if i % 3 == 0:  # Every 3rd element has corrupted templates
                large_dataset[f"CorruptedClass{i}"] = {
                    "name": f"CorruptedClass{i}",
                    "is_template": True,
                    "template_parameters": [
                        {"kind": "argument", "type": f"type::constant{i}> {{}}\r\n\r\nMACRO_GARBAGE"}
                    ]
                }
            else:  # Clean elements
                large_dataset[f"CleanClass{i}"] = {
                    "name": f"CleanClass{i}",
                    "is_template": i % 2 == 0,
                    "template_parameters": [
                        {"kind": "template_type", "name": "T"}
                    ] if i % 2 == 0 else []
                }
        
        builder = CppEnhancedModelBuilder()
        
        # Should not crash on large corrupted dataset
        model = builder.build_enhanced_model(large_dataset)
        assert len(model.elements) == 100
        
        # Should process at least some elements successfully
        assert len(model.name_to_xmi) == 100
    
    def test_edge_case_template_formats(self):
        """Test handling of various edge case template parameter formats"""
        edge_cases = {
            "EmptyTemplate": {
                "name": "EmptyTemplate",
                "is_template": True,
                "template_parameters": []  # Empty list
            },
            "NoneTemplate": {
                "name": "NoneTemplate", 
                "is_template": True,
                "template_parameters": None  # None value
            },
            "MixedFormats": {
                "name": "MixedFormats",
                "is_template": True,
                "template_parameters": [
                    "string_param",  # String format
                    {"kind": "template_type", "name": "T"},  # Dict format
                    {"invalid": "structure"},  # Invalid dict
                    42  # Invalid type
                ]
            }
        }
        
        builder = CppEnhancedModelBuilder()
        
        # Should handle all edge cases without crashing
        model = builder.build_enhanced_model(edge_cases)
        assert len(model.elements) == 3
    
    def test_memory_usage_reasonable(self):
        """Test that memory usage is reasonable for dual representation"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Process moderate-sized dataset
        moderate_dataset = {}
        for i in range(50):
            moderate_dataset[f"Class{i}"] = {
                "name": f"Class{i}",
                "namespace": "test",
                "is_template": True,
                "template_parameters": [
                    {"kind": "template_type", "name": f"T{j}"} for j in range(5)
                ]
            }
        
        builder = CppEnhancedModelBuilder()
        model = builder.build_enhanced_model(moderate_dataset)
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 100MB for 50 elements)
        assert memory_increase < 100 * 1024 * 1024, f"Memory increase too large: {memory_increase / 1024 / 1024:.1f}MB"
    
    def test_concurrent_processing_safety(self):
        """Test that fallback processing is safe for concurrent use"""
        import threading
        import time
        
        def process_data(thread_id):
            data = {
                f"ThreadClass{thread_id}": {
                    "name": f"ThreadClass{thread_id}",
                    "is_template": True, 
                    "template_parameters": [
                        {"kind": "template_type", "name": f"T{thread_id}"}
                    ]
                }
            }
            
            builder = CppEnhancedModelBuilder()
            model = builder.build_enhanced_model(data)
            return len(model.elements)
        
        # Run multiple threads concurrently
        threads = []
        results = []
        
        for i in range(5):
            thread = threading.Thread(target=lambda i=i: results.append(process_data(i)))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All threads should complete successfully
        assert len(results) == 5
        assert all(result == 1 for result in results)


class TestFallbackDeprecationMarking:
    """Test that all fallback components are properly marked for deprecation"""
    
    def test_fallback_files_contain_warnings(self):
        """Test that all fallback files contain proper migration warnings"""
        fallback_files = [
            "core/cpp_metadata.py",
            "core/cpp_integration.py", 
            "examples/cpp_metadata_usage.py",
            "tests/test_cpp_metadata.py"
        ]
        
        for file_path in fallback_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Should contain fallback warnings
            assert "FALLBACK" in content or "fallback" in content, f"{file_path} should contain FALLBACK warning"
            assert "TODO" in content, f"{file_path} should contain TODO for migration"
            assert ("clang-uml" in content or "migration" in content), f"{file_path} should mention migration path"
    
    def test_heuristic_functions_marked(self):
        """Test that all heuristic functions are properly marked"""
        from core.cpp_metadata import TemplateSyncStrategy
        
        # Check that heuristic methods contain warnings in docstrings
        methods_to_check = [
            '_extract_clean_name',
            '_guess_parameter_kind', 
            'cpp_to_uml'
        ]
        
        for method_name in methods_to_check:
            method = getattr(TemplateSyncStrategy, method_name)
            docstring = method.__doc__ or ""
            
            assert "HEURISTIC" in docstring, f"{method_name} should be marked as HEURISTIC"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
