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

The browser harness is the default selection tool. Use external tools only when a comparison exposes something that needs deeper inspection.

### FontGoggles

Open candidate font files in FontGoggles and use the same files from `specimens/` for interactive OpenType/variable-font inspection.

### Diffenator 2

Use Diffenator when you need an objective visual/internal diff between two candidate binaries. Feed it one of the repository specimen files as the user wordlist where appropriate.

### HarfBuzz

Use `hb-view` or `hb-shape` when the problem is specifically about shaping, ligatures, glyph selection, or advance positioning:

```bash
hb-view path/to/font.ttf '=> != === -> [] {} () 0123456789'
hb-shape path/to/font.ttf '=> != === ->' --features='liga=1,calt=1'
```

Do not promote those external tools to required repository dependencies unless a repeated workflow demonstrates that need.
