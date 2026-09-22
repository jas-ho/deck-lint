---
name: deck-lint
description: Check generated slide PDFs for overflow, wrapping, text collisions and typography risks using the local deck-lint CLI. Use after building or revising a slide deck, before delivery; supports any PDF export and optional Typst slide metadata.
---

# Deck layout checks

Run `deck-lint check path/to/deck.pdf --json` after the final build. It reports findings as text without rendering images. Exit 0 means no findings at the selected failure level, 1 means findings to assess, 2 means the check failed. A failed or incomplete check is not a clean deck.

For a custom Typst deck, `deck-lint check --typ path/to/deck.typ --json` compiles a temporary PDF and checks slide boundaries. Match the build's `--input`, `--root` and `--font-path` options. Stop source edits while it runs. This mode checks its own compile, not a pre-existing PDF. For unsupported compiler options, lint the actual exported PDF and disclose the missing slide-boundary check.

If metadata is missing, show the snippet returned by the tool. Add it inside the slide function only when source editing is authorized. It must be after the slide's page break; emit one marker per physical overlay or declare a `pages` allowance. The tool never inserts it automatically.

Fix definite spillover and unintended collisions. Assess wrapping/font warnings in context; deliberate headings, quotations, diagrams and formulas can trigger them. Do not repeatedly rewrite intentional layouts or silently disable checks to get exit 0. JSON `coverage` lists disabled checks; image-only pages have no typography coverage.

For a final visual pass, run `deck-lint sheet deck.pdf --output sheet.png` using a new output path. Inspect the sheet once, then only unclear/flagged pages at higher resolution. This does not check contrast, image contents or the quality of the slide narrative.

Use `deck-lint check --help` for configuration. If the CLI is unavailable, report that and use the existing visual-check workflow; do not imply the deck was linted.
