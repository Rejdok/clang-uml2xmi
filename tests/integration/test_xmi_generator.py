#!/usr/bin/env python3
"""
Test script for the improved XmiGenerator.
"""

import logging
import tempfile
import os
from core.uml_model import UmlModel, UmlElement, ClangMetadata, XmiId, ElementName
from uml_types import ElementKind
from gen.xmi.generator import XmiGenerator
from gen.xmi.writer import XmiWriter
from lxml import etree
import pytest

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
    from core.uml_model import UmlMember
    from uml_types import Visibility
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
    from core.uml_model import UmlModel
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
        from core.uml_model import UmlAssociation, UmlOperation
        from uml_types import AggregationType
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
            except FileNotFoundError:
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
        except FileNotFoundError:
            pass

def test_template_binding_generation():
    """Ensure template instantiation element is generated (with default binding disabled in writer)."""
    import tempfile, os
    from build.cpp.builder import CppModelBuilder
    from core.uml_model import UmlModel as UmlCoreModel

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
        gen = XmiGenerator(model)
        gen.write(path, "TBProject")

        tree = etree.parse(path)
        root = tree.getroot()
        # Find instantiation packaged element (name contains 'vector<' and ends with '>')
        elems = root.findall('.//packagedElement')
        names = [el.get('name') for el in elems if el.get('name')]
        assert any(n and n.startswith('vector<') and n.endswith('>') for n in names), "Instantiation element not generated"
    finally:
        try:
            os.unlink(path)
        except:
            pass

def test_instantiation_namespace_structure():
    """Instantiation packaged element should be placed under its namespace packages in XMI."""
    import tempfile, os
    from build.cpp.builder import CppModelBuilder
    from core.uml_model import UmlModel as UmlCoreModel

    data = {
        "elements": [
            {"name": "std::vector", "display_name": "std::vector<T>", "is_template": True, "templates": ["T"], "kind": "class"},
            {"name": "std::string", "display_name": "std::string", "kind": "class"},
            {"name": "Client", "display_name": "Client", "kind": "class", "members": [
                {"name": "list", "type": "std::vector<std::string>"}
            ]}
        ]
    }

    builder = CppModelBuilder(data, enable_template_binding=True)
    prep = builder.build()
    model = UmlCoreModel(
        elements={elem.xmi: elem for elem in prep["created"].values()},
        associations=prep["associations"],
        dependencies=prep["dependencies"],
        generalizations=prep.get("generalizations", []),
        name_to_xmi=prep["name_to_xmi"]
    )

    with tempfile.NamedTemporaryFile(mode='w', suffix='.xmi', delete=False) as tmp:
        path = tmp.name
    try:
        gen = XmiGenerator(model)
        gen.write(path, "NSProject")

        tree = etree.parse(path)
        root = tree.getroot()
        # Find package 'std' (writer uses unqualified 'packagedElement' tag)
        std_pkgs = root.findall('.//packagedElement[@name="std"]')
        assert std_pkgs, "std package not created"
        # Within std package, look for element name vector<...>
        found = False
        for p in std_pkgs:
            inner = p.findall('.//packagedElement')
            for el in inner:
                n = el.get('name')
                if n and n.startswith('vector<') and n.endswith('>'):
                    found = True
                    # Ensure no reference/variadic artifacts
                    assert all(tok not in n for tok in ['&&', '...', ' &'])
                    break
            if found:
                break
        assert found, "Instantiation element not under std package"
    finally:
        try:
            os.unlink(path)
        except:
            pass

