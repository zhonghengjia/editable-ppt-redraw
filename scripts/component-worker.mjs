// Local byte-only adapter. Upstream algorithms are pinned and unmodified.
import fs from 'node:fs';
import tracer from './vendor/imagetracer/imagetracer.cjs';
import pixelmatch from './vendor/pixelmatch/index.mjs';

const input = fs.readFileSync(0, 'utf8');
if (input.length > 24000000) throw new Error('component request exceeds limit');
const req = JSON.parse(input);
const {width, height} = req;
if (![width, height].every(v => Number.isInteger(v) && v > 0 && v <= 4096) || width * height > 1000000)
  throw new Error('component dimensions exceed profile');
function pixels(value) {
  if (typeof value !== 'string' || !/^[A-Za-z0-9+/]*={0,2}$/.test(value)) throw new Error('invalid RGBA encoding');
  const data = Uint8Array.from(Buffer.from(value, 'base64'));
  if (data.length !== width * height * 4) throw new Error('RGBA size mismatch');
  return data;
}
const first = pixels(req.first);

function edgeRing(points, reverse = false, compact = false) {
  const ordered = reverse ? [...points].reverse() : points;
  const corners = ordered.filter((b, i) => {
    const a = ordered[(i + ordered.length - 1) % ordered.length], c = ordered[(i + 1) % ordered.length];
    return (b.x - a.x) * (c.y - b.y) !== (b.y - a.y) * (c.x - b.x);
  });
  if (corners.length < 3) throw new Error('degenerate source boundary');
  let d = `M ${corners[0].x} ${corners[0].y}`;
  for (let i = 1; i < corners.length; i++) {
    const a = corners[i - 1], b = corners[i];
    if (compact) {
      if (a.x !== b.x && a.y !== b.y) throw new Error('non-lattice source edge');
      d += a.x === b.x ? `V${b.y}` : `H${b.x}`;
    } else d += ` L ${b.x} ${b.y}`;
  }
  return d + ' Z';
}

function edgeRegions(indexed, color, compact = false) {
  const paths = tracer.pathscan(tracer.layeringstep({array: indexed}, color), 0);
  return paths.filter(p => !p.isholepath).map(p => edgeRing(p.points, false, compact) + ' ' +
    p.holechildren.map(i => edgeRing(paths[i].points, true, compact)).join(' '));
}

function opaquePaintTree(colors, counts) {
  // Bounded color-space hierarchy, not spatial/biological instance inference.
  // Each parent covers exactly its observed descendant colors. Reusing its
  // representative paint avoids repeatedly tracing a cumulative 64-color tail.
  let nodes=colors.map((c,i)=>({members:[i], representative:i, weight:counts[i], rgb:c.slice(0,3)}))
    .filter(n=>colors[n.representative][3]===255);
  while(nodes.length>1) {
    let best=Infinity, pair=[0,1];
    for(let i=0;i<nodes.length;i++) for(let j=i+1;j<nodes.length;j++) {
      const cost=nodes[i].rgb.reduce((s,c,k)=>s+(c-nodes[j].rgb[k])**2,0);
      if(cost<best){best=cost;pair=[i,j];}
    }
    const [i,j]=pair,a=nodes[i],b=nodes[j],weight=a.weight+b.weight;
    const representative=counts[a.representative]>=counts[b.representative]?a.representative:b.representative;
    const parent={members:[...a.members,...b.members],representative,weight,
      rgb:a.rgb.map((v,k)=>(v*a.weight+b.rgb[k]*b.weight)/weight),children:[a,b]};
    nodes=nodes.filter((_,k)=>k!==i&&k!==j);nodes.push(parent);
  }
  const paints=[];
  function visit(node, inherited) {
    if(node.representative!==inherited) paints.push({label:node.representative,members:new Set(node.members)});
    for(const child of node.children??[]) visit(child,node.representative);
  }
  if(nodes.length)visit(nodes[0],null);
  return paints;
}

