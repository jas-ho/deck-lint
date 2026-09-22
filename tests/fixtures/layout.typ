#set page(width: 960pt, height: 540pt, margin: 50pt)
#set text(size: 26pt)
#page[
  #metadata((title: "Wrapping")) <deck-slide>
  A fairly long sentence ending with the switch turned \ OFF

  - This bullet has a deliberately forced first line \ and a deliberately forced second line \ and an unnecessary third line.

  #grid(columns: (220pt, 220pt), gutter: 40pt)[
    A date cell wraps here \ 2026
  ][An ordinary date cell]
]
#page[
  #metadata((title: "Collisions")) <deck-slide>
  #place(top + left, dx: 20pt, dy: 20pt)[Timeline label one]
  #place(top + left, dx: 130pt, dy: 20pt)[Timeline label two]
  #place(top + left, dx: 840pt, dy: 170pt)[Text crosses the page boundary]
  #place(top + left, dy: 250pt)[#text(size: 8pt)[TODO: small unfinished caption]]
]
#page[
  #metadata((title: "An overflowing final slide")) <deck-slide>
  Content starts on this page.
  #v(430pt)
  Content continues on an unintended second page.
]