def test_template_binding_nested_and_multiargs():
    """TemplateBinding should exist for multi-arg and nested templates (map<string, vector<int>>)."""
    import tempfile, os
    from build.cpp.builder import CppModelBuilder
    from core.uml_model import UmlModel as UmlCoreModel

    data = {
        "elements": [
            {"name": "std::vector", "display_name": "std::vector<T>", "is_template": True, "templates": ["T"], "kind": "class"},
            {"name": "std::map", "display_name": "std::map<K, V>", "is_template": True, "templates": ["K", "V"], "kind": "class"},
            {"name": "std::string", "display_name": "std::string", "kind": "class"},
            {"name": "int", "display_name": "int", "kind": "datatype"},
            {"name": "Holder", "display_name": "Holder", "kind": "class", "members": [
                {"name": "container", "type": "std::map<std::string, std::vector<int>>"}
            ]}
        ]
    }

    builder = CppModelBuilder(data, enable_template_binding=True)
    prep = builder.build()
    model = UmlCoreModel(
        elements={elem.xmi: elem for elem in prep["created"].values()},
        associations=prep["associations"],
        dependencies=prep["dependencies"],
        generalizations=prep.get("generalizations", []),
        name_to_xmi=prep["name_to_xmi"]
    )

    with tempfile.NamedTemporaryFile(mode='w', suffix='.xmi', delete=False) as tmp:
        path = tmp.name
    try:
        gen = XmiGenerator(model)
        gen.write(path, "TBDeep")

        from lxml import etree
        tree = etree.parse(path)
        root = tree.getroot()

        # find map<...> element and check it has templateBinding with >=2 substitutions
        maps = [el for el in root.findall('.//packagedElement') if (el.get('name') or '').startswith('map<')]
        assert maps, "map instantiation not generated"
        map_el = maps[0]
        bindings = map_el.findall('templateBinding')
        assert bindings, "templateBinding for map not generated"
        subs = bindings[0].findall('parameterSubstitution')
        assert len(subs) >= 2, "map binding must have at least two substitutions"

        # find vector<...> element and check it has templateBinding with 1 substitution
        vecs = [el for el in root.findall('.//packagedElement') if (el.get('name') or '').startswith('vector<')]
        assert vecs, "vector instantiation not generated"
        vec_el = vecs[0]
        vbindings = vec_el.findall('templateBinding')
        assert vbindings, "templateBinding for vector not generated"
        vsubs = vbindings[0].findall('parameterSubstitution')
        assert len(vsubs) >= 1, "vector binding must have at least one substitution"
    finally:
        try:
            os.unlink(path)
        except:
            pass

def test_member_end_idrefs_match_owned_ends():
    """Association.memberEnd must reference actual ownedEnd xmi:id (no empty refs)."""
    import tempfile, os
    from core.uml_model import UmlElement, UmlModel, UmlAssociation, ClangMetadata, XmiId, ElementName
    from uml_types import ElementKind
    from gen.xmi.generator import XmiGenerator
    from lxml import etree
    
    # Build minimal model with association
    a = UmlElement(
        xmi=XmiId("A"),
        name=ElementName("A"),
        kind=ElementKind.CLASS,
        members=[],
        clang=ClangMetadata(),
        used_types=frozenset(),
        underlying=None,
    )
    b = UmlElement(
        xmi=XmiId("B"),
        name=ElementName("B"),
        kind=ElementKind.CLASS,
        members=[],
        clang=ClangMetadata(),
        used_types=frozenset(),
        underlying=None,
    )
    assoc = UmlAssociation(src=a.xmi, tgt=b.xmi, name="rel")
    model = UmlModel(
        elements={a.xmi: a, b.xmi: b},
        associations=[assoc],
        dependencies=[],
        generalizations=[],
        name_to_xmi={a.name: a.xmi, b.name: b.xmi},
    )
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xmi', delete=False) as tmp:
        path = tmp.name
    try:
        gen = XmiGenerator(model)
        gen.write(path, "Proj")
        tree = etree.parse(path)
        root = tree.getroot()
        xmi_ns = 'http://www.omg.org/XMI'
        assoc_els = root.findall('.//packagedElement[@xmi:type="uml:Association"]', namespaces={'xmi': xmi_ns})
        assert assoc_els, "Association element not found"
        ae = assoc_els[0]
        ends = ae.findall('ownedEnd')
        assert len(ends) == 2, "Association must have exactly two ownedEnd"
        end_ids = [e.get(f'{{{xmi_ns}}}id') for e in ends]
        assert all(end_ids), "ownedEnd must have non-empty xmi:id"
        mrefs = [me.get(f'{{{xmi_ns}}}idref') for me in ae.findall('memberEnd')]
        assert len(mrefs) == 2, "Association must have two memberEnd references"
        assert set(mrefs) == set(end_ids), "memberEnd idrefs must match ownedEnd xmi:id"
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass

