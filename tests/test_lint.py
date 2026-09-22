import json
import subprocess
import sys
from pathlib import Path

import pymupdf as pdf
import pytest

from deck_lint import DEFAULTS, analyze, config_values, metadata_findings

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "deck_lint.py"


def run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(CLI), *map(str, args)], capture_output=True, text=True, cwd=cwd
    )


@pytest.fixture(scope="session")
def compiled(tmp_path_factory):
    folder = tmp_path_factory.mktemp("pdfs")
    for name in ["clean", "layout"]:
        subprocess.run(
            ["typst", "compile", str(ROOT / f"tests/fixtures/{name}.typ"), str(folder / f"{name}.pdf")],
            check=True,
            capture_output=True,
        )
    return folder


def test_clean_quiet_and_from_other_directory(compiled, tmp_path):
    r = run("check", compiled / "clean.pdf", cwd=tmp_path)
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


def test_typst_clean_and_metadata_options():
    r = run(
        "check",
        "--typ",
        ROOT / "tests/fixtures/clean.typ",
        "--json",
        "--set",
        "require_titles=true",
        "--set",
        "require_notes=true",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(r.stdout)["coverage"]["typst_metadata"]


def test_known_layout_rules():
    r = run("check", "--typ", ROOT / "tests/fixtures/layout.typ", "--json")
    data = json.loads(r.stdout)
    assert r.returncode == 1, data
    rules = {f["rule"] for f in data["findings"]}
    assert {
        "wrap.runt",
        "wrap.long",
        "text.overlap",
        "text.off-page",
        "font.small",
        "text.placeholder",
        "typst.spillover",
    } <= rules
    assert any(f["rule"] == "wrap.runt" and f["excerpt"] == "OFF" for f in data["findings"])
    assert any(f["rule"] == "typst.spillover" and f["page"] == 3 for f in data["findings"])


def test_source_and_existing_pdf_are_unchanged(tmp_path):
    source = tmp_path / "sample.typ"
    source.write_text("#set page(width: 960pt, height: 540pt)\nHello")
    target = source.with_suffix(".pdf")
    target.write_bytes(b"keep this existing file")
    before = source.read_bytes()
    r = run("check", "--typ", source, "--json")
    assert r.returncode == 1
    data = json.loads(r.stdout)
    assert data["snippet"].startswith("#metadata")
    assert source.read_bytes() == before
    assert target.read_bytes() == b"keep this existing file"
    text = run("check", "--typ", source)
    assert "#metadata" in text.stderr
    assert len(text.stdout.splitlines()) == len(data["findings"])


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--set", "min_font=nan"],
        ["--set", "bogus=1"],
        ["--set", "max_lines=0"],
        ["--set", "max_pages=true"],
        ["--disable", "bogus"],
        ["--set", "aspect=1:0"],
        ["--set", "footer_band=2"],
        ["--fail-on", "never"],
        ["--wat"],
    ],
)
def test_json_errors(compiled, args):
    base = ["check", "--json"] if not args else ["check", compiled / "clean.pdf", "--json"]
    r = run(*base, *args)
    assert r.returncode == 2
    assert json.loads(r.stdout)["error"]
    assert "Traceback" not in r.stderr


