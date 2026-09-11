"""Source alpha-field interpretation and bounded native axis-gradient fitting.

This is not a raster artwork converter. Fields have explicit mask meaning and a
source-coordinate owner. Returned Paint plugs into the existing compositing tree.
"""
from __future__ import annotations
import hashlib
import json
import numpy as np
from native_paint import normalize_paint, scalar


def decode_mask_field(pixels, *, meaning, color_space, transfer='identity'):
    """Decode supplied mask samples, not alpha inferred from a color picture.

    Samples must already be in the declared transparency-group color space,
    not simply have the same channel count. DeviceRGB luminosity follows PDF
    32000-1 section 11.5.3 (encoded components, not sRGB linear-light luminance).
    ICC/CMYK conversion and rendering a mask group are the caller's separate work.
    """
    if transfer != 'identity':
        raise ValueError('non-identity mask transfer requires its actual source function')
    a = np.asarray(pixels)
    if a.dtype != np.uint8 or a.ndim not in (2,3) or a.size == 0 or np.prod(a.shape[:2]) > 1_000_000:
        raise ValueError('mask needs bounded nonempty uint8 samples')
    if meaning == 'alpha' and color_space == 'alpha' and a.ndim == 2:
        return a.astype(float)/255
    if meaning == 'luminosity' and color_space == 'DeviceGray' and a.ndim == 2:
        return a.astype(float)/255
    if meaning == 'luminosity' and color_space == 'DeviceRGB' and a.ndim == 3 and a.shape[2] == 3:
        return (a.astype(float) @ np.array([.30,.59,.11]))/255
    raise ValueError('unsupported mask meaning/channel/color-space combination')


def fit_axis_mask(field, *, axis, field_bbox, owner_bbox, stop_count, max_abs_error):
    """Fit continuous native alpha along a declared source X or Y direction.

    Bounds are [x,y,w,h] in one source frame. Field must cover the entire owner.
    Checks every supplied pixel center inside it; no crop to output-derived masks.
    Fails instead of splitting artwork, dropping pixels or changing representation.
    Pixel fitting does not prove interpolation, semantic ownership or final rendering.
    """
    a = np.asarray(field)
    if a.ndim != 2 or a.size == 0 or a.size > 1_000_000 or a.dtype.kind not in 'fiu':
        raise ValueError('bounded scalar mask field required')
    a = a.astype(float)
    if not np.all(np.isfinite(a)) or np.any(a < 0) or np.any(a > 1):
        raise ValueError('alpha field must be finite within 0..1')
    if axis not in ('x','y') or type(stop_count) is not int or not 2 <= stop_count <= 32:
        raise ValueError('axis x/y and 2..32 stops required')
    tolerance = scalar(max_abs_error,'mask fit tolerance',0,.1)
    def box(value):
        if not isinstance(value,(list,tuple)) or len(value)!=4:
            raise ValueError('mask bounds need [x,y,w,h]')
        vals=[scalar(v,'mask coordinate',-1e9,1e9) for v in value]
        if min(vals[2:]) <= 0: raise ValueError('positive mask extent required')
        return vals
    fx,fy,fw,fh=box(field_bbox); ox,oy,ow,oh=box(owner_bbox)
    if fx>ox or fy>oy or fx+fw<ox+ow or fy+fh<oy+oh:
        raise ValueError('field must cover complete effect owner; no extrapolated backdrop')
    h,w=a.shape
    xs=fx+(np.arange(w)+.5)*fw/w; ys=fy+(np.arange(h)+.5)*fh/h
    ix=(xs>=ox)&(xs<=ox+ow); iy=(ys>=oy)&(ys<=oy+oh)
    if not ix.any() or not iy.any():raise ValueError('owner has no observed pixel centers')
    values=a[np.ix_(iy,ix)]
    coords=(xs[ix]-ox)/ow if axis=='x' else (ys[iy]-oy)/oh
    if len(coords)<stop_count:raise ValueError('insufficient observed positions for requested stops')
    profile=values.mean(axis=0 if axis=='x' else 1)
    pos=coords*(stop_count-1); k=np.minimum(pos.astype(int),stop_count-2); t=pos-k
    design=np.zeros((len(pos),stop_count)); rows=np.arange(len(pos))
    design[rows,k]=1-t; design[rows,k+1]=t
    if np.linalg.matrix_rank(design)<stop_count:raise ValueError('mask stop fit is underdetermined')
    stops=np.clip(np.linalg.lstsq(design,profile,rcond=None)[0],0,1)
    # Include actual Office 1/100000 alpha quantization in source residuals.
    stops=np.rint(stops*100000)/100000
    predicted=design@stops
    residual=np.abs(values-(predicted[None,:] if axis=='x' else predicted[:,None]))
    error=float(residual.max())
    if error > tolerance:
        raise ValueError(f'field not representable by declared axis gradient: max error {error:.6f} > {tolerance:.6f}')
    paint=normalize_paint(dict(kind='linear',angle=0 if axis=='x' else 90,
        stops=[dict(position=float(p),color='FFFFFF',alpha=float(v)) for p,v in zip(np.linspace(0,1,stop_count),stops)]))
    recipe=dict(axis=axis,field_bbox=list(field_bbox),owner_bbox=list(owner_bbox),
                stop_count=stop_count,max_abs_error=tolerance)
    return dict(paint=paint,evidence=dict(field_sha256=hashlib.sha256(a.astype('<f8').tobytes()).hexdigest(),
        field_shape=list(a.shape),recipe=recipe,recipe_sha256=hashlib.sha256(json.dumps(recipe,sort_keys=True).encode()).hexdigest(),
        observed_pixels=int(residual.size),max_abs_error=error,mean_abs_error=float(residual.mean()),
        status='SOURCE_FIELD_FIT_ONLY',final_render='NOT_VERIFIED'))