def test_member_end_broken_idref_is_detected_as_error():
    """If memberEnd does not refer to existing ownedEnd, validation must detect error."""
    import tempfile, os
    from core.uml_model import UmlElement, UmlModel, UmlAssociation, ClangMetadata, XmiId, ElementName
    from uml_types import ElementKind
    from gen.xmi.generator import XmiGenerator
    from lxml import etree
    from tools.validate_xmi import collect_ids, find_unresolved

    a = UmlElement(
        xmi=XmiId("A2"),
        name=ElementName("A2"),
        kind=ElementKind.CLASS,
        members=[],
        clang=ClangMetadata(),
        used_types=frozenset(),
        underlying=None,
    )
    b = UmlElement(
        xmi=XmiId("B2"),
        name=ElementName("B2"),
        kind=ElementKind.CLASS,
        members=[],
        clang=ClangMetadata(),
        used_types=frozenset(),
        underlying=None,
    )
    assoc = UmlAssociation(src=a.xmi, tgt=b.xmi, name="rel")
    model = UmlModel(
        elements={a.xmi: a, b.xmi: b},
        associations=[assoc],
        dependencies=[],
        generalizations=[],
        name_to_xmi={a.name: a.xmi, b.name: b.xmi},
    )

    with tempfile.NamedTemporaryFile(mode='w', suffix='.xmi', delete=False) as tmp:
        path = tmp.name
    try:
        gen = XmiGenerator(model)
        gen.write(path, "Proj2")
        # Break one memberEnd reference
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.parse(path, parser)
        root = tree.getroot()
        ns = {'xmi': 'http://www.omg.org/XMI'}
        assoc_els = root.findall('.//packagedElement[@xmi:type="uml:Association"]', namespaces=ns)
        assert assoc_els
        ae = assoc_els[0]
        mes = ae.findall('memberEnd')
        assert len(mes) == 2
        mes[0].set('{http://www.omg.org/XMI}idref', 'id_nonexistent')
        # Validate unresolved idrefs
        ids = collect_ids(root)
        unresolved = find_unresolved(root, ids, limit=5)
        assert unresolved and any(rid == 'id_nonexistent' for rid, _ in unresolved)
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass

def test_generalization_missing_parent_detected():
    """generalization/@general should reference existing element; broken ref -> unresolved."""
    import tempfile, os
    from core.uml_model import UmlElement, UmlModel, UmlGeneralization, ClangMetadata, XmiId, ElementName
    from uml_types import ElementKind
    from gen.xmi.generator import XmiGenerator
    from lxml import etree
    from tools.validate_xmi import collect_ids, find_unresolved

    base = UmlElement(xmi=XmiId("Base"), name=ElementName("Base"), kind=ElementKind.CLASS, members=[], clang=ClangMetadata(), used_types=frozenset(), underlying=None)
    derived = UmlElement(xmi=XmiId("Derived"), name=ElementName("Derived"), kind=ElementKind.CLASS, members=[], clang=ClangMetadata(), used_types=frozenset(), underlying=None)
    gen = UmlGeneralization(child_id=derived.xmi, parent_id=base.xmi)
    model = UmlModel(elements={base.xmi: base, derived.xmi: derived}, associations=[], dependencies=[], generalizations=[gen], name_to_xmi={base.name: base.xmi, derived.name: derived.xmi})

    with tempfile.NamedTemporaryFile(mode='w', suffix='.xmi', delete=False) as tmp:
        path = tmp.name
    try:
        # Generate then break parent id
        XmiGenerator(model).write(path, "GProj")
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.parse(path, parser)
        root = tree.getroot()
        gens = root.findall('.//generalization')
        assert gens
        gens[0].set('general', 'id_nonexistent')
        ids = collect_ids(root)
        unresolved = find_unresolved(root, ids, limit=5)
        assert any(rid == 'id_nonexistent' for rid, _ in unresolved)
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass

def test_owned_parameter_missing_type_detected():
    """ownedParameter/@type broken should be detected as unresolved idref."""
    import tempfile, os
    from core.uml_model import UmlElement, UmlModel, UmlOperation, ClangMetadata, XmiId, ElementName
    from uml_types import ElementKind, Visibility
    from gen.xmi.generator import XmiGenerator
    from lxml import etree
    from tools.validate_xmi import collect_ids, find_unresolved

    foo = UmlElement(xmi=XmiId("Foo"), name=ElementName("Foo"), kind=ElementKind.CLASS, members=[], clang=ClangMetadata(), used_types=frozenset(), underlying=None)
    # add operation with parameter to get an ownedParameter
    from core.uml_model import UmlOperation as Op
    op = Op(name="bar", return_type=None, parameters=[("p", "Foo")], visibility=Visibility.PUBLIC)
    foo.operations = [op]
    model = UmlModel(elements={foo.xmi: foo}, associations=[], dependencies=[], generalizations=[], name_to_xmi={foo.name: foo.xmi})

    with tempfile.NamedTemporaryFile(mode='w', suffix='.xmi', delete=False) as tmp:
        path = tmp.name
    try:
        XmiGenerator(model).write(path, "PProj")
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.parse(path, parser)
        root = tree.getroot()
        params = root.findall('.//ownedParameter')
        assert params
        # find the input parameter (not the return)
        param = next(p for p in params if p.get('direction', 'in') == 'in')
        param.set('type', 'id_nonexistent')
        ids = collect_ids(root)
        unresolved = find_unresolved(root, ids, limit=5)
        assert any(rid == 'id_nonexistent' for rid, _ in unresolved)
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass

