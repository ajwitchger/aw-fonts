# aw-fonts

Versioned, validated collection of redistributable fonts and reproducible platform installation artifacts.

## Source of truth

The repository stores font binaries once under `fonts/`. Profiles under `profiles/` select from that canonical inventory. Generated ZIP bundles, Apple configuration profiles, manifests, and checksums are release artifacts and are not committed.

```text
fonts/ + profiles/
        |
        v
validation + deterministic build
        |
        +-- portable ZIP
        +-- Apple .mobileconfig
        +-- manifest.json
        `-- SHA256SUMS
```

## Add a font family

Create one directory per family:

```text
fonts/<family-slug>/
├── font.toml
├── OFL.txt              # or the upstream license file
├── Regular.ttf
└── Bold.ttf
```

`family-slug` must contain only lowercase letters, numbers, and hyphens.

Example `font.toml`:

```toml
[font]
family = "Example Sans"
source = "https://example.org/example-sans"
license = "OFL-1.1"
license_file = "OFL.txt"
```

Repository policy requires every included font to be open source and publicly redistributable. Validation verifies that license metadata and the referenced license file are present; it does **not** make a legal determination about the declared license.

Supported font containers are `.ttf` and `.otf`. `.ttc`, `.otc`, `.woff`, and `.woff2` are rejected.

## Profiles

`profiles/all.toml` includes every validated family. Additional profiles may select family directory slugs explicitly:

```toml
[profile]
id = "development"
display_name = "Development Fonts"
description = "Fonts used on development machines."
include = ["jetbrains-mono", "ibm-plex-mono"]
```

A profile filename must match its `id`.

## Local validation

Python 3.11 or newer is required.

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate.py
```

Before fonts have been added, repository validation intentionally permits an empty inventory. Artifact builds and releases require at least one font:

```bash
python3 scripts/validate.py --require-fonts
```

## Build artifacts locally

```bash
python3 scripts/build.py \
  --version dev \
  --source-ref "$(git rev-parse HEAD)" \
  --output dist
```

The builder creates one portable ZIP and one Apple `.mobileconfig` per profile, plus `manifest.json` and `SHA256SUMS`.

## Release

Releases are explicit, not automatic.

1. Merge validated font/profile changes to `main`.
2. Open **Actions → Publish font artifacts → Run workflow**.
3. Enter a release tag in the form `vYYYY.MM.N`, for example `v2026.09.1`.
4. The workflow validates the repository, runs the test suite, builds artifacts, verifies checksums, creates a draft release, uploads every artifact, and only then publishes it.

The release workflow refuses to run from anything other than `main`.

## Apple installation

Download the desired `.mobileconfig` release asset on iPadOS/macOS and inspect/install it using the system profile UI. Generated configuration profiles contain only:

- outer `Configuration` payload
- child `com.apple.font` payloads

The builder fails if any other payload type appears.

## Licensing

Repository tooling and configuration are MIT-licensed; bundled font files are excluded from that grant and retain their upstream licenses. See [`LICENSE`](LICENSE) and [`LICENSES/README.md`](LICENSES/README.md).
