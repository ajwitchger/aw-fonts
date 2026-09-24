#!/usr/bin/env python3
"""Generate and optionally serve a local side-by-side font comparison harness."""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import webbrowser
from urllib.parse import quote


SUPPORTED_FONT_SUFFIXES = {".ttf", ".otf"}


def _url_from_output(output: Path, target: Path) -> str:
    relative = Path(os.path.relpath(target, start=output.parent))
    return "/".join(quote(part) for part in relative.parts)


def discover_fonts(repo_root: Path, output: Path) -> list[dict[str, str]]:
    fonts_root = repo_root / "fonts"
    fonts: list[dict[str, str]] = []
    if not fonts_root.is_dir():
        return fonts

    for path in sorted(fonts_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_FONT_SUFFIXES:
            continue
        relative = path.relative_to(repo_root).as_posix()
        family_slug = path.relative_to(fonts_root).parts[0]
        fonts.append(
            {
                "id": f"awf-{len(fonts):04d}",
                "family": family_slug,
                "file": path.name,
                "path": relative,
                "url": _url_from_output(output, path),
                "format": "opentype" if path.suffix.lower() == ".otf" else "truetype",
            }
        )
    return fonts


def load_specimens(repo_root: Path) -> dict[str, str]:
    specimens_root = repo_root / "specimens"
    specimens: dict[str, str] = {}
    if not specimens_root.is_dir():
        return specimens
    for path in sorted(specimens_root.glob("*.txt")):
        specimens[path.stem] = path.read_text(encoding="utf-8")
    return specimens


def render_html(fonts: list[dict[str, str]], specimens: dict[str, str]) -> str:
    font_faces = "\n".join(
        (
            f"@font-face {{ font-family: '{font['id']}'; "
            f"src: url('{font['url']}') format('{font['format']}'); "
            "font-display: swap; }}"
        )
        for font in fonts
    )
    fonts_json = json.dumps(fonts, ensure_ascii=False).replace("</", "<\\/")
    specimens_json = json.dumps(specimens, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>aw-fonts comparison harness</title>
<style>
{font_faces}
:root {{
  color-scheme: light dark;
  font-family: system-ui, sans-serif;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; padding: 1rem; }}
header, .controls, .metrics {{ max-width: 1800px; margin: 0 auto 1rem; }}
h1 {{ margin: 0 0 .35rem; font-size: 1.5rem; }}
p {{ margin: .25rem 0; }}
.controls {{
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: .75rem;
  align-items: end;
}}
.control {{ display: flex; flex-direction: column; gap: .25rem; }}
.control.wide {{ grid-column: span 2; }}
label {{ font-size: .85rem; font-weight: 600; }}
select, input, textarea, button {{
  font: inherit;
  padding: .45rem;
}}
textarea {{
  width: 100%;
  min-height: 12rem;
  resize: vertical;
  tab-size: 4;
  white-space: pre;
}}
#specimen-editor {{ max-width: 1800px; margin: 0 auto 1rem; }}
.panes {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: .75rem;
  max-width: 1800px;
  margin: 0 auto 1rem;
}}
.pane {{
  min-width: 0;
  border: 1px solid color-mix(in srgb, currentColor 25%, transparent);
  border-radius: .4rem;
  overflow: hidden;
}}
.pane header {{
  margin: 0;
  padding: .55rem .7rem;
  border-bottom: 1px solid color-mix(in srgb, currentColor 20%, transparent);
}}
.pane-title {{ font-weight: 700; }}
.pane-path {{
  display: block;
  margin-top: .15rem;
  opacity: .7;
  font: .75rem ui-monospace, monospace;
  overflow-wrap: anywhere;
}}
.render {{
  margin: 0;
  padding: .8rem;
  min-height: 22rem;
  overflow: auto;
  white-space: pre;
  tab-size: 4;
}}
.metrics {{
  overflow-x: auto;
}}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{
  border: 1px solid color-mix(in srgb, currentColor 20%, transparent);
  padding: .4rem .5rem;
  text-align: right;
  font-variant-numeric: tabular-nums;
}}
th:first-child, td:first-child {{ text-align: left; }}
.note {{ opacity: .75; font-size: .85rem; }}
@media (max-width: 1000px) {{
  .controls {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .control.wide {{ grid-column: span 2; }}
  .panes {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>
<header>
  <h1>aw-fonts comparison harness</h1>
  <p>Compare up to three repository fonts against the same editable specimen.</p>
</header>

<section class="controls">
  <div class="control wide">
    <label for="filter">Font filter</label>
    <input id="filter" type="search" placeholder="Filter by family, filename, or path">
  </div>
  <div class="control">
    <label for="font-size">Font size</label>
    <input id="font-size" type="number" min="6" max="144" step="1" value="22">
  </div>
  <div class="control">
    <label for="line-height">Line height</label>
    <input id="line-height" type="number" min="0.8" max="3" step="0.05" value="1.35">
  </div>
  <div class="control">
    <label><input id="ligatures" type="checkbox" checked> Ligatures</label>
  </div>
  <div class="control">
    <label><input id="kerning" type="checkbox" checked> Kerning</label>
  </div>

  <div class="control">
    <label for="specimen">Specimen</label>
    <select id="specimen"></select>
  </div>
  <div class="control wide">
    <label for="font-a">Font A</label>
    <select id="font-a"></select>
  </div>
  <div class="control wide">
    <label for="font-b">Font B</label>
    <select id="font-b"></select>
  </div>
  <div class="control wide">
    <label for="font-c">Font C</label>
    <select id="font-c"></select>
  </div>
</section>

<section id="specimen-editor">
  <label for="editor">Editable specimen</label>
  <textarea id="editor" spellcheck="false"></textarea>
</section>

<section class="panes">
  <article class="pane" data-pane="a">
    <header><span class="pane-title"></span><span class="pane-path"></span></header>
    <pre class="render"></pre>
  </article>
  <article class="pane" data-pane="b">
    <header><span class="pane-title"></span><span class="pane-path"></span></header>
    <pre class="render"></pre>
  </article>
  <article class="pane" data-pane="c">
    <header><span class="pane-title"></span><span class="pane-path"></span></header>
    <pre class="render"></pre>
  </article>
</section>

<section class="metrics">
  <h2>ASCII width probes</h2>
  <p class="note">Each probe contains the same number of characters. A zero spread across these probes is a strong practical indicator that the selected font behaves monospaced for common ASCII text in this browser.</p>
  <table>
    <thead>
      <tr><th>Probe</th><th>Font A</th><th>Font B</th><th>Font C</th></tr>
    </thead>
    <tbody id="metrics-body"></tbody>
    <tfoot>
      <tr><th>Spread (max − min)</th><th id="spread-a"></th><th id="spread-b"></th><th id="spread-c"></th></tr>
    </tfoot>
  </table>
</section>

<script>
const fonts = {fonts_json};
const specimens = {specimens_json};
const probes = [
  "iiiiiiiiiiiiiiii",
  "mmmmmmmmmmmmmmmm",
  "0000000000000000",
  "WWWWWWWWWWWWWWWW",
  "||||||||||||||||",
  "................",
  "++++++++++++++++"
];

const $ = (id) => document.getElementById(id);
const selectors = [$("font-a"), $("font-b"), $("font-c")];

function fontLabel(font) {{
  return `${{font.family}} / ${{font.file}}`;
}}

function filteredFonts() {{
  const needle = $("filter").value.trim().toLowerCase();
  if (!needle) return fonts;
  return fonts.filter(font =>
    `${{font.family}} ${{font.file}} ${{font.path}}`.toLowerCase().includes(needle)
  );
}}

function populateFontSelectors() {{
  const available = filteredFonts();
  selectors.forEach((select, index) => {{
    const previous = select.value;
    select.innerHTML = "";
    for (const font of available) {{
      const option = document.createElement("option");
      option.value = font.id;
      option.textContent = fontLabel(font);
      select.appendChild(option);
    }}
    if (available.some(font => font.id === previous)) {{
      select.value = previous;
    }} else if (available.length) {{
      select.selectedIndex = Math.min(index, available.length - 1);
    }}
  }});
  update();
}}

function selectedFont(index) {{
  return fonts.find(font => font.id === selectors[index].value) || null;
}}

async function ensureLoaded(font) {{
  if (!font) return;
  const size = Number($("font-size").value) || 22;
  await document.fonts.load(`${{size}}px '${{font.id}}'`);
}}

function applyRender(pane, font) {{
  const render = pane.querySelector(".render");
  const title = pane.querySelector(".pane-title");
  const path = pane.querySelector(".pane-path");
  const size = Number($("font-size").value) || 22;
  const lineHeight = Number($("line-height").value) || 1.35;
  const ligatures = $("ligatures").checked ? "normal" : "none";
  const kerning = $("kerning").checked ? "auto" : "none";

  title.textContent = font ? fontLabel(font) : "No font selected";
  path.textContent = font ? font.path : "";
  render.textContent = $("editor").value;
  render.style.fontFamily = font ? `'${{font.id}}'` : "monospace";
  render.style.fontSize = `${{size}}px`;
  render.style.lineHeight = String(lineHeight);
  render.style.fontVariantLigatures = ligatures;
  render.style.fontKerning = kerning;
}}

function measure(font, text) {{
  if (!font) return null;
  const canvas = measure.canvas || (measure.canvas = document.createElement("canvas"));
  const context = canvas.getContext("2d");
  const size = Number($("font-size").value) || 22;
  context.fontKerning = $("kerning").checked ? "auto" : "none";
  context.font = `${{size}}px '${{font.id}}'`;
  return context.measureText(text).width;
}}

function renderMetrics(selected) {{
  const body = $("metrics-body");
  body.innerHTML = "";
  const widths = [[], [], []];

  for (const probe of probes) {{
    const row = document.createElement("tr");
    const label = document.createElement("td");
    label.textContent = probe;
    row.appendChild(label);

    selected.forEach((font, index) => {{
      const value = measure(font, probe);
      if (value !== null) widths[index].push(value);
      const cell = document.createElement("td");
      cell.textContent = value === null ? "—" : `${{value.toFixed(2)}} px`;
      row.appendChild(cell);
    }});
    body.appendChild(row);
  }}

  widths.forEach((values, index) => {{
    const id = ["spread-a", "spread-b", "spread-c"][index];
    const spread = values.length ? Math.max(...values) - Math.min(...values) : null;
    $(id).textContent = spread === null ? "—" : `${{spread.toFixed(2)}} px`;
  }});
}}

async function update() {{
  const selected = [selectedFont(0), selectedFont(1), selectedFont(2)];
  await Promise.all(selected.map(ensureLoaded));
  document.querySelectorAll(".pane").forEach((pane, index) => {{
    applyRender(pane, selected[index]);
  }});
  renderMetrics(selected);
}}

function populateSpecimens() {{
  const select = $("specimen");
  for (const key of Object.keys(specimens)) {{
    const option = document.createElement("option");
    option.value = key;
    option.textContent = key.replaceAll("-", " ");
    select.appendChild(option);
  }}
  if (select.options.length) {{
    select.value = Object.keys(specimens)[0];
    $("editor").value = specimens[select.value];
  }}
}}

$("filter").addEventListener("input", populateFontSelectors);
$("specimen").addEventListener("change", () => {{
  $("editor").value = specimens[$("specimen").value] || "";
  update();
}});
$("editor").addEventListener("input", update);
$("font-size").addEventListener("input", update);
$("line-height").addEventListener("input", update);
$("ligatures").addEventListener("change", update);
$("kerning").addEventListener("change", update);
selectors.forEach(select => select.addEventListener("change", update));

populateSpecimens();
populateFontSelectors();
</script>
</body>
</html>
"""


def generate(repo_root: Path, output: Path) -> tuple[int, int]:
    repo_root = repo_root.resolve()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    fonts = discover_fonts(repo_root, output)
    specimens = load_specimens(repo_root)
    output.write_text(render_html(fonts, specimens), encoding="utf-8")
    return len(fonts), len(specimens)


def serve(repo_root: Path, output: Path, port: int, open_browser: bool) -> None:
    repo_root = repo_root.resolve()
    output = output.resolve()
    try:
        relative_output = output.relative_to(repo_root)
    except ValueError as exc:
        raise SystemExit("--serve requires --output to be inside the repository") from exc

    handler = partial(SimpleHTTPRequestHandler, directory=str(repo_root))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    url_path = "/".join(quote(part) for part in relative_output.parts)
    url = f"http://127.0.0.1:{port}/{url_path}"

    print(f"Serving font comparison harness at {url}")
    print("Press Ctrl-C to stop.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist/font-compare/index.html"),
    )
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    output = args.output
    if not output.is_absolute():
        output = args.repo_root / output

    font_count, specimen_count = generate(args.repo_root, output)
    print(f"Generated {output}")
    print(f"  fonts:     {font_count}")
    print(f"  specimens: {specimen_count}")

    if args.serve:
        serve(args.repo_root, output, args.port, not args.no_browser)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
