"""Known-truth color tests fixed before the proposed solver implementation."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from joint_foreground import estimate_foreground_background
from raster_components import digest
from source_layers import extract_layer, read_layer_bundle, validate_layer_options

OPTIONS = dict(kind='multilevel_joint_fb', regularization=1e-5,
               gradient_weight=1., small_size=32, small_iterations=30,
               large_iterations=8)


def color_truth(*, background='quadratic', variable_foreground=False):
    """Independent analytic RGB/coverage, with one-pixel and detached details."""
    yy, xx = np.mgrid[:72, :96]
    x, y = xx / 95, yy / 71
    alpha = np.clip((24-np.hypot(xx-47, yy-35))/7, 0, 1)
    alpha[35, 68:85] = np.maximum(alpha[35, 68:85], .7)
    alpha[34:37, 72:77] = np.maximum(alpha[34:37, 72:77], .4)
    alpha[14, 77:80] = .55
    alpha = np.rint(alpha*255).astype('uint8')
    a = alpha.astype(float)/255
    foreground = np.broadcast_to([42., 105., 158.], (72, 96, 3)).copy()
    if variable_foreground:
        foreground += np.stack((12*x, 8*y, -9*x), axis=2)
    if background == 'constant':
        back = np.broadcast_to([232., 220., 246.], foreground.shape).copy()
    elif background == 'affine':
        back = np.stack((210+25*x+6*y, 232-18*x+4*y, 245-8*x-7*y), axis=2)
    elif background == 'quadratic':
        back = np.stack((208+22*x+13*y*y+5*x*y,
                         224-14*x+12*y+4*x*x,
                         241-12*y+6*x*x-3*x*y), axis=2)
    else:
        raise ValueError(background)
    captured = np.rint(a[..., None]*foreground+(1-a[..., None])*back).astype('uint8')
    labels = np.full(alpha.shape, 255, dtype='uint8')
    labels[a == 0] = 0
    labels[a == 1] = 1
    return captured, alpha, foreground, back, labels


class FixedAlphaColors(unittest.TestCase):
    def test_nonuniform_background_color_improves_without_alpha_changes(self):
        image, alpha, truth, back, labels = color_truth()
        before = alpha.tobytes()
        solver_alpha=alpha/255.
        input_bytes=solver_alpha.tobytes()
        f, b, report = estimate_foreground_background(image, solver_alpha, labels, OPTIONS)
        band = (alpha > 25) & (alpha < 230)
        naive = float(np.abs(image[band].astype(float)-truth[band]).mean())
        error = float(np.abs(f[band]-truth[band]).mean())
        self.assertLess(error, 8)
        self.assertLess(error, .4*naive)
        residual = np.abs(alpha[..., None]/255*f+(1-alpha[..., None]/255)*b-image)
        self.assertLess(residual.mean(), 1)
        self.assertLess(residual.max(), 4)
        self.assertEqual(alpha.tobytes(), before)
        self.assertEqual(solver_alpha.tobytes(), input_bytes)
        np.testing.assert_array_equal(f[alpha == 255], image[alpha == 255])
        np.testing.assert_array_equal(b[alpha == 0], image[alpha == 0])
        self.assertEqual(report['alpha_changed_pixels'], 0)
        self.assertTrue(np.isfinite(f).all() and np.isfinite(b).all())

    def test_deterministic_color_estimates_and_all_opaque_anchors(self):
        image, alpha, _, _, labels = color_truth(background='affine', variable_foreground=True)
        # Even unmarked fully opaque output must retain the observed source RGB.
        labels[alpha == 255] = 255
        labels[35, 47] = 1
        f, b, report = estimate_foreground_background(image, alpha/255., labels, OPTIONS)
        f2, b2, report2 = estimate_foreground_background(image, alpha/255., labels, OPTIONS)
        np.testing.assert_array_equal(f, f2)
        np.testing.assert_array_equal(b, b2)
        np.testing.assert_array_equal(f[alpha == 255], image[alpha == 255])
        self.assertEqual(report, report2)

    def test_explicit_failures_and_no_input_mutation(self):
        image, alpha, _, _, labels = color_truth()
        for a, marks, options in ((alpha/255., labels, dict(OPTIONS, regularization=0)),
                                  (alpha/255.+np.nan, labels, OPTIONS),
                                  (alpha/255., np.zeros_like(labels), OPTIONS),
                                  (alpha[:10]/255., labels, OPTIONS)):
            with self.subTest(), self.assertRaises(ValueError):
                estimate_foreground_background(image, a, marks, options)
        saved = image.copy(), labels.copy()
        estimate_foreground_background(image, alpha/255., labels, OPTIONS)
        np.testing.assert_array_equal(image, saved[0])
        np.testing.assert_array_equal(labels, saved[1])


@unittest.skipUnless(importlib.util.find_spec('scipy'), 'Run in the qualified SciPy extraction interpreter')
class JointBundle(unittest.TestCase):
    def test_explicit_union_and_v3_reader(self):
        from test_source_layers_spatial import fixture
        with tempfile.TemporaryDirectory() as temp:
            source, _, _, _, plan = fixture(Path(temp))
            plan['matting'] = dict(epsilon=1e-7, solver='direct',
                                  foreground_estimation=copy.deepcopy(OPTIONS))
            validate_layer_options(plan)
            outputs, evidence = extract_layer(source, plan)
            self.assertEqual(evidence['bundle_version'], 3)
            self.assertEqual(set(outputs), {'context_mask','alpha','rgba','trimap','occlusion_mask',
                'coverage_adjustment','reconstructed_color','estimated_background','recomposition_residual'})
            self.assertEqual(evidence['foreground_estimation']['alpha_changed_pixels'], 0)
            alpha = np.asarray(Image.open(io.BytesIO(outputs['alpha'])))
            trimap = np.asarray(Image.open(io.BytesIO(outputs['trimap'])))
            rgb = np.asarray(Image.open(io.BytesIO(outputs['rgba'])))[:, :, :3]
            original = np.asarray(Image.open(source))
            np.testing.assert_array_equal(rgb[alpha == 255], original[alpha == 255])
            self.assertTrue((alpha[trimap == 255] == 255).all())
            self.assertTrue((alpha[trimap == 0] == 0).all())
            folder=Path(temp)/'layer'; folder.mkdir()
            for key,value in outputs.items(): (folder/(key+'.png')).write_bytes(value)
            receipt=folder/'candidate.json'; receipt.write_text(json.dumps(evidence), encoding='utf8')
            binding=dict(path=str(receipt), sha256=digest(receipt.read_bytes()))
            read_layer_bundle(binding, plan['source_sha256'], plan['context_bbox'])
            saved=copy.deepcopy(evidence)
            evidence['foreground_estimation']['output_recomposition_mean_error']=float('nan')
            receipt.write_text(json.dumps(evidence), encoding='utf8'); binding['sha256']=digest(receipt.read_bytes())
            with self.assertRaises(ValueError): read_layer_bundle(binding, plan['source_sha256'], plan['context_bbox'])
            evidence=saved
            bad=copy.deepcopy(plan); bad['matting']['background_patches']=[[0,0,4,4]]
            with self.assertRaises(ValueError): validate_layer_options(bad)
            evidence.pop('bundle_version')
            receipt.write_text(json.dumps(evidence), encoding='utf8'); binding['sha256']=digest(receipt.read_bytes())
            with self.assertRaises(ValueError): read_layer_bundle(binding, plan['source_sha256'], plan['context_bbox'])

    def test_legacy_constant_and_affine_keep_seven_file_contract(self):
        from test_source_layers_spatial import fixture
        with tempfile.TemporaryDirectory() as temp:
            for spatial in (False, True):
                source, _, _, _, plan=fixture(Path(temp), spatial=spatial)
                outputs,evidence=extract_layer(source, plan)
                self.assertEqual(set(outputs), {'context_mask','alpha','rgba','trimap',
                    'occlusion_mask','coverage_adjustment','reconstructed_color'})
                self.assertNotIn('bundle_version', evidence)
                self.assertNotIn('foreground_estimation', evidence)
                self.assertEqual('background_model' in evidence, spatial)


if __name__ == '__main__':
    unittest.main()