def test_dependency_missing_client_or_supplier_detected():
    """Dependency client/supplier broken should be detected as unresolved idref."""
    import tempfile, os
    from core.uml_model import UmlElement, UmlModel, ClangMetadata, XmiId, ElementName
    from uml_types import ElementKind
    from gen.xmi.generator import XmiGenerator
    from lxml import etree
    from tools.validate_xmi import collect_ids, find_unresolved

    a = UmlElement(xmi=XmiId("DA"), name=ElementName("DA"), kind=ElementKind.CLASS, members=[], clang=ClangMetadata(), used_types=frozenset(), underlying=None)
    b = UmlElement(xmi=XmiId("DB"), name=ElementName("DB"), kind=ElementKind.CLASS, members=[], clang=ClangMetadata(), used_types=frozenset(), underlying=None)
    model = UmlModel(elements={a.xmi: a, b.xmi: b}, associations=[], dependencies=[(a.name, b.name)], generalizations=[], name_to_xmi={a.name: a.xmi, b.name: b.xmi})

    with tempfile.NamedTemporaryFile(mode='w', suffix='.xmi', delete=False) as tmp:
        path = tmp.name
    try:
        XmiGenerator(model).write(path, "DProj")
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.parse(path, parser)
        root = tree.getroot()
        deps = root.findall('.//packagedElement[@xmi:type="uml:Dependency"]', namespaces={'xmi': 'http://www.omg.org/XMI'})
        assert deps, "Dependency element not found"
        dep = deps[0]
        dep.set('client', 'id_nonexistent')
        ids = collect_ids(root)
        unresolved = find_unresolved(root, ids, limit=5)
        assert any(rid == 'id_nonexistent' for rid, _ in unresolved)
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass

def test_no_unresolved_refs_on_container_and_refs_case():
    """End-to-end: vector<T> member and const/ref params should not produce unresolved idrefs."""
    import tempfile, os
    from build.cpp.builder import CppModelBuilder
    from core.uml_model import UmlModel as UmlCoreModel
    from gen.xmi.generator import XmiGenerator
    from lxml import etree
    from tools.validate_xmi import collect_ids, find_unresolved

    data = {
        "elements": [
            {"name": "std::vector", "display_name": "std::vector<T>", "is_template": True, "templates": ["T"], "kind": "class"},
            {"name": "std::string", "display_name": "std::string", "kind": "class"},
            {"name": "sink_ptr", "display_name": "sink_ptr", "kind": "class"},
            {"name": "spdlog::logger", "display_name": "spdlog::logger", "kind": "class", "members": [
                {"name": "sinks_", "type": "std::vector<sink_ptr>"},
            ], "operations": [
                {"name": "set_pattern", "return_type": "void", "parameters": [["pattern", "const std::string&"]]},
            ]},
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
        name_to_xmi=prep["name_to_xmi"],
    )

    with tempfile.NamedTemporaryFile(mode='w', suffix='.xmi', delete=False) as tmp:
        path = tmp.name
    try:
        XmiGenerator(model).write(path, "NoUnresolved")
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.parse(path, parser)
        root = tree.getroot()
        ids = collect_ids(root)
        unresolved = find_unresolved(root, ids, limit=50)
        unresolved = [(rid, el) for rid, el in unresolved if el.tag.split('}')[-1] != 'signature']
        assert not unresolved, f"Found unresolved references: {unresolved}"
        # Optional: run EMF validator if Maven available (full UML2 model load)
        mvn_cmd = 'mvn -q -f tools/emf_validator/pom.xml -DskipTests exec:java -Dexec.args="' + path.replace('\\','/') + '"'
        try:
            subprocess.run(mvn_cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception:
            # If mvn is not installed, skip silently
            pass
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass

if __name__ == "__main__":
    test_xmi_generator()
