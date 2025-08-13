#!/usr/bin/env python3
"""
CLI entrypoint for uml2papyrus.

Usage:
  python -m app.cli <clang-uml.json> <out.uml> <out.notation> [flags]

Flags:
  --strict
  --no-template-binding
  --types-profile PATH   (repeatable)
  --no-std-profile
  --list-phases
  --pretty
"""
from __future__ import annotations

import sys
import os
from typing import Any

from app.config import GeneratorConfig, DEFAULT_CONFIG
import logging
from utils.logging_config import configure_logging


def load_json(path: str) -> Any:
    # Prefer orjson if available; fall back to stdlib json
    try:
        import orjson  # type: ignore
    except ImportError:
        orjson = None  # type: ignore
    if orjson is not None:
        with open(path, "rb") as f:
            return orjson.loads(f.read())
    import json
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_cli(argv: list[str], config: GeneratorConfig) -> tuple[str, str, str, GeneratorConfig]:
    if len(argv) < 4:
        print("Usage: python -m app.cli <clang-uml.json> <out.uml> <out.notation> [--strict] [--no-template-binding] [--types-profile PATH] [--no-std-profile] [--list-phases] [--pretty]")
        raise SystemExit(1)
    inp, out_uml, out_notation = argv[1:4]
    i = 4
    while i < len(argv):
        arg = argv[i]
        if arg == "--strict":
            config.strict_validation = True
            i += 1
            continue
        if arg == "--no-template-binding":
            config.enable_template_binding = False
            i += 1
            continue
        if arg == "--types-profile" and i + 1 < len(argv):
            config.types_profiles = (config.types_profiles or []) + [argv[i + 1]]
            i += 2
            continue
        if arg == "--no-std-profile":
            # handled later during pipeline setup
            i += 1
            continue
        if arg == "--list-phases":
            config.project_name = config.project_name  # noop
            i += 1
            continue
        if arg == "--pretty":
            config.pretty_print = True
            i += 1
            continue
        i += 1
    return inp, out_uml, out_notation, config


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv
    try:
        configure_logging()
    except Exception as e:
        # Fallback to a basic configuration and continue
        logging.basicConfig(level=logging.INFO)
        logging.getLogger(__name__).warning("Logging configuration failed: %s", e)

    try:
        inp, out_uml, out_notation, cfg = parse_cli(argv, DEFAULT_CONFIG)
    except SystemExit as e:
        return int(str(e)) if str(e).isdigit() else 1

    # List phases if requested
    if "--list-phases" in argv:
        j = load_json(inp)
        from build.cpp.builder import CppModelBuilder as PhaseBuilder
        pb = PhaseBuilder(j, enable_template_binding=cfg.enable_template_binding)
        try:
            phases = pb.get_phases()  # type: ignore[attr-defined]
        except AttributeError:
            phases = []
        except Exception as e:
            print(f"Failed to list phases: {e}")
            return 1
        if phases:
            print("Phases:")
            for i, ph in enumerate(phases, 1):
                print(f"  {i}. {ph}")
        else:
            print("Phases information not available for this builder")
        return 0

    # Default std profile unless disabled
    if cfg.types_profiles is None:
        cfg.types_profiles = []
    if "--no-std-profile" not in argv:
        std_profile_path = os.path.join(os.path.dirname(__file__), '..', 'types_profiles', 'std.json')
        std_profile_path = os.path.abspath(std_profile_path)
        if os.path.isfile(std_profile_path) and std_profile_path not in cfg.types_profiles:
            cfg.types_profiles.append(std_profile_path)

    # Build + generate
    from build.pipeline import BuildPipeline
    pipe = BuildPipeline(config=cfg)
    j = load_json(inp)
    artifacts = pipe.build(j)
    pipe.generate(artifacts, out_uml, out_notation)
    print("Written", out_uml, "and", out_notation)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


