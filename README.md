# deck-lint

Local slide-layout checks. Works on any PDF deck, including Typst, PowerPoint, Marp and Beamer exports. It reports geometry and typography problems as text before a visual pass. It never edits a source deck.

## Design decisions

Use PyMuPDF alone: its blocks, lines and font spans cover the same wrapping cases observed with Poppler, while also exposing text drawing operations, image placements and rendering. This avoids reconciling two extractors. Dependencies are installed with uv. Typst mode requires Typst 0.15.1 or newer; PDF mode does not require Typst.

PDF checks are format-agnostic. Slide boundaries, intended page counts, titles and speaker-note presence need source metadata. Typst mode compiles a fresh temporary PDF and queries metadata with the same options. It checks that compile, not an existing exported PDF. The source and its dependencies must remain unchanged while it runs. Main-source changes and out-of-range metadata pages are rejected, but separate compile/query runs cannot prove identical layout for time-dependent or changing imports. Use a deterministic build. Encrypted or unreadable PDFs fail with exit 2. PDFs MuPDF can repair emit `pdf.repaired` and still receive layout checks.

CLI plus a shared skill and a short agent-instructions entry is the integration. Run it after building a slide PDF, before delivery. No shell hook: matching `typst compile` inside arbitrary shell commands is unreliable, misses watch builds and other exporters, and a Claude-only hook misses Codex. This is instruction-driven, not an enforced gate.

Warnings need judgment. A deliberate line break, tightly set equation or decorative text can trigger a heuristic. Do not automatically rewrite every flagged slide or disable a rule solely to get a clean exit.

## Install

