#!/usr/bin/env python3
"""
Unit tests for association generation rules:
- Field-based association: one class-owned end, other may fallback to ownedEnd
- Non-field association: both ends are ownedEnd with stereotype annotation
- Association naming: SrcFQN::src_prop->TgtFQN::tgt_prop
"""

from __future__ import annotations

import os
import tempfile
from lxml import etree

from core.uml_model import (
    UmlModel,
    UmlElement,
    UmlMember,
    ClangMetadata,
    UmlAssociation,
    ElementKind,
    ElementName,
    XmiId,
)
from gen.xmi.generator import XmiGenerator
from utils.ids import stable_id


def _mk_class(xmi: str, qname: str, members: list[tuple[str, str]] = None) -> UmlElement:
    if members is None:
        members = []
    return UmlElement(
        xmi=XmiId(xmi),
        name=ElementName(qname),
        kind=ElementKind.CLASS,
        members=[UmlMember(name=n, type_repr=t) for n, t in members],
        clang=ClangMetadata(qualified_name=qname, display_name=qname.split('::')[-1], name=qname.split('::')[-1]),
        used_types=frozenset(),
    )


def _parse(uml_path: str):
    parser = etree.XMLParser(remove_blank_text=True)
    return etree.parse(uml_path, parser).getroot()


def test_field_based_association_one_class_end_and_owned_end():
    # A has field b:B; B has no back field
    a = _mk_class("id_A", "ns::A", members=[("b", "ns::B")])
    b = _mk_class("id_B", "ns::B")
    name_to_xmi = {a.name: a.xmi, b.name: b.xmi}
    elements = {a.xmi: a, b.xmi: b}

    # Association produced by builder would carry name=m.name -> "b"
    assoc = UmlAssociation(src=a.xmi, tgt=b.xmi, name="b")

    model = UmlModel(
        elements=elements,
        associations=[assoc],
        dependencies=[],
        generalizations=[],
        name_to_xmi=name_to_xmi,
    )

    with tempfile.TemporaryDirectory() as td:
        out_uml = os.path.join(td, "m.uml")
        XmiGenerator(model).write(out_uml, "test", pretty=True)
        root = _parse(out_uml)
        XMI = 'http://www.omg.org/XMI'
        ids = {el.get(f'{{{XMI}}}id'): el for el in root.xpath('//*[@xmi:id]', namespaces={'xmi': XMI})}
        # Find association
        assocs = [el for el in root.xpath('//*[@xmi:type]', namespaces={'xmi': XMI}) if (el.get(f'{{{XMI}}}type') or '').endswith('Association')]
        assert len(assocs) == 1
        ael = assocs[0]
        # memberEnd refers to class property id on src side; second end exists (class or ownedEnd)
        mem_ids = [me.get(f'{{{XMI}}}idref') for me in ael if isinstance(me.tag, str) and me.tag.endswith('memberEnd')]
        assert len(mem_ids) == 2
        prop_src_id = stable_id("id_A:attr:b")
        assert prop_src_id in mem_ids
        # The class ownedAttribute must have association link to the association id
        assoc_id = ael.get(f'{{{XMI}}}id')
        owned_attr = ids.get(prop_src_id)
        assert owned_attr is not None
        assert owned_attr.get('association') == assoc_id


def test_non_field_association_both_owned_ends_with_annotation():
    # No members on either side; association explicitly added
    a = _mk_class("id_A2", "pkg::A2")
    b = _mk_class("id_B2", "pkg::B2")
    name_to_xmi = {a.name: a.xmi, b.name: b.xmi}
    elements = {a.xmi: a, b.xmi: b}
    assoc = UmlAssociation(src=a.xmi, tgt=b.xmi, name="rel")
    model = UmlModel(
        elements=elements,
        associations=[assoc],
        dependencies=[],
        generalizations=[],
        name_to_xmi=name_to_xmi,
    )
    with tempfile.TemporaryDirectory() as td:
        out_uml = os.path.join(td, "m.uml")
        XmiGenerator(model).write(out_uml, "test", pretty=True)
        root = _parse(out_uml)
        XMI = 'http://www.omg.org/XMI'
        # Find association and ensure it has ownedEnd children and eAnnotations stereotype
        assocs = [el for el in root.xpath('//*[@xmi:type]', namespaces={'xmi': XMI}) if (el.get(f'{{{XMI}}}type') or '').endswith('Association')]
        assert len(assocs) == 1
        ael = assocs[0]
        owned = [ch for ch in ael if isinstance(ch.tag, str) and ch.tag.endswith('ownedEnd')]
        assert len(owned) == 2
        # both owned ends should have type attributes
        assert all(ch.get('type') in ("id_A2", "id_B2") for ch in owned)
        # annotation presence
        anns = [ch for ch in ael if isinstance(ch.tag, str) and ch.tag.endswith('eAnnotations')]
        assert anns, "Expected eAnnotations on ownedEnd association"
        dets = [d for an in anns for d in an if isinstance(d.tag, str) and d.tag.endswith('details')]
        kv = {d.get('key'): d.get('value') for d in dets}
        assert kv.get('stereotype') == 'OwnedEnd'
        assert kv.get('end1') in ('owned', 'class')
        assert kv.get('end2') in ('owned', 'class')


