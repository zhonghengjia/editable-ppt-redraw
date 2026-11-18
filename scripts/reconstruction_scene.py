"""Source-frame assembly over existing emitters; no alternate SVG/Paint engine.

One scene owns placement and paint order, while the manifest owns observations,
component content and authorization. Callbacks allow a qualified target adapter
without duplicating the native-component schema. Failed assembly is discarded,
never delivered as a partial success.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import heapq
import math
from pathlib import Path
from typing import Callable


def _rect(value):
    if (len(value) != 4 or any(isinstance(v, bool) or not isinstance(v, (int, float))
                              or not math.isfinite(v) for v in value)
            or min(value[2:]) <= 0):
        raise ValueError('rectangle requires finite [x,y,width,height] with positive size')
    return tuple(value)


@dataclass(frozen=True)
class SourceFrame:
    """Source region in pixels -> target viewport in inches, uniformly contained."""
    source: tuple
    viewport: tuple

    @property
    def scale(self):
        _, _, sw, sh = _rect(self.source)
        _, _, tw, th = _rect(self.viewport)
        return min(tw/sw, th/sh)

    def place(self, bbox):
        sx, sy, sw, sh = _rect(self.source)
        tx, ty, tw, th = _rect(self.viewport)
        x, y, w, h = _rect(bbox)
        if x < sx or y < sy or x+w > sx+sw+1e-8 or y+h > sy+sh+1e-8:
            raise ValueError('object bbox outside source frame')
        scale = self.scale
        return (tx+(tw-sw*scale)/2+(x-sx)*scale,
                ty+(th-sh*scale)/2+(y-sy)*scale, w*scale, h*scale)


@dataclass
class SceneNode:
    id: str
    bbox: tuple
    draw: Callable | RectLink
    role: str = 'component'
    parent: str | None = None
    behind: tuple = ()
    z: int = 0
    relation: tuple | None = None


@dataclass(frozen=True)
class EditingGroup:
    """A named editing unit, independent of background containment/paint edges."""
    id: str
    members: tuple


@dataclass(frozen=True)
class RectLink:
    """The existing, restricted top-level rectangular connector emitter."""
    source_port: str
    target_port: str
    color: str = '173D6A'
    width_pt: float = 1.8


@dataclass
class ReconstructionScene:
    frame: SourceFrame
    nodes: list[SceneNode] = field(default_factory=list)
    editing_groups: list[EditingGroup] = field(default_factory=list)

    def ordered(self):
        """Stable topological order; explicit dependencies take priority over z.

        A parent is a container background, not arbitrary anatomical grouping.
        Interleaved anatomy uses explicit behind edges and existing part trees.
        """
        nodes = self.nodes
        if not nodes or len(nodes) > 10000:
            raise ValueError('scene requires 1..10000 nodes')
        by = {}
        for node in nodes:
            if not isinstance(node.id, str) or not node.id.strip() or node.id in by:
                raise ValueError('scene IDs must be nonempty and unique')
            if (not callable(node.draw) and not isinstance(node.draw, RectLink)) or type(node.z) is not int:
                raise ValueError('invalid draw callback or z index')
            if node.role not in ('component', 'text', 'container', 'relation'):
                raise ValueError('unknown scene role')
            self.frame.place(node.bbox)
            by[node.id] = node
        edges = {n.id: set() for n in nodes}
        for node in nodes:
            if node.parent is not None:
                if node.parent not in by or by[node.parent].role != 'container':
                    raise ValueError('parent must reference a container background')
                px, py, pw, ph = by[node.parent].bbox
                x, y, w, h = node.bbox
                if x < px or y < py or x+w > px+pw+1e-8 or y+h > py+ph+1e-8:
                    raise ValueError('child geometry outside declared container')
                edges[node.parent].add(node.id)
            if not isinstance(node.behind, (list, tuple)):
                raise ValueError('behind requires a list of scene IDs')
            for target in node.behind:
                if target not in by:
                    raise ValueError('unknown layer target: ' + str(target))
                edges[node.id].add(target)
            if node.role == 'relation':
                if (not isinstance(node.relation, (tuple, list)) or len(node.relation) != 2
                        or any(v not in by or by[v].role == 'relation' for v in node.relation)):
                    raise ValueError('relation requires existing non-relation source/target IDs')
            elif node.relation is not None:
                raise ValueError('relation endpoints require relation role')
            if isinstance(node.draw, RectLink) and node.role != 'relation':
                raise ValueError('rectangular binding requires relation role and endpoints')
        indegree = {n.id: 0 for n in nodes}
        for targets in edges.values():
            for target in targets:
                indegree[target] += 1
        rank = {n.id: i for i, n in enumerate(nodes)}
        ready = [(n.z, rank[n.id], n.id) for n in nodes if not indegree[n.id]]
        heapq.heapify(ready)
        result = []
        while ready:
            _, _, identity = heapq.heappop(ready)
            result.append(by[identity])
            for target in sorted(edges[identity], key=rank.get):
                indegree[target] -= 1
                if not indegree[target]:
                    heapq.heappush(ready, (by[target].z, rank[target], target))
        if len(result) != len(nodes):
            raise ValueError('cyclic layer/containment constraints; do not guess order')
        self.group_plan(result)
        return result

    def group_plan(self, ordered):
        """Reject grouping that would reorder an interleaved source paint stack.

        Flat, disjoint groups are deliberate: arbitrary nested membership and
        cross-group bindings need another qualified profile, not guessed XML.
        """
        if not isinstance(self.editing_groups, (list, tuple)):
            raise ValueError('editing_groups requires a list')
        positions = {node.id: i for i, node in enumerate(ordered)}
        names, owners, result = set(positions), {}, []
        for group in self.editing_groups:
            if not isinstance(group, EditingGroup) or not isinstance(group.id, str) or not group.id.strip() or group.id in names:
                raise ValueError('editing group name must be nonempty and globally unique')
            names.add(group.id)
            if (not isinstance(group.members, (tuple, list)) or len(group.members) < 2
                    or any(not isinstance(v, str) or v not in positions for v in group.members)
                    or len(set(group.members)) != len(group.members)):
                raise ValueError('editing group requires at least two distinct existing scene items')
            if any(v in owners for v in group.members):
                raise ValueError('editing groups must be disjoint; nesting is unsupported')
            indices = sorted(positions[v] for v in group.members)
            if indices != list(range(indices[0], indices[-1]+1)):
                raise ValueError('interleaved paint order cannot be grouped without changing visual order')
            members = [ordered[i].id for i in indices]
            owners.update((v, group.id) for v in members)
            result.append((indices[0], group, members))
        for node in ordered:
            if isinstance(node.draw, RectLink) and (node.id in owners or any(v in owners for v in node.relation)):
                raise ValueError('rectangular bound links and endpoints must remain top-level')
        return sorted(result, key=lambda entry: entry[0])


def assemble_pptx(slide, scene):
    """Construct on an empty disposable slide; return actual top-level mappings.

    Do not save/deliver on exception. Callbacks return one top-level shape/group;
    structural output is inspected here but visual semantics remain source review.
    """
    if len(slide.shapes):
        raise ValueError('assemble on an empty disposable slide, preserving existing artifacts')
    ordered = scene.ordered()  # all placement/dependency errors before mutation
    inventory, relations, shapes = [], [], {}
    # A connector may be painted behind its nodes. Emit nodes first and move
    # the resulting XML back into the already validated paint order afterward.
    emission = [n for n in ordered if not isinstance(n.draw, RectLink)]
    emission += [n for n in ordered if isinstance(n.draw, RectLink)]
    for node in emission:
        before = len(slide.shapes)
        bounds = scene.frame.place(node.bbox)
        if isinstance(node.draw, RectLink):
            from native_vectors import add_rect_link
            shape = add_rect_link(slide, shapes[node.relation[0]], shapes[node.relation[1]],
                                  name=node.id, **vars(node.draw))
        else:
            shape = node.draw(slide, bounds, node.id, scene.frame.scale)
        if (len(slide.shapes) != before+1
                or getattr(shape, 'shape_id', None) != slide.shapes[-1].shape_id):
            raise ValueError('adapter must emit exactly one top-level shape/group; discard failed slide')
        shape.name = node.id
        shapes[node.id] = shape
        inventory.append({'id': node.id, 'role': node.role, 'source_bbox': list(node.bbox),
                          'shape_id': shape.shape_id, 'output_name': shape.name,
                          'placed_bounds_inches': list(bounds), 'parent_background': node.parent})
        if node.relation is not None:
            relations.append({'id': node.id, 'source': node.relation[0], 'target': node.relation[1],
                              'shape_id': shape.shape_id,
                              'binding': ('native rectangular sites; interactive behavior NOT_PERFORMED'
                                          if isinstance(node.draw, RectLink) else 'source-observed path, not drag-bound')})
    tree = slide.shapes._spTree
    for node in ordered:
        tree.insert_element_before(shapes[node.id]._element, 'p:extLst')
    groups, group_by_member = [], {}
    for _, group_spec, members in scene.group_plan(ordered):
        first = tree.index(shapes[members[0]]._element)
        group = slide.shapes.add_group_shape([shapes[v] for v in members])
        group.name = group_spec.id
        tree.remove(group._element)
        tree.insert(first, group._element)
        group_by_member.update((v, group.name) for v in members)
        groups.append({'id': group.name, 'output_name': group.name,
                       'shape_id': group.shape_id, 'members': members})
    by_id = {entry['id']: entry for entry in inventory}
    inventory = [by_id[node.id] for node in ordered]
    for entry in inventory:
        entry['editing_group'] = group_by_member.get(entry['id'])
    names = [el.get('name') for el in slide._element.iter('{http://schemas.openxmlformats.org/presentationml/2006/main}cNvPr')]
    if len(names) != len(set(names)):
        raise ValueError('duplicate output names; discard failed slide')
    return {'items': inventory, 'relations': relations, 'paint_order': [n.id for n in ordered],
            'top_level_paint_order': [s.name for s in slide.shapes], 'editing_groups': groups,
            'source_frame': list(scene.frame.source), 'viewport_inches': list(scene.frame.viewport),
            'visual_review': 'NOT_PERFORMED'}


def picture_draw(path, *, expected_sha256, crop=(0, 0, 0, 0), rotation=0):
    """Embed one approved picture through python-pptx, with checked aspect/crop.

    The manifest and component package audit own provenance, native-required
    roles, alpha-visible crop, effective DPI and anchors. This emitter does not
    infer backgrounds or silently rasterize any native item.
    """
    from raster_components import read_image
    path = Path(path)
    if (not isinstance(crop, (tuple, list)) or len(crop) != 4
            or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v < 1 for v in crop)
            or crop[0]+crop[2] >= 1 or crop[1]+crop[3] >= 1
            or type(rotation) not in (int, float) or rotation not in (0, 90, 180, 270)):
        raise ValueError('picture route supports explicit valid crop and orthogonal rotation only')

    def draw(slide, bbox, identity, source_scale):
        from pptx.util import Inches
        image = read_image(path, expected_sha256)
        try:
            iw, ih = image.size
        finally:
            image.close()
        x, y, w, h = bbox
        if rotation in (90, 270):
            x, y, w, h = x+(w-h)/2, y+(h-w)/2, h, w
        ratio = iw*(1-crop[0]-crop[2])/(ih*(1-crop[1]-crop[3]))
        if abs((w/h)/ratio-1) > 1e-6:
            raise ValueError('picture placement would distort approved cropped asset aspect ratio')
        shape = slide.shapes.add_picture(str(path), *(Inches(v) for v in (x, y, w, h)))
        shape.name = identity
        shape.crop_left, shape.crop_top, shape.crop_right, shape.crop_bottom = crop
        shape.rotation = rotation
        return shape
    return draw


def svg_draw(path, *, expected_sha256):
    """Keep source controls/viewBox through the existing native SVG emitter."""
    from native_vectors import add_svg_component
    from raster_components import digest
    path = Path(path)

    def draw(slide, bbox, identity, source_scale):
        if digest(path.read_bytes()) != expected_sha256:
            raise ValueError('SVG source hash changed')
        return add_svg_component(slide, path, *bbox, name=identity)['group']
    return draw


def manifest_component_draw(manifest, component_id, *, base_dir):
    from native_components import ManifestComponentBuilder
    builder=(manifest if isinstance(manifest,ManifestComponentBuilder)
             else ManifestComponentBuilder(manifest,base_dir=base_dir))

    def draw(slide, bbox, identity, source_scale):
        if builder.output_name(component_id) != identity:
            raise ValueError('scene identity must equal manifest component output_name')
        return builder.add(slide,component_id,*bbox)['group']
    return draw


def text_draw(text, *, font_size_px, color='222222', font='Arial', bold=False, align='left'):
    """Text sizes use the same source-to-target scale as geometry, not fixed pt."""
    if (not isinstance(text, str) or not text or not math.isfinite(font_size_px)
            or font_size_px <= 0 or align not in ('left', 'center', 'right')):
        raise ValueError('invalid native text specification')
    def draw(slide, bbox, identity, source_scale):
        from pptx.util import Inches, Pt
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
        shape = slide.shapes.add_textbox(*(Inches(v) for v in bbox))
        frame = shape.text_frame
        frame.clear()
        frame.word_wrap = True
        frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = 0
        frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        for i, line in enumerate(text.split('\n')):
            para = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
            para.text = line
            para.space_before = para.space_after = Pt(0)
            para.alignment = {'left': PP_ALIGN.LEFT, 'center': PP_ALIGN.CENTER, 'right': PP_ALIGN.RIGHT}[align]
            para.font.name, para.font.size, para.font.bold = font, Pt(font_size_px*source_scale*72), bold
            para.font.color.rgb = RGBColor.from_string(color.lstrip('#'))
        return shape
    return draw


def rectangle_draw(*, fill=None, stroke='222222', stroke_pt=1):
    def draw(slide, bbox, identity, source_scale):
        from pptx.util import Inches, Pt
        from pptx.enum.shapes import MSO_SHAPE
        from pptx.dml.color import RGBColor
        shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, *(Inches(v) for v in bbox))
        # This primitive declares no effects. Block the template's implicit shadow;
        # explicit Paint effects are emitted separately and are not normalized here.
        shape.shadow.inherit = False
        for target, value in ((shape.fill, fill), (shape.line.fill, stroke)):
            if value is None:
                target.background()
            else:
                target.solid()
                target.fore_color.rgb = RGBColor.from_string(value.lstrip('#'))
        shape.line.width = Pt(stroke_pt)
        return shape
    return draw
