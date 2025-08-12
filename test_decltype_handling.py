#!/usr/bin/env python3
"""
Test file for decltype handling in CppParser.
"""

from CppParser import CppTypeParser

def test_decltype_parsing():
    """Test how decltype expressions are parsed."""
    print("=== Testing decltype Parsing ===")
    
    test_cases = [
        "decltype(std)",
        "decltype(std::vector<int>)",
        "decltype(declval<T>().data())",
        "decltype(auto)",
        "decltype(std::string)",
        "decltype(std::map<std::string, int>)"
    ]
    
    for test_case in test_cases:
        # Current parsing returns tokens including decltype expr itself
        tokens = CppTypeParser.extract_all_type_identifiers(test_case)
        assert isinstance(tokens, list)
        # Template parsing
        base, args = CppTypeParser.parse_template_args(test_case)
        assert base is not None
        # Inner expression parsing for decltype
        if test_case.startswith('decltype(') and test_case.endswith(')'):
            inner_expr = test_case[9:-1]
            inner_tokens = CppTypeParser.extract_all_type_identifiers(inner_expr)
            assert isinstance(inner_tokens, list)
            inner_base, inner_args = CppTypeParser.parse_template_args(inner_expr)
            assert inner_base is not None

def test_decltype_inside_templates():
    """Ensure decltype works as template argument and nested."""
    cases = [
        "std::vector<decltype(std::string)>",
        "std::map<decltype(std::string), std::vector<decltype(std::vector<int>)>>",
        "MyType<decltype(declval<T>().f()), std::tuple<int, decltype(g())>>"
    ]
    for s in cases:
        base, args = CppTypeParser.parse_template_args(s)
        assert '<' not in base  # base extracted without args
        # Ensure args list parsed non-empty for templated cases
        assert isinstance(args, list) and len(args) >= 1
        tokens = CppTypeParser.extract_all_type_identifiers(s)
        assert isinstance(tokens, list)

if __name__ == "__main__":
    test_decltype_parsing()
    print("\n=== decltype parsing test completed ===")
