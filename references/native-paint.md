# Native parts and continuous Paint

Read only when constructing native part trees, gradients, compositing or shared paint domains. Reuse the selected backend and serializer; [native-toolkit](native-toolkit.md) owns SVG input and connector interfaces.

## Executable native parts and Paint

Use `native_components.add_manifest_component(slide, manifest, component_id,
x, y, width, height, base_dir=manifest_directory)` to construct an inventory-backed
tree in the existing builder. Placement uses inches and aspect-preserving contain.
The part-tree schema is defined in [native-component-schema](native-component-schema.md).
For isolated geometry fixtures the lower-level `add_native_component` accepts the
same component value; production source-sampled work uses the manifest entrypoint,
which rechecks sampled colors and all declared regional/appearance contracts,
including source hash/size, before emitting anything. Missing sensitive-item
contracts fail before slide mutation. The lower-level geometry fixture helper
does not perform this manifest preflight and must not bypass it in source work.

Groups, local translation and positive uniform scale are composed through the tree.
An explicit `group_fill` owns paint across its real descendant geometry. A leaf
with `fill: {"kind":"group"}` inherits that paint instead of recalculating it in
the fragment's bounds. Intervening groups retain the inherited owner; an orphan
group fill, group fill on a stroke, or opacity attached to it is rejected. Groups
without this declaration keep their existing independent leaf fills. Do not add
invisible geometry to force a paint domain. The visible source host must establish
the required group bounds; arbitrary clipping or off-center PDF paint still needs
separate qualification. Regrouping or changing the host bounds changes this domain.
Children are emitted in back-to-front list order; a group is a contiguous paint
unit. Interleaved independent objects need source-supported visible-part grouping,
not a fabricated total depth order. A parent transform moves its nested parts;
this does not clip them or establish their scientific attachment. Source visibility,
contours and independent landmarks remain authoring inputs. For touching visible
pieces, construct the joint source partition under [component fidelity](source-tracing.md#marked-source-assemblies)
before passing its ordinary component trees here; independent closed-path fits
are not a coverage model. Shared native coordinates still require an actual render
check for antialias seams and a source-grounded ownership review.

Each leaf uses the existing SVG path parser and `native_vectors.path_shape_xml`.
Solid SVG imports and these trees share the same path/paint emitter, not two
competing OOXML implementations. The entire component is prepared before the slide
changes. Names are stable hierarchical paths; the returned `element_map` includes
actual shape IDs, immediate parent group IDs and initial bounds. Reopen to resolve
final geometry. The tree has no text/image nodes, no automatic segmentation,
arbitrary clipping, PDF backdrop blending, rotations or nonuniform/mirrored transforms.
The existing SVG path/element limits remain unchanged; tree depth is at most 16.

`native_paint.py` owns the supported Paint values:

- `null` or `{"kind":"none"}`: no fill.
- `"#AABBCC"` or `{"kind":"solid","color":"AABBCC","alpha":1}`.
- `{"kind":"linear","angle":90,"stops":[...]}`: Office linear gradient,
  clockwise degrees from a left-to-right direction; no automatic lighting inference.
- `{"kind":"path","focus":[0.3,0.25],"stops":[...]}`: Office circular path
  gradient. Stops use the circle circumscribing the actual paint owner's geometry
  bounds, and focus is relative to that circle's bounds. Existing Office stop
  coordinates are not source-radius coordinates. A shape's `xfrm` alone does not
  establish an independent paint domain. This is not arbitrary SVG radial/mesh
  equivalence.
- `{"kind":"group"}`: a leaf fill bound to its explicit ancestor `group_fill`.
  This selects an owner; it is not a standalone color or a composite operand.
- Each stop is `{"position":0,"color":"AABBCC","alpha":1}`. Use 2..32 stops,
  strictly increasing at Office's 1/100000 precision with endpoints 0 and 1.
  Colors are six-digit sRGB; alpha is 0..1. Paths use nonzero winding; compound
  holes remain real holes. Gradient strokes are not supported.
- `{"kind":"composite","mode":"multiply","backdrop":<Paint>,
  "source":{"kind":"solid","color":"804020","alpha":0.5},"opacity":0.6}`:
  a recomputable same-domain paint expression. `mode` is `normal`, `multiply` or
  `screen`; opacity defaults to 1 and is 0..1. The backdrop must be opaque solid
  or opaque-at-every-stop gradient; source must compile to a constant solid.
  Nesting is limited to 8 composites. Unknown fields/modes, transparent backdrops
  and gradient sources are rejected. This is not a group node or a second object.

Composite colors are computed per stop using encoded-sRGB compositing. For this
restricted case the operation is affine in the backdrop, so its existing angle,
focus, positions and continuous transitions are retained (8-bit channel rounding
can introduce up to half a code value per compilation). `normalize_paint` is the
single compiler used by both validation and the existing XML emitter. Preserve
the expression in the canonical part; do not replace it by its computed stops.
Input `source_samples` are recursively rechecked by the manifest builder; computed
colors are not labelled as directly sampled. Changing the source/backdrop recipe
requires regeneration. Independently moving underlying objects in PowerPoint does
not dynamically recomposite this fill. Do not apply it to a differently bounded
partial overlay, an unknown backdrop, a spatial mask, or a group of overlapping
children and claim equivalent rendering.

Paint is independent of path geometry. Changing a stop must not refit a contour,
move a nucleus or reorder layers. Source sampling is defined only in
[appearance-fidelity.md](appearance-fidelity.md); its returned Paint carries a
`source_samples` provenance record and is assigned directly to the leaf fill.
Do not replace continuous shading with hundreds of flat regions unless that
approximation and editing scope are explicitly selected.

For an independently established **centered circular** source profile, use
`native_paint.centered_radial_paint(stops, radius, bounds)` with actual owner bounds
`[x,y,width,height]` in the radius's units. It maps 2..31 source stops to Office's
circumscribed radius and adds a constant outer stop, within the existing 32-stop
limit. It does not fit source pixels, infer a center or accept an unqualified
elliptical/off-center mask. Keep the source profile/radius and recompute after
changing owner geometry; do not repeatedly rescale already compiled Office stops.

### Compositing scope and source alpha fields

Any part may declare `compositing: {"opacity":0.5,"alpha_mask":<Paint>}`; both
keys are optional (defaults 1 and null). This applies the mask and then constant
opacity to the completed part, including its stroke, or the group's composed
children. Nested boundaries remain nested. It does not multiply the opacity into
each overlapping leaf. The serializer emits native `effectDag` alpha effects;
omitting compositing leaves legacy XML unchanged. Geometry remains editable.

The mask is a solid, linear or circular path Paint with **white RGB and explicit
alpha**, not a colored luminosity image or inherited group fill. It uses the
actual effect owner's geometry bounds, not the component viewbox or an arbitrary
source crop. `source_samples` is color provenance and is not accepted as alpha
provenance. Mask recipes and their source mapping belong in the canonical builder;
the manifest entrypoint does not automatically re-extract or authenticate them.
Native effect editing is by canonical recipe/regeneration; GUI effect editing
is not qualified. Windows Office 16 qualification covers overlapping children,
nested opacity, linear/circular masks and save/reopen, not arbitrary PDF effects.

`spatial_masks.decode_mask_field(pixels, meaning=..., color_space=...)` interprets
at most one million supplied uint8 mask pixels: one-channel alpha, DeviceGray
luminosity, or DeviceRGB luminosity under PDF 32000-1 §11.5.3. Samples must already
be in the declared transparency-group space. RGB channel count alone is not
color-space evidence. This helper does not render mask groups, convert ICC/CMYK,
handle separate image alpha or execute non-identity transfer functions.

For an independently identified axis gradient, `fit_axis_mask(field, axis="x"
or "y", field_bbox=[x,y,w,h], owner_bbox=[x,y,w,h], stop_count=..., max_abs_error=...)`
fits 2..32 alpha stops in the declared source frame. The full owner must be covered;
all observed pixel centers inside it are checked against a preselected tolerance
in 0..0.1, including Office alpha quantization. Nonseparable fields fail rather
than becoming a one-dimensional average. Returned field/recipe hashes and errors
prove only the supplied sample fit, not source extraction, clipping, interpolation
between samples or final rendering. Retain original source hash and transform
evidence separately; compare the actual saved/reopened output under the appearance
contract before accepting it.

Raw PDF `blendmode`, isolation, knockout and soft-mask resources are not native
compositing inputs. Source-over native group opacity is not equivalent to a
non-isolated Multiply/Screen group over an external backdrop. No automatic mapping
of arbitrary two-dimensional fields, hidden support geometry, raster masks or
contour-distance shading is provided. For unsupported source effects, use the
explicitly selected source-rendered object-paint route in
[source-tracing](source-tracing.md), or report the remaining limitation.
That route reuses the native path emitter; it does not extend native blend support.
The mask semantics follow the [PDF standard](https://opensource.adobe.com/dc-acrobat-sdk-docs/standards/pdfstandards/pdf/PDF32000_2008.pdf);
native effect scope uses [DrawingML alpha modulation](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.drawing.alphamodulationeffect?view=openxml-3.0.1).

### Shared fill/stroke coverage

When a source's closed fill and centered round stroke have the same opaque paint
**before one shared mask/opacity**, compute their union once with
`native_support.fill_stroke_union(d, width, tolerance=...)`. Assign the shared
paint to the returned `d` as a fill, with no second stroke. This avoids applying
the mask twice at overlapping fill/stroke edges. Different fill/stroke colors,
open paths, dash patterns and other joins/alignment are outside this operation.

This optional Windows adapter uses installed WPF `GetWidenedPathGeometry` and
`Geometry.Combine`, with declared absolute source-unit tolerance. It returns a
bounded native approximation plus input hash/engine/tolerance evidence. It does
not install dependencies, guess widths, fix gaps by inflation, compute a mask,
or rasterize output. Its 5000-command bound is a safety limit, not permission to
ignore the source-part editing budget. Missing WPF or unsupported input fails
explicitly. Preserve the original path and stroke recipe and review final-source
edges as well as interiors. Other platforms need a separately qualified route.

Office's actual geometry-bound radial behavior is documented by the
[Microsoft Open Specifications team](https://learn.microsoft.com/en-us/answers/questions/2248059/non-preset-a-tilerect-behaves-strange-in-case-of-g).
Coverage geometry uses the existing
[WPF API](https://learn.microsoft.com/en-us/dotnet/api/system.windows.media.geometry.getwidenedpathgeometry)
and [implementation](https://github.com/dotnet/wpf/blob/main/src/Microsoft.DotNet.Wpf/src/PresentationCore/System/Windows/Media/Geometry.cs).

PowerPoint editing qualification uses actual saved/reopened files. In the tested
Office 16.0 COM interface, `GroupItems` enumerates leaves of nested groups even
for Office-authored groups. Ungroup the outer assembly once to select/move an
inner unit. Edit an independently painted leaf through that exact leaf, not the
group's aggregate `Fill` interface. For explicit group-owned paint, that aggregate
interface can change a child gradient while leaving `grpSpPr` unchanged. Change
the canonical `group_fill` and regenerate to preserve ownership; direct UI/COM
editing of that shared paint is not qualified. Do not claim all native gradients
have the same interactive editing surface. Keep grouping shallow enough for the
requested task and verify the exact edited owner after reopening.
