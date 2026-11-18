"""Bounded fixed-alpha foreground/background color estimation with NumPy.

Adapted from PyMatting's multilevel F/B initialization and local 2x2 color
updates, commit 6d5c4a6bed0e5672abac0bad078e594423ffe4fd:
https://github.com/pymatting/pymatting/blob/6d5c4a6bed0e5672abac0bad078e594423ffe4fd/pymatting/foreground/estimate_foreground_ml.py
Copyright (c) 2020 PyMatting, MIT; retain third_party/PyMatting/LICENSE.md.

Local changes: vectorized synchronous (Jacobi) rather than pixelwise Numba
updates; explicit opaque-color anchors, shape/iteration bounds and diagnostic
residuals. Alpha is an input, never an optimization variable. Smooth inferred
F/B are one possible decomposition, not recovered physical ground truth.
"""
from __future__ import annotations

import math
import numpy as np

MAX_COLOR_PIXELS = 250_000
OPTION_FIELDS = {'kind', 'regularization', 'gradient_weight', 'small_size',
                 'small_iterations', 'large_iterations'}


def validate_color_options(options):
    if (not isinstance(options, dict) or set(options) != OPTION_FIELDS
            or options['kind'] != 'multilevel_joint_fb'):
        raise ValueError('foreground_estimation needs explicit multilevel_joint_fb settings')
    for name in ('regularization', 'gradient_weight'):
        value = options[name]
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError('finite color regularization/gradient weight required')
    if options['regularization'] <= 0 or options['gradient_weight'] < 0:
        raise ValueError('positive color regularization and nonnegative gradient weight required')
    for name, high in (('small_size', 128), ('small_iterations', 100),
                       ('large_iterations', 100)):
        if type(options[name]) is not int or not 1 <= options[name] <= high:
            raise ValueError('bounded positive integer color schedule required: ' + name)


def _nearest(array, height, width):
    """Nearest mapping used at both sides of the explicit multilevel schedule."""
    ys = np.arange(height)*array.shape[0]//height
    xs = np.arange(width)*array.shape[1]//width
    return array[ys[:, None], xs[None, :]].copy()


def _neighbors(array):
    padding = ((1, 1), (1, 1)) + ((0, 0),)*(array.ndim-2)
    padded = np.pad(array, padding, mode='edge')
    return (padded[:-2, 1:-1], padded[2:, 1:-1],
            padded[1:-1, :-2], padded[1:-1, 2:])


def _weighted_neighbors(array, weights):
    result = np.zeros_like(array)
    for neighbor, weight in zip(_neighbors(array), weights):
        result += weight[..., None]*neighbor
    return result


