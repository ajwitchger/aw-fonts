# aw-fonts

Versioned, validated collection of redistributable fonts and reproducible platform installation artifacts.

## Source of truth

The repository stores font binaries once under `fonts/`. Profiles under `profiles/` select from that canonical inventory. `aw-fonts.toml` selects the repository's default deployment profile. Generated ZIP bundles, Apple configuration profiles, manifests, and checksums are release artifacts and are not committed.

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

Supported font containers:
- `.ttf`
- `.otf`

Unsupported font containers include: 
- `.ttc`
- `.otc`
- `.woff`
- `.woff2`

## Profiles

`profiles/all.toml` includes every validated family. Additional profiles may select family directory slugs explicitly:

```toml
[profile]
id = "dev"
display_name = "Development Fonts"
description = "Fonts used on development machines."
include = ["font-fira-code-nerd-font", "font-iosevka-nerd-font",  "iosevka-aw-term"]
```

A profile filename must match its `id`.

### Default profile

The unqualified `aw-fonts` artifact is an alias for one explicit profile. The pointer is defined once at the repository root:

```toml
# aw-fonts.toml
[repository]
default_profile = "all"
```

While only `all` exists, it is the default. Once a stable `core` profile is defined, the intended long-term configuration is:

```toml
[repository]
default_profile = "core"
```

The alias is not another profile and contains no separately generated state. For each release, `aw-fonts-<version>.zip` and `aw-fonts-<version>.mobileconfig` are byte-for-byte copies of the selected profile's explicit artifacts. Validation fails if `default_profile` does not name an existing profile.

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

The builder creates one portable ZIP and one Apple `.mobileconfig` per profile, plus an unqualified `aw-fonts` alias for the configured default profile, `manifest.json`, and `SHA256SUMS`.

For example, while `all` is the default:

```text
aw-fonts-all-v2026.09.1.zip
aw-fonts-all-v2026.09.1.mobileconfig
aw-fonts-v2026.09.1.zip
aw-fonts-v2026.09.1.mobileconfig
```

The two unqualified artifacts are byte-identical to their `all` counterparts. The release manifest records the resolved `default_profile` and alias relationship explicitly.

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
