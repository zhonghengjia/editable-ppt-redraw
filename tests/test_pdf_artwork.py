import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
import pymupdf
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from pdf_paint_scene import render_artwork

class ArtworkTests(unittest.TestCase):
    def fixture(self, root):
        p=Path(root)/'source.pdf'
        with pymupdf.open() as d:
            page=d.new_page(width=100,height=100)
            page.draw_rect(page.rect,color=None,fill=(0.8,0.4,0.6))
            page.insert_text((15,50),'CELL',fontsize=20)
            d.save(p)
        return p

    def test_existing_artwork_revealed_without_cover_or_source_change(self):
        with tempfile.TemporaryDirectory() as root:
            p=self.fixture(root);before=p.read_bytes()
            image,evidence=render_artwork(p,1,scale=1)
            self.assertEqual(len(image.getcolors()),1)
            self.assertEqual(image.getpixel((25,40)),(204,102,153,255))
            self.assertEqual(p.read_bytes(),before)
            self.assertEqual(evidence['source_sha256'],hashlib.sha256(before).hexdigest())
            self.assertGreater(evidence['source_text_characters'],0)
            with pymupdf.open(p) as d:self.assertIn('CELL',d[0].get_text())

    def test_invalid_region_scale_and_page(self):
        with tempfile.TemporaryDirectory() as root:
            p=self.fixture(root)
            for kw in (dict(scale=float('nan')),dict(scale=0),dict(scale=1000),dict(region=[-1,0,10,10]),dict(region=[1,1,1,2])):
                with self.assertRaises(ValueError):render_artwork(p,1,**kw)
            with self.assertRaises(ValueError):render_artwork(p,0)

if __name__=='__main__':unittest.main()
