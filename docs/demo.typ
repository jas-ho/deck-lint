// Synthetic demo deck for the README visual. Slide 3 and slide 5 are broken on purpose.
#set page(width: 960pt, height: 540pt, margin: (x: 60pt, top: 110pt, bottom: 50pt))
#set text(font: "Libertinus Serif", size: 28pt, fill: rgb("#1f2933"))
#let accent = rgb("#2f6fdf")
#let slide(title, body) = page(
  header: block(width: 100%, inset: (top: 40pt))[
    #text(size: 38pt, weight: "bold", fill: accent)[#title]
  ],
)[
  #metadata((title: title)) <deck-slide>
  #body
]

#slide("Garden sensor network")[
  #v(40pt)
  #text(size: 34pt)[A demo deck with two broken slides]
  #v(20pt)
  #text(fill: gray)[Synthetic example]
]
#slide("Where the sensors go")[
  - Soil moisture in every raised bed
  - One light sensor per greenhouse wall
  - Rain gauge on the shed roof
]
#slide("Battery life")[
  - Sensors wake every ten minutes, read, transmit and go back to sleep, which in practice means the battery budget is dominated by radio time and not by the sensor readings themselves
  - Two AA cells last one season
  #place(top + left, dx: 560pt, dy: 250pt)[#box(fill: rgb("#fff4d6"), inset: 10pt)[Measured in the cold greenhouse at night]]
]
#slide("Data flow")[
  #grid(columns: (1fr, 1fr, 1fr), gutter: 20pt,
    box(fill: rgb("#e8f0fe"), inset: 16pt, width: 100%)[Sensor],
    box(fill: rgb("#e8f0fe"), inset: 16pt, width: 100%)[Gateway],
    box(fill: rgb("#e8f0fe"), inset: 16pt, width: 100%)[Dashboard],
  )
]
#slide("Next steps")[
  - Order twelve more soil probes
  - Weatherproof the gateway enclosure
  - Add frost alerts to the dashboard
  - Log a full season of readings
  - Compare beds with and without mulch
  - Write up what worked
  - Share the wiring diagram
  - Plan the second season
  - Test solar charging
  - Retire the old rain gauge
  - Label every probe cable
  - Back up the dashboard data
  - Invite the neighbours to try it
]
