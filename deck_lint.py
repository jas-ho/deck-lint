"""Local PDF geometry checks; sources are never rewritten."""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from statistics import median

import pymupdf as pdf
import typer

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)
SNIPPET = "#metadata((title: title)) <deck-slide>"
DEFAULTS = dict(
    min_font=12.0,
    footer_min_font=9.0,
    footer_band=0.09,
    max_lines=2,
    runt_ratio=0.35,
    overlap_pt=2.0,
    image_dpi=100.0,
    aspect="",
    max_pages=0,
    require_titles=False,
    require_notes=False,
    disabled=[],
)
RULES = set(
    "text.off-page text.overlap wrap.runt wrap.long font.small font.tall "
    "font.unembedded text.placeholder image.low-dpi page.size page.budget "
    "page.no-text typst.spillover typst.unmarked typst.notes-page "
    "typst.title-missing typst.notes-missing typst.compiler-warning "
    "typst.metadata-missing pdf.repaired".split()
)
BULLET = re.compile(r"^\s*(?:[•●▪◦‣–-]|\d+[.)])\s*")
PLACEHOLDER = re.compile(r"\b(?:TODO|FIXME|TBD)\b")


def config_values(path, overrides, disabled):
    cfg = DEFAULTS.copy()
    supplied = tomllib.loads(path.read_text()) if path else {}
    for item in overrides:
        key, sep, value = item.partition("=")
        if not sep:
            raise ValueError("--set requires key=value")
        try:
            supplied[key] = tomllib.loads("value=" + value)["value"]
        except tomllib.TOMLDecodeError:
            if key != "aspect":
                raise ValueError(f"invalid TOML value for {key}") from None
            supplied[key] = value
    for key, value in supplied.items():
        if key not in cfg:
            raise ValueError(f"unknown setting: {key}")
        expected = type(cfg[key])
        if expected is float:
            valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
        else:
            valid = type(value) is expected
        if not valid:
            raise ValueError(f"invalid value for {key}")
        cfg[key] = value
    if (
        cfg["max_lines"] < 1
        or cfg["max_pages"] < 0
        or not 0 < cfg["runt_ratio"] < 1
        or not 0 <= cfg["footer_band"] < 0.5
    ):
        raise ValueError("invalid line/page limit, runt ratio or footer band")
    cfg["disabled"] = cfg["disabled"] + list(disabled)
    if any(not isinstance(r, str) or r not in RULES for r in cfg["disabled"]):
        raise ValueError("unknown disabled rule")
    if cfg["aspect"]:
        pieces = cfg["aspect"].split(":")
        if len(pieces) != 2 or any(not math.isfinite(float(v)) or float(v) <= 0 for v in pieces):
            raise ValueError("aspect must be positive WIDTH:HEIGHT")
    return cfg


def compact(text, limit=110):
    return " ".join(text.split())[:limit]


def issue(rule, page, message, bbox=None, text="", severity="warning"):
    return dict(
        rule=rule,
        severity=severity,
        page=page,
        bbox=[round(x, 2) for x in bbox] if bbox is not None else None,
        message=message,
        excerpt=compact(text),
    )


def text_lines(page):
    flags = pdf.TEXTFLAGS_DICT & ~pdf.TEXT_PRESERVE_IMAGES & ~pdf.TEXT_MEDIABOX_CLIP
    lines = []
    seen = set()
    for block in page.get_text("dict", flags=flags, clip=pdf.INFINITE_RECT())["blocks"]:
        for line in block.get("lines", []):
            spans = [s for s in line["spans"] if s["text"].strip()]
            if not spans:
                continue
            key = (tuple(round(v, 1) for v in line["bbox"]), "".join(s["text"] for s in spans))
            if key in seen:
                continue
            seen.add(key)
            lines.append(
                dict(
                    box=pdf.Rect(line["bbox"]),
                    spans=spans,
                    text="".join(s["text"] for s in line["spans"]).strip(),
                    size=median(s["size"] for s in spans),
                    direction=line["dir"],
                    baseline=median(s["origin"][1] for s in spans),
                )
            )
    return lines