def test_association_name_format():
    a = _mk_class("id_A3", "n1::A3", members=[("x", "n2::B3")])
    b = _mk_class("id_B3", "n2::B3")
    name_to_xmi = {a.name: a.xmi, b.name: b.xmi}
    elements = {a.xmi: a, b.xmi: b}
    assoc = UmlAssociation(src=a.xmi, tgt=b.xmi, name="x")
    model = UmlModel(
        elements=elements,
        associations=[assoc],
        dependencies=[],
        generalizations=[],
        name_to_xmi=name_to_xmi,
    )
    with tempfile.TemporaryDirectory() as td:
        out_uml = os.path.join(td, "m.uml")
        XmiGenerator(model).write(out_uml, "test", pretty=True)
        root = _parse(out_uml)
        XMI = 'http://www.omg.org/XMI'
        assocs = [el for el in root.xpath('//*[@xmi:type]', namespaces={'xmi': XMI}) if (el.get(f'{{{XMI}}}type') or '').endswith('Association')]
        assert len(assocs) == 1
        ael = assocs[0]
        assert ael.get('name') == 'n1::A3::x->n2::B3'


def test_bidirectional_field_based_both_class_ends_with_opposite():
    a = _mk_class("id_A4", "n::A4", members=[("b", "n::B4")])
    b = _mk_class("id_B4", "n::B4", members=[("b", "n::A4")])  # same member name to match both ends
    name_to_xmi = {a.name: a.xmi, b.name: b.xmi}
    elements = {a.xmi: a, b.xmi: b}
    assoc = UmlAssociation(src=a.xmi, tgt=b.xmi, name="b")
    model = UmlModel(elements=elements, associations=[assoc], dependencies=[], generalizations=[], name_to_xmi=name_to_xmi)
    with tempfile.TemporaryDirectory() as td:
        out_uml = os.path.join(td, "m.uml")
        XmiGenerator(model).write(out_uml, "test", pretty=True)
        root = _parse(out_uml)
        XMI = 'http://www.omg.org/XMI'
        ids = {el.get(f'{{{XMI}}}id'): el for el in root.xpath('//*[@xmi:id]', namespaces={'xmi': XMI})}
        assocs = [el for el in root.xpath('//*[@xmi:type]', namespaces={'xmi': XMI}) if (el.get(f'{{{XMI}}}type') or '').endswith('Association')]
        assert len(assocs) == 1
        ael = assocs[0]
        mem_ids = [me.get(f'{{{XMI}}}idref') for me in ael if isinstance(me.tag, str) and me.tag.endswith('memberEnd')]
        assert len(mem_ids) == 2
        a_prop = stable_id("id_A4:attr:b")
        b_prop = stable_id("id_B4:attr:b")
        assert set(mem_ids) == {a_prop, b_prop}
        # opposites on both class-owned attributes
        assert ids[a_prop].get('opposite') == b_prop
        assert ids[b_prop].get('opposite') == a_prop


def test_mismatched_names_one_owned_end_annotation_flags():
    a = _mk_class("id_A5", "n::A5", members=[("b", "n::B5")])
    b = _mk_class("id_B5", "n::B5", members=[("a", "n::A5")])  # mismatched field name
    name_to_xmi = {a.name: a.xmi, b.name: b.xmi}
    elements = {a.xmi: a, b.xmi: b}
    assoc = UmlAssociation(src=a.xmi, tgt=b.xmi, name="b")
    model = UmlModel(elements=elements, associations=[assoc], dependencies=[], generalizations=[], name_to_xmi=name_to_xmi)
    with tempfile.TemporaryDirectory() as td:
        out_uml = os.path.join(td, "m.uml")
        XmiGenerator(model).write(out_uml, "test", pretty=True)
        root = _parse(out_uml)
        XMI = 'http://www.omg.org/XMI'
        assocs = [el for el in root.xpath('//*[@xmi:type]', namespaces={'xmi': XMI}) if (el.get(f'{{{XMI}}}type') or '').endswith('Association')]
        assert len(assocs) == 1
        ael = assocs[0]
        # annotation present and indicates one class end and one owned end
        anns = [ch for ch in ael if isinstance(ch.tag, str) and ch.tag.endswith('eAnnotations')]
        assert anns
        dets = {d.get('key'): d.get('value') for an in anns for d in an if isinstance(d.tag, str) and d.tag.endswith('details')}
        assert dets.get('stereotype') == 'OwnedEnd'
        assert dets.get('end1') == 'class'  # src has class field 'b'
        assert dets.get('end2') in ('owned', 'class')  # likely 'owned'


