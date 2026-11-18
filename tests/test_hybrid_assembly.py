"""Source-first v4 qualification; synthetic sources, actual PPTX serialization.

No test claims PowerPoint application rendering or interactive dragging.
"""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
import zipfile

from PIL import Image, ImageDraw
import numpy as np
from pptx import Presentation
from pptx.util import Inches

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / 'scripts'))
import reconstruction_pipeline as P
from reconstruction_scene import (EditingGroup, RectLink, ReconstructionScene,
    SceneNode, SourceFrame, assemble_pptx, rectangle_draw, text_draw)
import component_assets
from raster_components import prepare_asset, replace_instance_asset

def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


class HybridAssembly(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=HERE)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'original.png'
        source = Image.new('RGB', (180, 120), 'white')
        ImageDraw.Draw(source).ellipse((24, 24, 55, 55), fill='#2679aa')
        source.save(self.source)
        alpha = Image.new('L', (40, 40), 0)
        ImageDraw.Draw(alpha).ellipse((4, 4, 35, 35), fill=255)
        self.alpha = self.root / 'observed-alpha.png'
        alpha.save(self.alpha)
        self.asset = self.root / 'approved.png'
        self.manifest = dict(schema_version=1, mode='faithful', execution_profile='standard',
            editing_policy='hybrid', hybrid_authorization='Synthetic test: move/scale/replace the independent blue object.',
            source=dict(path=self.source.name, width=180, height=120, sha256=P.sha(self.source)),
            canvas=dict(width=180, height=120), targets=[dict(format='pptx', path='candidate.pptx')],
            modules=[dict(id='panel', type='illustration', bbox=[0, 0, 180, 120], reading_order=1)],
            connections=[], uncertainties=[], construction=dict(version=4, slide_width_inches=6,
                editing_groups=[dict(id='object-and-label', members=['object', 'label'],
                                     observation='The independent object and its native label move together.')]),
            component_assets=[dict(asset_id='blue-object', path=self.asset.name, sha256='0'*64,
                source_kind='source_crop', source_sha256=P.sha(self.source), source_bbox=[20, 20, 40, 40],
                origin='Synthetic original source crop with independently supplied circle alpha.',
                authorization='Synthetic local preparation permitted.', editing_unit='One circle object',
                extent='object', content_class='illustration', contains_native_required=False,
                requires_alpha=True, min_visible_pixels=8, min_dpi=1,
                invariants=['One blue circle; preserve its boundary and transparent margin.'], comparison='source_exact',
                preparation=dict(method='supplied-alpha', authorization='Synthetic observed alpha accepted.',
                    alpha_path=self.alpha.name, alpha_sha256=P.sha(self.alpha), rgb_mode='straight'))],
            component_instances=[dict(instance_id='object-1', asset_id='blue-object', slide=1, output_name='object',
                bbox_inches=[2/3, 2/3, 4/3, 4/3], rotation=0, crop=[0, 0, 0, 0],
                placement_tolerance_inches=.001, anchors=[dict(id='center', uv=[.5, .5], expected_inches=[4/3, 4/3])])],
            source_inventory=[
                dict(id='object', module='panel', role='shape', bbox=[20, 20, 40, 40],
                    output_name='object', representation='component_raster', component_instance='object-1',
                    construction=dict(kind='picture', observation='Synthetic independent blue circle.', parent='background')),
                dict(id='label', module='panel', role='text', bbox=[18, 62, 65, 14], text='Circle label',
                    output_name='label', native_required=True, representation='native_primitive',
                    construction=dict(kind='text', observation='Source native label beneath the circle.',
                                      options=dict(font_size_px=10), parent='background')),
                dict(id='background', module='panel', role='shape', bbox=[0, 0, 180, 120], output_name='background',
                    representation='native_primitive', construction=dict(kind='rectangle', container=True,
                        observation='White source background.', options=dict(fill='FFFFFF', stroke=None)))])
        payload, self.manifest, _ = prepare_asset(self.manifest, 'blue-object', self.root)
        self.asset.write_bytes(payload)
        self.path = self.root / 'manifest.json'

    def prepare(self, name='prepared'):
        write_json(self.path, self.manifest)
        destination = self.root / name
        P.prepare(self.path, destination)
        return destination

    def reviewed(self, prepared):
        review = P.read_json(prepared / 'review-template.json')
        for item in review['items']:
            item.update(accepted=True, note='Synthetic fixture: original circle, transparent margin and independent label checked.')
        path = self.root / (prepared.name + '-review.json')
        write_json(path, review)
        return path

    def test_hybrid_source_build_reopens_named_group_and_native_text(self):
        prepared = self.prepare()
        output = self.root / 'build'
        report = P.build(prepared, output, review=self.reviewed(prepared))
        slide = Presentation(output / 'candidate.pptx').slides[0]
        self.assertEqual([s.name for s in slide.shapes], ['background', 'object-and-label'])
        group = slide.shapes[1]
        self.assertEqual([s.name for s in group.shapes], ['object', 'label'])
        self.assertEqual(group.shapes[1].text, 'Circle label')
        self.assertEqual(len(slide._element.xpath('.//p:pic')), 1)
        self.assertEqual(report['paint_order'], ['background', 'object', 'label'])
        self.assertEqual(report['top_level_paint_order'], ['background', 'object-and-label'])
        audit = component_assets.audit(output / 'candidate.pptx', P.read_json(output / 'resolved-manifest.json'),
                                       output / 'resolved-manifest.json')
        self.assertEqual(audit['errors'], [])
        self.assertEqual(audit['unverified'], [])
        self.assertEqual(audit['instances'][0]['name'], 'object')
        self.assertEqual(report['editor_review'], 'NOT_PERFORMED')
        self.assertIsNone(report['delivery_ready'])

    def test_prepared_and_final_audit_inputs_are_portable(self):
        prepared = self.prepare()
        moved = self.root / 'moved-prepared'
        prepared.rename(moved)
        # These synthetic originals become unusable. A correct frozen build
        # must not consult their original locations, even for alpha verification.
        for path in (self.source, self.alpha, self.asset):
            path.write_bytes(b'original locations intentionally unavailable')
        output = self.root / 'portable-build'
        P.build(moved, output, review=self.reviewed(moved))
        final = self.root / 'moved-final'
        output.rename(final)
        manifest = P.read_json(final / 'resolved-manifest.json')
        self.assertFalse(Path(manifest['source']['path']).is_absolute())
        for asset in manifest['component_assets']:
            self.assertFalse(Path(asset['path']).is_absolute())
            self.assertFalse(Path(asset['preparation']['alpha_path']).is_absolute())
        audit = component_assets.audit(final / 'candidate.pptx', manifest, final / 'resolved-manifest.json')
        self.assertEqual(audit['errors'], [])
        self.assertTrue(audit['valid'])

    def test_serialized_group_preserves_coordinates_and_moves_text_with_object(self):
        prepared = self.prepare()
        output = self.root / 'build'
        report = P.build(prepared, output, review=self.reviewed(prepared))
        deck = Presentation(output / 'candidate.pptx')
        group = deck.slides[0].shapes[1]
        object_shape, text_shape = group.shapes
        before = (object_shape.shape_id, text_shape.shape_id, text_shape.left, text_shape.top)
        with zipfile.ZipFile(output / 'candidate.pptx') as archive:
            objects, _ = component_assets.read_objects(archive)
        picture = next(o for o in objects if o['name'] == 'object')
        self.assertAlmostEqual(picture['bbox_inches'][0], 2/3, places=5)
        self.assertAlmostEqual(picture['bbox_inches'][1], 2/3, places=5)
        xfrm = group._element.grpSpPr.xfrm
        self.assertEqual((xfrm.off.x, xfrm.off.y, xfrm.ext.cx, xfrm.ext.cy),
                         (xfrm.chOff.x, xfrm.chOff.y, xfrm.chExt.cx, xfrm.chExt.cy))
        group.left += Inches(.4)
        group.top += Inches(.2)
        moved = self.root / 'moved-group.pptx'
        deck.save(moved)
        reread = Presentation(moved).slides[0].shapes[1]
        self.assertEqual((reread.shapes[0].shape_id, reread.shapes[1].shape_id,
                          reread.shapes[1].left, reread.shapes[1].top), before)
        # Text's raw coordinates stay in the group frame; its world position
        # follows the changed group transform by the same measured delta.
        xfrm = reread._element.grpSpPr.xfrm
        self.assertEqual(xfrm.off.x-xfrm.chOff.x, Inches(.4))
        self.assertEqual(xfrm.off.y-xfrm.chOff.y, Inches(.2))
        self.assertEqual(reread.shapes[1].text, 'Circle label')
        with zipfile.ZipFile(moved) as archive:
            objects, _ = component_assets.read_objects(archive)
        moved_picture = next(o for o in objects if o['name'] == 'object')
        self.assertAlmostEqual(moved_picture['bbox_inches'][0]-picture['bbox_inches'][0], .4, places=6)
        self.assertAlmostEqual(moved_picture['bbox_inches'][1]-picture['bbox_inches'][1], .2, places=6)
        ids = {i['id']: i['shape_id'] for i in report['items']}
        self.assertEqual(ids['object'], before[0])
        self.assertEqual(ids['label'], before[1])

    def test_interleaved_group_rejected_before_output_creation(self):
        self.manifest['source_inventory'].insert(1, dict(id='occluder', module='panel', role='shape',
            bbox=[50, 35, 15, 15], output_name='occluder', representation='native_primitive',
            construction=dict(kind='rectangle', observation='Synthetic intervening overlap.', options={}, parent='background')))
        self.assertIn('interleaved', ';'.join(P.validate_contract(self.manifest)))
        with self.assertRaisesRegex(ValueError, 'interleaved'):
            self.prepare('bad')
        self.assertFalse((self.root / 'bad').exists())

    def test_group_membership_is_explicit_not_background_parent(self):
        self.manifest['construction'].pop('editing_groups')
        prepared = self.prepare()
        output = self.root / 'build'
        report = P.build(prepared, output, review=self.reviewed(prepared))
        self.assertEqual([s.name for s in Presentation(output / 'candidate.pptx').slides[0].shapes],
                         ['background', 'object', 'label'])
        self.assertEqual(report['editing_groups'], [])

    def test_hybrid_can_mix_approved_picture_and_named_native_svg_group(self):
        vector = self.root / 'native-detail.svg'
        vector.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 30 30"><rect id="outline" x="1" y="1" width="28" height="28" fill="none" stroke="#173d6a"/></svg>', encoding='utf-8')
        with Image.open(self.source) as original:
            source = original.copy()
        ImageDraw.Draw(source).rectangle((91, 31, 119, 59), outline='#173d6a')
        source.save(self.source)
        self.manifest['source']['sha256'] = P.sha(self.source)
        self.manifest['component_assets'][0]['source_sha256'] = P.sha(self.source)
        self.manifest['source_inventory'].insert(2, dict(id='native-detail', module='panel', role='shape',
            bbox=[90, 30, 30, 30], output_name='native-detail', native_required=True, representation='native_composite',
            construction=dict(kind='svg', observation='Synthetic observed editable outlined rectangle.',
                              asset=dict(path=vector.name, sha256=P.sha(vector)), parent='background')))
        prepared = self.prepare()
        output = self.root / 'mixed-native'
        P.build(prepared, output, review=self.reviewed(prepared))
        audit = component_assets.audit(output / 'candidate.pptx', P.read_json(output / 'resolved-manifest.json'),
                                       output / 'resolved-manifest.json')
        self.assertEqual(audit['errors'], [])
        self.assertTrue(audit['valid'])
        deck = Presentation(output / 'candidate.pptx')
        group = next(s for s in deck.slides[0].shapes if s.name == 'native-detail')
        inner = group.shapes.add_group_shape()
        inner.name = 'forbidden-nested-group'
        picture = inner.shapes.add_picture(str(self.asset), Inches(3.1), Inches(1.1), Inches(.4), Inches(.4))
        picture.name = 'forbidden-raster-detail'
        nested = self.root / 'nested-raster.pptx'
        deck.save(nested)
        rejected = component_assets.audit(nested, P.read_json(output / 'resolved-manifest.json'), output / 'resolved-manifest.json')
        self.assertIn('native-detail: required native object coverage failed', rejected['errors'])
        self.assertTrue(any('unregistered picture' in e for e in rejected['errors']))
        with zipfile.ZipFile(nested) as archive:
            leaves, _ = component_assets.read_objects(archive)
        self.assertNotIn('native-detail', [o['name'] for o in leaves])
        self.assertNotIn('forbidden-nested-group', [o['name'] for o in leaves])

    def test_missing_hybrid_authority_and_native_required_picture_rejected(self):
        for change in ('authorization', 'required', 'text', 'asset-contents'):
            with self.subTest(change=change):
                manifest = copy.deepcopy(self.manifest)
                if change == 'authorization':
                    manifest.pop('hybrid_authorization')
                elif change == 'required':
                    manifest['source_inventory'][0]['native_required'] = True
                elif change == 'text':
                    manifest['source_inventory'][0]['role'] = 'text'
                else:
                    manifest['component_assets'][0]['contains_native_required'] = True
                self.assertTrue(P.validate_contract(manifest))

    def test_no_ignored_assets_or_instances(self):
        for key in ('component_assets', 'component_instances'):
            with self.subTest(key=key):
                manifest = copy.deepcopy(self.manifest)
                extra = copy.deepcopy(manifest[key][0])
                extra['asset_id' if key == 'component_assets' else 'instance_id'] = 'unregistered'
                if key == 'component_instances':
                    extra['output_name'] = 'unregistered'
                manifest[key].append(extra)
                self.assertTrue(P.validate_contract(manifest))

    def test_every_picture_requires_its_exact_review(self):
        prepared = self.prepare()
        with self.assertRaisesRegex(ValueError, 'exact review'):
            P.build(prepared, self.root / 'bad')
        review_path = self.reviewed(prepared)
        review = P.read_json(review_path)
        review['items'][0]['candidate_sha256'] = '0'*64
        write_json(review_path, review)
        with self.assertRaisesRegex(ValueError, 'stale component'):
            P.build(prepared, self.root / 'stale', review=review_path)
        self.assertFalse((self.root / 'bad').exists())
        self.assertFalse((self.root / 'stale').exists())

    def test_tampered_frozen_asset_and_alpha_fail_before_any_deck(self):
        for kind in ('asset', 'alpha'):
            with self.subTest(kind=kind):
                prepared = self.prepare(kind)
                receipt = P.read_json(prepared / 'prepared.json')
                target = prepared / receipt['component_assets'][0][kind]['path']
                target.write_bytes(target.read_bytes() + b'tampered')
                with self.assertRaisesRegex(ValueError, 'hash changed'):
                    P.build(prepared, self.root / (kind+'-build'), review=self.reviewed(prepared))
                self.assertFalse((self.root / (kind+'-build')).exists())

    def use_extracted_source_layer(self):
        """Actual optional SciPy production extraction, never a fabricated receipt."""
        interpreter = os.environ.get('EDITABLE_PPT_EXTRACT_PYTHON')
        if not interpreter and importlib.util.find_spec('scipy') is None:
            self.skipTest('Optional SciPy extraction runtime not supplied')
        interpreter = interpreter or sys.executable
        yy, xx = np.mgrid[:48, :64]
        alpha = np.clip((19-np.hypot(xx-32, yy-24))/10, 0, 1)
        foreground = np.array([40, 120, 175])
        background = np.stack((205+.5*xx+.25*yy, 225-.25*xx+.25*yy, 240-.25*xx-.5*yy), axis=2)
        patch = np.rint(alpha[:, :, None]*foreground+(1-alpha[:, :, None])*background).astype('uint8')
        source = Image.new('RGB', (180, 120), 'white')
        source.paste(Image.fromarray(patch), (20, 20))
        source.save(self.source)
        def shift(points):
            return [[x+20, y+20] for x, y in points]
        annotations = [dict(kind='polygon', label='background', observation='Synthetic observed spatial-background border.', points=shift(points))
            for points in ([[0, 0], [63, 0], [63, 3], [0, 3]], [[0, 44], [63, 44], [63, 47], [0, 47]],
                           [[0, 0], [5, 0], [5, 47], [0, 47]], [[59, 0], [63, 0], [63, 47], [59, 47]])]
        plan = dict(method='closed_form', foreground=[[52, 44]], background=[[20, 20]], reserved_regions=[],
            annotations=annotations, matting=dict(background_patches=[[20, 20, 6, 6], [78, 20, 6, 6], [20, 62, 6, 6], [78, 62, 6, 6]],
                background_tolerance=1, epsilon=1e-7, solver='direct',
                background_model=dict(kind='affine', observation='Synthetic original has a smooth affine backdrop.', max_condition=20)),
            source_sha256=P.sha(self.source), context_bbox=[20, 20, 64, 48],
            observation='Synthetic soft independent foreground on an observed affine backdrop.')
        plan_path = self.root / 'source-layer-plan.json'
        write_json(plan_path, plan)
        bundle = self.root / 'extracted-layer'
        extracted = subprocess.run([interpreter, '-X', 'utf8', '-B', str(P.SCRIPTS / 'source_objects.py'),
                                    str(self.source), str(plan_path), str(bundle)],
                                   capture_output=True, text=True, encoding='utf-8', timeout=120)
        self.assertEqual(extracted.returncode, 0, extracted.stderr)
        self.manifest['source']['sha256'] = P.sha(self.source)
        self.manifest['source_inventory'][0]['bbox'] = [20, 20, 64, 48]
        self.manifest['source_inventory'][1]['bbox'] = [20, 70, 65, 14]
        self.manifest['component_instances'][0].update(bbox_inches=[20/30, 20/30, 64/30, 48/30],
            anchors=[dict(id='center', uv=[.5, .5], expected_inches=[52/30, 44/30])])
        asset = self.manifest['component_assets'][0]
        asset.update(source_sha256=P.sha(self.source), source_bbox=[20, 20, 64, 48],
            preparation=dict(method='source-layer', authorization='Synthetic estimated layer representation accepted for this serialization test.',
                             receipt_path='extracted-layer/candidate.json', receipt_sha256=P.sha(bundle / 'candidate.json')))
        payload, self.manifest, metrics = prepare_asset(self.manifest, 'blue-object', self.root)
        self.asset.write_bytes(payload)
        self.assertTrue(metrics['alpha_inferred'])
        self.assertEqual(metrics['rgb_semantics'], 'estimated_straight_foreground')
        self.assertEqual(metrics['physical_layer_identity'], 'NOT_VERIFIED')
        self.assertFalse(metrics['hidden_content_generated'])
        return bundle

    def test_source_layer_receipt_and_all_companions_are_portable_without_reinference(self):
        from source_layers import read_layer_bundle
        bundle = self.use_extracted_source_layer()
        original_receipt = (bundle / 'candidate.json').read_bytes()
        with Image.open(bundle / 'rgba.png') as image:
            expected_rgba = image.tobytes()
        prepared = self.prepare()
        record = P.read_json(prepared / 'prepared.json')['component_assets'][0]
        expected_names = {'context_mask', 'alpha', 'rgba', 'trimap', 'occlusion_mask', 'coverage_adjustment', 'reconstructed_color'}
        self.assertEqual(set(record['source_layer_outputs']), expected_names)
        self.assertEqual((prepared / record['source_layer']['path']).read_bytes(), original_receipt)
        bundle.rename(self.root / 'old-original-layer-location')
        self.source.write_bytes(b'original source location intentionally unavailable')
        self.asset.write_bytes(b'original approved asset location intentionally unavailable')
        output = self.root / 'layer-build'
        P.build(prepared, output, review=self.reviewed(prepared))
        manifest = P.read_json(output / 'resolved-manifest.json')
        asset = manifest['component_assets'][0]
        receipt_path = output / asset['preparation']['receipt_path']
        self.assertEqual(receipt_path.read_bytes(), original_receipt)
        layer, evidence = read_layer_bundle(dict(path=str(receipt_path), sha256=asset['preparation']['receipt_sha256']),
                                            manifest['source']['sha256'], asset['source_bbox'])
        self.assertEqual(layer.tobytes(), expected_rgba)
        layer.close()
        self.assertEqual(evidence['physical_layer_identity'], 'NOT_VERIFIED')
        with Image.open(output / asset['path']) as image:
            self.assertEqual(image.tobytes(), expected_rgba)
        audit = component_assets.audit(output / 'candidate.pptx', manifest, output / 'resolved-manifest.json')
        self.assertEqual(audit['errors'], [])

    def test_source_layer_stale_companion_blocks_build_even_when_asset_unchanged(self):
        self.use_extracted_source_layer()
        prepared = self.prepare()
        record = P.read_json(prepared / 'prepared.json')['component_assets'][0]
        companion = prepared / record['source_layer_outputs']['coverage_adjustment']['path']
        companion.write_bytes(companion.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError, 'hash changed'):
            P.build(prepared, self.root / 'stale-layer', review=self.reviewed(prepared))
        self.assertFalse((self.root / 'stale-layer').exists())

    def test_picture_placement_must_use_source_frame_and_orthogonal_rotation(self):
        for field, value in (('bbox_inches', [0, 0, 1, 1]), ('rotation', 17)):
            with self.subTest(field=field):
                manifest = copy.deepcopy(self.manifest)
                manifest['component_instances'][0][field] = value
                self.assertTrue(P.validate_contract(manifest))

    def test_orthogonal_picture_rotation_and_safe_transparent_crop_readback(self):
        self.manifest['component_instances'][0].update(rotation=90, crop=[.05, .05, .05, .05])
        prepared = self.prepare()
        output = self.root / 'rotated'
        P.build(prepared, output, review=self.reviewed(prepared))
        audit = component_assets.audit(output / 'candidate.pptx', P.read_json(output / 'resolved-manifest.json'),
                                       output / 'resolved-manifest.json')
        self.assertEqual(audit['errors'], [])
        self.assertAlmostEqual(audit['instances'][0]['rotation'], 90)
        self.assertEqual(audit['instances'][0]['crop'], [.05]*4)

    def test_non_square_asymmetric_transparent_crop_rotates90_without_distortion(self):
        asset_image = Image.new('RGBA', (80, 40), (0, 0, 0, 0))
        ImageDraw.Draw(asset_image).ellipse((8, 6, 63, 33), fill=(38, 121, 170, 200))
        asset_image.save(self.asset)
        # Remove only transparent margins: 4 left, 2 top, 12 right, 4 bottom.
        # The remaining 64x34 frame becomes a 34x64 clockwise-rotated placement.
        visible_frame = asset_image.crop((4, 2, 68, 36)).transpose(Image.Transpose.ROTATE_270)
        source = Image.new('RGBA', (180, 120), 'white')
        source.alpha_composite(visible_frame, (20, 20))
        source.convert('RGB').save(self.source)
        self.manifest['source']['sha256'] = P.sha(self.source)
        asset = self.manifest['component_assets'][0]
        for key in ('preparation', 'source_sha256', 'source_bbox'):
            asset.pop(key)
        asset.update(source_kind='local', sha256=P.sha(self.asset),
            origin='Synthetic independently approved 80x40 object with asymmetric transparent margins.')
        self.manifest['source_inventory'][0]['bbox'] = [20, 20, 34, 64]
        self.manifest['source_inventory'][1]['bbox'] = [18, 86, 80, 14]
        expected_bbox = [20/30, 20/30, 34/30, 64/30]
        self.manifest['component_instances'][0].update(bbox_inches=expected_bbox, rotation=90,
            crop=[.05, .05, .15, .1],
            anchors=[dict(id='off-center-feature', uv=[.25, .5], expected_inches=[1.2, 1.2])])
        prepared = self.prepare()
        output = self.root / 'non-square-rotated'
        P.build(prepared, output, review=self.reviewed(prepared))
        saved = output / 'candidate.pptx'
        reopened = Presentation(saved).slides[0]
        picture = next(shape for group in reopened.shapes if hasattr(group, 'shapes')
                       for shape in group.shapes if shape.name == 'object')
        self.assertEqual(picture.rotation, 90)
        self.assertEqual([picture.crop_left, picture.crop_top, picture.crop_right, picture.crop_bottom],
                         [.05, .05, .15, .1])
        audit = component_assets.audit(saved, P.read_json(output / 'resolved-manifest.json'),
                                       output / 'resolved-manifest.json')
        self.assertEqual(audit['errors'], [])
        self.assertEqual(audit['unverified'], [])
        instance = audit['instances'][0]
        self.assertAlmostEqual(instance['rotation'], 90)
        self.assertEqual(instance['crop'], [.05, .05, .15, .1])
        # Bounds/centers serialize as integer EMUs, including half-extent
        # calculations for a non-square rotated frame. Allow two EMUs only.
        for actual, expected in zip(instance['bbox_inches'], expected_bbox):
            self.assertAlmostEqual(actual, expected, delta=2/914400)
        self.assertEqual(instance['placement_integrity']['errors'], [])
        for actual in instance['anchors'][0]['actual_inches']:
            self.assertAlmostEqual(actual, 1.2, delta=2/914400)
        with zipfile.ZipFile(saved) as archive:
            with Image.open(io.BytesIO(archive.read(instance['target']))) as embedded:
                self.assertEqual(embedded.size, (80, 40))
                self.assertEqual(embedded.getchannel('A').tobytes(), asset_image.getchannel('A').tobytes())

    def test_legacy_versions_remain_native_and_cannot_enable_v4_features(self):
        for version in (1, 2, 3):
            with self.subTest(version=version):
                manifest = copy.deepcopy(self.manifest)
                manifest['construction']['version'] = version
                self.assertTrue(P.validate_contract(manifest))
        native = copy.deepcopy(self.manifest)
        for key in ('component_assets', 'component_instances', 'editing_policy', 'hybrid_authorization'):
            native.pop(key)
        native['source_inventory'].pop(0)
        native['construction'].pop('editing_groups')
        native['construction']['version'] = 1
        self.assertEqual(P.validate_contract(native), [])

    def test_manifest_replacement_regenerates_same_identity_and_group_geometry(self):
        first = self.prepare('before-prepared')
        before = self.root / 'before'
        P.build(first, before, review=self.reviewed(first))
        replacement_path = self.root / 'approved-replacement.png'
        replacement_image = Image.new('RGBA', (40, 40), (0, 0, 0, 0))
        ImageDraw.Draw(replacement_image).ellipse((4, 4, 35, 35), fill='#5070b0')
        replacement_image.save(replacement_path)
        replacement = copy.deepcopy(self.manifest['component_assets'][0])
        for key in ('preparation', 'source_sha256', 'source_bbox'):
            replacement.pop(key)
        replacement.update(asset_id='approved-replacement', path=replacement_path.name,
            sha256=P.sha(replacement_path), source_kind='local', origin='Synthetic independently approved replacement fixture.',
            authorization='Synthetic replacement of this independent object is accepted.')
        self.manifest = replace_instance_asset(self.manifest, 'object-1', replacement, self.root)
        second = self.prepare('after-prepared')
        after = self.root / 'after'
        P.build(second, after, review=self.reviewed(second))
        checked = component_assets.verify_replacement(before / 'candidate.pptx', after / 'candidate.pptx',
                                                       1, 'object', replacement['sha256'])
        self.assertEqual(checked['errors'], [])
        self.assertTrue(checked['valid'])
        self.assertEqual(checked['interactive_drag_follow'], 'NOT_VERIFIED')
        original_group = Presentation(before / 'candidate.pptx').slides[0].shapes[1]
        replaced_group = Presentation(after / 'candidate.pptx').slides[0].shapes[1]
        self.assertEqual(original_group._element.grpSpPr.xml, replaced_group._element.grpSpPr.xml)

    def test_group_validation_disallows_duplicate_unknown_nested_and_colliding_names(self):
        for groups in (
            [dict(id='label', members=['object', 'label'], observation='Name collision.')],
            [dict(id='unit', members=['object', 'object'], observation='Duplicate membership.')],
            [dict(id='unit', members=['object', 'missing'], observation='Unknown membership.')],
            [dict(id='unit1', members=['object', 'label'], observation='First unit.'),
             dict(id='unit2', members=['background', 'object'], observation='Overlapping second unit.')],
            [dict(id='unit1', members=['object', 'label'], observation='First unit.'),
             dict(id='unit2', members=['unit1', 'background'], observation='Nesting is outside this profile.')],
        ):
            with self.subTest(groups=groups):
                manifest = copy.deepcopy(self.manifest)
                manifest['construction']['editing_groups'] = groups
                self.assertTrue(P.validate_contract(manifest))

    def test_disjoint_groups_keep_paint_order_despite_reversed_group_declarations(self):
        deck = Presentation()
        slide = deck.slides.add_slide(deck.slide_layouts[6])
        nodes = [SceneNode(name, (10+i*20, 10, 10, 10), rectangle_draw(fill='123456'))
                 for i, name in enumerate(('a', 'b', 'c', 'd'))]
        scene = ReconstructionScene(SourceFrame((0, 0, 100, 50), (0, 0, 5, 2.5)), nodes,
            [EditingGroup('second-unit', ['d', 'c']), EditingGroup('first-unit', ['b', 'a'])])
        report = assemble_pptx(slide, scene)
        stream = io.BytesIO()
        deck.save(stream)
        reopened = Presentation(io.BytesIO(stream.getvalue())).slides[0]
        self.assertEqual([s.name for s in reopened.shapes], ['first-unit', 'second-unit'])
        self.assertEqual([[s.name for s in group.shapes] for group in reopened.shapes], [['a', 'b'], ['c', 'd']])
        self.assertEqual(report['paint_order'], ['a', 'b', 'c', 'd'])

    def connector_manifest(self, svg=False):
        source = Image.new('RGB', (180, 120), 'white')
        draw = ImageDraw.Draw(source)
        draw.rectangle((10, 20, 40, 40), outline='#173d6a')
        draw.rectangle((80, 20, 110, 40), outline='#173d6a')
        draw.line((40, 30, 80, 30), fill='#173d6a', width=1)
        source.save(self.source)
        nodes = [dict(id=name, module=module, role='shape', bbox=bbox,
                      representation='native_primitive', construction=dict(kind='rectangle', options={},
                      observation='Synthetic observed rectangle '+name+'.'))
                 for name, module, bbox in [('left', 'left-module', [10, 20, 30, 20]),
                                            ('right', 'right-module', [80, 20, 30, 20])]]
        recipe = dict(kind='rect_link', observation='Synthetic straight right-to-left rectangular-port connection.',
                      options=dict(source_port='right', target_port='left'), connection='edge', endpoints=['left', 'right'], z=-10)
        edge_bbox = [40, 29, 40, 2]
        if svg:
            asset = self.root / 'observed-relation.svg'
            asset.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 12"><path id="route" d="M0 6 C10 0 30 12 40 6" fill="none" stroke="#173d6a"/></svg>', encoding='utf-8')
            recipe.pop('options')
            recipe.update(kind='svg', asset=dict(path=asset.name, sha256=P.sha(asset)))
            edge_bbox = [40, 24, 40, 12]
        nodes.append(dict(id='link', module='left-module', role='connector', bbox=edge_bbox,
                          representation='native_composite', construction=recipe))
        return dict(schema_version=1, mode='faithful', execution_profile='standard',
            source=dict(path=self.source.name, width=180, height=120, sha256=P.sha(self.source)),
            canvas=dict(width=180, height=120), targets=[dict(format='pptx', path='candidate.pptx')],
            modules=[dict(id=name, type='illustration', bbox=bbox, reading_order=i+1)
                     for i, (name, bbox) in enumerate([('left-module', [5, 15, 40, 30]), ('right-module', [75, 15, 40, 30])])],
            connections=[dict(id='edge', source='left-module', target='right-module')], uncertainties=[],
            construction=dict(version=4, slide_width_inches=6), source_inventory=nodes,
            diagram_grammar=dict(visual_type='two-node diagram', preserve_visual_type=True, allow_representation_change=False,
                routing='direct', node_roles={m: dict(role='observed rectangle', allowed_geometries=['rect'], output_names=[n])
                                            for m, n in [('left-module', 'left'), ('right-module', 'right')]},
                edge_roles=dict(edge=dict(role='directed source relation', output_name_regex='^link$',
                    endpoint_binding=dict(source_output_name='left', target_output_name='right')))))

    def test_rect_link_saved_bindings_exact_and_paint_order_preserved(self):
        self.manifest = self.connector_manifest()
        prepared = self.prepare()
        output = self.root / 'connectors'
        report = P.build(prepared, output)
        slide = Presentation(output / 'candidate.pptx').slides[0]
        shapes = {s.name: s for s in slide.shapes}
        self.assertEqual(list(shapes), ['link', 'left', 'right'])
        self.assertEqual(report['paint_order'], ['link', 'left', 'right'])
        for shape in shapes.values():
            effects = shape._element.xpath('./p:spPr/a:effectLst')
            self.assertEqual(len(effects), 1)
            self.assertEqual(len(effects[0]), 0)
            self.assertFalse(shape.shadow.inherit)
        connector = shapes['link']
        self.assertEqual(connector._element.xpath('.//a:stCxn/@id'), [str(shapes['left'].shape_id)])
        self.assertEqual(connector._element.xpath('.//a:endCxn/@id'), [str(shapes['right'].shape_id)])
        expected = P.read_json(output / 'expected-connections.json')
        audit = P.load('audit-pptx-connections').audit(output / 'candidate.pptx', True, expected)
        self.assertEqual(audit['issues'], [])
        self.assertTrue(audit['geometry_complete'])
        self.assertIn('NOT_PERFORMED', report['relations'][0]['binding'])

    def test_rect_link_rejects_wrong_module_diagonal_and_grouped_endpoints(self):
        for change in ('wrong-module', 'diagonal', 'grouped-endpoint', 'wrong-kind', 'reversed-port'):
            with self.subTest(change=change):
                manifest = self.connector_manifest()
                if change == 'wrong-module':
                    manifest['source_inventory'][-1]['construction']['endpoints'] = ['right', 'left']
                elif change == 'diagonal':
                    manifest['source_inventory'][1]['bbox'][1] += 3
                elif change == 'grouped-endpoint':
                    manifest['construction']['editing_groups'] = [dict(id='node-pair', members=['left', 'right'], observation='Test forbidden binding into group.')]
                elif change == 'wrong-kind':
                    manifest['source_inventory'][0]['construction']['kind'] = 'native_component'
                else:
                    manifest['source_inventory'][-1]['construction']['options']['source_port'] = 'left'
                self.assertTrue(P.validate_contract(manifest))

    def test_complex_svg_relation_remains_editable_path_without_false_binding(self):
        self.manifest = self.connector_manifest(svg=True)
        prepared = self.prepare()
        output = self.root / 'svg-relation'
        report = P.build(prepared, output)
        slide = Presentation(output / 'candidate.pptx').slides[0]
        self.assertFalse(slide._element.xpath('.//p:cxnSp'))
        self.assertTrue(slide._element.xpath('.//a:cubicBezTo'))
        self.assertEqual(report['relations'][0]['binding'], 'source-observed path, not drag-bound')
        self.assertFalse((output / 'expected-connections.json').exists())


if __name__ == '__main__':
    unittest.main()