def paragraphs(lines):
    """Split bullets; join adjacent wrapped lines, including split PDF blocks."""
    groups = []
    for line in lines:
        if line["direction"] != (1.0, 0.0):
            continue
        if groups:
            prev, first = groups[-1][-1], groups[-1][0]
            gap = line["baseline"] - prev["baseline"]
            similar = abs(line["size"] - prev["size"]) < 0.1 * max(1, prev["size"])
            indent = abs(line["box"].x0 - first["box"].x0) <= max(3, first["size"])
            if (
                similar
                and indent
                and 0.8 * line["size"] < gap < 1.9 * line["size"]
                and not BULLET.match(line["text"])
            ):
                groups[-1].append(line)
                continue
        groups.append([line])
    return groups


def drawn_runs(page):
    """Keep character boxes, so empty space between positioned labels isn't ink."""
    runs = []
    seen = set()
    for span in page.get_texttrace():
        if span["type"] == 3 or span["opacity"] <= 0:
            continue
        rows = {}
        for char in span["chars"]:
            if chr(char[0]).isspace():
                continue
            rows.setdefault(round(char[2][1], 1), []).append(char)
        for chars in rows.values():
            boxes = [pdf.Rect(c[3]) for c in chars]
            box = pdf.Rect(boxes[0])
            for b in boxes[1:]:
                box |= b
            text = "".join(chr(c[0]) for c in chars)
            key = (text, *(round(v, 1) for v in box))
            if key not in seen:
                seen.add(key)
                runs.append((box, boxes, text))
    return runs


def inspect_page(page, cfg):
    findings = []
    n = page.number + 1
    bounds = pdf.Rect(0, 0, page.cropbox.width, page.cropbox.height)
    scale = page.rect.height / 540
    lines = text_lines(page)
    if not lines:
        findings.append(issue("page.no-text", n, "No extractable text; typography checks have no coverage"))
    for line in lines:
        box, spans = line["box"], line["spans"]
        displayed = box * page.rotation_matrix
        footer = displayed.y0 >= page.rect.height * (1 - cfg["footer_band"])
        threshold = cfg["footer_min_font"] if footer else cfg["min_font"]
        small = [s for s in spans if s["size"] / scale < threshold - 0.1]
        if small:
            size = min(s["size"] for s in small)
            findings.append(
                issue(
                    "font.small",
                    n,
                    f"{size:.1f}pt actual / {size / scale:.1f}pt normalized, below {threshold:g}",
                    box,
                    line["text"],
                )
            )
        if PLACEHOLDER.search(line["text"]):
            findings.append(issue("text.placeholder", n, "Placeholder token", box, line["text"]))
        emoji = [s for s in spans if "emoji" in s["font"].lower()]
        ordinary = [s for s in spans if "emoji" not in s["font"].lower()]
        emoji_risk = bool(
            emoji and ordinary and max(s["size"] for s in emoji) >= 0.9 * median(s["size"] for s in ordinary)
        )
        if emoji_risk:
            findings.append(
                issue(
                    "font.tall",
                    n,
                    "Full-size emoji font mixed with text; check baseline and leading",
                    box,
                    line["text"],
                )
            )
        heights = [pdf.Rect(s["bbox"]).height for s in spans]
        if (
            not emoji_risk
            and len(set(s["font"] for s in spans)) > 1
            and max(heights) > 1.4 * min(heights)
            and max(s["size"] for s in spans) < 1.15 * min(s["size"] for s in spans)
        ):
            findings.append(
                issue(
                    "font.tall",
                    n,
                    "Mixed-font line has unusually different span heights; check leading",
                    box,
                    line["text"],
                )
            )
    for group in paragraphs(lines):
        if any(s["flags"] & 8 for line in group for s in line["spans"]):
            continue
        first, last = group[0], group[-1]
        if len(group) > cfg["max_lines"]:
            findings.append(
                issue(
                    "wrap.long",
                    n,
                    f"{len(group)} lines (limit {cfg['max_lines']})",
                    first["box"] | last["box"],
                    first["text"],
                )
            )
        words = re.findall(r"\S+", last["text"])
        if (
            len(group) >= 2
            and len(words) == 1
            and any(c.isalnum() for c in words[0])
            and last["box"].width < cfg["runt_ratio"] * group[-2]["box"].width
        ):
            findings.append(issue("wrap.runt", n, "Single-word final line", last["box"], last["text"]))
    runs = drawn_runs(page)
    tolerance = cfg["overlap_pt"] * scale
    for i, (box, chars, text) in enumerate(runs):
        if not (bounds + (-scale, -scale, scale, scale)).contains(box):
            findings.append(issue("text.off-page", n, "Text crosses page bounds", box, text, "error"))
        for other, other_chars, other_text in runs[:i]:
            overlap = box & other
            if overlap.width <= tolerance or overlap.height <= tolerance:
                continue
            if any(
                (a & b).width > tolerance and (a & b).height > max(tolerance, 0.25 * min(a.height, b.height))
                for a in chars
                for b in other_chars
            ):
                findings.append(
                    issue(
                        "text.overlap",
                        n,
                        "Text runs intersect; inspect for a collision",
                        overlap,
                        text + " / " + other_text,
                    )
                )
    seen_fonts = set()
    for xref, ext, kind, name, *_ in page.get_fonts(full=True):
        if ext == "n/a" and kind != "Type3" and xref not in seen_fonts:
            seen_fonts.add(xref)
            findings.append(issue("font.unembedded", n, f"Font not embedded: {name}"))
    for image in page.get_image_info():
        a, b, c, d, _, _ = image["transform"]
        width, height = math.hypot(a, b), math.hypot(c, d)
        if min(width, height) <= 0 or width * height < 0.01 * bounds.get_area():
            continue
        dpi = min(image["width"] * 72 / width, image["height"] * 72 / height)
        if dpi < cfg["image_dpi"]:
            findings.append(
                issue(
                    "image.low-dpi",
                    n,
                    f"{dpi:.0f} effective DPI (minimum {cfg['image_dpi']:g})",
                    image["bbox"],
                )
            )
    return findings


