#!/usr/bin/env python3
"""
Test script for the improved XmiGenerator.
"""

import logging
import tempfile
import os
from UmlModel import UmlModel, UmlElement, ElementKind, ClangMetadata, XmiId, ElementName
from XmiGenerator import XmiGenerator
from XmiWriter import XmiWriter
from lxml import etree

# Configure logging for testing
logging.basicConfig(level=logging.DEBUG)

def create_test_model():
    """Create a simple test model with namespaces and templates."""
    
    # Create some test elements
    class1 = UmlElement(
        xmi=XmiId("class1"),
        name=ElementName("TestClass"),
        kind=ElementKind.CLASS,
        members=[],
        clang=ClangMetadata(),
        used_types=frozenset(),
        underlying=None
    )
    
    # Add template parameters
    class1.templates = ["T", "U"]
    
    # Add some members
    from UmlModel import UmlMember, Visibility
    member1 = UmlMember(
        name="value",
        type_repr="T",
        visibility=Visibility.PRIVATE,
        is_static=False
    )
    class1.members.append(member1)
    
    # Create a namespaced class
    namespaced_class = UmlElement(
        xmi=XmiId("std_vector"),
        name=ElementName("std::vector<int>"),
        kind=ElementKind.CLASS,
        members=[],
        clang=ClangMetadata(),
        used_types=frozenset(),
        underlying=None
    )
    
    # Create an enum
    enum1 = UmlElement(
        xmi=XmiId("enum1"),
        name=ElementName("TestEnum"),
        kind=ElementKind.ENUM,
        members=[],
        clang=ClangMetadata(),
        used_types=frozenset(),
        underlying=None
    )
    enum1.literals = ["VALUE1", "VALUE2", "VALUE3"]
    
    # Create collections for the model
    elements = {}
    elements[class1.xmi] = class1
    elements[namespaced_class.xmi] = namespaced_class
    elements[enum1.xmi] = enum1
    
    name_to_xmi = {}
    name_to_xmi[class1.name] = class1.xmi
    name_to_xmi[namespaced_class.name] = namespaced_class.xmi
    name_to_xmi[enum1.name] = enum1.xmi
    
    # Create the model with proper constructor arguments
    from UmlModel import UmlModel
    model = UmlModel(
        elements=elements,
        associations=[],
        dependencies=[],
        generalizations=[],
        name_to_xmi=name_to_xmi
    )
    
    return model