def test_link_object_both_owned():
    a = _mk_class("id_A6", "n::A6")
    b = _mk_class("id_B6", "n::B6")
    link = _mk_class("id_L6", "n::Link6", members=[("a", "n::A6"), ("b", "n::B6")])
    name_to_xmi = {a.name: a.xmi, b.name: b.xmi, link.name: link.xmi}
    elements = {a.xmi: a, b.xmi: b, link.xmi: link}
    assoc = UmlAssociation(src=a.xmi, tgt=b.xmi, name="rel")
    model = UmlModel(elements=elements, associations=[assoc], dependencies=[], generalizations=[], name_to_xmi=name_to_xmi)
    with tempfile.TemporaryDirectory() as td:
        out_uml = os.path.join(td, "m.uml")
        XmiGenerator(model).write(out_uml, "test", pretty=True)
        root = _parse(out_uml)
        XMI = 'http://www.omg.org/XMI'
        assocs = [el for el in root.xpath('//*[@xmi:type]', namespaces={'xmi': XMI}) if (el.get(f'{{{XMI}}}type') or '').endswith('Association')]
        assert len(assocs) == 1
        ael = assocs[0]
        owned = [ch for ch in ael if isinstance(ch.tag, str) and ch.tag.endswith('ownedEnd')]
        assert len(owned) == 2


def test_manager_relation_both_owned():
    a = _mk_class("id_A7", "n::User")
    b = _mk_class("id_B7", "n::Group")
    registry = _mk_class("id_R7", "n::Registry")
    name_to_xmi = {a.name: a.xmi, b.name: b.xmi, registry.name: registry.xmi}
    elements = {a.xmi: a, b.xmi: b, registry.xmi: registry}
    assoc = UmlAssociation(src=a.xmi, tgt=b.xmi, name="groups")
    model = UmlModel(elements=elements, associations=[assoc], dependencies=[], generalizations=[], name_to_xmi=name_to_xmi)
    with tempfile.TemporaryDirectory() as td:
        out_uml = os.path.join(td, "m.uml")
        XmiGenerator(model).write(out_uml, "test", pretty=True)
        root = _parse(out_uml)
        XMI = 'http://www.omg.org/XMI'
        assocs = [el for el in root.xpath('//*[@xmi:type]', namespaces={'xmi': XMI}) if (el.get(f'{{{XMI}}}type') or '').endswith('Association')]
        assert len(assocs) == 1
        ael = assocs[0]
        owned = [ch for ch in ael if isinstance(ch.tag, str) and ch.tag.endswith('ownedEnd')]
        assert len(owned) == 2


def test_getter_only_non_field_both_owned():
    a = _mk_class("id_A8", "n::A8")
    b = _mk_class("id_B8", "n::B8")
    name_to_xmi = {a.name: a.xmi, b.name: b.xmi}
    elements = {a.xmi: a, b.xmi: b}
    assoc = UmlAssociation(src=a.xmi, tgt=b.xmi, name="getB")
    model = UmlModel(elements=elements, associations=[assoc], dependencies=[], generalizations=[], name_to_xmi=name_to_xmi)
    with tempfile.TemporaryDirectory() as td:
        out_uml = os.path.join(td, "m.uml")
        XmiGenerator(model).write(out_uml, "test", pretty=True)
        root = _parse(out_uml)
        XMI = 'http://www.omg.org/XMI'
        assocs = [el for el in root.xpath('//*[@xmi:type]', namespaces={'xmi': XMI}) if (el.get(f'{{{XMI}}}type') or '').endswith('Association')]
        assert len(assocs) == 1
        ael = assocs[0]
        owned = [ch for ch in ael if isinstance(ch.tag, str) and ch.tag.endswith('ownedEnd')]
        assert len(owned) == 2