def metadata_findings(markers, pages, cfg):
    if not isinstance(markers, list):
        raise ValueError("Typst metadata must be an array")
    if not markers:
        return [issue("typst.metadata-missing", None, "Add a marker inside each slide; see snippet")]
    previous = 0
    for marker in markers:
        if not isinstance(marker, dict):
            raise ValueError("Each deck-slide marker must be a dictionary")
        page = marker.get("page")
        if type(page) is not int or not previous < page <= pages:
            raise ValueError("Markers must have unique increasing physical pages within the PDF")
        previous = page
        if marker.get("title") is not None and not isinstance(marker["title"], str):
            raise ValueError("Marker title must be a string or none")
        if (
            marker.get("kind", "slide") not in ("slide", "notes")
            or type(marker.get("pages", 1)) is not int
            or marker.get("pages", 1) < 1
            or type(marker.get("notes", False)) is not bool
        ):
            raise ValueError("Invalid marker kind, pages or notes field")
    result = []
    if markers[0]["page"] != 1:
        result.append(issue("typst.unmarked", 1, "Pages before the first slide marker"))
    for index, marker in enumerate(markers):
        page = marker["page"]
        end = markers[index + 1]["page"] if index + 1 < len(markers) else pages + 1
        span = end - page
        title = marker.get("title") or ""
        if span > marker.get("pages", 1):
            result.append(
                issue(
                    "typst.spillover",
                    page,
                    f"Slide occupies {span} pages; expected at most {marker.get('pages', 1)}",
                    text=title,
                    severity="error",
                )
            )
        if marker.get("kind", "slide") == "notes":
            result.append(issue("typst.notes-page", page, "Notes page included in deck", text=title))
        else:
            if cfg["require_titles"] and not title.strip():
                result.append(issue("typst.title-missing", page, "No title in slide metadata"))
            if cfg["require_notes"] and not marker.get("notes", False):
                result.append(
                    issue("typst.notes-missing", page, "No notes declared in slide metadata", text=title)
                )
    return result


