# PyMatting-derived multilevel color estimator

Upstream: https://github.com/pymatting/pymatting
Commit: `6d5c4a6bed0e5672abac0bad078e594423ffe4fd`
Source: `pymatting/foreground/estimate_foreground_ml.py`
Copyright (c) 2020 PyMatting. License: MIT, reproduced in LICENSE.md.

The local joint_foreground.py adapts the multilevel initialization, nearest
resampling and local 2x2 F/B update mechanism. It replaces Numba/pixelwise updates
with bounded NumPy synchronous updates, fixes all observed opaque colors, and
exposes numerical projection and recomposition diagnostics. This is a modified
implementation and does not claim bit equivalence to upstream PyMatting.

No upstream package, model weights, images or executable module was installed or
run during source research. Keep this notice and LICENSE.md with the integrated
solver.