function paletteEdges(data, stacked = false) {
  // One immutable label map owns all color boundaries. No independent fits,
  // pixel omission, blur or palette nearest-color reassignment. Paint composition
  // may combine observed color supports without changing their visible assignment.
  if (!Number.isInteger(req.path_char_limit) || req.path_char_limit < 1)
    throw new Error('native path character limit required');
  const indexed = Array.from({length: height + 2}, () => Array(width + 2).fill(-1));
  const colors = [], lookup = new Map(), counts = [];
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const i = (y * width + x) * 4, color = Array.from(data.slice(i, i + 4)), key = color.join(',');
    if (!lookup.has(key)) { lookup.set(key, colors.length); colors.push(color); counts.push(0); }
    if (colors.length > 64) throw new Error('palette_edges requires at most 64 prepared RGBA colors');
    const label = lookup.get(key); indexed[y + 1][x + 1] = label; counts[label]++;
  }
  if (stacked && colors.some(c => c[3] !== 0 && c[3] !== 255))
    throw new Error('palette_stack requires opaque colors and binary support alpha');
  // Paint composition is selected BEFORE tracing. Hierarchical masks preserve the
  // visible quantized color at every source pixel; they never inspect a render.
  // Parent colors paint first, ties retain source order. All masks remain
  // inside the declared visible part, including every transparent source hole.
  const paintNodes=stacked?opaquePaintTree(colors,counts):colors.map((_,label)=>({label,members:new Set([label])}));
  if(stacked)for(let i=0;i<colors.length;i++)if(colors[i][3]===0)paintNodes.push({label:i,members:new Set([i])});
  const order=paintNodes.map(p=>p.label);
  const output = [], layers = []; let sourceRegions = 0;
  for (const {label,members} of paintNodes) {
    const color = colors[label];
    const layer = {rgba: color, pixels: counts[label], source_regions: 0, paths: []};
    layers.push(layer);
    if (color[3] === 0) continue; // Invisible pixels remain accounted for above.
    let scan = indexed, selected = label;
    if (stacked) {
      scan = indexed.map(row => row.map(value => members.has(value) ? 1 : 0));
      // Keep the upstream scanner's one-pixel sentinel outside the canvas.
      scan[0].fill(-1); scan[height+1].fill(-1);
      for (const row of scan) { row[0] = -1; row[width+1] = -1; }
      selected = 1;
      layer.painted_pixels = scan.reduce((n,row) => n+row.filter(v => v===1).length,0);
      layer.source_color_members=[...members];
    }
    const regions = edgeRegions(scan, selected, true);
    layer.source_regions = regions.length; sourceRegions += regions.length;
    let d = '', firstRegion = 0;
    const flush = (endRegion) => {
      if (!d) return;
      const id = `paint-path-${String(output.length + 1).padStart(4, '0')}`;
      layer.paths.push({id, region_range: [firstRegion, endRegion]});
      const fill = '#' + color.slice(0, 3).map(v => v.toString(16).padStart(2, '0')).join('');
      output.push(`<path id="${id}" fill="${fill}" fill-opacity="${color[3]/255}" d="${d}"/>`);
      d = ''; firstRegion = endRegion;
    };
    for (let i = 0; i < regions.length; i++) {
      if (regions[i].length > req.path_char_limit) throw new Error('one intact source region exceeds native path character limit');
      if (d.length + regions[i].length > req.path_char_limit) flush(i);
      d += regions[i];
    }
    flush(regions.length);
  }
  return {svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}">${output.join('')}</svg>`,
    partition: {layers, source_regions: sourceRegions, packed_paths: output.length,
      source_pixels: width * height, shared_boundaries: 'one_indexed_pixel_lattice',
      packing: 'intact_disjoint_same_fill_regions_with_holes', geometry_simplified: false,
      composition: stacked ? 'opaque_source_color_tree' : 'disjoint_color_faces',
      color_order: order, semantic_depth_inferred: false},
    options: {representation: stacked ? 'palette_stack' : 'palette_edges', pathomit: 0, simplification: 'exact_collinear_only',
      fill_rule: 'nonzero', coordinates: 'source_pixel_cell_corners', smoothing: false}};
}

