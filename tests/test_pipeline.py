#!/usr/bin/env python3
import tempfile
import os

from build.pipeline import BuildPipeline


def test_build_pipeline_generates_files():
    j = {
        "project_name": "PipeProject",
        "elements": [
            {
                "name": "std::vector",
                "display_name": "std::vector<T>",
                "is_template": True,
                "kind": "class",
                "templates": ["T"],
            },
            {
                "name": "int",
                "display_name": "int",
                "kind": "datatype",
            },
            {
                "name": "MyNS::Holder",
                "qualified_name": "MyNS::Holder",
                "display_name": "MyNS::Holder",
                "kind": "class",
                "members": [
                    {"name": "items", "type": "std::vector<int>", "visibility": "private"}
                ],
            },
        ],
    }

    pipe = BuildPipeline()
    artifacts = pipe.build(j)
    assert artifacts.project_name == "PipeProject"
    assert artifacts.model is not None
    # graph should be available
    assert getattr(artifacts, "graph", None) is not None

    fu = tempfile.NamedTemporaryFile(mode="w", suffix=".uml", delete=False)
    fn = tempfile.NamedTemporaryFile(mode="w", suffix=".notation", delete=False)
    out_uml = fu.name
    out_notation = fn.name
    fu.close()
    fn.close()
    try:
        pipe.generate(artifacts, out_uml, out_notation)
        assert os.path.exists(out_uml)
        assert os.path.getsize(out_uml) > 0
        # basic check for packages
        content = open(out_uml, "r", encoding="utf-8").read()
        assert "uml:Package" in content
        assert "name=\"MyNS\"" in content
    finally:
        for p in (out_uml, out_notation):
            try:
                os.unlink(p)
            except Exception:
                pass