Requirements: Python 3.11+ and [uv](https://docs.astral.sh/uv/). Typst 0.15.1+ on `PATH` only for `--typ` mode.

```sh
uv tool install git+https://github.com/jas-ho/deck-lint
# or from a local clone, with edits taking effect immediately:
git clone https://github.com/jas-ho/deck-lint && uv tool install --editable ./deck-lint
deck-lint --help
```

Agent skill (optional): `skills/deck-lint/SKILL.md` tells a coding agent when and how to run the CLI. Copy or symlink the `skills/deck-lint` folder into your agent's skills directory (for Claude Code: `~/.claude/skills/deck-lint`), and add a line to your agent instructions to lint after building slides.

## Usage

```sh
deck-lint check deck.pdf
deck-lint check deck.pdf --json
deck-lint check --typ deck.typ --input notes=false
deck-lint check deck.pdf --set min_font=16 --set max_pages=30
deck-lint check deck.pdf --config deck-lint.toml --disable wrap.long
deck-lint sheet deck.pdf --output sheet.png --replace
deck-lint snippet
```

The CLI works from any directory. Relative paths resolve from the caller's working directory. `--typ` accepts a source instead of a PDF; it never replaces the source's existing PDF. `--root`, repeatable `--font-path` and `--input key=value` apply to both Typst calls. The config's `inputs` list supplies the real build's inputs; a command-line `--input` overrides the same key, PDF mode ignores the list, and JSON `coverage.typst_inputs` records what was compiled. Other compiler switches are not supported in this version; use PDF mode for a custom build.

Text output has one finding per line: severity, rule ID, physical page, bounding box and a short excerpt. JSON is one object with `schema_version`, `findings`, `coverage`, `pages` and `error`. `coverage.text_unavailable_pages` lists pages without extractable text even if that warning is disabled. Coordinates are points from the top-left of the unrotated CropBox; page numbers are physical and one-based. A clean text-mode run emits nothing. Exit 0 means no findings at the selected failure level, 1 means findings, 2 means invalid input or a tool failure. `--fail-on error` lets warnings remain advisory. `coverage.accepted` counts warnings hidden by the `accepted` list and `coverage.accepted_unmatched` lists entries that no longer match anything. JSON errors also use the same envelope.

## Typst hook

At the beginning of each slide's page content, after its page break:

```typst
#metadata((title: title)) <deck-slide>
```

`title` should be a string or `none`. `deck-lint snippet` prints this line. Typst mode without the hook reports `typst.metadata-missing` and prints the snippet. Plain PDF mode does not require metadata.

Optional fields: `pages: 2` permits up to two physical pages before the next marker (including intentional overlays); `kind: "notes"` marks a notes page; `notes: true` declares speaker notes available for a slide. Emit one marker per physical slide/overlay, or declare its intended `pages`. Every marker starts a new interval; repeated overlay markers on consecutive pages therefore each cover one page. Multiple markers on one page are rejected. Touying/Polylux pdfpc metadata is not interpreted. A marker placed before the actual page break gives incorrect boundaries; check placement in your slide function. `--set require_titles=true` and `--set require_notes=true` enable checks for the optional fields. Unmarked notes pages look like spillover; mark them explicitly.

The query uses `it.location().page()`, a physical page number unaffected by resets to the displayed page counter. It includes the final slide's span through the end of the PDF.

## Defaults and rules

Optional config is an explicitly named TOML file with flat keys. Precedence: built-in defaults, config, then repeatable `--set key=value`. `--disable rule.id` adds rule exclusions. Values use TOML types; unknown keys, invalid types/ranges and unknown rule IDs fail with exit 2. There is no parent-folder search or plugin system.

Two list settings are meant for a per-deck `deck-lint.toml` next to the deck:

```toml
# Regexes; each match on a rendered line is an error. Use single quotes so backslashes stay literal.
forbidden = ['TICKET-\d+', 'Do not say', 'Jhon']
# Warnings already judged deliberate, as "rule.id: excerpt" copied from check output.
accepted = ['wrap.runt: begins.', 'wrap.long: A DELIBERATELY LONG SECTION OPENER']
# Typst inputs of the delivered build, so check --typ lints that deck.
inputs = ['theme=light', 'notes=false']
```

`forbidden` catches internal IDs, speaker guidance and known misspellings that reach the slides. Matching is per rendered line, so a pattern split across a line break is missed. `accepted` hides warnings only, never errors, and matches rule plus excerpt rather than page, so it survives slides moving. Editing an accepted line changes its excerpt and the warning returns.

Font sizes and geometric tolerances are normalized to a 540-point-high slide. Reported coordinates retain original PDF units; font findings include actual and normalized sizes. For example, `min_font=16` on a 720-point-high page means an actual threshold of 21.3pt. This keeps the thresholds useful for differently scaled exports. Defaults: `min_font=12`, `footer_min_font=9`, `footer_band=0.09` (bottom fraction), `max_lines=2`, `runt_ratio=0.35`, `overlap_pt=2`, `image_dpi=100`, `aspect=""` (consistent size only), `max_pages=0` (unlimited), `require_titles=false`, `require_notes=false`, `disabled=[]`, `forbidden=[]`, `accepted=[]`, `inputs=[]`.

| Rule                                          | Meaning                                                                                          |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `text.off-page`                               | Drawn text crosses the page boundary (error).                                                    |
| `text.overlap`                                | Separate text runs have substantially intersecting non-space character boxes.                    |
| `wrap.runt`                                   | A multi-line paragraph ends in one unusually short word.                                         |
| `wrap.long`                                   | A paragraph or bullet exceeds the line budget; monospace blocks are excluded.                    |
| `font.small`                                  | Text is below the body/footer size threshold.                                                    |
| `font.tall`                                   | A mixed-font line has unusually tall metrics or an unscaled emoji; inspect baseline and leading. |
| `font.unembedded`                             | A font resource is not embedded.                                                                 |
| `text.placeholder`                            | Rendered TODO, FIXME or TBD token.                                                               |
| `text.forbidden`                              | Rendered text matches a configured `forbidden` pattern (error).                                  |
| `image.low-dpi`                               | A large placed raster image is below the effective DPI threshold.                                |
| `page.size`                                   | Mixed page dimensions, or the requested aspect ratio is wrong.                                   |
| `page.budget`                                 | Physical page count exceeds the budget (error).                                                  |
| `pdf.repaired`                                | MuPDF repaired the file while opening it; verify rendering.                                      |
| `page.no-text`                                | No extractable text; typography checks cannot assess this page.                                  |
| `typst.spillover`                             | A slide spans more pages than declared (error).                                                  |
| `typst.unmarked`                              | Pages precede the first slide marker.                                                            |
| `typst.notes-page`                            | An explicitly marked notes page is in the PDF.                                                   |
| `typst.title-missing` / `typst.notes-missing` | Opt-in source metadata checks.                                                                   |
| `typst.compiler-warning`                      | Typst emitted a warning, including unavailable fonts.                                            |

Compiler warning messages are deduplicated first-line summaries; run Typst directly for source locations and full diagnostics. Rules are warnings unless marked as errors. Default failure level is warning.

## Limits

PDFs contain positioned glyphs, not reliable paragraph or table semantics. Paragraph grouping and overlap are heuristics. Multi-line date cells can trigger wrapping checks; a two-line mid-phrase break of reasonable length cannot be distinguished from an intentional break. Clipping, occlusion, vector-only text, image contents, tight math and rotated text need visual inspection. Bounding boxes are not precise glyph outlines. A tall font span suggests a metric issue; a PDF does not identify the reason a font was chosen or prove that it changed line spacing.

No contrast check against arbitrary images/gradients, title-case/style judgment, slide narrative analysis or speaker-note inference from a PDF. Blank or image-only pages report missing text coverage. Font checks allow embedded Type3 fonts. Low-resolution checks use placed size, not an image's stored DPI tag.

Use a contact sheet for one visual pass and inspect only flagged pages at higher resolution. The sheet is an aid, not a test result. `sheet` refuses to overwrite unless `--replace` is given, and then only replaces an existing PNG; keep one fixed sheet path per deck so an open viewer reloads it.

## Development and evidence

```sh
uv sync --group dev
uv run pytest -q
uv run ruff check .
uv run mypy --ignore-missing-imports deck_lint.py
```

Tests need Typst on `PATH`; the emoji fixture is skipped when its macOS fonts (Apple Color Emoji, Helvetica Neue) are unavailable.

Synthetic fixtures are checked in; real decks and reports belong under ignored `tmp/`. Tests use plain Typst without downloaded packages. Do not add reference content, local paths or private test excerpts to version control.

References: [Typst query](https://typst.app/docs/reference/introspection/query/), [physical locations](https://typst.app/docs/reference/introspection/location/), [PyMuPDF text extraction](https://pymupdf.readthedocs.io/en/latest/app1.html), [text tracing](https://pymupdf.readthedocs.io/en/latest/functions.html#Page.get_texttrace).

## License

MIT, see [LICENSE](LICENSE).
