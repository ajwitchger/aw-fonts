from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import plistlib
import struct
import subprocess
import tempfile
import unittest

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from fontrepo import (  # noqa: E402
    ValidationError,
    build_mobileconfig,
    load_inventory,
    postscript_name,
    resolve_profile,
    validate_mobileconfig,
)


def make_sfnt(ps_name: str) -> bytes:
    encoded = ps_name.encode("utf-16-be")
    name_table = (
        struct.pack(">HHH", 0, 1, 18)
        + struct.pack(">HHHHHH", 3, 1, 0x0409, 6, len(encoded), 0)
        + encoded
    )
    offset = 12 + 16
    header = struct.pack(">IHHHH", 0x00010000, 1, 0, 0, 0)
    record = struct.pack(">4sIII", b"name", 0, offset, len(name_table))
    return header + record + name_table


def write_config(root: Path, default_profile: str = "all") -> None:
    (root / "aw-fonts.toml").write_text(
        f"""[repository]
default_profile = "{default_profile}"
""",
        encoding="utf-8",
    )


def write_all_profile(root: Path) -> None:
    (root / "profiles").mkdir(exist_ok=True)
    (root / "profiles" / "all.toml").write_text(
        """[profile]
id = "all"
display_name = "All Fonts"
description = "All fonts."
include = ["*"]
""",
        encoding="utf-8",
    )


def write_example_family(root: Path) -> None:
    family = root / "fonts" / "example"
    family.mkdir(parents=True)
    (family / "font.toml").write_text(
        """[font]
family = "Example"
source = "https://example.invalid/example"
license = "OFL-1.1"
license_file = "OFL.txt"
""",
        encoding="utf-8",
    )
    (family / "OFL.txt").write_text("license\n", encoding="utf-8")
    (family / "Example.ttf").write_bytes(make_sfnt("Example-Regular"))


class FontRepoTests(unittest.TestCase):
    def test_postscript_name(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "Example.ttf"
            path.write_bytes(make_sfnt("Example-Regular"))
            self.assertEqual(postscript_name(path), "Example-Regular")

    def test_empty_scaffold_is_valid_but_release_is_not(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "fonts").mkdir()
            write_config(root)
            write_all_profile(root)

            inventory = load_inventory(root)
            self.assertEqual(len(inventory.fonts), 0)
            self.assertEqual(inventory.default_profile, "all")
            with self.assertRaisesRegex(ValidationError, "artifact builds require"):
                load_inventory(root, require_fonts=True)

    def test_default_profile_must_exist(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "fonts").mkdir()
            write_config(root, default_profile="core")
            write_all_profile(root)

            with self.assertRaisesRegex(
                ValidationError, "default profile `core` does not exist"
            ):
                load_inventory(root)

    def test_duplicate_postscript_names_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "fonts" / "one").mkdir(parents=True)
            (root / "fonts" / "two").mkdir(parents=True)
            write_config(root)
            write_all_profile(root)

            for slug in ("one", "two"):
                family = root / "fonts" / slug
                (family / "font.toml").write_text(
                    f"""[font]
family = "{slug}"
source = "https://example.invalid/{slug}"
license = "OFL-1.1"
license_file = "OFL.txt"
""",
                    encoding="utf-8",
                )
                (family / "OFL.txt").write_text("license\n", encoding="utf-8")
                (family / f"{slug}.ttf").write_bytes(
                    make_sfnt("Same-PS-Name") + slug.encode()
                )

            with self.assertRaisesRegex(ValidationError, "duplicate PostScript name"):
                load_inventory(root)

    def test_generated_profile_contains_only_font_payloads(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_config(root)
            write_all_profile(root)
            write_example_family(root)

            inventory = load_inventory(root, require_fonts=True)
            profile = inventory.profiles[0]
            selected = resolve_profile(inventory, profile)
            first = build_mobileconfig(
                inventory, profile, selected, version="v2026.09.1"
            )
            second = build_mobileconfig(
                inventory, profile, selected, version="v2026.09.1"
            )
            self.assertEqual(sha256(first).digest(), sha256(second).digest())

            validate_mobileconfig(first)
            parsed = plistlib.loads(first)
            self.assertEqual(parsed["PayloadType"], "Configuration")
            self.assertEqual(
                {child["PayloadType"] for child in parsed["PayloadContent"]},
                {"com.apple.font"},
            )

    def test_default_release_artifacts_are_byte_identical_aliases(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_config(root)
            write_all_profile(root)
            write_example_family(root)

            output = root / "dist"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "build.py"),
                    "--version",
                    "v2026.09.1",
                    "--source-ref",
                    "deadbeef",
                    "--repo-root",
                    str(root),
                    "--output",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            explicit_mobileconfig = output / "aw-fonts-all-v2026.09.1.mobileconfig"
            alias_mobileconfig = output / "aw-fonts-v2026.09.1.mobileconfig"
            explicit_zip = output / "aw-fonts-all-v2026.09.1.zip"
            alias_zip = output / "aw-fonts-v2026.09.1.zip"

            self.assertEqual(
                explicit_mobileconfig.read_bytes(), alias_mobileconfig.read_bytes()
            )
            self.assertEqual(explicit_zip.read_bytes(), alias_zip.read_bytes())

            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["default_profile"], "all")
            self.assertEqual(manifest["aliases"]["aw-fonts"]["profile"], "all")


if __name__ == "__main__":
    unittest.main()
