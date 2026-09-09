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
let result;
if (req.action === 'trace') {
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
