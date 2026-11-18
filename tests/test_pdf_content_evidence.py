"""Behavior checks with synthetic PDF bytes; no downloaded code is executed."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import pymupdf

HERE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(ROOT))
import pdf_paint_scene as candidate

SCRIPT = Path(candidate.__file__).resolve()


def synthetic_pdf():
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=200)
    page.draw_rect(pymupdf.Rect(5, 5, 290, 190), color=(0, 0, 0))
    page.insert_text((20, 30), 'VISIBLE', fontname='helv', fontsize=11)
    page.insert_text((20, 60), 'HIDDEN', render_mode=3, fontname='helv')
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 4, 4))
    pix.clear_with(128)
    xref = page.insert_image(pymupdf.Rect(10, 80, 30, 100), stream=pix.tobytes('png'))
    page.insert_image(pymupdf.Rect(40, 80, 60, 100), xref=xref)
    # Repeat exactly the same placement: bbox is insufficient for unique seqno.
    page.insert_image(pymupdf.Rect(40, 80, 60, 100), xref=xref)
    inline = b'\nq 20 0 0 20 80 80 cm BI /W 1 /H 1 /CS /RGB /BPC 8 /F /AHx ID ff0000> EI Q\n'
    stream = doc.get_new_xref()
    doc.update_object(stream, '<<>>')
    doc.update_stream(stream, page.read_contents() + inline)
    page.set_contents(stream)
    data = doc.tobytes()
    doc.close()
    return data


class Proxy:
    def __init__(self, page, **overrides):
        self.page = page
        self.overrides = overrides

    def __getattr__(self, name):
        if name in self.overrides:
            return self.overrides[name]
        return getattr(self.page, name)


class ContentEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.doc = pymupdf.open(stream=synthetic_pdf(), filetype='pdf')
        self.page = self.doc[0]

    def tearDown(self):
        self.doc.close()

    def evidence(self, page=None, region=None):
        return candidate.extract_page(page or self.page, region, include_content=True)

    def test_default_minimal_page_needs_no_new_methods(self):
        class MinimalPage:
            rect = (0, 0, 100, 100)
            def get_drawings(self, extended):
                return []
            def get_bboxlog(self):
                return [('ignore-text', (1, 1, 5, 5))]
        page = MinimalPage()
        result = candidate.extract_page(page)
        self.assertNotIn('content_evidence', result)
        self.assertEqual(result['region'], [0, 0, 100, 100])
        self.assertEqual(result['paths'], [])
        self.assertEqual(result['scopes'], [])
        expected_operation = dict(seqno=0, kind='ignore-text', bounds=[1, 1, 5, 5],
                                  path_record_present=False)
        self.assertEqual(result['operations'], [expected_operation])
        self.assertEqual(result['unresolved_operations'], [expected_operation])
        self.assertEqual(result['operation_counts'], {'ignore-text': 1})
        self.assertEqual(result['native_conversion_status'], 'NOT_PERFORMED')
        opt_in = self.evidence()
        opt_in.pop('content_evidence')
        self.assertEqual(candidate.extract_page(self.page), opt_in)

    def test_hidden_text_remains_evidence_and_unresolved(self):
        result = self.evidence()
        content = result['content_evidence']
        self.assertEqual(content['status'], 'EXTRACTED')
        trace = content['channels']['text_trace']['records']
        hidden = next(r for r in trace if r['type'] == 3)
        self.assertEqual(''.join(chr(c[0]) for c in hidden['chars']), 'HIDDEN')
        self.assertEqual(hidden['display_kind'], 'ignore-text')
        self.assertEqual(hidden['visibility'], 'NOT_INFERRED')
        self.assertEqual(hidden['display_seqno_validation'], 'TEXT_KIND_MATCH')
        self.assertIn('ignore-text', [r['kind'] for r in result['unresolved_operations']])
        self.assertEqual(result['unresolved_operations'], candidate.extract_page(self.page)['unresolved_operations'])
        raw = content['channels']['text_spans']['records']
        self.assertEqual(''.join(c['c'] for r in raw for c in r['chars']), 'VISIBLEHIDDEN')
        self.assertTrue(all(r['paint_sequence_association'] == 'NOT_INFERRED' for r in raw))
        fonts = content['channels']['fonts']['records']
        self.assertTrue(any(f['basefont'] == 'Helvetica' for f in fonts))
        json.dumps(result, allow_nan=False)

    def test_repeated_and_inline_image_instances_keep_distinct_ctms(self):
        records = self.evidence()['content_evidence']['channels']['image_instances']['records']
        self.assertEqual(len(records), 4)
        self.assertEqual(len({r['evidence_id'] for r in records}), 4)
        self.assertEqual(len([r for r in records if r['xref'] > 0]), 3)
        self.assertEqual(len([r for r in records if r['xref'] == 0]), 1)
        repeated = [r for r in records if r['bbox'] == [40.0, 80.0, 60.0, 100.0]]
        self.assertEqual(len(repeated), 2)
        self.assertTrue(all(r['candidate_display_operation_count'] == 2 for r in repeated))
        self.assertTrue(all(r['paint_sequence_association'] == 'NOT_INFERRED' for r in records))
        self.assertEqual(records[0]['instance_ctm'], [20.0, 0.0, -0.0, 20.0, 10.0, 80.0])

    def test_rotated_page_uses_unrotated_default_region_without_mutation(self):
        unrotated = self.evidence()
        self.page.set_rotation(90)
        before = self.doc.tobytes(no_new_id=True)
        rotated = self.evidence()
        self.assertEqual(rotated['region'], [0.0, 0.0, 300.0, 200.0])
        self.assertEqual(rotated['content_evidence']['page_frame']['rotation_degrees'], 90)
        self.assertEqual(rotated['content_evidence']['channels'], unrotated['content_evidence']['channels'])
        self.assertEqual(self.page.rotation, 90)
        self.assertEqual(self.doc.tobytes(no_new_id=True), before)
        region = self.evidence(region=[0, 0, 35, 45])['content_evidence']['channels']
        self.assertEqual(len(region['image_instances']['records']), 0)
        self.assertEqual(len(region['text_trace']['records']), 1)
        self.assertEqual(len(region['text_spans']['records']), 1)

    def test_missing_or_unsupported_public_api_is_explicit_and_bounded(self):
        def unsupported(**kwargs):
            raise NotImplementedError('do not leak arbitrary source contents')
        proxy = Proxy(self.page, get_texttrace=None, get_image_info=unsupported)
        result = self.evidence(proxy)
        channels = result['content_evidence']['channels']
        self.assertEqual(result['content_evidence']['status'], 'PARTIAL')
        self.assertEqual(channels['text_trace']['status'], 'UNAVAILABLE')
        self.assertEqual(channels['image_instances']['status'], 'UNSUPPORTED')
        self.assertNotIn('do not leak', json.dumps(channels))
        self.assertEqual(result['unresolved_operations'], candidate.extract_page(self.page)['unresolved_operations'])

    def test_trace_seqno_is_validated_not_reconstructed_from_order(self):
        records = self.page.get_texttrace()
        records[0]['seqno'] = 987654
        proxy = Proxy(self.page, get_texttrace=lambda: list(reversed(records)))
        trace = self.evidence(proxy)['content_evidence']['channels']['text_trace']['records']
        invalid = next(r for r in trace if r['seqno'] == 987654)
        self.assertEqual(invalid['display_seqno_validation'], 'UNVERIFIED')
        self.assertIsNone(invalid['display_kind'])
        self.assertEqual(trace[0]['type'], 3)

    def test_budget_rejects_channel_without_silent_truncation(self):
        with patch.object(candidate, 'MAX_CONTENT_CHARACTERS', 2):
            channels = self.evidence()['content_evidence']['channels']
        self.assertEqual(channels['text_trace']['status'], 'REJECTED')
        self.assertEqual(channels['text_trace']['records'], [])
        self.assertEqual(channels['text_spans']['status'], 'REJECTED')
        self.assertEqual(channels['image_instances']['status'], 'EXTRACTED')

    def test_public_api_and_cli_opt_in_and_source_immutable(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'synthetic.pdf'
            output = Path(temp) / 'example.json'
            source.write_bytes(synthetic_pdf())
            original = source.read_bytes()
            self.assertNotIn('content_evidence', candidate.inspect_pdf(source, 1))
            self.assertIn('content_evidence', candidate.inspect_pdf(source, 1, include_content=True))
            env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(SCRIPT.parent),
                       os.environ.get('PYTHONPATH', '')]))
            run = subprocess.run([sys.executable, '-X', 'utf8', str(SCRIPT),
                                  str(source), str(output), '--page', '1', '--include-content'],
                                 env=env, capture_output=True, text=True, encoding='utf8')
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(output.read_text(encoding='utf8'))
            self.assertEqual(result['content_evidence']['status'], 'EXTRACTED')
            self.assertEqual(result['native_conversion_status'], 'NOT_PERFORMED')
            self.assertEqual(source.read_bytes(), original)
            repeat = subprocess.run([sys.executable, '-X', 'utf8', str(SCRIPT),
                                     str(source), str(output), '--page', '1', '--include-content'],
                                    env=env, capture_output=True, text=True, encoding='utf8')
            self.assertNotEqual(repeat.returncode, 0)  # create-only output remains protected


if __name__ == '__main__':
    unittest.main(verbosity=2)
