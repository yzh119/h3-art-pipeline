# Rejected procedural designs and textured bootstraps

User rejected the procedural wight and lich appearance: baglike cloth and primitive
headgear. `spectral_study.py` is retained as a rejected prototype, not a production
asset source. Its manifests mark `artisticallyRejected`; `roster_mod.py` rejects
that flag and incomplete `previewOnly` exports. Existing installed 0.8.0 is intact.

The reviewed failures are `~/vcmi-art/necropolis-roster/wight-probe-05` and
`lich-probe-01`. Each four-clip probe passed 334 saved frame/subframe hand/contact
checks; that did not establish visual quality. Earlier wight-probe-03 calibrated
with a collapsed garment (174 pixels high) then exported an extended one (279).
Resetting shape keys fixed calibration, not the rejected appearance.

Built-in imagegen made new concepts using native reference sprites. The first
wight output baked a checkerboard into RGB; another imagegen edit made a pale
background before reconstruction. Exact prompts and images are in
`wight-bootstrap-01` and `lich-bootstrap-01` under the roster art directory.

Both images went to Meshy 7: image enhancement disabled, quad target 40000, 4k
texture requested. Each returned task consumed30credits; both actual textures
are4096x4096. Imported geometry: wight71107verts/82522faces; lich64784/79306.
Do not report requested polygon count as measured GLB face count. `gen_mesh.py`
now records pending task IDs/source hashes immediately and exposes enhancement
and texture controls; compatibility with Meshy5 defaults is retained.

`bootstrap_review.py` normalizes height to1.7, saves a packed editable scene,
and renders eight fixed-scale views. `bootstrap_showcase.py` renders a static
native-sized panel; final showcase-02 uses azimuth-45/elevation15, front fill2,
ambient0.55. Ghost skull exists but hood occlusion needs fill. Actual2x heights
are174/183pixels, versus174/182native. Lich calibration oscillated by2pixels;
final exported height is within one logical pixel. These are STATIC appearance
reviews: no animation/skin validation or new game integration is implied.

Reproduction (Blender tools require --python-exit-code 1):

```sh
blender -b --python-exit-code 1 --python bootstrap_review.py -- \
  --model /path/to/wight.glb --out /path/to/new-review
blender -b --python-exit-code 1 --python bootstrap_showcase.py -- \
  --scene /path/to/new-review/normalized.blend --out /path/to/new-showcase \
  --height-px 87 --ground 265
```

Blog `necropolis-bootstrap` (both languages) preserves failed procedural renders,
calibration mismatch, fake transparency, concepts, actual mesh turnarounds and
small-panel comparisons. Assets: `/images/necropolis-bootstrap/`. Published audit
contains dimensions/geometry/sourcehashes, not expiring service download URLs.

Next: repair and rig the generated models, check deformation under original
motions, export all native groups and only then integrate accepted replacements.
