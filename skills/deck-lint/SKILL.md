---
name: deck-lint
description: Check generated slide PDFs for overflow, wrapping, text collisions, typography risks and forbidden strings using the local deck-lint CLI, and render a contact sheet. Use after building or revising a slide deck, before delivery; supports any PDF export and optional Typst slide metadata.
---

# Deck layout checks

Three commands, run from any directory:

```sh
deck-lint check --typ deck.typ --config deck-lint.toml --json   # Typst: same --input/--root/--font-path as the real build
deck-lint check deck.pdf --config deck-lint.toml --json         # any other PDF export
deck-lint sheet deck.pdf --output sheet.png --replace --columns 4 --width 420
```

Exit 0 means no findings at the selected failure level, 1 means findings to assess, 2 means the check failed. A failed or incomplete check is not a clean deck. Run `check` after each batch of edits and before delivery; use the contact sheet for visual review instead of rendering pages one at a time.

**Typst mode** compiles a temporary PDF and checks slide boundaries (`typst.spillover`). It must compile the delivered build: put that build's inputs in the config's `inputs` list (or pass the same `--input`, `--root` and `--font-path` options), otherwise it lints a different deck. Check `coverage.typst_inputs`. Lint the public build; a speaker-notes variant does not need layout linting. Stop source edits while it runs. It checks its own compile, not a pre-existing PDF. For unsupported compiler options, lint the exported PDF and disclose the missing slide-boundary check.

**PDF mode** cannot see slide boundaries, so a slide spilling onto an extra page goes unnoticed. Add `--set max_pages=N` with the expected page count; exceeding it is an error.

If metadata is missing, show the snippet returned by the tool. Add it inside the slide function only when source editing is authorized. It must be after the slide's page break; emit one marker per physical overlay or declare a `pages` allowance. The tool never inserts it automatically.

**Per-deck config** `deck-lint.toml` next to the deck (TOML single quotes keep regex backslashes literal):

```toml
forbidden = ['TICKET-\d+', 'Do not say', 'Jhon']   # internal IDs, speaker guidance, known misspellings: errors
accepted = ['wrap.runt: begins.']                   # warnings judged deliberate, "rule.id: excerpt" from check output
inputs = ['theme=light']                            # Typst --input values of the delivered build
```

Fix definite spillover, forbidden strings and unintended collisions. Assess wrapping/font warnings in context; deliberate headings, quotations, diagrams and formulas can trigger them. Once a warning has been checked on the rendered slide and judged deliberate, add it to `accepted` so later runs show only new findings, and tell the user which entries you added. `accepted` never hides errors. Drop entries listed in `coverage.accepted_unmatched`. Do not repeatedly rewrite intentional layouts or disable whole rules to get exit 0. JSON `coverage` lists disabled checks; image-only pages have no typography coverage.

**Contact sheet:** keep one fixed path per deck with `--replace`, so an open viewer reloads it; without `--replace` it refuses to overwrite. Inspect the sheet once, then only unclear or flagged pages at 120 ppi or more (at low resolution bullets can vanish). This does not check contrast, image contents or the quality of the slide narrative.

Use `deck-lint check --help` for all settings. If the CLI is unavailable, report that and use the existing visual-check workflow; do not imply the deck was linted.
