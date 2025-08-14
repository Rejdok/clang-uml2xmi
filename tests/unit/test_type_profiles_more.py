#!/usr/bin/env python3
import os
from typing import Any, Dict

from build.pipeline import BuildPipeline
from app.config import GeneratorConfig
from uml_types import AggregationType


def _std_profile_path() -> str:
    here = os.path.dirname(__file__)
    return os.path.abspath(os.path.join(here, '..', 'types_profiles', 'std.json'))


def _build_with_profiles(data: Dict[str, Any], enable_template_binding: bool = True):
    cfg = GeneratorConfig()
    cfg.enable_template_binding = enable_template_binding
    cfg.types_profiles = [_std_profile_path()]
    pipe = BuildPipeline(config=cfg)
    return pipe.build(data)


def test_map_values_end_label_non_instantiated():
    data = {
        "elements": [
            {"name": "int", "kind": "datatype"},
            {"name": "std::string", "kind": "class"},
            {"name": "Holder", "kind": "class", "members": [
                {"name": "m", "type": "std::map<std::string, int>"}
            ]}
        ]
    }
    artifacts = _build_with_profiles(data, enable_template_binding=False)
    assoc_names = [a.name for a in artifacts.model.associations]
    # expect link to value with label 'values'
    assert 'values' in assoc_names


def test_map_values_end_label_instantiated():
    data = {
        "elements": [
            {"name": "int", "kind": "datatype"},
            {"name": "std::string", "kind": "class"},
            {"name": "Holder", "kind": "class", "members": [
                {"name": "m", "type": "std::map<std::string, int>"}
            ]}
        ]
    }
    artifacts = _build_with_profiles(data, enable_template_binding=True)
    assoc_names = [a.name for a in artifacts.model.associations]
    assert 'values' in assoc_names


def test_unique_ptr_sets_composite_aggregation():
    data = {
        "elements": [
            {"name": "int", "kind": "datatype"},
            {"name": "Owner", "kind": "class", "members": [
                {"name": "up", "type": "std::unique_ptr<int>"}
            ]}
        ]
    }
    artifacts = _build_with_profiles(data, enable_template_binding=False)
    # find association pointing to int and check aggregation
    int_xmi = next(xmi for name, xmi in artifacts.model.name_to_xmi.items() if str(name) == 'int')
    assoc = next(a for a in artifacts.model.associations if a.tgt == int_xmi)
    assert assoc.aggregation == AggregationType.COMPOSITE


def test_pmr_vector_alias_as_container():
    data = {
        "elements": [
            {"name": "int", "kind": "datatype"},
            {"name": "Owner", "kind": "class", "members": [
                {"name": "v", "type": "std::pmr::vector<int>"}
            ]}
        ]
    }
    artifacts = _build_with_profiles(data, enable_template_binding=False)
    # multiplicity should be '*'
    mults = [a.multiplicity for a in artifacts.model.associations if a.name in ('v','v_arg0','items')]
    assert '*' in mults


def test_reference_wrapper_shared_aggregation():
    data = {
        "elements": [
            {"name": "int", "kind": "datatype"},
            {"name": "Owner", "kind": "class", "members": [
                {"name": "ref", "type": "std::reference_wrapper<int>"}
            ]}
        ]
    }
    artifacts = _build_with_profiles(data, enable_template_binding=False)
    int_xmi = next(xmi for name, xmi in artifacts.model.name_to_xmi.items() if str(name) == 'int')
    assoc = next(a for a in artifacts.model.associations if a.tgt == int_xmi)
    assert assoc.aggregation == AggregationType.SHARED


