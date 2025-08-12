#!/usr/bin/env python3
"""
Test file for improved template handling in CppModelBuilder.
"""

import json
from build.cpp.builder import CppModelBuilder
from CppParser import CppTypeParser

def test_template_parsing():
    """Test enhanced template parsing functionality."""
    print("=== Testing Template Parsing ===")
    
    test_cases = [
        "std::vector<int>",
        "std::map<std::string, int>",
        "MyClass<T, U>",
        "std::unique_ptr<MyClass<int>>",
        "std::tuple<int, float, std::string>",
        "Container<Item<Type>>"
    ]
    
    for test_case in test_cases:
        base, args = CppTypeParser.parse_template_args(test_case)
        print(f"'{test_case}' -> base: '{base}', args: {args}")

def test_template_matching():
    """Test template matching functionality."""
    print("\n=== Testing Template Matching ===")
    
    # Mock data for testing
    mock_data = {
        "elements": [
            {
                "name": "std::vector",
                "display_name": "std::vector<T>",
                "is_template": True,
                "kind": "class",
                "templates": ["T"]
            },
            {
                "name": "std::map",
                "display_name": "std::map<K, V>",
                "is_template": True,
                "kind": "class",
                "templates": ["K", "V"]
            },
            {
                "name": "MyClass",
                "display_name": "MyClass<T>",
                "is_template": True,
                "kind": "class",
                "templates": ["T"]
            }
        ]
    }
    
    builder = CppModelBuilder(mock_data)
    # prepare is implicit in build
    
    # Test template matching
    test_types = [
        "std::vector<int>",
        "std::map<std::string, int>",
        "MyClass<float>"
    ]
    
    candidates = [(name, info) for name, info in builder.created.items()]
    
    for test_type in test_types:
        match = builder.find_best_template_match(test_type, candidates)
        print(f"'{test_type}' -> matched: {match}")

def test_template_dependencies():
    """Test template dependency resolution."""
    print("\n=== Testing Template Dependencies ===")
    
    mock_data = {
        "elements": [
            {
                "name": "std::vector",
                "display_name": "std::vector<T>",
                "is_template": True,
                "kind": "class",
                "templates": ["T"]
            },
            {
                "name": "int",
                "display_name": "int",
                "kind": "datatype"
            },
            {
                "name": "std::string",
                "display_name": "std::string",
                "kind": "class"
            }
        ]
    }
    
    builder = CppModelBuilder(mock_data)
    # prepare is implicit in build
    
    candidates = [(name, info) for name, info in builder.created.items()]
    
    test_type = "std::vector<int>"
    resolved = builder.resolve_template_dependencies(test_type, candidates)
    print(f"'{test_type}' -> resolved dependencies: {resolved}")

def test_inheritance_resolution():
    """Test inheritance resolution with templates."""
    print("\n=== Testing Inheritance Resolution ===")
    
    mock_data = {
        "elements": [
            {
                "name": "BaseClass",
                "display_name": "BaseClass<T>",
                "is_template": True,
                "kind": "class",
                "templates": ["T"]
            },
            {
                "name": "DerivedClass",
                "display_name": "DerivedClass<int>",
                "kind": "class",
                "bases": ["BaseClass<int>"]
            }
        ]
    }
    
    builder = CppModelBuilder(mock_data)
    # prepare is implicit in build
    result = builder.build()
    
    print(f"Generalizations: {len(result['generalizations'])}")
    for gen in result['generalizations']:
        print(f"  {gen.child_id} -> {gen.parent_id}")

if __name__ == "__main__":
    test_template_parsing()
    test_template_matching()
    test_template_dependencies()
    test_inheritance_resolution()
    print("\n=== All tests completed ===")
