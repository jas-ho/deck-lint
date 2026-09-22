#set page(width: 960pt, height: 540pt, margin: 50pt)
#set text(font: "Helvetica Neue", size: 26pt)
#page[
  #metadata((title: "Unscaled emoji")) <deck-slide>
  A text line with a full-size emoji 🙃 that may inflate leading.
]
#page[
  #metadata((title: "Scaled emoji")) <deck-slide>
  A line with #box(baseline: 12%, text(size: 0.8em)[🙃]) adjusted explicitly.
]
