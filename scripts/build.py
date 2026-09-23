#!/usr/bin/env python3
"""Build deterministic release artifacts from the canonical font inventory."""

from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import shutil
import sys

from fontrepo import (
    ValidationError,
    build_mobileconfig,
    build_portable_zip,
    json_bytes,
    load_inventory,
    manifest_for_profile,
    resolve_profile,
    validate_version,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-ref", required=True)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--output", type=Path, default=Path("dist"))
    args = parser.parse_args()

    try:
        validate_version(args.version)
        inventory = load_inventory(args.repo_root, require_fonts=True)
    except ValidationError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    output = args.output.resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    release_manifest = {
        "schema_version": 1,
        "version": args.version,
        "source_ref": args.source_ref,
        "profiles": [],
    }

    created: list[Path] = []

    try:
        for profile in inventory.profiles:
            selected = resolve_profile(inventory, profile)
            profile_manifest = manifest_for_profile(
                inventory,
                profile,
                selected,
                version=args.version,
                source_ref=args.source_ref,
            )
            manifest_bytes = json_bytes(profile_manifest)

            stem = f"aw-fonts-{profile.id}-{args.version}"
            mobileconfig = output / f"{stem}.mobileconfig"
            portable = output / f"{stem}.zip"

            mobileconfig.write_bytes(
                build_mobileconfig(
                    inventory,
                    profile,
                    selected,
                    version=args.version,
                )
            )
            build_portable_zip(
                inventory,
                selected,
                manifest_bytes=manifest_bytes,
                output=portable,
            )
            created.extend([mobileconfig, portable])
            release_manifest["profiles"].append(
                {
                    "id": profile.id,
                    "display_name": profile.display_name,
                    "font_count": len(selected),
                    "mobileconfig": mobileconfig.name,
                    "portable_zip": portable.name,
                }
            )

        manifest_path = output / "manifest.json"
        manifest_path.write_bytes(json_bytes(release_manifest))
        created.append(manifest_path)

        checksum_lines = []
        for path in sorted(created, key=lambda item: item.name):
            checksum_lines.append(f"{sha256(path.read_bytes()).hexdigest()}  {path.name}")
        (output / "SHA256SUMS").write_text(
            "\n".join(checksum_lines) + "\n", encoding="utf-8"
        )
    except (OSError, ValidationError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print(f"Built {len(inventory.profiles)} profile(s) into {output}")
    for path in sorted(output.iterdir()):
        print(f"  {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
