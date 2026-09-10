"""Component contract, generation preflight and actual PPTX media readback.

No network, model invocation, image editing or presentation authoring. The manifest
owns asset identity; readback never treats a builder assertion as visual proof.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import math
import posixpath
import re
from pathlib import Path
from xml.etree import ElementTree as ET
import zipfile

NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
NATIVE = {'native_primitive', 'native_composite'}
PROTECTED = {'text', 'chart', 'table', 'connector'}
IDENTITY = (1., 0., 0., 1., 0., 0.)


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(data):
    return hashlib.sha256(data).hexdigest()


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def vector(value, length):
    return isinstance(value, list) and len(value) == length and all(number(v) for v in value)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def hash_string(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def sequence(value):
    return value if isinstance(value, list) else []


def generation_preflight(request, tool_available=True, manifest=None):
    """Validate a proposed call, not permission enforcement around external tools.

    The agent must run this before the built-in call. No call is made here.
    """
    errors = []
    if not isinstance(request, dict):
        return {'valid': False, 'errors': ['generation request must be an object']}
    if not tool_available:
        errors.append('built-in image generation unavailable; no automatic fallback')
    if request.get('provider') != 'builtin_imagegen':
        errors.append('only explicitly selected built-in image generation is supported')
    if not nonempty(request.get('authorization')):
        errors.append('generation authorization is required')
    if request.get('attempt') not in (1, 2) or type(request.get('attempt')) is not int:
        errors.append('attempt must be 1 or 2 within the shared correction budget')
    if request.get('attempt') == 2 and not nonempty(request.get('correction_reason')):
        errors.append('second attempt needs evidence-driven correction_reason')
    for field in ('prompt', 'subject', 'style'):
        if not nonempty(request.get(field)):
            errors.append(f'generation.{field} is required')
    invariants = request.get('invariants')
    if not isinstance(invariants, list) or not invariants or not all(nonempty(v) for v in invariants):
        errors.append('generation invariants must be a nonempty string list')
    refs = request.get('references')
    if not isinstance(refs, list):
        errors.append('references must explicitly list transmitted inputs, including [] for text only')
    for ref in sequence(refs):
        if not isinstance(ref, dict):
            errors.append('reference must be an object'); continue
        if ref.get('role') not in ('structure', 'style', 'edit_target'):
            errors.append('reference role must identify structure, style or edit_target')
        if not all(nonempty(ref.get(f)) for f in ('path', 'authorization', 'transmitted_scope')) or not hash_string(ref.get('sha256')):
            errors.append('each reference needs its own file hash, scope and upload authorization')
    errors.extend(load('appearance_fidelity').validate_generation(request, manifest))
    return {'valid': not errors, 'errors': errors, 'executes_remote_call': False}


def validate_contract(manifest):
    try:
        return _validate_contract(manifest)
    except (TypeError, ValueError, KeyError) as exc:
        return [f'invalid component field type or value: {exc}']


def _validate_contract(manifest):
    """Optional schema-1 extension. Legacy manifests remain unchanged."""
    errors = []
    policy = manifest.get('editing_policy', 'native')
    assets = manifest.get('component_assets')
    instances = manifest.get('component_instances')
    inventory = sequence(manifest.get('source_inventory', []))
    uses_components = any(isinstance(i, dict) and i.get('representation') == 'component_raster' for i in inventory)
    if policy not in ('native', 'hybrid'):
        errors.append('editing_policy must be native or hybrid')
    if assets is None and instances is None and not uses_components and policy != 'hybrid':
        return errors
    if policy != 'hybrid' or not nonempty(manifest.get('hybrid_authorization')):
        errors.append('component assets require hybrid policy and explicit hybrid_authorization')
    if manifest.get('execution_profile') == 'fast':
        errors.append('hybrid needs at least standard profile')
    if not isinstance(assets, list) or not assets or not isinstance(instances, list) or not instances:
        return errors + ['hybrid requires nonempty component_assets and component_instances']
    asset_map, instance_map, output_keys = {}, {}, set()
    for asset in assets:
        if not isinstance(asset, dict):
            errors.append('asset must be an object'); continue
        aid = asset.get('asset_id')
        if not nonempty(aid) or aid in asset_map:
            errors.append('asset_id missing or duplicated'); continue
        asset_map[aid] = asset
        for field in ('path', 'origin', 'authorization', 'editing_unit'):
            if not nonempty(asset.get(field)):
                errors.append(f'{aid}: {field} is required')
        if not hash_string(asset.get('sha256')):
            errors.append(f'{aid}: invalid sha256')
        kind = asset.get('source_kind')
        if kind not in ('local', 'licensed', 'source_crop', 'generated'):
            errors.append(f'{aid}: unsupported source_kind')
        if asset.get('extent') != 'object':
            errors.append(f'{aid}: raster editing extent must be object, never native internals')
        if asset.get('content_class') not in ('illustration', 'evidence'):
            errors.append(f'{aid}: component must be illustration or evidence, not a panel/tile')
        if asset.get('contains_native_required') is not False:
            errors.append(f'{aid}: must explicitly exclude flattened native-required content')
        if not isinstance(asset.get('requires_alpha'), bool):
            errors.append(f'{aid}: requires_alpha must be explicit')
        if not number(asset.get('min_visible_pixels')) or asset['min_visible_pixels'] < 1:
            errors.append(f'{aid}: min_visible_pixels must be positive')
        if not number(asset.get('min_dpi')) or asset['min_dpi'] <= 0:
            errors.append(f'{aid}: min_dpi must be positive')
        inv = asset.get('invariants')
        if not isinstance(inv, list) or not inv or not all(nonempty(s) for s in inv):
            errors.append(f'{aid}: source/approved structure invariants required')
        if kind == 'licensed' and not all(nonempty(asset.get(f)) for f in ('license', 'attribution')):
            errors.append(f'{aid}: license and attribution required')
        if kind == 'source_crop':
            crop = asset.get('source_bbox')
            if not hash_string(asset.get('source_sha256')) or not vector(crop, 4) or min(crop[:2]) < 0 or min(crop[2:]) <= 0:
                errors.append(f'{aid}: source hash and source pixel bbox required')
        if kind == 'generated':
            errors.extend(f'{aid}: {e}' for e in generation_preflight(asset.get('generation'), manifest=manifest)['errors'])
            if asset.get('content_class') != 'illustration' or asset.get('comparison') != 'approved_surrogate':
                errors.append(f'{aid}: generation cannot invent evidence or claim exact source copying')
            generation = asset.get('generation')
            if not isinstance(generation, dict) or generation.get('status') != 'succeeded':
                errors.append(f'{aid}: failed/pending generation is not an asset')
        elif asset.get('comparison') != 'source_exact':
            errors.append(f'{aid}: local/source/library asset comparison must be source_exact')
    for item in instances:
        if not isinstance(item, dict):
            errors.append('instance must be an object'); continue
        iid = item.get('instance_id')
        if not nonempty(iid) or iid in instance_map:
            errors.append('instance_id missing or duplicated'); continue
        instance_map[iid] = item
        if item.get('asset_id') not in asset_map:
            errors.append(f'{iid}: unknown asset_id')
        if not nonempty(item.get('output_name')) or not isinstance(item.get('slide'), int) or isinstance(item.get('slide'), bool) or item['slide'] < 1:
            errors.append(f'{iid}: output_name and one-based slide required')
        else:
            key = (item['slide'], item['output_name'])
            if key in output_keys:
                errors.append(f'{iid}: duplicate output selector')
            output_keys.add(key)
        box = item.get('bbox_inches')
        if not vector(box, 4) or min(box[:2]) < 0 or min(box[2:]) <= 0:
            errors.append(f'{iid}: valid bbox_inches required')
        crop = item.get('crop')
        if not vector(crop, 4) or any(v < 0 or v >= 1 for v in crop) or crop[0]+crop[2] >= 1 or crop[1]+crop[3] >= 1:
            errors.append(f'{iid}: crop must be valid left,top,right,bottom fractions')
        if not number(item.get('rotation')):
            errors.append(f'{iid}: rotation must be explicit degrees')
        if not number(item.get('placement_tolerance_inches')) or not 0 <= item['placement_tolerance_inches'] <= .05:
            errors.append(f'{iid}: placement tolerance must be 0..0.05 inches')
        anchors = item.get('anchors')
        if not isinstance(anchors, list):
            errors.append(f'{iid}: anchors must be explicit, including []')
        anchor_ids = set()
        for anchor in sequence(anchors):
            if not isinstance(anchor, dict):
                errors.append(f'{iid}: invalid anchor'); continue
            if not nonempty(anchor.get('id')) or anchor['id'] in anchor_ids:
                errors.append(f'{iid}: invalid or duplicate anchor id')
            else:
                anchor_ids.add(anchor['id'])
            uv = anchor.get('uv')
            if not vector(uv, 2) or not all(0 <= v <= 1 for v in uv) or not vector(anchor.get('expected_inches'), 2):
                errors.append(f'{iid}: anchor needs source-image uv and planned slide coordinates')
    referenced = set()
    for item in inventory:
        if not isinstance(item, dict):
            continue
        iid = item.get('component_instance')
        if item.get('representation') == 'component_raster':
            if iid not in instance_map:
                errors.append(f"{item.get('id')}: unknown component_instance")
            elif iid in referenced:
                errors.append(f'{iid}: one instance cannot flatten multiple inventory items')
            referenced.add(iid)
            if item.get('role') in PROTECTED or item.get('native_required') is True:
                errors.append(f"{item.get('id')}: native-required role cannot be rasterized")
        else:
            if iid is not None:
                errors.append('native item cannot claim a component picture')
            if item.get('representation') not in NATIVE:
                errors.append('hybrid inventories migrate all pictures to component_raster; do not mix legacy exceptions')
            if not nonempty(item.get('output_name')):
                errors.append(f"{item.get('id')}: hybrid native coverage requires exact output_name")
    if set(instance_map) != referenced:
        errors.append('component instances must map one-to-one to source inventory')
    if set(asset_map) != {i.get('asset_id') for i in instances if isinstance(i, dict)}:
        errors.append('every component asset must have an instance')
    if 'appearance_fidelity' in manifest:
        for aid, asset in asset_map.items():
            if asset.get('source_kind') != 'generated':
                continue
            owned = {i.get('id') for i in inventory if isinstance(i, dict)
                     and instance_map.get(i.get('component_instance'), {}).get('asset_id') == aid}
            request = asset.get('generation')
            binding = request.get('appearance_binding', {}) if isinstance(request, dict) else {}
            bound = binding.get('item_ids') if isinstance(binding, dict) else None
            if not isinstance(bound, list) or any(not isinstance(i, str) for i in bound) or set(bound) != owned:
                errors.append(f'{aid}: appearance binding must cover exactly this asset inventory')
    if manifest.get('raster_exceptions'):
        errors.append('hybrid asset records replace legacy raster_exceptions; do not duplicate authority')
    return errors


def multiply(a, b):
    return (a[0]*b[0]+a[2]*b[1], a[1]*b[0]+a[3]*b[1],
            a[0]*b[2]+a[2]*b[3], a[1]*b[2]+a[3]*b[3],
            a[0]*b[4]+a[2]*b[5]+a[4], a[1]*b[4]+a[3]*b[5]+a[5])


def point(m, x, y):
    return [m[0]*x+m[2]*y+m[4], m[1]*x+m[3]*y+m[5]]


def rectangle_union(boxes):
    """Exact union of axis-aligned bounds; a risk indicator, not alpha area."""
    xs=sorted({x for b in boxes for x in (b[0],b[0]+b[2])})
    area=0.
    for x1,x2 in zip(xs,xs[1:]):
        spans=sorted((b[1],b[1]+b[3]) for b in boxes if b[0] < x2 and b[0]+b[2] > x1)
        height=0.; end=-math.inf
        for start,stop in spans:
            height += max(0,stop-max(start,end)); end=max(end,stop)
        area += (x2-x1)*height
    return area


def transform(xfrm, group=False):
    if xfrm is None:
        raise ValueError('missing transform')
    off, ext = xfrm.find('a:off', NS), xfrm.find('a:ext', NS)
    if off is None or ext is None:
        raise ValueError('incomplete transform')
    x,y = float(off.get('x')),float(off.get('y'))
    w,h = float(ext.get('cx')),float(ext.get('cy'))
    if not all(math.isfinite(v) for v in (x,y,w,h)) or min(w,h) <= 0:
        raise ValueError('nonpositive transform extent')
    flipx = -1 if xfrm.get('flipH') in ('1','true') else 1
    flipy = -1 if xfrm.get('flipV') in ('1','true') else 1
    r = math.radians(float(xfrm.get('rot',0))/60000)
    if not math.isfinite(r):
        raise ValueError('nonfinite rotation')
    rotate = (math.cos(r)*flipx, math.sin(r)*flipx, -math.sin(r)*flipy, math.cos(r)*flipy,0,0)
    m = multiply((1,0,0,1,x+w/2,y+h/2),multiply(rotate,(1,0,0,1,-w/2,-h/2)))
    if group:
        co,ce = xfrm.find('a:chOff',NS), xfrm.find('a:chExt',NS)
        if co is None or ce is None or min(float(ce.get('cx')),float(ce.get('cy'))) <= 0:
            raise ValueError('invalid group child coordinates')
        sx,sy = w/float(ce.get('cx')),h/float(ce.get('cy'))
        m = multiply(m,(sx,0,0,sy,-float(co.get('x'))*sx,-float(co.get('y'))*sy))
    else:
        m = multiply(m,(w,0,0,h,0,0))
    if not all(math.isfinite(v) for v in m):
        raise ValueError('nonfinite group transform')
    return m


def read_objects(archive):
    """Recursive DrawingML transforms; UV matrix maps picture frame to slide EMU."""
    existing = load('audit-pptx-editability')
    parts, size = existing.slide_parts_in_order(archive)
    objects = []
    for slide, part in enumerate(parts,1):
        root = ET.fromstring(archive.read(part))
        rels = existing.read_relationships(archive,part)
        def walk(parent, matrix=IDENTITY, parent_error=None):
            for child in parent:
                tag = child.tag.split('}')[-1]
                if tag == 'grpSp':
                    try:
                        gm = multiply(matrix,transform(child.find('p:grpSpPr/a:xfrm',NS),True))
                        walk(child,gm,parent_error)
                    except (ValueError,TypeError) as exc:
                        walk(child,matrix,str(exc))
                    continue
                if tag not in ('pic','sp','cxnSp','graphicFrame'):
                    continue
                name = existing.object_name(child)
                record = dict(slide=slide,name=name,kind=tag,part=part,xml=ET.tostring(child).decode(),
                              text=''.join(n.text or '' for n in child.findall('.//a:t',NS)))
                if tag == 'pic':
                    record['target'] = existing.picture_target(child,rels,part)
                    try:
                        if parent_error:
                            raise ValueError(parent_error)
                        m = multiply(matrix,transform(child.find('p:spPr/a:xfrm',NS)))
                        record['matrix'] = [v/914400 for v in m]
                        corners = [point(record['matrix'],*uv) for uv in ((0,0),(1,0),(1,1),(0,1))]
                        record['corners_inches'] = corners
                        record['bbox_inches'] = [min(p[0] for p in corners),min(p[1] for p in corners),
                                                  max(p[0] for p in corners)-min(p[0] for p in corners),
                                                  max(p[1] for p in corners)-min(p[1] for p in corners)]
                        src = child.find('p:blipFill/a:srcRect',NS)
                        record['crop'] = [float(src.get(k,0))/100000 if src is not None else 0 for k in ('l','t','r','b')]
                        record['rotation'] = math.degrees(math.atan2(m[1],m[0]))%360
                        if abs(m[0]*m[2]+m[1]*m[3]) > 1e-7*math.hypot(m[0],m[1])*math.hypot(m[2],m[3]):
                            record['unsupported'] = 'nonorthogonal nested transform'
                        if m[0]*m[3]-m[1]*m[2] <= 0:
                            record['unsupported'] = 'reflected picture requires independent qualification'
                        preset = child.find('p:spPr/a:prstGeom',NS)
                        if child.find('p:spPr/a:custGeom',NS) is not None or (preset is not None and preset.get('prst') != 'rect'):
                            record['unsupported'] = 'nonrectangular picture clipping'
                        if any(child.find('.//a:'+tag,NS) is not None for tag in ('effectLst','effectDag','tile','alphaModFix','duotone','lum','grayscl','clrChange','scene3d','sp3d')):
                            record['unsupported'] = 'picture effect/tile/3D rendering is not qualified'
                    except (ValueError,TypeError) as exc:
                        record['unsupported'] = str(exc)
                objects.append(record)
        tree = root.find('p:cSld/p:spTree',NS)
        if tree is not None:
            walk(tree)
    return objects,size


def audit(artifact, manifest, manifest_path=None):
    errors = validate_contract(manifest)
    report = dict(valid=not errors, errors=errors, unverified=[], instances=[], assets=[],
                  claim_boundary='Media identity and placement only; scientific truth and visual fidelity require rendered review.')
    if errors:
        return report
    if manifest.get('editing_policy','native') != 'hybrid':
        return report
    if Path(artifact).suffix.lower() != '.pptx':
        report['unverified'].append('hybrid package audit currently supports PPTX only'); return report
    base = Path(manifest_path).resolve().parent if manifest_path else Path.cwd()
    raster = load('audit-raster-asset-integrity')
    with zipfile.ZipFile(artifact) as archive:
        objects,size = read_objects(archive)
        assets = {a['asset_id']:a for a in manifest['component_assets']}
        blobs = {}
        for aid,a in assets.items():
            try:
                blob = (base/a['path']).read_bytes()
                if sha(blob) != a['sha256']:
                    raise ValueError('asset file hash mismatch')
                from PIL import Image
                with Image.open(io.BytesIO(blob)) as image:
                    if image.getexif().get(274,1) != 1:
                        raise ValueError('EXIF orientation must be normalized before hashing/placement')
                integrity = raster.audit_asset(base/a['path'],8,.02,32,.05,.96)
                report['assets'].append(dict(asset_id=aid,integrity=integrity))
                errors.extend(f'{aid}: {e}' for e in integrity['errors']+integrity['risks'])
                if a['requires_alpha'] and not integrity.get('meaningful_alpha'):
                    errors.append(f'{aid}: required transparency missing (painted checkerboard is opaque)')
                if integrity.get('frame_count') != 1:
                    errors.append(f'{aid}: animated/multi-frame assets unsupported')
                if a['source_kind'] == 'source_crop':
                    source = (base/manifest['source']['path']).read_bytes()
                    if sha(source) != a['source_sha256']:
                        errors.append(f'{aid}: source crop origin hash mismatch')
                    with Image.open(io.BytesIO(source)) as src:
                        x,y,w,h=a['source_bbox']
                        if x+w > src.width or y+h > src.height:
                            errors.append(f'{aid}: declared crop exceeds source pixels')
                if a['source_kind'] == 'generated':
                    for ref in a['generation']['references']:
                        if sha((base/ref['path']).read_bytes()) != ref['sha256']:
                            errors.append(f'{aid}: transmitted reference hash mismatch')
                blobs[aid] = blob
            except (OSError,ValueError) as exc:
                errors.append(f'{aid}: {exc}')
        bound = set()
        for i in manifest['component_instances']:
            iid,aid = i['instance_id'],i['asset_id']
            matches = [o for o in objects if (o['slide'],o['name']) == (i['slide'],i['output_name'])]
            if len(matches) != 1 or matches[0]['kind'] != 'pic':
                errors.append(f'{iid}: exact picture selector missing, duplicated or not p:pic'); continue
            o = matches[0]; bound.add((o['slide'],o['name']))
            entry = {k:v for k,v in o.items() if k != 'xml'}
            entry['instance_id'] = iid; entry['asset_id'] = aid
            report['instances'].append(entry)
            try:
                embedded = archive.read(o['target'])
                entry['embedded_sha256'] = sha(embedded)
                if entry['embedded_sha256'] != assets[aid]['sha256']:
                    errors.append(f'{iid}: embedded media differs from approved asset')
            except (KeyError,TypeError) as exc:
                errors.append(f'{iid}: missing embedded media: {exc}'); continue
            if 'unsupported' in o:
                report['unverified'].append(f"{iid}: {o['unsupported']}"); continue
            tol = i['placement_tolerance_inches']
            if any(abs(a-b)>tol+1e-6 for a,b in zip(i['bbox_inches'],o['bbox_inches'])):
                errors.append(f'{iid}: actual placement differs from plan')
            if any(abs(a-b)>1e-5 for a,b in zip(i['crop'],o['crop'])):
                errors.append(f'{iid}: actual crop differs from plan')
            if abs((o['rotation']-i['rotation']+180)%360-180) > .001:
                errors.append(f'{iid}: actual rotation differs from plan')
            if any(x < -1e-6 or y < -1e-6 or x > size[0]/914400+1e-6 or y > size[1]/914400+1e-6 for x,y in o['corners_inches']):
                errors.append(f'{iid}: transformed picture outside slide')
            if o['bbox_inches'][2]*o['bbox_inches'][3] >= .8*size[0]*size[1]/914400**2 and assets[aid]['content_class'] != 'evidence':
                errors.append(f'{iid}: whole-composition picture is not an independent component')
            a = assets[aid]
            metrics = raster.audit_placement(embedded,o['matrix'],o['crop'],a['min_dpi'],a['min_visible_pixels'])
            entry['placement_integrity'] = metrics
            errors.extend(f'{iid}: {e}' for e in metrics['errors'])
            entry['anchors'] = []
            l,t,r,b = o['crop']
            if l+r < 1 and t+b < 1:
                for anchor in i['anchors']:
                    u,v = anchor['uv']; p = point(o['matrix'],(u-l)/(1-l-r),(v-t)/(1-t-b))
                    entry['anchors'].append({'id':anchor['id'],'actual_inches':p})
                    if not l <= u <= 1-r or not t <= v <= 1-b:
                        errors.append(f"{iid}: anchor {anchor['id']} cropped away")
                    if math.dist(p,anchor['expected_inches']) > tol+1e-6:
                        errors.append(f"{iid}: anchor {anchor['id']} moved from planned connection")
        for slide in {i['slide'] for i in report['instances']}:
            boxes=[i['bbox_inches'] for i in report['instances'] if i['slide']==slide and
                   'bbox_inches' in i and assets[i['asset_id']]['content_class']!='evidence']
            coverage=rectangle_union(boxes)/(size[0]*size[1]/914400**2)
            if coverage >= .8:
                report['unverified'].append(f'slide {slide}: combined picture bounds cover {coverage:.1%}; possible tiled composition, independent semantic review required')
        for o in objects:
            if o['kind'] == 'pic' and (o['slide'],o['name']) not in bound:
                errors.append(f"unregistered picture on slide {o['slide']}: {o['name']}")
        for item in manifest['source_inventory']:
            if item.get('representation') not in NATIVE:
                continue
            matches = [o for o in objects if (o['slide'],o['name']) == (item.get('output_slide',1),item['output_name'])]
            if len(matches) != item.get('required_count',1) or any(o['kind'] == 'pic' or ET.fromstring(o['xml']).find('.//a:blip',NS) is not None for o in matches):
                errors.append(f"{item['id']}: required native object coverage failed")
        # Inherited media cannot evade registration inside a master/layout/background.
        for name in archive.namelist():
            if re.match(r'ppt/(slideMasters|slideLayouts)/[^/]+\.xml$',name):
                if ET.fromstring(archive.read(name)).find('.//a:blip',NS) is not None:
                    report['unverified'].append(f'inherited media needs separate scope: {name}')
        for name in {o['part'] for o in objects}:
            if ET.fromstring(archive.read(name)).find('.//p:bg//a:blip',NS) is not None:
                errors.append('raster slide background is not a registered component')
    report['valid'] = not errors
    return report


def verify_replacement(before, after, slide, name, expected_sha256):
    """Qualify regenerated files: same instance geometry, all unrelated object XML/media.

    This does not replace files or promise interactive connector rerouting.
    """
    errors = []
    def snapshot(path):
        with zipfile.ZipFile(path) as z:
            objs,size = read_objects(z)
            for o in objs:
                if o['kind'] == 'pic':
                    o['media_sha256'] = sha(z.read(o['target']))
                    # Relationship IDs are package-local references, not object
                    # identity. Compare their resolved bytes, retaining shape IDs.
                    root = ET.fromstring(o['xml'])
                    for blip in root.findall('.//a:blip', NS):
                        rid = blip.get('{'+NS['r']+'}embed')
                        if rid is not None:
                            blip.set('{'+NS['r']+'}embed', o['media_sha256'])
                    o['xml'] = ET.tostring(root).decode()
                    o['target'] = o['media_sha256']
            return objs,size
    a,asize = snapshot(before); b,bsize = snapshot(after)
    key = lambda o:(o['slide'],o['name'])
    target = (slide,name)
    aa = [o for o in a if key(o)==target]; bb = [o for o in b if key(o)==target]
    if asize != bsize or len(aa)!=1 or len(bb)!=1 or aa[0]['kind']!='pic' or bb[0]['kind']!='pic':
        return {'valid':False,'errors':['replacement target/slide size mismatch']}
    for field in ('matrix','crop','rotation','unsupported'):
        if aa[0].get(field)!=bb[0].get(field):
            errors.append('replacement changed '+field)
    for o in (aa[0],bb[0]):
        root = ET.fromstring(o['xml'])
        for blip in root.findall('.//a:blip',NS):
            blip.attrib.pop('{'+NS['r']+'}embed',None)
        o['identity_xml'] = ET.tostring(root)
    if aa[0]['identity_xml'] != bb[0]['identity_xml']:
        errors.append('replacement changed instance identity or non-media properties')
    if bb[0].get('media_sha256') != expected_sha256:
        errors.append('replacement media hash mismatch')
    if [o for o in a if key(o)!=target] != [o for o in b if key(o)!=target]:
        errors.append('unrelated object/media changed')
    return {'valid':not errors,'errors':errors,'interactive_drag_follow':'NOT_VERIFIED'}
