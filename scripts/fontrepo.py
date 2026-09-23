#!/usr/bin/env python3
"""Shared inventory, validation, and build primitives for aw-fonts."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import plistlib
import re
import struct
import tomllib
import uuid
import zipfile


SUPPORTED_FONT_SUFFIXES = {".ttf", ".otf"}
REJECTED_FONT_SUFFIXES = {".ttc", ".otc", ".woff", ".woff2"}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PROFILE_ID_RE = SLUG_RE
SAFE_VERSION_RE = re.compile(r"^[A-Za-z0-9._-]+$")
UUID_NAMESPACE = uuid.UUID("b21a90df-1664-5f76-9b13-d8cc67bd65db")
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


class ValidationError(Exception):
    """Raised when repository inputs violate the canonical schema."""


@dataclass(frozen=True)
class Family:
    slug: str
    family: str
    source: str
    license: str
    license_file: str
    directory: Path


@dataclass(frozen=True)
class Font:
    family_slug: str
    family: str
    path: Path
    relative_path: str
    postscript_name: str
    sha256: str


@dataclass(frozen=True)
class Profile:
    id: str
    display_name: str
    description: str
    include: tuple[str, ...]


@dataclass(frozen=True)
class Inventory:
    root: Path
    families: dict[str, Family]
    fonts: tuple[Font, ...]
    profiles: tuple[Profile, ...]


def _require_string(mapping: dict, key: str, context: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{context}: `{key}` must be a non-empty string")
    return value.strip()


def _read_toml(path: Path) -> dict:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValidationError(f"{path}: unable to read TOML: {exc}") from exc


def _decode_name(platform_id: int, raw: bytes) -> str | None:
    try:
        if platform_id in {0, 3}:
            return raw.decode("utf-16-be").strip("\x00 ")
        if platform_id == 1:
            return raw.decode("mac_roman").strip("\x00 ")
        return raw.decode("latin-1").strip("\x00 ")
    except UnicodeDecodeError:
        return None


def postscript_name(path: Path) -> str:
    """Extract OpenType/TrueType nameID 6 without third-party dependencies."""
    data = path.read_bytes()
    if len(data) < 12:
        raise ValidationError(f"{path}: truncated SFNT header")

    num_tables = struct.unpack_from(">H", data, 4)[0]
    directory_end = 12 + (num_tables * 16)
    if directory_end > len(data):
        raise ValidationError(f"{path}: truncated SFNT table directory")

    name_offset = None
    name_length = None
    for index in range(num_tables):
        record = 12 + (index * 16)
        tag, _, offset, length = struct.unpack_from(">4sIII", data, record)
        if tag == b"name":
            name_offset, name_length = offset, length
            break

    if name_offset is None or name_length is None:
        raise ValidationError(f"{path}: missing OpenType/TrueType `name` table")
    if name_offset + name_length > len(data) or name_length < 6:
        raise ValidationError(f"{path}: invalid `name` table bounds")

    table = memoryview(data)[name_offset : name_offset + name_length]
    _, count, string_offset = struct.unpack_from(">HHH", table, 0)
    records_end = 6 + (count * 12)
    if records_end > len(table) or string_offset > len(table):
        raise ValidationError(f"{path}: malformed `name` table")

    candidates: list[tuple[int, str]] = []
    for index in range(count):
        record = 6 + (index * 12)
        platform_id, encoding_id, language_id, name_id, length, offset = struct.unpack_from(
            ">HHHHHH", table, record
        )
        del encoding_id
        if name_id != 6:
            continue
        start = string_offset + offset
        end = start + length
        if start < string_offset or end > len(table):
            continue
        decoded = _decode_name(platform_id, bytes(table[start:end]))
        if not decoded:
            continue

        if platform_id == 3 and language_id == 0x0409:
            priority = 0
        elif platform_id == 0:
            priority = 1
        elif platform_id == 3:
            priority = 2
        elif platform_id == 1:
            priority = 3
        else:
            priority = 4
        candidates.append((priority, decoded))

    if not candidates:
        raise ValidationError(f"{path}: missing PostScript name (nameID 6)")

    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][1]


def _load_families(root: Path) -> tuple[dict[str, Family], list[Font]]:
    fonts_root = root / "fonts"
    if not fonts_root.is_dir():
        raise ValidationError("missing required `fonts/` directory")

    families: dict[str, Family] = {}
    font_records: list[Font] = []
    seen_ps: dict[str, str] = {}
    seen_hash: dict[str, str] = {}
    seen_casefold_paths: dict[str, str] = {}

    for family_dir in sorted(path for path in fonts_root.iterdir() if path.is_dir()):
        slug = family_dir.name
        if not SLUG_RE.fullmatch(slug):
            raise ValidationError(
                f"{family_dir}: family directory must be a lowercase hyphenated slug"
            )

        metadata_path = family_dir / "font.toml"
        if not metadata_path.is_file():
            raise ValidationError(f"{family_dir}: missing `font.toml`")

        data = _read_toml(metadata_path)
        section = data.get("font")
        if not isinstance(section, dict):
            raise ValidationError(f"{metadata_path}: missing `[font]` table")

        family_name = _require_string(section, "family", str(metadata_path))
        source = _require_string(section, "source", str(metadata_path))
        license_id = _require_string(section, "license", str(metadata_path))
        license_file = _require_string(section, "license_file", str(metadata_path))

        license_path = (family_dir / license_file).resolve()
        try:
            license_path.relative_to(family_dir.resolve())
        except ValueError as exc:
            raise ValidationError(
                f"{metadata_path}: `license_file` must stay inside the family directory"
            ) from exc
        if not license_path.is_file():
            raise ValidationError(
                f"{metadata_path}: declared license file `{license_file}` does not exist"
            )

        family = Family(
            slug=slug,
            family=family_name,
            source=source,
            license=license_id,
            license_file=license_file,
            directory=family_dir,
        )
        families[slug] = family

        supported = sorted(
            path
            for path in family_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_FONT_SUFFIXES
        )
        rejected = sorted(
            path
            for path in family_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in REJECTED_FONT_SUFFIXES
        )
        if rejected:
            names = ", ".join(str(path.relative_to(root)) for path in rejected)
            raise ValidationError(f"{family_dir}: unsupported font container(s): {names}")
        if not supported:
            raise ValidationError(f"{family_dir}: contains no .ttf or .otf font files")

        for path in supported:
            relative_path = path.relative_to(root).as_posix()
            folded = relative_path.casefold()
            previous_path = seen_casefold_paths.get(folded)
            if previous_path and previous_path != relative_path:
                raise ValidationError(
                    f"case-insensitive path collision: `{previous_path}` and `{relative_path}`"
                )
            seen_casefold_paths[folded] = relative_path

            digest = sha256(path.read_bytes()).hexdigest()
            previous_hash = seen_hash.get(digest)
            if previous_hash:
                raise ValidationError(
                    f"duplicate font bytes: `{previous_hash}` and `{relative_path}`"
                )
            seen_hash[digest] = relative_path

            ps_name = postscript_name(path)
            previous_ps = seen_ps.get(ps_name)
            if previous_ps:
                raise ValidationError(
                    f"duplicate PostScript name `{ps_name}`: "
                    f"`{previous_ps}` and `{relative_path}`"
                )
            seen_ps[ps_name] = relative_path

            font_records.append(
                Font(
                    family_slug=slug,
                    family=family_name,
                    path=path,
                    relative_path=relative_path,
                    postscript_name=ps_name,
                    sha256=digest,
                )
            )

    return families, font_records


def _load_profiles(root: Path, families: dict[str, Family]) -> tuple[Profile, ...]:
    profiles_root = root / "profiles"
    if not profiles_root.is_dir():
        raise ValidationError("missing required `profiles/` directory")

    paths = sorted(profiles_root.glob("*.toml"))
    if not paths:
        raise ValidationError("`profiles/` must contain at least one .toml profile")

    profiles: list[Profile] = []
    seen_ids: set[str] = set()

    for path in paths:
        data = _read_toml(path)
        section = data.get("profile")
        if not isinstance(section, dict):
            raise ValidationError(f"{path}: missing `[profile]` table")

        profile_id = _require_string(section, "id", str(path))
        if not PROFILE_ID_RE.fullmatch(profile_id):
            raise ValidationError(f"{path}: invalid profile id `{profile_id}`")
        if path.stem != profile_id:
            raise ValidationError(
                f"{path}: filename must match profile id `{profile_id}.toml`"
            )
        if profile_id in seen_ids:
            raise ValidationError(f"duplicate profile id `{profile_id}`")
        seen_ids.add(profile_id)

        display_name = _require_string(section, "display_name", str(path))
        description = _require_string(section, "description", str(path))
        include_raw = section.get("include")
        if (
            not isinstance(include_raw, list)
            or not include_raw
            or not all(isinstance(item, str) and item for item in include_raw)
        ):
            raise ValidationError(f"{path}: `include` must be a non-empty string array")

        include = tuple(include_raw)
        if "*" in include and include != ("*",):
            raise ValidationError(f"{path}: wildcard `*` cannot be combined with family slugs")

        if include != ("*",):
            duplicates = sorted({item for item in include if include.count(item) > 1})
            if duplicates:
                raise ValidationError(
                    f"{path}: duplicate included families: {', '.join(duplicates)}"
                )
            missing = sorted(set(include) - set(families))
            if missing:
                raise ValidationError(
                    f"{path}: unknown family slug(s): {', '.join(missing)}"
                )

        profiles.append(
            Profile(
                id=profile_id,
                display_name=display_name,
                description=description,
                include=include,
            )
        )

    return tuple(profiles)


def load_inventory(root: Path, *, require_fonts: bool = False) -> Inventory:
    root = root.resolve()
    families, font_records = _load_families(root)
    profiles = _load_profiles(root, families)

    if require_fonts and not font_records:
        raise ValidationError("no fonts found; artifact builds require at least one font")

    return Inventory(
        root=root,
        families=families,
        fonts=tuple(sorted(font_records, key=lambda font: font.relative_path)),
        profiles=profiles,
    )


def resolve_profile(inventory: Inventory, profile: Profile) -> tuple[Font, ...]:
    if profile.include == ("*",):
        selected = inventory.fonts
    else:
        included = set(profile.include)
        selected = tuple(
            font for font in inventory.fonts if font.family_slug in included
        )
    if not selected:
        raise ValidationError(f"profile `{profile.id}` resolves to zero fonts")
    return tuple(sorted(selected, key=lambda font: font.relative_path))


def _profile_uuid(kind: str, identity: str) -> str:
    return str(uuid.uuid5(UUID_NAMESPACE, f"{kind}:{identity}")).upper()


def build_mobileconfig(
    inventory: Inventory,
    profile: Profile,
    selected: tuple[Font, ...],
    *,
    version: str,
) -> bytes:
    children = []
    for font in selected:
        payload_id = (
            f"com.ajwitchger.aw-fonts.{profile.id}.font."
            f"{sha256(font.postscript_name.encode()).hexdigest()[:16]}"
        )
        children.append(
            {
                "Font": font.path.read_bytes(),
                "Name": font.path.name,
                "PayloadDisplayName": font.postscript_name,
                "PayloadIdentifier": payload_id,
                "PayloadType": "com.apple.font",
                "PayloadUUID": _profile_uuid(
                    "font", f"{profile.id}:{font.postscript_name}"
                ),
                "PayloadVersion": 1,
            }
        )

    outer = {
        "PayloadContent": children,
        "PayloadDescription": (
            f"{profile.description} Built from aw-fonts release {version}."
        ),
        "PayloadDisplayName": profile.display_name,
        "PayloadIdentifier": f"com.ajwitchger.aw-fonts.{profile.id}",
        "PayloadOrganization": "aw-fonts",
        "PayloadRemovalDisallowed": False,
        "PayloadType": "Configuration",
        "PayloadUUID": _profile_uuid("profile", profile.id),
        "PayloadVersion": 1,
    }
    data = plistlib.dumps(outer, fmt=plistlib.FMT_XML, sort_keys=True)
    validate_mobileconfig(data)
    return data


def validate_mobileconfig(data: bytes) -> None:
    try:
        profile = plistlib.loads(data)
    except Exception as exc:
        raise ValidationError(f"generated mobileconfig is not valid plist: {exc}") from exc

    if profile.get("PayloadType") != "Configuration":
        raise ValidationError("generated profile outer payload is not `Configuration`")
    children = profile.get("PayloadContent")
    if not isinstance(children, list) or not children:
        raise ValidationError("generated profile contains no child payloads")

    unexpected: list[str] = []
    for child in children:
        if not isinstance(child, dict):
            unexpected.append(type(child).__name__)
            continue
        payload_type = child.get("PayloadType")
        if payload_type != "com.apple.font":
            unexpected.append(str(payload_type))

    if unexpected:
        raise ValidationError(
            "generated profile contains unexpected payload type(s): "
            + ", ".join(sorted(unexpected))
        )


def _zip_write_bytes(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=FIXED_ZIP_TIME)
    # Store rather than deflate so identical inputs produce identical ZIP bytes
    # independently of zlib implementation/version.
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, data)


def build_portable_zip(
    inventory: Inventory,
    selected: tuple[Font, ...],
    *,
    manifest_bytes: bytes,
    output: Path,
) -> None:
    family_slugs = sorted({font.family_slug for font in selected})
    with zipfile.ZipFile(output, "w") as archive:
        for font in selected:
            family = inventory.families[font.family_slug]
            within_family = font.path.relative_to(family.directory).as_posix()
            name = f"fonts/{font.family_slug}/{within_family}"
            _zip_write_bytes(archive, name, font.path.read_bytes())

        for slug in family_slugs:
            family = inventory.families[slug]
            license_path = family.directory / family.license_file
            _zip_write_bytes(
                archive,
                f"fonts/{slug}/{family.license_file}",
                license_path.read_bytes(),
            )
            metadata_path = family.directory / "font.toml"
            _zip_write_bytes(
                archive,
                f"fonts/{slug}/font.toml",
                metadata_path.read_bytes(),
            )

        _zip_write_bytes(archive, "manifest.json", manifest_bytes)


def manifest_for_profile(
    inventory: Inventory,
    profile: Profile,
    selected: tuple[Font, ...],
    *,
    version: str,
    source_ref: str,
) -> dict:
    return {
        "schema_version": 1,
        "version": version,
        "source_ref": source_ref,
        "profile": {
            "id": profile.id,
            "display_name": profile.display_name,
            "description": profile.description,
        },
        "fonts": [
            {
                "family_slug": font.family_slug,
                "family": font.family,
                "path": font.relative_path,
                "postscript_name": font.postscript_name,
                "sha256": font.sha256,
                "license": inventory.families[font.family_slug].license,
                "license_file": inventory.families[font.family_slug].license_file,
                "source": inventory.families[font.family_slug].source,
            }
            for font in selected
        ],
    }


def json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def validate_version(version: str) -> None:
    if not SAFE_VERSION_RE.fullmatch(version):
        raise ValidationError(
            "version may contain only ASCII letters, numbers, dot, underscore, and hyphen"
        )
