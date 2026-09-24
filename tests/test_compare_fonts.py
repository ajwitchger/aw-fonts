from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from compare_fonts import discover_fonts, generate  # noqa: E402


class FontCompareTests(unittest.TestCase):
    def test_discovers_supported_fonts_without_copying_them(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "fonts" / "family-one").mkdir(parents=True)
            (root / "fonts" / "family-two").mkdir(parents=True)
            (root / "fonts" / "family-one" / "Regular.ttf").write_bytes(b"ttf")
            (root / "fonts" / "family-two" / "Display.otf").write_bytes(b"otf")
            (root / "fonts" / "family-two" / "Ignored.woff2").write_bytes(b"woff")
            output = root / "dist" / "font-compare" / "index.html"

            fonts = discover_fonts(root, output)

            self.assertEqual(len(fonts), 2)
            self.assertEqual(
                {font["path"] for font in fonts},
                {
                    "fonts/family-one/Regular.ttf",
                    "fonts/family-two/Display.otf",
                },
            )
            self.assertTrue(all("../../fonts/" in font["url"] for font in fonts))

    def test_generate_embeds_specimens_and_references_source_fonts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "fonts" / "example").mkdir(parents=True)
            (root / "specimens").mkdir()
            (root / "fonts" / "example" / "Example Regular.ttf").write_bytes(b"font")
            (root / "specimens" / "coding.txt").write_text(
                "=> != 0O 1Il|\n", encoding="utf-8"
            )
            output = root / "dist" / "font-compare" / "index.html"

            font_count, specimen_count = generate(root, output)
            html = output.read_text(encoding="utf-8")

            self.assertEqual(font_count, 1)
            self.assertEqual(specimen_count, 1)
            self.assertIn("Example%20Regular.ttf", html)
            self.assertIn("=> != 0O 1Il|", html)
            self.assertIn("ASCII width probes", html)
            self.assertFalse((output.parent / "Example Regular.ttf").exists())


if __name__ == "__main__":
    unittest.main()