def analyze(path, cfg, markers=None):
    with pdf.open(path) as doc:
        if not doc.is_pdf or doc.needs_pass or not len(doc):
            raise ValueError("Expected a nonempty, readable, unencrypted PDF")
        findings = []
        if doc.is_repaired:
            findings.append(issue("pdf.repaired", None, "PDF needed repair to open; verify rendering"))
        unembedded = set()
        size = doc[0].rect
        aspect = cfg["aspect"]
        ratio = float(aspect.split(":")[0]) / float(aspect.split(":")[1]) if aspect else None
        for page in doc:
            if (
                abs(page.rect.width - size.width) > 1
                or abs(page.rect.height - size.height) > 1
                or (ratio and abs(page.rect.width / page.rect.height / ratio - 1) > 0.01)
            ):
                findings.append(
                    issue("page.size", page.number + 1, "Unexpected page dimensions or aspect ratio")
                )
            for finding in inspect_page(page, cfg):
                if finding["rule"] == "font.unembedded":
                    if finding["message"] in unembedded:
                        continue
                    unembedded.add(finding["message"])
                findings.append(finding)
        if cfg["max_pages"] and len(doc) > cfg["max_pages"]:
            findings.append(
                issue(
                    "page.budget",
                    None,
                    f"{len(doc)} pages exceed budget {cfg['max_pages']}",
                    severity="error",
                )
            )
        if markers is not None:
            findings.extend(metadata_findings(markers, len(doc), cfg))
        return len(doc), findings


