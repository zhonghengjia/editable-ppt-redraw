#!/usr/bin/env python3
"""Run applicable local audits without certifying unperformed visual review."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_checks(artifact, manifest_path=None, layout_path=None, expected_path=None, profile=None,
               render_evidence=None, node=None):
    artifact = Path(artifact)
    checks = []
    manifest = {}

    def record(name, status, detail=None, required=True):
        checks.append({'check': name, 'status': status, 'required_for_automation': required,
                       'detail': detail})

    def audited(name, action):
        try:
            report = action()
            failed = (report.get('valid') is False or report.get('ok') is False or
                      bool(report.get('issues') or report.get('errors') or report.get('risks')) or
                      bool(report.get('totals', {}).get('blocking_risks')))
            state = 'FAIL' if failed else ('NOT_VERIFIED' if report.get('unverified') else 'PASS')
            record(name, state, report)
            return report
        except Exception as exc:
            # A failed prerequisite stays visible; never silently skip the audit.
            record(name, 'NOT_VERIFIED', {'exception': type(exc).__name__, 'reason': str(exc)})
            return None

    digest = None
    try:
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        record('artifact_read', 'PASS', {'bytes': artifact.stat().st_size, 'sha256': digest})
    except OSError as exc:
        record('artifact_read', 'FAIL', str(exc))

    if manifest_path:
        try:
            manifest_path = Path(manifest_path)
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            if not isinstance(manifest, dict):
                raise ValueError('manifest must be an object')
            audited('manifest', lambda: load('validate-visual-manifest').validate_manifest(manifest))
        except (OSError, ValueError) as exc:
            manifest = {}
            record('manifest', 'FAIL', str(exc))
    selected = profile or manifest.get('execution_profile', 'standard')
    if selected not in ('fast', 'standard', 'dense'):
        record('execution_profile', 'FAIL', 'unsupported execution profile')
    if not manifest_path:
        record('manifest', 'NOT_VERIFIED' if selected == 'dense' else 'NOT_APPLICABLE',
               'dense requires a manifest; other profiles may use working notes', selected == 'dense')

    pptx = artifact.suffix.lower() == '.pptx'
    if pptx:
        audited('editability', lambda: load('audit-pptx-editability').audit_pptx(
            artifact, .8, source_inventory=manifest.get('source_inventory', [])))
    else:
        module = load('audit-editable-source')
        fmt = module.detect_format(artifact, None)
        if fmt in module.SUPPORTED:
            audited('editable_source', lambda: getattr(module, 'audit_' + fmt)(artifact))
            if fmt in ('mermaid', 'graphviz'):
                record('native_parser', 'NOT_VERIFIED', 'lexical inspection is not a native Mermaid/Graphviz parse')
        else:
            record('editable_source', 'NOT_VERIFIED', 'no supported auditor for this file type')

    layouts = None
    if layout_path:
        try:
            paths = load('audit-diagram-grammar').layout_files(Path(layout_path))
            layouts = [json.loads(path.read_text(encoding='utf-8')) for path in paths]
            if not layouts or any(not isinstance(d, dict) for d in layouts):
                raise ValueError('no layout objects')
            if any(d.get('artifact_sha256') != digest for d in layouts):
                record('layout_provenance', 'NOT_VERIFIED', 'each reopened layout must record matching artifact_sha256')
            else:
                record('layout_provenance', 'PASS', {'documents': len(layouts)})
        except (OSError, ValueError) as exc:
            record('layout_read', 'FAIL', str(exc))
            layouts = None

    if 'diagram_grammar' in manifest:
        if layouts is None:
            record('diagram_grammar', 'NOT_VERIFIED', 'reopened layout required')
        else:
            audited('diagram_grammar', lambda: load('audit-diagram-grammar').audit_grammar(manifest, layouts))
    else:
        record('diagram_grammar', 'NOT_APPLICABLE', 'no declared grammar; visual review still checks diagram family', False)

    if 'typography_hierarchy' in manifest:
        module = load('audit-typography-hierarchy')
        if pptx:
            audited('typography', lambda: module.audit_typography(manifest, [{'elements': module.collect_pptx_elements(artifact)[0]}]))
        elif layouts is not None:
            audited('typography', lambda: module.audit_typography(manifest, layouts))
        else:
            record('typography', 'NOT_VERIFIED', 'resolved per-run layout required')
    else:
        record('typography', 'NOT_APPLICABLE', 'no declared hierarchy', False)

    if 'curve_fidelity' in manifest:
        if pptx:
            audited('curves', lambda: load('audit-curve-fidelity').audit_curve_fidelity(manifest, manifest_path, artifact))
        else:
            record('curves', 'NOT_VERIFIED', 'native curve auditor supports PPTX only')
    else:
        record('curves', 'NOT_APPLICABLE', 'no declared curves', False)

    inventory = manifest.get('source_inventory', [])
    sensitive = isinstance(inventory, list) and any(isinstance(item, dict) and item.get('fidelity_sensitive') is True
                                                   for item in inventory)
    if 'regional_fidelity' in manifest or sensitive:
        audited('regional_fidelity', lambda: load('component_fidelity').audit_fidelity(
            artifact, manifest, manifest_path, render_evidence, node))
    else:
        record('regional_fidelity', 'NOT_APPLICABLE', 'no declared regions; manual source inventory remains required', False)

    if 'surface_relations' in manifest or (isinstance(inventory, list) and any(isinstance(i, dict) and i.get('surface_detail') is True for i in inventory)):
        audited('surface_relations', lambda: load('surface_relations').audit(artifact, manifest, manifest_path))
    else:
        record('surface_relations', 'NOT_APPLICABLE', 'no declared surface details; manual source coverage still required', False)

    if 'text_clearance' in manifest:
        audited('text_clearance', lambda: load('text_clearance').audit(artifact, manifest))
    elif pptx and selected == 'dense' and isinstance(inventory, list) and any(isinstance(i,dict) and i.get('role') == 'text' for i in inventory):
        record('text_clearance', 'NOT_VERIFIED', 'dense text-bearing PPTX requires label/obstacle clearance contract')
    else:
        record('text_clearance', 'NOT_APPLICABLE', 'no declared clearance; visible text still requires render review', False)

    native = None
    if pptx:
        def connections():
            expected = json.loads(Path(expected_path).read_text(encoding='utf-8')) if expected_path else None
            return load('audit-pptx-connections').audit(artifact, bool(expected_path), expected)
        native = audited('native_connections', connections)
        if native and native.get('geometry_unverified'):
            record('native_connection_geometry', 'NOT_VERIFIED', native['geometry_unverified'])
    elif expected_path:
        record('native_connections', 'NOT_VERIFIED', 'expected-connections applies to PPTX only')
    grammar = manifest.get('diagram_grammar')
    routing = grammar.get('routing') if isinstance(grammar, dict) else None
    if routing == 'orthogonal' and not (native and native.get('geometry_complete')):
        if layouts is None:
            record('orthogonal_routes', 'NOT_VERIFIED', 'reopened routed layout required')
        else:
            def routes():
                module = load('audit-orthogonal-flow-lines')
                issues, matches = [], 0
                for path in module.layout_files(Path(layout_path)):
                    count, found, _, _, _ = module.audit_file(path, re.compile(module.DEFAULT_INCLUDE), None, .05, 1.)
                    matches += count
                    issues.extend(found)
                return {'valid': matches > 0 and not issues, 'issues': issues, 'matches': matches}
            audited('orthogonal_routes', routes)

    manual = ['full composition and detail comparison', 'rendered font/glyph bounds', 'missing visible items and icons', 'host-surface attachment, edge termination and visible occlusion for each declared relation']
    if manifest.get('semantic_constraints') or manifest.get('negative_constraints'):
        manual.append('manifest semantic/negative constraints not implemented by specialized auditors')
    record('manual_visual_review', 'NOT_VERIFIED', manual, False)
    automation_passed = all(c['status'] in ('PASS', 'NOT_APPLICABLE') for c in checks if c['required_for_automation'])
    return {'schema_version': 1, 'artifact': str(artifact.resolve()), 'artifact_sha256': digest,
            'execution_profile': selected, 'checks': checks, 'automation_passed': automation_passed,
            'delivery_ready': None,
            'claim_boundary': 'Only declared, applicable machine checks. Delivery requires separate source-grounded visual review; no visual sign-off is inferred.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifact', type=Path)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--layout', type=Path)
    parser.add_argument('--expected-connections', type=Path)
    parser.add_argument('--profile', choices=('fast', 'standard', 'dense'))
    parser.add_argument('--render-evidence', type=Path)
    parser.add_argument('--node', help='Existing Node.js runtime for local component checks')
    parser.add_argument('--json', type=Path)
    parser.add_argument('--fail-on-risk', action='store_true')
    args = parser.parse_args()
    report = run_checks(args.artifact, args.manifest, args.layout, args.expected_connections, args.profile,
                        args.render_evidence, args.node)
    if args.json:
        if args.json.resolve() in {p.resolve() for p in (args.artifact, args.manifest, args.layout, args.expected_connections, args.render_evidence) if p}:
            parser.error('report must not overwrite an input')
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    for check in report['checks']:
        print(f"{check['check']}: {check['status']}")
    print(f"automation_passed={report['automation_passed']}; visual review remains separate")
    return int(args.fail_on_risk and not report['automation_passed'])


if __name__ == '__main__':
    sys.exit(main())
