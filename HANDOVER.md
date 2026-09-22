# Handover

`deck-lint` is installed with `uv tool install --editable .`. The executable is on the user's PATH, and edits in this checkout take effect without reinstalling. Run from any directory:

```sh
deck-lint check deck.pdf --json
deck-lint check --typ deck.typ --json
deck-lint sheet deck.pdf --output sheet.png
```

PDF mode checks the file supplied. Typst mode compiles to temporary storage; it requires the one-line marker from `deck-lint snippet` for slide-boundary checks. It does not update the source or its exported PDF. Do not run while the source/imports are being edited.

Text mode is silent when clean. Exit codes: 0 below the chosen failure level, 1 findings, 2 failed check. Wrapping/font/collision warnings require judgment. Contrast, image contents and arbitrary mid-phrase breaks still need visual inspection. A full-size emoji warning identifies a risk, not proof of inflated line spacing.

## Validation

26 tests pass, covering synthetic Typst layouts and generated PDF edge cases. Ruff and mypy are the code checks. Tests need Typst; the emoji fixture is skipped when its macOS fonts are unavailable.

The private reference copy has 34 slide starts across 36 pages: two confirmed spillovers, 23 wrapping-risk findings, and three false positives for intentional layouts. The full per-finding assessment is in ignored `tmp/reference/REPORT.md`; the contact sheet is `tmp/reference/sheet.png`. No reference-project files were edited. PDF checks took about 0.23 seconds; Typst compile/query/check about 0.85 seconds on the test machine, before the version-check subprocess was added.

## Integration status (2026-09-22)

- Installed: CLI on PATH; shared skill linked for Claude Code and Codex through `agent-config`.
- Discovered: Codex runtime lists the skill as enabled. The existing deck-building Claude session successfully loaded the skill after receiving the handover.
- Dependencies ready: installed uv environment; Typst 0.15.1 available for source mode.
- Operationally exercised: CLI, Typst mode and contact sheet, including invocation from another directory. The deck-building Claude session loaded the skill and invoked the CLI for a baseline after the handover.

The shared instructions require linting after completed slide builds. There is no shell hook. Both `agent-config audit --runtime` and runtime skill inspection were run; the parity audit passed. The active Claude session discovered the new skill without a restart. Other existing sessions can use the CLI directly if their skill list has not refreshed.

## Next use

Add the metadata line to the actual deck only as part of an authorized deck edit, then run Typst mode after its next build. Address spillovers first, assess wrapping warnings, and inspect one contact sheet. Keep the private test copy/report out of any published repository.

Development: `uv sync --group dev`, then `uv run pytest -q`, `uv run ruff check .`, and `uv run mypy --ignore-missing-imports deck_lint.py`.
