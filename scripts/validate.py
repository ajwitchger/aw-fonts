#!/usr/bin/env python3
"""Validate the canonical aw-fonts source tree."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from fontrepo import ValidationError, load_inventory


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--require-fonts",
        action="store_true",
        help="fail when the repository contains no font files",
    )
    args = parser.parse_args()

    try:
        inventory = load_inventory(args.repo_root, require_fonts=args.require_fonts)
    except ValidationError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print("Repository validation")
    print(f"  families: {len(inventory.families)}")
    print(f"  fonts:    {len(inventory.fonts)}")
    print(f"  profiles: {len(inventory.profiles)}")
    print(f"  default:  {inventory.default_profile}")
    if not inventory.fonts:
        print("  note:     empty font inventory allowed for repository scaffolding")
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