def command(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise ValueError(compact(result.stderr, 1200) or f"{args[0]} failed")
    return result


def compile_typst(source, target, root, inputs, font_paths):
    before = source.read_bytes()
    version = command(["typst", "--version"]).stdout
    match = re.search(r"typst (\d+)\.(\d+)\.(\d+)", version)
    if not match or tuple(map(int, match.groups())) < (0, 15, 1):
        raise ValueError("Typst mode requires Typst 0.15.1 or newer (eval --in)")
    opts = []
    if root:
        opts += ["--root", str(root.resolve())]
    for value in inputs:
        if "=" not in value:
            raise ValueError("--input requires key=value")
        opts += ["--input", value]
    for path in font_paths:
        opts += ["--font-path", str(path.resolve())]
    compiled = command(["typst", "compile", str(source.resolve()), str(target), *opts])
    queried = command(
        [
            "typst",
            "eval",
            "query(<deck-slide>).map(it => (..it.value, page: it.location().page()))",
            "--in",
            str(source.resolve()),
            *opts,
        ]
    )
    if source.read_bytes() != before:
        raise ValueError("Source changed during compile/query; retry when editing has stopped")
    warnings = set(re.findall(r"^warning: (.+)$", compiled.stderr + "\n" + queried.stderr, re.MULTILINE))
    return json.loads(queried.stdout), [issue("typst.compiler-warning", None, w) for w in sorted(warnings)]


def emit(result, json_output):
    if json_output:
        print(json.dumps(result, ensure_ascii=False))
    elif result["error"]:
        print("deck-lint: " + result["error"], file=sys.stderr)
    else:
        for f in result["findings"]:
            location = f"p{f['page']}" if f["page"] else "deck"
            bbox = ",".join(f"{v:g}" for v in f["bbox"]) if f["bbox"] else "-"
            excerpt = f" | {f['excerpt']}" if f["excerpt"] else ""
            print(f"{f['severity']} {f['rule']} {location} [{bbox}] {compact(f['message'])}{excerpt}")
        if "snippet" in result:
            print("Inside each slide page:\n" + result["snippet"], file=sys.stderr)


def envelope(**values):
    return dict(schema_version=1, pages=None, findings=[], coverage={}, error=None, **values)


@app.command()
def check(
    document: Path | None = typer.Argument(None),
    typ: Path | None = typer.Option(None, help="Compile and inspect a Typst source"),
    json_output: bool = typer.Option(False, "--json"),
    config: Path | None = typer.Option(None),
    setting: list[str] = typer.Option([], "--set"),
    disable: list[str] = typer.Option([]),
    fail_on: str = typer.Option("warning"),
    root: Path | None = typer.Option(None),
    inputs: list[str] = typer.Option([], "--input"),
    font_paths: list[Path] = typer.Option([], "--font-path"),
):
    """Check a PDF, or compile a Typst source into temporary storage."""
    result = envelope()
    try:
        if (document is None) == (typ is None):
            raise ValueError("Provide a PDF or --typ SOURCE, but not both")
        if fail_on not in ("warning", "error"):
            raise ValueError("--fail-on must be warning or error")
        if not typ and (root or inputs or font_paths):
            raise ValueError("Typst options require --typ")
        cfg = config_values(config, setting, disable)
        with tempfile.TemporaryDirectory(prefix="deck-lint-") as scratch:
            markers, warnings = None, []
            if typ:
                document = Path(scratch) / "compiled.pdf"
                markers, warnings = compile_typst(typ, document, root, inputs, font_paths)
            count, findings = analyze(document, cfg, markers)
        result["pages"] = count
        result["findings"] = sorted(
            [f for f in findings + warnings if f["rule"] not in cfg["disabled"]],
            key=lambda f: (f["page"] or 0, f["rule"], f["bbox"] or []),
        )
        result["coverage"] = dict(
            pdf_geometry=True,
            typst_metadata=bool(markers),
            disabled=cfg["disabled"],
            visual_review=False,
            text_unavailable_pages=[f["page"] for f in findings if f["rule"] == "page.no-text"],
        )
        if any(f["rule"] == "typst.metadata-missing" for f in result["findings"]):
            result["snippet"] = SNIPPET
        emit(result, json_output)
        raise typer.Exit(
            int(any(fail_on == "warning" or f["severity"] == "error" for f in result["findings"]))
        )
    except typer.Exit:
        raise
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        result["error"] = compact(str(exc), 1200)
        emit(result, json_output)
        raise typer.Exit(2) from None


@app.command()
def snippet():
    """Print the minimal marker for a custom Typst slide function."""
    print(SNIPPET)


@app.command()
def sheet(
    document: Path,
    output: Path = typer.Option(...),
    columns: int = typer.Option(6, min=1, max=20),
    width: int = typer.Option(240, min=80, max=800),
):
    """Write a numbered, low-resolution PNG contact sheet. Never overwrite."""
    try:
        if output.exists() or output.resolve() == document.resolve():
            raise ValueError("Output exists; choose a new output path")
        with pdf.open(document) as doc, pdf.open() as canvas:
            if not doc.is_pdf or doc.needs_pass or not len(doc):
                raise ValueError("Expected a nonempty unencrypted PDF")
            height = math.ceil(max(p.rect.height / p.rect.width for p in doc) * width) + 22
            rows = math.ceil(len(doc) / columns)
            if rows * height * columns * width > 40_000_000:
                raise ValueError("Contact sheet exceeds 40 megapixels; reduce --width")
            page = canvas.new_page(width=columns * width, height=rows * height)
            for index, source in enumerate(doc):
                x, y = index % columns * width, index // columns * height
                thumb = source.get_pixmap(
                    matrix=pdf.Matrix((width - 8) / source.rect.width, (width - 8) / source.rect.width),
                    alpha=False,
                )
                page.insert_image(pdf.Rect(x + 4, y + 18, x + width - 4, y + height - 4), pixmap=thumb)
                page.insert_text((x + 4, y + 12), str(index + 1), fontsize=10)
            data = page.get_pixmap(alpha=False).tobytes("png")
            with output.open("xb") as dest:
                dest.write(data)
        print(output)
    except (OSError, ValueError, RuntimeError) as exc:
        print("deck-lint: " + compact(str(exc)), file=sys.stderr)
        raise typer.Exit(2) from None


def main():
    pdf.TOOLS.mupdf_display_errors(False)
    pdf.TOOLS.mupdf_display_warnings(False)
    try:
        raise SystemExit(app(standalone_mode=False))
    except typer.TyperException as exc:
        result = envelope()
        result["error"] = exc.format_message()
        emit(result, "--json" in sys.argv)
        raise SystemExit(2) from None
    except typer.Exit as exc:
        raise SystemExit(exc.exit_code) from None


if __name__ == "__main__":
    main()
