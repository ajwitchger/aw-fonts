# Font inventory

This directory is the canonical source of font binaries.

Create one lowercase, hyphenated directory per family:

```text
fonts/example-family/
├── font.toml
├── OFL.txt
├── ExampleFamily-Regular.ttf
└── ExampleFamily-Bold.ttf
```

`font.toml` schema:

```toml
[font]
family = "Example Family"
source = "https://upstream.example/font"
license = "OFL-1.1"
license_file = "OFL.txt"
```

Rules enforced by `scripts/validate.py`:

- family directory names are lowercase slugs;
- `.ttf` and `.otf` are the only supported font containers;
- `.ttc`, `.otc`, `.woff`, and `.woff2` are rejected;
- each font must expose a PostScript name in its OpenType/TrueType `name` table;
- PostScript names must be unique across the repository;
- duplicate font bytes are rejected;
- case-insensitive font path collisions are rejected;
- every family requires explicit source/license metadata and its referenced license file.
