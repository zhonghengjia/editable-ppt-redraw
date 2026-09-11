"""Optional local Windows coverage geometry for an explicitly shared fill/stroke.

Uses installed WPF, not raster tracing or an inferred outline. Its approximation
tolerance is caller-declared in the same units as the supplied source path.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from native_paint import scalar
from vendor.svg_paths.drawingml_paths import (parse_svg_path, svg_path_to_absolute,
                                             normalize_path_commands, path_bounds)


def fill_stroke_union(d, width, *, tolerance, powershell=None):
    """Return native coverage for a filled closed path plus centered round stroke.

    Use only when fill and stroke have the SAME opaque paint before a shared
    mask/opacity. Different colors, dashes, open paths, clipping and arbitrary
    stroke alignment require another qualified operation, not this union.
    """
    if not isinstance(d, str) or not d.strip() or len(d) > 100000:
        raise ValueError('bounded source path required')
    width = scalar(width, 'stroke width', 1e-6, 1e6)
    tolerance = scalar(tolerance, 'absolute coverage tolerance', 1e-6, 1)
    commands = normalize_path_commands(svg_path_to_absolute(parse_svg_path(d)))
    if len(commands) > 5000:
        raise ValueError('coverage input exceeds 5000 commands')
    closed = True
    for c in commands:
        if c.cmd == 'M':
            if not closed:
                raise ValueError('all coverage subpaths must be explicitly closed')
            closed = False
        elif c.cmd == 'Z':
            closed = True
        for value in c.args:
            scalar(value, 'coverage coordinate', -1e6, 1e6)
    if not closed:
        raise ValueError('all coverage subpaths must be explicitly closed')
    executable = powershell or shutil.which('powershell.exe')
    if not executable:
        raise RuntimeError('WPF coverage requires installed Windows PowerShell; no fallback performed')
    path = ' '.join(c.cmd+' '.join(str(v) for v in c.args) for c in commands)
    recipe = dict(d=path, width=width, tolerance=tolerance)
    with tempfile.TemporaryDirectory(prefix='native-coverage-') as folder:
        src, dst = Path(folder)/'input.json', Path(folder)/'output.json'
        src.write_text(json.dumps(recipe, allow_nan=False), encoding='utf8')
        result = subprocess.run([str(executable), '-NoProfile', '-NonInteractive', '-File',
            str(Path(__file__).with_name('native_support.ps1')), '-InputPath', str(src),
            '-OutputPath', str(dst)], capture_output=True, text=True, timeout=45)
        if result.returncode or not dst.is_file():
            raise RuntimeError('WPF coverage failed: '+(result.stderr or result.stdout)[-1500:])
        response = json.loads(dst.read_text(encoding='utf-8-sig'))
    if response.get('fill_rule') != 'Nonzero' or not response.get('d'):
        raise ValueError('unsupported/empty coverage result')
    out = normalize_path_commands(svg_path_to_absolute(parse_svg_path(response['d'])))
    if len(out) > 5000 or len(response['d']) > 100000:
        raise ValueError('coverage output exceeds the native command budget')
    for cmd in out:
        for value in cmd.args:
            scalar(value, 'coverage result coordinate', -1e6, 1e6)
    response.update(commands=len(out), bounds=list(path_bounds(out)),
        input_sha256=hashlib.sha256(json.dumps(recipe, sort_keys=True).encode()).hexdigest(),
        tolerance=tolerance, operation='fill_union_centered_round_stroke',
        qualification='computed coverage only; source paint eligibility and final render require review')
    return response