def estimate_foreground_background(rgb, alpha, labels, options):
    """Return estimated F/B in RGB codes and diagnostics, leaving inputs intact.

    rgb: finite HxWx3 RGB codes in 0..255, alpha: HxW in 0..1.
    labels: existing 0=hard BG, 1=hard FG, other values=unknown ownership.
    Every alpha=1 F and alpha=0 B pixel is fixed to its observed RGB, including
    unmarked opaque regions. Hard labels must agree with those endpoints.
    """
    validate_color_options(options)
    image = np.asarray(rgb, dtype=np.float64)
    a = np.asarray(alpha, dtype=np.float64)
    marks = np.asarray(labels)
    if (a.ndim != 2 or image.shape != a.shape+(3,) or marks.shape != a.shape
            or min(a.shape) < 2 or a.size > MAX_COLOR_PIXELS
            or not np.isfinite(image).all() or not np.isfinite(a).all()
            or not np.isfinite(marks).all() or np.any((image < 0)|(image > 255))
            or np.any((a < 0)|(a > 1))):
        raise ValueError('finite matching bounded RGB/alpha/labels required for color estimation')
    fg, bg = marks == 1, marks == 0
    if not fg.any() or not bg.any() or np.any(a[fg] != 1) or np.any(a[bg] != 0):
        raise ValueError('color estimation requires agreeing hard foreground/background anchors')
    normalized = image/255
    # Full-resolution opaque means remain available even when a tiny pyramid
    # level has no foreground sample after nearest resampling.
    f = normalized[a == 1].mean(axis=0)[None, None, :]
    b = normalized[a == 0].mean(axis=0)[None, None, :]
    h0, w0 = a.shape
    n_levels = int(math.ceil(math.log2(max(h0, w0))))
    schedule = []
    clipped_updates = 0
    max_unbounded_excursion = 0.
    for level in range(n_levels+1):
        height = max(1, round(h0**(level/n_levels)))
        width = max(1, round(w0**(level/n_levels)))
        color = _nearest(normalized, height, width)
        coverage = _nearest(a, height, width)
        f = _nearest(f, height, width)
        b = _nearest(b, height, width)
        opaque_fg, opaque_bg = coverage == 1, coverage == 0
        f[opaque_fg] = color[opaque_fg]
        b[opaque_bg] = color[opaque_bg]
        weights = [options['regularization'] + options['gradient_weight']*
                   np.abs(coverage-neighbor) for neighbor in _neighbors(coverage)]
        weight_sum = sum(weights)
        other = 1-coverage
        diagonal_f = coverage*coverage+weight_sum
        diagonal_b = other*other+weight_sum
        off_diagonal = coverage*other
        determinant = diagonal_f*diagonal_b-off_diagonal*off_diagonal
        if not np.isfinite(determinant).all() or np.any(determinant <= 0):
            raise ValueError('degenerate/nonfinite fixed-alpha color system')
        iterations = options['small_iterations'] if max(height, width) <= options['small_size'] else options['large_iterations']
        last_change = 0.
        for _ in range(iterations):
            rhs_f = coverage[..., None]*color+_weighted_neighbors(f, weights)
            rhs_b = other[..., None]*color+_weighted_neighbors(b, weights)
            new_f = (diagonal_b[..., None]*rhs_f-off_diagonal[..., None]*rhs_b)/determinant[..., None]
            new_b = (diagonal_f[..., None]*rhs_b-off_diagonal[..., None]*rhs_f)/determinant[..., None]
            if not np.isfinite(new_f).all() or not np.isfinite(new_b).all():
                raise ValueError('nonfinite fixed-alpha foreground/background estimate')
            # Projection is part of the bounded estimate, not an exact inverse.
            # Count projected unknown channels and preserve all observed anchors.
            new_f[opaque_fg] = color[opaque_fg]
            new_b[opaque_bg] = color[opaque_bg]
            clipped_updates += int(((new_f < 0)|(new_f > 1)).sum()+((new_b < 0)|(new_b > 1)).sum())
            max_unbounded_excursion = max(max_unbounded_excursion,
                float(np.maximum(-new_f, new_f-1).max(initial=0)),
                float(np.maximum(-new_b, new_b-1).max(initial=0)))
            np.clip(new_f, 0, 1, out=new_f)
            np.clip(new_b, 0, 1, out=new_b)
            last_change = max(float(np.abs(new_f-f).max()), float(np.abs(new_b-b).max()))
            f, b = new_f, new_b
        schedule.append(dict(size=[width, height], iterations=iterations,
                             last_max_color_change=255*last_change))
    f, b = f*255, b*255
    f[a == 1] = image[a == 1]
    b[a == 0] = image[a == 0]
    residual = np.abs(a[..., None]*f+(1-a[..., None])*b-image)
    return f, b, dict(kind='multilevel_joint_fb', update='NumPy synchronous 2x2 / fixed schedule',
        options=dict(options), schedule=schedule, total_iterations=sum(row['iterations'] for row in schedule),
        alpha_changed_pixels=0, opaque_foreground_anchors=int((a == 1).sum()),
        opaque_background_anchors=int((a == 0).sum()), hard_foreground_anchors=int(fg.sum()),
        hard_background_anchors=int(bg.sum()), projected_channel_updates=clipped_updates,
        maximum_unbounded_excursion=255*max_unbounded_excursion,
        float_recomposition_mean_error=float(residual.mean()),
        float_recomposition_max_error=float(residual.max()),
        convergence='fixed schedule completed; convergence not certified',
        uncertainty='F and B are smooth estimated colors conditional on the fixed alpha')
