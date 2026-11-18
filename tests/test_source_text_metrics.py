"""Local source-ink controls without invoking PowerPoint or an OCR provider."""

from hashlib import sha256
from importlib.util import find_spec
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from source_text_metrics import measure_manifest


FONT_ROOT = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
ARIAL = FONT_ROOT / "arial.ttf"
ARIAL_BOLD = FONT_ROOT / "arialbd.ttf"
FITZ_AVAILABLE = find_spec("pymupdf") is not None or find_spec("fitz") is not None


def rectangular_marks(background=255, foreground=0):
    image = Image.new("L", (160, 80), background)
    draw = ImageDraw.Draw(image)
    for left in (40, 55, 76):
        draw.rectangle((left, 22, left + 8, 31), fill=foreground)
    return image


class SourceTextMetricsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "input.png"
        self.manifest = self.root / "input.json"
        self.output = self.root / "measurements"

    def write_inputs(self, image, *, items=None, slide_width=True):
        image.save(self.source)
        manifest = {
            "source": {"path": self.source.name, "sha256": sha256(self.source.read_bytes()).hexdigest(),
                       "width": image.width, "height": image.height},
            "source_inventory": items if items is not None else [
                {"role": "text", "id": "observed", "bbox": [20, 10, 100, 64], "text": "ABC"}
            ],
        }
        if slide_width:
            manifest["construction"] = {"slide_width_inches": image.width / 36}
        self.manifest.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        return manifest

    def test_source_geometry_dark_text_and_output_binding(self):
        expected = self.write_inputs(rectangular_marks())
        manifest_bytes = self.manifest.read_bytes()
        source_bytes = self.source.read_bytes()
        result = measure_manifest(self.manifest, self.output)
        item = result["items"][0]
        self.assertEqual(result["status"], "ADVISORY")
        self.assertEqual(result["source"], expected["source"])
        self.assertEqual(result["manifest"]["sha256"], sha256(manifest_bytes).hexdigest())
        self.assertEqual(result["source_font_scale_pt_per_px"], 2)
        self.assertEqual(item["status"], "INK_MEASURED")
        self.assertEqual(item["ink_bbox"], [40, 22, 45, 10])
        self.assertEqual(item["line_bands"], [{"ink_bbox": [40, 22, 45, 10]}])
        self.assertEqual(item["ink_pixels"], 270)
        self.assertEqual(item["ink_polarity"], "dark")
        self.assertEqual(item["font_suggestion"]["reason"], "not_requested")
        self.assertEqual(json.loads((self.output / "measurements.json").read_text(encoding="utf-8")), result)
        self.assertTrue((self.output / "overview.png").is_file())
        with Image.open(self.output / item["crop_path"]) as crop:
            self.assertEqual(crop.tobytes(), rectangular_marks().crop((20, 10, 120, 74)).tobytes())
        with Image.open(self.output / item["mask_path"]) as mask:
            self.assertEqual(mask.size, (100, 64))
            self.assertEqual(mask.getbbox(), (20, 12, 65, 22))
        self.assertEqual(self.manifest.read_bytes(), manifest_bytes)
        self.assertEqual(self.source.read_bytes(), source_bytes)

    def test_light_text_on_dark_background_and_explicit_line_bands(self):
        image = rectangular_marks(background=12, foreground=245)
        image.paste(image.crop((35, 20, 90, 34)), (35, 48))
        items = [{"id": "multiline", "role": "text", "bbox": [20, 10, 100, 64], "text": "ABC\nABC"}]
        self.write_inputs(image, items=items, slide_width=False)
        result = measure_manifest(self.manifest, self.output)
        item = result["items"][0]
        self.assertIsNone(result["source_font_scale_pt_per_px"])
        self.assertEqual(item["status"], "INK_MEASURED")
        self.assertEqual(item["ink_polarity"], "light")
        self.assertEqual(item["line_bands"], [
            {"ink_bbox": [40, 22, 45, 10]}, {"ink_bbox": [40, 50, 45, 10]},
        ])

    def test_scaled_canvas_is_rejected_before_output(self):
        data = self.write_inputs(rectangular_marks())
        for canvas in ({'width':320,'height':160}, {'width':160,'height':80.5},
                       {'width':True,'height':80}, None):
            data['canvas'] = canvas
            self.manifest.write_text(json.dumps(data),encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'source-pixel canvas'):
                measure_manifest(self.manifest,self.output)
            self.assertFalse(self.output.exists())
        data['canvas'] = {'width':160,'height':80}
        self.manifest.write_text(json.dumps(data),encoding='utf-8')
        self.assertEqual(measure_manifest(self.manifest,self.output)['status'],'ADVISORY')

    def test_fractional_bounds_preserve_declared_box_and_quantize_outward(self):
        box = [20.5,10.25,99.75,63.5]
        self.write_inputs(rectangular_marks(), items=[{'id':'fractional','role':'text','bbox':box,'text':'ABC'}])
        item = measure_manifest(self.manifest,self.output)['items'][0]
        self.assertEqual(item['source_bbox'],box)
        self.assertEqual(item['measurement_bbox'],[20,10,101,64])
        self.assertEqual(item['ink_bbox'],[40,22,45,10])
        with Image.open(self.output/item['crop_path']) as crop:
            self.assertEqual(crop.tobytes(), rectangular_marks().crop((20,10,121,74)).tobytes())

    def test_blank_crop_reports_no_ink(self):
        self.write_inputs(Image.new("L", (160, 80), 100))
        item = measure_manifest(self.manifest, self.output)["items"][0]
        self.assertEqual(item["status"], "AMBIGUOUS")
        self.assertIn("no_detectable_ink", item["uncertainty"])
        self.assertIsNone(item["ink_bbox"])
        self.assertEqual(item["line_bands"], [])
        self.assertEqual(item["ink_pixels"], 0)

    def test_boundary_and_detached_single_pixel_are_preserved(self):
        image = rectangular_marks()
        draw = ImageDraw.Draw(image)
        draw.rectangle((20, 22, 24, 31), fill=0)
        draw.point((74, 20), fill=0)
        self.write_inputs(image)
        result = measure_manifest(self.manifest, self.output)["items"][0]
        self.assertIn("ink_touches_crop_edge", result["uncertainty"])
        self.assertEqual(result["edge_contacts"], ["left"])
        self.assertEqual(result["ink_bbox"], [20, 20, 65, 12])
        self.assertEqual(result["ink_pixels"], 321)
        with Image.open(self.output / result["mask_path"]) as mask:
            self.assertEqual(mask.getpixel((0, 12)), 255)
            self.assertEqual(mask.getpixel((54, 10)), 255)

    def test_explicit_context_padding_keeps_placement_and_clamps_to_image(self):
        image = rectangular_marks()
        items = [{'id':'label', 'role':'text', 'bbox':[40,22,45,10], 'text':'ABC'}]
        self.write_inputs(image, items=items)
        original = self.manifest.read_bytes()
        direct = measure_manifest(self.manifest, self.output)['items'][0]
        self.assertIn('ink_touches_crop_edge', direct['uncertainty'])
        padded = measure_manifest(self.manifest, self.root/'padded', context_padding_px=4)['items'][0]
        self.assertEqual(padded['source_bbox'], [40,22,45,10])
        self.assertEqual(padded['measurement_bbox'], [36,18,53,18])
        self.assertEqual(padded['ink_bbox'], [40,22,45,10])
        self.assertNotIn('ink_touches_crop_edge', padded['uncertainty'])
        large = measure_manifest(self.manifest, self.root/'large', context_padding_px=128)['items'][0]
        self.assertEqual(large['measurement_bbox'], [0,0,160,80])
        self.assertEqual(self.manifest.read_bytes(), original)
        for invalid in (-1, True, 129, 1.5):
            with self.assertRaisesRegex(ValueError, 'context_padding_px'):
                measure_manifest(self.manifest, self.root/'invalid', context_padding_px=invalid)
        self.assertFalse((self.root/'invalid').exists())

    def test_low_contrast_isolated_from_font_recommendation(self):
        self.write_inputs(rectangular_marks(background=120, foreground=110))
        item = measure_manifest(self.manifest, self.output, font_file=ARIAL)["items"][0]
        self.assertIn("low_luminance_contrast", item["uncertainty"])
        self.assertEqual(item["gray_separation"], 10)
        self.assertEqual(item["ink_pixels"], 270)
        self.assertEqual(item["font_suggestion"]["status"], "NOT_ESTIMATED")

    def test_mixed_polarity_rule_and_line_count_are_visible_uncertainties(self):
        image = rectangular_marks(background=128)
        draw = ImageDraw.Draw(image)
        draw.rectangle((90, 22, 98, 31), fill=255)
        draw.line((32, 38, 103, 38), fill=0)
        self.write_inputs(image)
        item = measure_manifest(self.manifest, self.output, font_file=ARIAL)["items"][0]
        self.assertIn("suspected_mixed_polarity", item["uncertainty"])
        self.assertIn("suspected_thin_rule", item["uncertainty"])
        self.assertIn("line_count_disagrees_with_transcription", item["uncertainty"])
        self.assertEqual(item["font_suggestion"]["status"], "NOT_ESTIMATED")
        with Image.open(self.output / item["mask_path"]) as mask:
            self.assertEqual(mask.getpixel((13, 28)), 255)

    def test_source_change_prevents_output_and_bad_dimensions_fail(self):
        self.write_inputs(rectangular_marks())
        rectangular_marks(background=120).save(self.source)
        with self.assertRaisesRegex(ValueError, "source hash"):
            measure_manifest(self.manifest, self.output)
        self.assertFalse(self.output.exists())
        data = self.write_inputs(rectangular_marks())
        data["source"]["width"] += 1
        self.manifest.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "dimensions"):
            measure_manifest(self.manifest, self.output)
        self.assertFalse(self.output.exists())

    def test_select_text_item_and_preserve_existing_output(self):
        items = [
            {"id": "box", "role": "geometry", "bbox": [0, 0, 1, 1]},
            {"id": "one", "role": "text", "bbox": [20, 10, 100, 36], "text": "ABC"},
            {"id": "two", "role": "text", "bbox": [20, 45, 100, 30], "text": "ABC"},
        ]
        self.write_inputs(rectangular_marks(), items=items)
        for invalid in (["box"], ["missing"], []):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, "must select"):
                measure_manifest(self.manifest, self.output, item_ids=invalid)
        report = measure_manifest(self.manifest, self.output, item_ids=["two"])
        self.assertEqual([item["id"] for item in report["items"]], ["two"])
        before = (self.output / "measurements.json").read_bytes()
        with self.assertRaises(FileExistsError):
            measure_manifest(self.manifest, self.output, item_ids=["one"])
        self.assertEqual((self.output / "measurements.json").read_bytes(), before)

    @unittest.skipUnless(ARIAL.is_file() and ARIAL_BOLD.is_file() and FITZ_AVAILABLE, "requires Arial and PyMuPDF")
    def test_font_size_uses_same_actual_face_and_text(self):
        image = Image.new("L", (370, 150), 255)
        items = []
        for index, text in enumerate(("xxxxxx", "HHHHHH", "Hybrid group")):
            y = index * 50
            ImageDraw.Draw(image).text((17, y + 6), text, fill=0, font=ImageFont.truetype(str(ARIAL), 32))
            items.append({"id": str(index), "role": "text", "bbox": [0, y, 365, 49], "text": text})
        self.write_inputs(image, items=items)
        report = measure_manifest(self.manifest, self.output, font_file=ARIAL)
        self.assertEqual(report["font_candidate"]["sha256"], sha256(ARIAL.read_bytes()).hexdigest())
        heights = [item["ink_bbox"][3] for item in report["items"]]
        self.assertEqual(len(set(heights)), 3)
        for item in report["items"]:
            fit = item["font_suggestion"]
            self.assertEqual(fit["status"], "ADVISORY_ESTIMATE", item)
            self.assertAlmostEqual(fit["font_size_px"], 32, delta=1.5)
            self.assertAlmostEqual(fit["font_size_pt"], 64, delta=3)
        wrong_face = measure_manifest(self.manifest, self.root / "wrong-face", font_file=ARIAL_BOLD)
        self.assertEqual(wrong_face["items"][0]["font_suggestion"]["reason"], "font_mismatch")

    @unittest.skipUnless(ARIAL.is_file() and FITZ_AVAILABLE, "requires Arial and PyMuPDF")
    def test_missing_glyph_and_no_point_size_without_slide_width(self):
        image = Image.new("L", (200, 70), 255)
        ImageDraw.Draw(image).text((25, 15), "Notes", fill=0, font=ImageFont.truetype(str(ARIAL), 24))
        items = [{"id": "line", "role": "text", "bbox": [5, 5, 180, 60], "text": "Notes"}]
        self.write_inputs(image, items=items, slide_width=False)
        no_scale = measure_manifest(self.manifest, self.output, font_file=ARIAL)["items"][0]["font_suggestion"]
        self.assertEqual(no_scale["status"], "ADVISORY_ESTIMATE")
        self.assertNotIn("font_size_pt", no_scale)
        items[0]["text"] = "𰻞"
        self.write_inputs(image, items=items)
        missing = measure_manifest(self.manifest, self.root / "missing", font_file=ARIAL)["items"][0]["font_suggestion"]
        self.assertEqual(missing["reason"], "font_missing_glyphs")
        self.assertEqual(missing["missing_codepoints"], ["U+30EDE"])


if __name__ == "__main__":
    unittest.main()
