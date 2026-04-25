# MOCT Visual Research

Current public context checked April 25, 2026:

- MOCT started in 2019 and describes itself as an Armenian electronic music and contemporary art collective.
- The April 25, 2026 anniversary event is MOCT 7 at Hayfilm Cluster.
- Hayfilm is central to the identity: MOCT describes it as a renovated post-Soviet film site with permanent stages.
- Stage language matters: STUDIO, BAR, PROJECTOR ROOM, and BAK appear repeatedly in public listings and poster systems.

Useful source links:

- https://www.moct.am/about-us
- https://ra.co/events/2420645
- https://ra.co/events/2409633
- https://ra.co/events/2400376
- https://ra.co/events/2349617

Poster language from the supplied screenshots:

- Huge uppercase typography, usually white or black, often stacked and centered.
- Small technical metadata around edges: dates, venue, stage, country tags, short slashes, plus signs.
- Liquid/chrome 3D forms for the 7-year identity, especially blue, lavender, white, and purple.
- Hard flyer fields for clubnights: black/white, electric blue, red/orange, acid yellow, pale blue.
- Thin arcs, globe lines, crosshair marks, small logo clusters, and block/pixel artifacts.
- Camera/photo material is treated as poster matter, not naturalistic video: high contrast, tint, crop, and overlay.

Implementation mapping:

- `LIQUID` mode: anniversary identity, chrome/liquid movement, large MOCT/7 type.
- `POSTER` mode: generic MOCT flyer system, stage labels, metadata, arcs, block artifacts.
- `nodes.py`: mic and camera energy drive both modes through `audio_level`, `audio_peak`, `camera4_motion`, and `camera2_motion`.
- `ArtNetOut` / `ArtNetRGB`: optional lighting output nodes for syncing fixtures to the same graph.
