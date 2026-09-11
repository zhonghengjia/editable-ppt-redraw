# Native component manifest schema

This is a conditional extension of the [visual manifest](visual-manifest.md). Read before writing `native_components`; basic AutoShapes/text need no part-tree schema.

## Executable native component contract (single authority)

Optional `native_components` extends schema 1 with construction inputs, not another
source inventory or an automatic reconstruction result. Each of 1..100 entries has
exactly `id`, `output_name`, `viewbox: [x,y,width,height]`, and `parts`. `id` uniquely
references a `native_composite` inventory item; its optional inventory output_name
must agree. The viewbox describes local geometry, not an alternative source image.

Each part has unique component-local `id` (no slash), a descriptive `role`, and a
nonempty source/approval-grounded `observation`. Groups have `children` and may
define `group_fill` using one concrete Paint; leaves have
SVG path `d` and `fill`. Optional `translate: [x,y]` and positive uniform `scale`
compose in the parent's local frame. A group cannot also contain path/fill fields.
Leaves optionally declare solid `stroke` and local `stroke_width` (default 0).
Leaves may inherit an explicit ancestor's group paint as defined in
[native-paint](native-paint.md); inherited paint has no independent leaf
opacity. Group source sampling uses the same provenance checks as leaf Paint.
Both leaves and groups optionally declare `compositing` under the
[native toolkit's scope contract](native-paint.md#compositing-scope-and-source-alpha-fields).
List order is back-to-front. Output names are `component/ancestor/part`; the builder
rejects collisions. Node/transform/paint fields are strict, so an unsupported
rotation, clipping, raw opacity or PDF blend-mode field cannot silently disappear.

Paint values and numeric bounds have one authority in [native-paint.md](native-paint.md).
Source sampling/provenance is defined in [appearance-fidelity.md](appearance-fidelity.md).
Do not copy those schemas into separate manifests or store a second color truth.
This compact synthetic example demonstrates syntax, not a biological template:

```json
{
  "native_components": [{
    "id": "source-object-01", "output_name": "object-01", "viewbox": [0,0,100,100],
    "parts": [{
      "id": "assembly", "role": "object", "observation": "Synthetic API example",
      "children": [{
        "id": "body", "role": "surface", "observation": "Synthetic curved boundary",
        "d": "M10 20 C35 0 85 10 90 50 C85 90 20 95 10 20 Z",
        "fill": {"kind":"path", "focus":[0.3,0.25], "stops":[
          {"position":0,"color":"F4DFDD"}, {"position":1,"color":"A86173"}
        ]}
      }, {
        "id":"detail", "role":"inner part", "observation":"Synthetic internal detail",
        "d":"M40 40 L60 40 L60 60 L40 60 Z", "fill":"#704F69"
      }]
    }]
  }]
}
```

Use `native_components.add_manifest_component` from the existing builder with its
ordinary placement inputs. It emits real paths/groups, consumes source-sampled
Paint and returns the actual output mapping. Separate text/relationships remain
ordinary native objects. New fields do not change existing manifests without this
extension. Structural validation does not prove observations correct, parts attached
or colors faithful; the established source/final-render checks retain their scope.
