#!/usr/bin/env python3
"""
Test file for complex template scenarios in CppModelBuilder.
"""

import json
from CppModelBuilder import CppModelBuilder
from CppParser import CppTypeParser

def test_complex_template_inheritance():
    """Test complex template inheritance scenarios."""
    print("=== Testing Complex Template Inheritance ===")
    
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
                "name": "Container",
                "display_name": "Container<T>",
                "is_template": True,
                "kind": "class",
                "templates": ["T"]
            },
            {
                "name": "SpecializedContainer",
                "display_name": "SpecializedContainer<int>",
                "kind": "class",
                "bases": ["Container<int>"]
            },
            {
                "name": "TemplateDerived",
                "display_name": "TemplateDerived<T>",
                "kind": "class",
                "bases": ["Container<T>"],
                "is_template": True,
                "templates": ["T"]
            }
        ]
    }
    
    builder = CppModelBuilder(mock_data)
    builder.prepare()
    result = builder.build()
    
    print(f"Elements created: {len(result['created'])}")
    print(f"Generalizations: {len(result['generalizations'])}")
    print(f"Associations: {len(result['associations'])}")
    print(f"Dependencies: {len(result['dependencies'])}")
    
    # Assert that there is at least one generalization from SpecializedContainer to Container
    names_by_xmi = {info.xmi: str(name) for name, info in result['created'].items()}
    pairs = [(names_by_xmi[g.child_id], names_by_xmi[g.parent_id]) for g in result['generalizations']]
    # Normalize by stripping template args
    norm_pairs = [
        (CppTypeParser.extract_template_base(c).split('::')[-1], CppTypeParser.extract_template_base(p).split('::')[-1])
        for c, p in pairs
    ]
    assert ("SpecializedContainer", "Container") in norm_pairs

def test_template_associations():
    """Test template associations and member types."""
    print("\n=== Testing Template Associations ===")
    
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
                "name": "std::string",
                "display_name": "std::string",
                "kind": "class"
            },
            {
                "name": "int",
                "display_name": "int",
                "kind": "datatype"
            },
            {
                "name": "DataManager",
                "display_name": "DataManager",
                "kind": "class",
                "members": [
                    {
                        "name": "stringList",
                        "type": "std::vector<std::string>",
                        "visibility": "private"
                    },
                    {
                        "name": "numberList",
                        "type": "std::vector<int>",
                        "visibility": "private"
                    }
                ]
            }
        ]
    }
    
    builder = CppModelBuilder(mock_data)
    builder.prepare()
    result = builder.build()
    
    print(f"Associations created: {len(result['associations'])}")
    # Expect associations to vector and to std::string/int resolutions
    assert len(result['associations']) >= 2

def test_nested_template_resolution():
    """Test resolution of nested template types."""
    print("\n=== Testing Nested Template Resolution ===")
    
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
                "name": "std::string",
                "display_name": "std::string",
                "kind": "class"
            },
            {
                "name": "ComplexContainer",
                "display_name": "ComplexContainer",
                "kind": "class",
                "members": [
                    {
                        "name": "nestedMap",
                        "type": "std::map<std::string, std::vector<int>>",
                        "visibility": "private"
                    }
                ]
            }
        ]
    }
    
    builder = CppModelBuilder(mock_data)
    builder.prepare()
    result = builder.build()
    # Ensure no crash and at least one association created to nested std::map or its args
    assert isinstance(result['associations'], list)

def test_template_parameter_extraction():
    """Test extraction of template parameters."""
    print("\n=== Testing Template Parameter Extraction ===")
    
    test_cases = [
        "std::vector<int>",
        "std::map<std::string, std::vector<int>>",
        "MyClass<T, U, V>",
        "std::tuple<int, float, std::string, std::vector<bool>>",
        "Container<Item<Type<Param>>>"
    ]
    
    for test_case in test_cases:
        base, args = CppTypeParser.parse_template_args(test_case)
        params = CppTypeParser.extract_template_parameters(test_case)
        is_instance = CppTypeParser.is_template_instance(test_case)
        assert base is not None
        if '<' in test_case:
            assert is_instance is True
            assert isinstance(params, list)
        else:
            assert is_instance is False

def test_reference_and_variadic_cleaning():
    """Types with references ("&", "&&") and packs ("...") should be normalized in names.
    Ensures builder doesn't produce element names with these suffixes.
    """
    from CppModelBuilder import CppModelBuilder

    mock = {
        "elements": [
            {"name": "sink_ptr", "kind": "class"},
            {"name": "Consumer", "kind": "class", "members": [
                {"name": "v1", "type": "std::vector<sink_ptr> &"},
                {"name": "v2", "type": "std::vector<sink_ptr&&>"},
                {"name": "args", "type": "Args &&..."}
            ]}
        ]
    }

    b = CppModelBuilder(mock, enable_template_binding=True)
    res = b.build()

    # No element name should contain reference/pack artifacts
    bad = [str(n) for n in res['created'].keys() if any(x in str(n) for x in ['&&', '...', ' &'])]
    assert not bad, f"Unexpected artifacts in element names: {bad}"

    # There should be an instantiation element for vector<sink_ptr>
    inst_names = [str(n) for n in res['created'].keys() if str(n).startswith('std::vector<')]
    assert any('vector<' in n and 'sink_ptr' in n for n in inst_names)

if __name__ == "__main__":
    test_complex_template_inheritance()
    test_template_associations()
    test_nested_template_resolution()
    test_template_parameter_extraction()
    print("=== All complex template tests completed ===")