def test_corrupt_and_encrypted_pdf(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a PDF")
    assert run("check", bad, "--json").returncode == 2
    with pdf.open() as doc:
        doc.new_page()
        doc.save(
            tmp_path / "encrypted.pdf", encryption=pdf.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="reader"
        )
    r = run("check", tmp_path / "encrypted.pdf", "--json")
    assert r.returncode == 2
    assert json.loads(r.stdout)["error"]


def test_config_precedence(tmp_path):
    c = tmp_path / "lint.toml"
    c.write_text('min_font=15\ndisabled=["wrap.runt"]\n')
    cfg = config_values(c, ["min_font=18"], ["wrap.long"])
    assert cfg["min_font"] == 18
    assert cfg["disabled"] == ["wrap.runt", "wrap.long"]


def test_metadata_limits_and_last_slide():
    markers = [{"title": "One", "page": 1}, {"title": "Two", "page": 2}]
    findings = metadata_findings(markers, 3, DEFAULTS)
    assert [(f["rule"], f["page"]) for f in findings] == [("typst.spillover", 2)]
    markers[-1]["pages"] = 2
    assert not metadata_findings(markers, 3, DEFAULTS)
    # Repeated overlays each define their own interval, pages is an upper limit.
    assert not metadata_findings([{"page": 1, "pages": 2}, {"page": 2, "pages": 2}], 2, DEFAULTS)
    with pytest.raises(ValueError):
        metadata_findings([{"page": 1}, {"page": 1}], 2, DEFAULTS)
    with pytest.raises(ValueError):
        metadata_findings([{"page": 3}], 2, DEFAULTS)
    cfg = DEFAULTS | dict(require_titles=True, require_notes=True)
    rules = {f["rule"] for f in metadata_findings([{"page": 2}, {"page": 3, "kind": "notes"}], 3, cfg)}
    assert {"typst.unmarked", "typst.title-missing", "typst.notes-missing", "typst.notes-page"} <= rules


def test_budget_aspect_and_advisory(compiled):
    assert run("check", compiled / "clean.pdf", "--set", "max_pages=1").returncode == 1
    r = run("check", compiled / "clean.pdf", "--set", "aspect=4:3", "--fail-on", "error")
    assert r.returncode == 0 and "page.size" in r.stdout


def test_sheet_no_overwrite(compiled, tmp_path):
    output = tmp_path / "sheet.png"
    r = run("sheet", compiled / "clean.pdf", "--output", output)
    assert r.returncode == 0, r.stderr
    assert output.read_bytes().startswith(b"\x89PNG")
    before = output.read_bytes()
    assert run("sheet", compiled / "clean.pdf", "--output", output).returncode == 2
    assert output.read_bytes() == before


def test_fonts_images_rotated_text_and_scale(tmp_path):
    target = tmp_path / "extras.pdf"
    with pdf.open() as doc:
        page = doc.new_page(width=960, height=540)
        page.insert_text((50, 80), "Small", fontsize=8)
        # Same draw twice must not create a collision warning.
        page.insert_text((50, 80), "Small", fontsize=8)
        pix = pdf.Pixmap(pdf.csRGB, pdf.IRect(0, 0, 10, 10), False)
        pix.clear_with(150)
        page.insert_image(pdf.Rect(100, 100, 600, 400), pixmap=pix)
        page.set_rotation(90)
        doc.new_page(width=1920, height=1080).insert_text((100, 160), "Small", fontsize=16)
        doc.save(target)
    _, findings = analyze(target, DEFAULTS)
    assert sum(f["rule"] == "font.small" for f in findings) == 2
    assert any(f["rule"] == "font.unembedded" for f in findings)
    assert any(f["rule"] == "image.low-dpi" for f in findings)
    assert not any(f["rule"] == "text.overlap" for f in findings)


def test_no_text_coverage(tmp_path):
    p = tmp_path / "blank.pdf"
    with pdf.open() as doc:
        doc.new_page(width=960, height=540)
        doc.save(p)
    r = run("check", p, "--json")
    assert r.returncode == 1
    assert "page.no-text" in r.stdout


def test_emoji_risk_heuristic():
    fonts = subprocess.run(["typst", "fonts"], capture_output=True, text=True, check=True).stdout
    if "Apple Color Emoji" not in fonts or "Helvetica Neue" not in fonts:
        pytest.skip("This font-specific fixture requires the macOS emoji and body fonts")
    r = run("check", "--typ", ROOT / "tests/fixtures/emoji.typ", "--json")
    data = json.loads(r.stdout)
    assert [(f["rule"], f["page"]) for f in data["findings"] if f["rule"] == "font.tall"] == [
        ("font.tall", 1)
    ]


def test_typst_tool_failure_and_input_options(tmp_path):
    source = tmp_path / "input.typ"
    source.write_text(
        '#set page(width: 960pt, height: 540pt)\n#set text(size: 26pt)\n#metadata((title: "Input")) <deck-slide>\n#sys.inputs.at("message")'
    )
    assert run("check", "--typ", source, "--json").returncode == 2
    r = run("check", "--typ", source, "--input", "message=TODO", "--root", tmp_path, "--json")
    assert r.returncode == 1
    assert "text.placeholder" in r.stdout


def test_natural_wrapping(tmp_path):
    from deck_lint import paragraphs, text_lines

    target = tmp_path / "natural.pdf"
    subprocess.run(["typst", "compile", str(ROOT / "tests/fixtures/natural.typ"), str(target)], check=True)
    with pdf.open(target) as doc:
        groups = paragraphs(text_lines(doc[0]))
    assert [len(g) for g in groups] == [4, 2]
    _, findings = analyze(target, DEFAULTS)
    assert [f["excerpt"] for f in findings if f["rule"] == "wrap.runt"] == ["word."]
    assert sum(f["rule"] == "wrap.long" for f in findings) == 1


def test_offset_crop_and_equivalent_rotated_page(tmp_path):
    target = tmp_path / "crop-rotate.pdf"
    with pdf.open() as doc:
        page = doc.new_page(width=1060, height=640)
        page.insert_text((150, 160), "Crop offset", fontsize=20)
        page.set_cropbox(pdf.Rect(100, 100, 1060, 640))
        page = doc.new_page(width=540, height=960)
        page.insert_text((60, 300), "Rotated landscape", fontsize=20, rotate=90)
        page.set_rotation(90)
        doc.save(target)
    _, findings = analyze(target, DEFAULTS | {"min_font": 18})
    assert not {"text.off-page", "font.small", "page.size"} & {f["rule"] for f in findings}
    assert sum(f["rule"] == "font.unembedded" for f in findings) == 1


def test_recoverable_pdf_reports_warning(tmp_path):
    target = tmp_path / "repair.pdf"
    with pdf.open() as doc:
        page = doc.new_page(width=960, height=540)
        page.insert_text((50, 80), "Readable despite a broken xref offset", fontsize=26)
        data = doc.tobytes()
    import re

    target.write_bytes(re.sub(rb"startxref\s+\d+", b"startxref\n0", data))
    r = run("check", target, "--json")
    assert r.returncode == 1, r.stderr
    assert any(f["rule"] == "pdf.repaired" for f in json.loads(r.stdout)["findings"])
