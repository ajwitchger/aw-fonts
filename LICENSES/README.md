# Licensing policy

`aw-fonts` intentionally contains only font families that are open source and publicly redistributable.

The root [`LICENSE`](../LICENSE) applies to repository tooling, workflows, configuration, and documentation. It does **not** relicense font binaries.

Every directory under `fonts/` must contain:

1. `font.toml` declaring the family name, upstream source, license identifier, and license filename.
2. The exact upstream license file referenced by `license_file`.
3. One or more `.ttf` or `.otf` font files.

Validation checks that those declarations and files exist and are internally consistent. It cannot prove that a license declaration is legally correct or that upstream redistribution terms have not changed. Adding or updating a family therefore requires checking the upstream project's current license before committing it.
