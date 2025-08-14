#!/usr/bin/env python3
import os
from typing import Any, Dict

from build.pipeline import BuildPipeline
from app.config import GeneratorConfig


def _std_profile_path() -> str:
    here = os.path.dirname(__file__)
    stdp = os.path.abspath(os.path.join(here, '..', 'types_profiles', 'std.json'))
    return stdp


def _build_with_profiles(data: Dict[str, Any], enable_template_binding: bool = True):
    cfg = GeneratorConfig()
    cfg.enable_template_binding = enable_template_binding
    cfg.types_profiles = [ _std_profile_path() ]
    pipe = BuildPipeline(config=cfg)
    return pipe.build(data)


def test_pair_end_names_instantiated():
    data = {
        "elements": [
            {"name": "int", "display_name": "int", "kind": "datatype"},
            {"name": "std::string", "display_name": "std::string", "kind": "class"},
            {"name": "Holder", "display_name": "Holder", "kind": "class", "members": [
                {"name": "p", "type": "std::pair<int, std::string>"}
            ]}
        ]
    }
    artifacts = _build_with_profiles(data, enable_template_binding=True)
    assoc_names = [a.name for a in artifacts.model.associations]
    assert "first" in assoc_names
    assert "second" in assoc_names


def test_tuple_end_names_non_instantiated():
    data = {
        "elements": [
            {"name": "int", "display_name": "int", "kind": "datatype"},
            {"name": "double", "display_name": "double", "kind": "datatype"},
            {"name": "std::string", "display_name": "std::string", "kind": "class"},
            {"name": "Holder", "display_name": "Holder", "kind": "class", "members": [
                {"name": "t", "type": "std::tuple<int, std::string, double>"}
            ]}
        ]
    }
    artifacts = _build_with_profiles(data, enable_template_binding=False)
    assoc_names = [a.name for a in artifacts.model.associations]
    assert any(n in assoc_names for n in ["e0", "e1", "e2"])  # at least some labeled
    assert "e0" in assoc_names and "e1" in assoc_names and "e2" in assoc_names


def test_optional_multiplicity_value_end():
    data = {
        "elements": [
            {"name": "int", "display_name": "int", "kind": "datatype"},
            {"name": "Holder", "display_name": "Holder", "kind": "class", "members": [
                {"name": "opt", "type": "std::optional<int>"}
            ]}
        ]
    }
    artifacts = _build_with_profiles(data, enable_template_binding=False)
    mult_by_name = {a.name: a.multiplicity for a in artifacts.model.associations}
    assert mult_by_name.get("value") == "0..1"