function sourceEdges(data) {
  // Use pinned upstream pixel-cell boundaries BEFORE internodes/curve fitting.
  // Opposite hole winding makes one compound native path; no background masks.
  const indexed = Array.from({length: height + 2}, () => Array(width + 2).fill(-1));
  let fill = null, selected = 0;
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const i = (y * width + x) * 4, alpha = data[i + 3];
    if (alpha !== 0 && alpha !== 255) throw new Error('source_edges requires binary support alpha');
    indexed[y + 1][x + 1] = alpha ? 0 : 1;
    if (alpha) {
      const color = Array.from(data.slice(i, i + 3));
      if (fill && color.some((v, k) => v !== fill[k])) throw new Error('source_edges requires uniform support fill');
      fill = color; selected++;
    }
  }
  if (!selected || selected === width * height) throw new Error('source_edges requires separated nonempty support');
  const color = '#' + fill.map(v => v.toString(16).padStart(2, '0')).join('');
  const groups = edgeRegions(indexed, 0);
  return {svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}">` +
    groups.map(d => `<path fill="${color}" d="${d}"/>`).join('') + '</svg>',
    options: {representation: 'source_edges', pathomit: 0, simplification: 'exact_collinear_only',
      fill_rule: 'nonzero', coordinates: 'source_pixel_cell_corners', smoothing: false}};
}

let result;
if (req.action === 'trace') {
  const representation = req.representation ?? 'smooth';
  if (!['smooth', 'source_edges', 'palette_edges', 'palette_stack'].includes(representation)) throw new Error('unsupported representation');
  if (representation === 'palette_edges' || representation === 'palette_stack') {
    result = paletteEdges(first, representation === 'palette_stack');
  } else if (representation === 'source_edges') {
    result = sourceEdges(first);
  } else {
  if (!Number.isInteger(req.colors) || req.colors < 2 || req.colors > 64) throw new Error('colors must be 2..64');
  if (!Array.isArray(req.palette) || !req.palette.length || req.palette.length > req.colors ||
      !req.palette.every(c => ['r','g','b','a'].every(k => Number.isInteger(c[k]) && c[k] >= 0 && c[k] <= 255)))
    throw new Error('explicit source-derived RGBA palette required');
  const options = {
    numberofcolors: req.colors, pal: req.palette, colorsampling: 2, mincolorratio: 0,
    colorquantcycles: 1, layering: 0, pathomit: 0, linefilter: false,
    blurradius: 0, rightangleenhance: false, ltres: 0.25, qtres: 0.25,
    roundcoords: -1, scale: 1, viewbox: true, strokewidth: 0, desc: false
  };
  const traced = tracer.imagedataToTracedata({width, height, data: first}, options);
  result = {svg: tracer.getsvgstring(traced, options), options};
  }
} else if (req.action === 'compare') {
  if (!Number.isFinite(req.threshold) || req.threshold < 0 || req.threshold >= 1)
    throw new Error('threshold must be 0..<1');
  if (!Number.isInteger(req.window) || req.window < 1 || req.window > Math.min(width, height))
    throw new Error('window must fit region');
  const second = pixels(req.second);
  const options = {threshold: req.threshold, includeAA: true, checkerboard: false};
  result = {
    mismatch_pixels: pixelmatch(first, second, undefined, width, height, options),
    worst_window_pixels: pixelmatch(first, second, undefined, width, height, {...options, windowSize: req.window})
  };
} else throw new Error('unsupported action');
process.stdout.write(JSON.stringify(result));
