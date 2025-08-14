#!/usr/bin/env python3
"""
Integration test: run cpp2uml on spdlog classes.json, then validate outputs.

Skips if the input JSON file is not present on this machine.
"""
from __future__ import annotations

import os
import sys
import tempfile
import shutil
import subprocess
from lxml import etree
import glob


def _find_spdlog_json() -> str | None:
    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, '..'))
    # Highest priority: environment variable override
    env_path = os.environ.get('SPDLOG_CLASSES_JSON')
    if env_path and os.path.isfile(env_path):
        return os.path.abspath(env_path)
    candidates = [
        os.path.abspath(os.path.join(repo_root, 'tests', 'assets', 'spdlog', 'classes.json')),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


def _find_maven_exe() -> str | None:
    # Prefer PATH lookup first
    mvn = shutil.which('mvn') or shutil.which('mvn.cmd')
    if mvn:
        return mvn
    # Check common env vars
    for var in ('MAVEN_HOME', 'M2_HOME'):
        home = os.environ.get(var)
        if home and os.path.isdir(home):
            candidate_cmd = os.path.join(home, 'bin', 'mvn.cmd')
            candidate_sh = os.path.join(home, 'bin', 'mvn')
            if os.path.isfile(candidate_cmd):
                return candidate_cmd
            if os.path.isfile(candidate_sh):
                return candidate_sh
    # Heuristics for common Windows install locations
    candidates = []
    candidates += glob.glob(r'C:\\Program Files\\Apache\\maven*\\bin\\mvn.cmd')
    candidates += glob.glob(r'C:\\Program Files\\Apache\\apache-maven-*\\bin\\mvn.cmd')
    candidates += glob.glob(r'C:\\Program Files\\Apache\\Maven\\apache-maven-*\\bin\\mvn.cmd')
    candidates += [os.path.expanduser(r'~\\scoop\\apps\\maven\\current\\bin\\mvn.cmd')]
    candidates += [r'C:\\ProgramData\\chocolatey\\bin\\mvn.exe', r'C:\\ProgramData\\chocolatey\\bin\\mvn.cmd']
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


def test_spdlog_integration_generate_and_validate():
    src = _find_spdlog_json()
    if not src:
        import pytest
        pytest.skip("spdlog classes.json not found on this machine; skipping integration test")

    with tempfile.TemporaryDirectory() as td:
        inp = os.path.join(td, 'classes.json')
        out_uml = os.path.join(td, 'modelcpp.uml')
        out_notation = os.path.join(td, 'modelcpp.notation')
        shutil.copyfile(src, inp)

        # Run generator CLI
        cmd = [sys.executable, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'cpp2uml.py')), inp, out_uml, out_notation, '--pretty']
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert res.returncode == 0, f"cpp2uml failed: rc={res.returncode}, out={res.stdout}, err={res.stderr}"
        assert os.path.isfile(out_uml) and os.path.getsize(out_uml) > 0
        assert os.path.isfile(out_notation) and os.path.getsize(out_notation) > 0

        # EMF/UML2 validation via Maven if available (sole validation)
        mvn = _find_maven_exe()
        if not mvn:
            import pytest
            pytest.skip("Maven (mvn) not found; skipping EMF validation")
        uml_posix = out_uml.replace('\\', '/')
        # Run Maven without shell to avoid arg parsing issues on Windows
        mvn_cmd = [
            mvn,
            '-q',
            '-f', 'tools/emf_validator/pom.xml',
            '-DskipTests',
            'exec:java',
            f'-Dexec.args={uml_posix}',
        ]
        res = subprocess.run(mvn_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            # Extra diagnostics: unresolved memberEnd/member report
            try:
                parser = etree.XMLParser(remove_blank_text=True)
                root = etree.parse(out_uml, parser).getroot()
                XMI = 'http://www.omg.org/XMI'
                # Build id index
                ids = {el.get(f'{{{XMI}}}id'): el for el in root.xpath('//*[@xmi:id]', namespaces={'xmi': XMI})}
                # Find associations robustly (independent of UML namespace prefix)
                def is_assoc(el: etree._Element) -> bool:
                    if not el.tag.endswith('packagedElement'):
                        return False
                    t = el.get(f'{{{XMI}}}type') or ''
                    return t.endswith('Association')
                assocs = [el for el in root.iter() if is_assoc(el)]
                lines: list[str] = []
                count = 0
                for a in assocs:
                    aid = a.get(f'{{{XMI}}}id')
                    aname = a.get('name') or ''
                    # memberEnd nodes regardless of prefix
                    mem_nodes = [me for me in a if isinstance(me.tag, str) and me.tag.endswith('memberEnd')]
                    mem = [(me.get(f'{{{XMI}}}idref') or '') for me in mem_nodes]
                    missing = [rid for rid in mem if rid and rid not in ids]
                    too_few = len(mem) < 2
                    if missing:
                        owned = any(isinstance(ch.tag, str) and ch.tag.endswith('eAnnotations') and ch.get('source') == 'cpp' for ch in a)
                        lines.append(f"assoc id={aid} name='{aname}' missing={len(missing)} ownedAnn={owned}")
                        for rid in mem[:4]:
                            suffix = ' (MISSING)' if rid in missing else ''
                            lines.append(f"  memberEnd -> {rid}{suffix}")
                        count += 1
                    elif too_few:
                        lines.append(f"assoc id={aid} name='{aname}' memberEnd_count={len(mem)} (expected 2)")
                        for rid in mem[:4]:
                            lines.append(f"  memberEnd -> {rid}")
                        count += 1
                        if count >= 30:
                            break
                report = "\n".join(lines) if lines else "(no associations with missing memberEnd found by test parser)"
            except Exception:
                report = "(failed to build unresolved memberEnd report)"
            # Print report first, then fail briefly to keep it visible
            print("==== Unresolved associations (top) ====")
            print(report)
            print("==== Validator stdout ====")
            try:
                print(res.stdout)
            except Exception:
                print("<no stdout>")
            print("==== Validator stderr ====")
            try:
                print(res.stderr)
            except Exception:
                print("<no stderr>")
            import pytest as _pytest
            _pytest.fail("EMF validator failed; see unresolved associations above", pytrace=False)


