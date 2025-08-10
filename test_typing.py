#!/usr/bin/env python3
"""
Test file to verify the new strict typing in UmlModel
"""

from UmlModel import *
from CppModelBuilder import CppModelBuilder

def test_uml_model_creation():
    """Test creating UmlModel with new types."""
    
    # Create test elements
    clang_meta = ClangMetadata(
        is_abstract=False,
        is_enum=False,
        is_typedef=False,
        is_interface=False,
        is_struct=False,
        is_datatype=False,
        qualified_name="TestClass",
        display_name="TestClass",
        name="TestClass",
        type="class",
        kind="class"
    )
    
    member = UmlMember(
        name="testMember",
        type_repr="int",
        visibility=Visibility.PRIVATE,
        is_static=False
    )
    
    element = UmlElement(
        xmi="test_id_1",
        name="TestClass",
        kind=ElementKind.CLASS,
        members=[member],
        clang=clang_meta,
        used_types={"int"},
        underlying=None
    )
    
    # Create association
    association = UmlAssociation(
        src="test_id_1",
        tgt="test_id_2",
        aggregation=AggregationType.SHARED,
        multiplicity="*",
        name="testAssoc"
    )
    
    # Create model
    model = UmlModel(
        elements={"TestClass": element},
        associations=[association],
        dependencies=[("TestClass", "UnknownType")],
        generalizations=[("child", "parent")],
        name_to_xmi={"TestClass": "test_id_1"}
    )
    
    print("✓ UmlModel created successfully with strict typing")
    print(f"  - Element kind: {element.kind}")
    print(f"  - Member visibility: {member.visibility}")
    print(f"  - Association aggregation: {association.aggregation}")
    print(f"  - Model has {len(model.elements)} elements")
    
    return model

def test_cpp_model_builder():
    """Test CppModelBuilder with new types."""
    
    # Create mock JSON data
    mock_json = {
        "elements": [
            {
                "name": "TestClass",
                "type": "class",
                "members": [
                    {
                        "name": "member1",
                        "type": "int",
                        "visibility": "private"
                    }
                ]
            }
        ],
        "project_name": "TestProject"
    }
    
    try:
        builder = CppModelBuilder(mock_json)
        result = builder.build()
        print("✓ CppModelBuilder works with new types")
        print(f"  - Created {len(result['created'])} elements")
        print(f"  - Created {len(result['associations'])} associations")
        return result
    except Exception as e:
        print(f"✗ CppModelBuilder failed: {e}")
        return None

if __name__ == "__main__":
    print("Testing new strict typing in UmlModel...")
    print("=" * 50)
    
    # Test 1: Direct UmlModel creation
    model = test_uml_model_creation()
    
    print()
    
    # Test 2: CppModelBuilder integration
    result = test_cpp_model_builder()
    
    print()
    print("=" * 50)
    print("All tests completed!")