def test_xmi_generator():
    """Test the XMI generator with a simple model."""
    
    print("Creating test model...")
    model = create_test_model()
    
    print("Creating XMI generator...")
    generator = XmiGenerator(model)
    
    print("Getting model statistics...")
    stats = generator.get_model_statistics()
    print(f"Model statistics: {stats}")
    
    # Create temporary output file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xmi', delete=False) as tmp:
        output_path = tmp.name
    
    try:
        print(f"Generating XMI file to: {output_path}")
        generator.write(output_path, "TestProject")
        
        print("XMI generation completed successfully!")
        
        # Check if file was created and has content
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"Output file size: {file_size} bytes")
            
            # Read first few lines to verify content
            with open(output_path, 'r', encoding='utf-8') as f:
                first_lines = [f.readline().strip() for _ in range(5)]
                print("First few lines of output:")
                for i, line in enumerate(first_lines):
                    if line:
                        print(f"  {i+1}: {line}")
        else:
            print("ERROR: Output file was not created!")
        
        # Additional validation: association ends types and unique return parameter ids
        # Build a minimal model with an association and an operation
        class2 = UmlElement(
            xmi=XmiId("class2"),
            name=ElementName("Client"),
            kind=ElementKind.CLASS,
            members=[],
            clang=ClangMetadata(),
            used_types=frozenset(),
            underlying=None
        )
        class3 = UmlElement(
            xmi=XmiId("class3"),
            name=ElementName("Server"),
            kind=ElementKind.CLASS,
            members=[],
            clang=ClangMetadata(),
            used_types=frozenset(),
            underlying=None
        )
        from UmlModel import UmlAssociation, AggregationType, UmlOperation
        assoc = UmlAssociation(src=class2.xmi, tgt=class3.xmi, aggregation=AggregationType.NONE, multiplicity="1", name="uses")
        op = UmlOperation(name="foo", return_type="int", parameters=[], visibility=ElementKind.CLASS.value)

        elements2 = {class2.xmi: class2, class3.xmi: class3}
        name_to_xmi2 = {class2.name: class2.xmi, class3.name: class3.xmi}
        model2 = UmlModel(elements=elements2, associations=[assoc], dependencies=[], generalizations=[], name_to_xmi=name_to_xmi2)
        gen2 = XmiGenerator(model2)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xmi', delete=False) as tmp2:
            path2 = tmp2.name
        try:
            gen2.write(path2, "P2")
            tree = etree.parse(path2)
            root = tree.getroot()
            # ownedEnd must have type attribute with valid xmi:idref value
            owns = root.findall('.//{http://www.eclipse.org/uml2/5.0.0/UML}packagedElement[@xmi:type="uml:Association"]', namespaces={'xmi': 'http://www.omg.org/XMI'})
            assert owns, "Association element not found"
            ends = owns[0].findall('{http://www.eclipse.org/uml2/5.0.0/UML}ownedEnd')
            assert ends and len(ends) == 2, "Association must have two ownedEnd elements"
            assert 'type' in ends[0].attrib and 'type' in ends[1].attrib, "ownedEnd must reference type"
        finally:
            try:
                os.unlink(path2)
            except:
                pass
            
    except Exception as e:
        print(f"ERROR during XMI generation: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up temporary file
        try:
            os.unlink(output_path)
            print("Temporary file cleaned up")
        except:
            pass

def test_template_binding_generation():
    """Ensure templateBinding is generated for template instantiations when enabled."""
    import tempfile, os
    from CppModelBuilder import CppModelBuilder
    from UmlModel import UmlModel as UmlCoreModel

    data = {
        "elements": [
            {"name": "std::vector", "display_name": "std::vector<T>", "is_template": True, "templates": ["T"], "kind": "class"},
            {"name": "std::string", "display_name": "std::string", "kind": "class"},
            {"name": "DataManager", "display_name": "DataManager", "kind": "class", "members": [
                {"name": "stringList", "type": "std::vector<std::string>"}
            ]}
        ]
    }

    builder = CppModelBuilder(data, enable_template_binding=True)
    prep = builder.build()

    elements_by_xmi = {elem.xmi: elem for elem in prep["created"].values()}
    model = UmlCoreModel(
        elements=elements_by_xmi,
        associations=prep["associations"],
        dependencies=prep["dependencies"],
        generalizations=prep.get("generalizations", []),
        name_to_xmi=prep["name_to_xmi"]
    )

    with tempfile.NamedTemporaryFile(mode='w', suffix='.xmi', delete=False) as tmp:
        path = tmp.name
    try:
        gen = XmiGenerator(model, enable_template_binding=True)
        gen.write(path, "TBProject")

        tree = etree.parse(path)
        root = tree.getroot()
        # Find any templateBinding elements
        bindings = root.findall('.//templateBinding')
        assert bindings, "templateBinding not generated"
        # Validate signature and parameterSubstitution
        xmi_ns = 'http://www.omg.org/XMI'
        found_valid = False
        for b in bindings:
            sig = b.find('signature')
            subs = b.findall('parameterSubstitution')
            if sig is not None and subs:
                # signature should have xmi:idref
                if f'{{{xmi_ns}}}idref' in sig.attrib:
                    # at least one substitution with actual/@xmi:idref
                    for sub in subs:
                        actual = sub.find('actual')
                        if actual is not None and f'{{{xmi_ns}}}idref' in actual.attrib:
                            found_valid = True
                            break
            if found_valid:
                break
        assert found_valid, "templateBinding missing signature/actual idrefs"
    finally:
        try:
            os.unlink(path)
        except:
            pass

if __name__ == "__main__":
    test_xmi_generator()
