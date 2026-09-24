# Font comparison specimens

These files are a versioned regression corpus for evaluating font variants.

Use them in the local comparison harness, FontGoggles, Diffenator, HarfBuzz, or any other renderer. When a real application exposes a subtle font problem that is hard to recreate later, copy the exact triggering text into the most appropriate specimen file rather than relying on memory.

The initial set is intentionally small:

- `alignment.txt` — equal-width and column-alignment probes.
- `ambiguity.txt` — visually confusable glyphs.
- `coding.txt` — operators, delimiters, ligature-sensitive sequences, and source code.
- `terminal.txt` — prompts, paths, box drawing, tabular output, and shell text.
- `nerd-fonts.txt` — Powerline and common Nerd Font/private-use glyph probes.

Prefer adding real failure cases over expanding this into an exhaustive glyph catalogue.
