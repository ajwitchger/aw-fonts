# Font comparison workflow

The repository includes a zero-dependency local browser harness plus a versioned specimen corpus. Its purpose is to make font-variant decisions reproducible before fonts are promoted into deployment profiles.

## Start the local harness

From the repository root:

```bash
python3 scripts/compare_fonts.py --serve
```

This generates `dist/font-compare/index.html`, starts a loopback-only HTTP server on port 8765, and opens the page in the default browser.

Use `--no-browser` when you only want the URL printed:

```bash
python3 scripts/compare_fonts.py --serve --no-browser
```

The generated page references fonts directly from the repository. It does **not** copy them into `dist/`, and browsers load only the selected fonts. That makes it practical even while a working branch contains a large number of candidate binaries.

## What the harness compares

Up to three fonts can be rendered side by side against the same editable specimen. Controls include:

- font-family/filename/path filtering;
- font size;
- line height;
- ligatures on/off;
- kerning on/off;
- a shared editable specimen;
- ASCII equal-length width probes.

The width-probe spread is intentionally descriptive rather than a formal classification. A spread of `0.00 px` across the supplied ASCII probes is a strong practical indication that those common characters are behaving monospaced in the browser. Nerd Font/private-use glyphs may still use different advances.

## Specimen corpus

The canonical specimens live under `specimens/`. When a real terminal, editor, document, or application exposes a subtle problem, add the exact triggering text to the relevant specimen file so the issue becomes reproducible.

## Escalation tools

The browser harness is the default selection tool. Use external tools when a comparison exposes something that needs deeper inspection.

### FontGoggles

Open candidate font files in FontGoggles and use the same files from `specimens/` for interactive OpenType/variable-font inspection.

### Diffenator 3

Diffenator 3 is the current Rust successor to Diffenator 2 and is the repository's preferred objective pairwise-diff tool.

Use the repository specimens as custom wordlists so a binary comparison exercises the same cases used in the local harness:

```bash
diffenator3 \
  --html \
  --custom-wordlists specimens/coding.txt \
  --custom-wordlists specimens/terminal.txt \
  --output dist/diffenator3 \
  path/to/font-a.ttf \
  path/to/font-b.ttf
```

Useful outputs include table, glyph-image, word-image, language-support, and kerning differences. For variable fonts, `diffenator3 --help` exposes location/instance/design-space controls.

Use `--json --pretty` instead of `--html` when machine-readable output is more useful.

### diff3proof

`diff3proof` is bundled with Diffenator 3 and generates human-reviewable HTML proofs. It can also proof a single font, which is useful when deciding whether a newly added candidate is worth keeping.

Stable Diffenator 3 v1.1.4 supports:

```bash
diff3proof \
  --sample-mode context \
  --output dist/diff3proof-context \
  path/to/font-a.ttf \
  path/to/font-b.ttf

diff3proof \
  --sample-mode cover \
  --output dist/diff3proof-cover \
  path/to/font-a.ttf \
  path/to/font-b.ttf
```

The current Diffenator 3 development branch also adds `waterfall`, `glyphs`, and `spacing` proof modes and allows combining modes. Do not assume an installed release has those flags; verify with:

```bash
diff3proof --help
```

before using development-only proof modes.

### HarfBuzz

Use `hb-view` or `hb-shape` when the problem is specifically about shaping, ligatures, glyph selection, or advance positioning:

```bash
hb-view path/to/font.ttf '=> != === -> [] {} () 0123456789'
hb-shape path/to/font.ttf '=> != === ->' --features='liga=1,calt=1'
```

Do not promote these external tools to required repository dependencies unless a repeated workflow demonstrates that need.
