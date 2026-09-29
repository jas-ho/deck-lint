// Composite for docs/img/readme-visual.png; built by docs/readme-visual.sh.
#let sheet = sys.inputs.sheet
#let lines = sys.inputs.check.split("\n").filter(l => l.trim() != "")
#let cols = 3
#let cell-w = int(sys.inputs.width)
#let cell-h = int(sys.inputs.cellh)
#let W = 840pt
#let k = W / (cols * cell-w)
#set page(width: W + 40pt, height: auto, margin: 20pt, fill: white)
#set text(font: "Libertinus Serif", size: 13pt)
#let red = rgb("#d93025")
#let amber = rgb("#e8a100")
#let frame(idx, n: 1, stroke: 0.75pt + luma(200), tag: none) = {
  let x = calc.rem(idx, cols) * cell-w
  let y = calc.div-euclid(idx, cols) * cell-h
  let (w, h) = ((n * cell-w - 6) * k, (cell-h - 20) * k)
  place(top + left, dx: (x + 3) * k, dy: (y + 17) * k, {
    rect(width: w, height: h, stroke: stroke, radius: 2pt)
    if tag != none {
      place(bottom + right, dx: -6pt, dy: -6pt,
        box(fill: red, radius: 3pt, inset: (x: 6pt, y: 4pt),
          text(size: 10pt, fill: white, weight: "bold", font: "Menlo", tag)))
    }
  })
}
#box(width: W)[
  #image(sheet, width: W)
  #for i in (0, 1, 3) { frame(i) }
  #frame(2, stroke: 2.5pt + red, tag: "text.off-page · wrap.long")
  #frame(4, n: 2, stroke: 2.5pt + red, tag: "typst.spillover")
]
#v(6pt)
#block(width: W, fill: rgb("#1e2229"), radius: 6pt, inset: (x: 16pt, y: 14pt))[
  #set text(font: "Menlo", size: 12pt, fill: rgb("#d7dce2"))
  #set par(leading: 0.55em)
  #text(fill: rgb("#8b949e"), "$ deck-lint check --typ demo.typ") \
  #v(2pt)
  #grid(columns: 4, column-gutter: 14pt, row-gutter: 7pt,
    ..lines.map(l => {
      let f = l.split(" ")
      let msg = l.split(" | ").at(0).split("] ").at(-1).trim()
      let c = if f.at(0) == "error" { rgb("#ff7b72") } else { rgb("#e3b341") }
      (text(fill: c, f.at(0)), f.at(1), f.at(2), msg)
    }).flatten()
  )
]
