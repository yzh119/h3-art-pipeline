# Necropolis town-art study

Extract original town layers and adventure-map town variants before changing
resolution. The town background is TBNCBACK.PCX, 800×374. The faction config
contains 42 structure definitions, including upgrade stages and overlays.
The reference exporter composes 23 selected fully upgraded layers at their
configured positions. It is a reference layout, not a game-state screenshot.

The three map templates use AVCNECR0 (village), AVCNECX0 (fort/citadel/castle) and
AVCNECZ0 (capitol). Each original has a 192×192 canvas and one frame. Raw decoding
preserves the original canvas/margins and indexed shadow alpha. Generated assets
live outside the source repository.

```sh
creature-art/.venv/bin/python town-art/export_necropolis_reference.py \
  --data "$HOME/Library/Application Support/vcmi/Data" \
  --out "$HOME/vcmi-art/necropolis-hd/reference-01"
```

The first HD comparison uses built-in `image_gen`, with the extracted full-town
reference and fortified map castle as edit targets. Prompts are retained with
the generated outputs under `~/vcmi-art/necropolis-hd/review-01`. This pass is a
visual study, not an installed replacement pack. The town output is a flattened
1832×858 panorama; it cannot represent arbitrary unbuilt/upgraded town states.
The first castle output was RGB with a painted checkerboard, which is not alpha
transparency and must not be installed as a game sprite.

Integration needs separate background, building and effect assets, preserving
`config/factions/necropolis.json` positions, z-order, upgrade relationships and
area/border masks. Map images must preserve canvas, anchor, footprint and owner
color handling. `clientsdl2/render/RenderHandler.cpp::loadScaledImage` supports
DATA2X/3X/4X and SPRITES2X/3X/4X, gated by `video.useHdTextures`.
High-resolution files must match the scale of their logical canvas; a larger
PNG alone does not satisfy that contract. Keep preview images separate from
installable assets until registration, alpha and state-dependent layers pass.

## Layered 2x prototype

`build_layered_town.py` exports all 42 town definitions (100 frames) and three
map variants (3 frames) as a separate graphical mod. Optional `--background`
and `--castle` accept built-in image_gen outputs. The empty background becomes
1600×748; the castle interior is keyed from solid magenta and blended inside
the exact original alpha, retaining original pixels around uncertain edges.
Other assets use bicubic enlargement and mild unsharp masking, not invented
high-resolution detail. Every exported frame is reopened and checked against
its original canvas and nearest-scaled alpha.

```sh
creature-art/.venv/bin/python town-art/build_layered_town.py \
  --data "$HOME/Library/Application Support/vcmi/Data" \
  --out "$HOME/vcmi-art/necropolis-hd/layered-02" \
  --background "$HOME/vcmi-art/necropolis-hd/layer-input-02/background.png" \
  --castle "$HOME/vcmi-art/necropolis-hd/layer-input-02/castle-magenta.png"
```

The generated `mod` directory can be installed under a distinct Mods name.
It supplies only `data2x` and `sprites2x`; enable `video.useHdTextures` and use
2x rendering. Native resources remain the fallback at 1x. Area/border resources,
town configuration, upgrade chains and map templates are not overridden.
Town COLORKEY frames retain all palette colors except transparent index 0;
map frames have separate body/shadow/owner-overlay PNGs.

`CCastleBuildings::recreate` selects the furthest built upgrade in each base
building group. `CBuildingRect::operator<` compares z only, not y. The engine
still controls both behaviors. Copy `layer-review.html` to the output as
`index.html` and serve it over HTTP to inspect independent layers and all
effect frames (frame 0 is drawn as a base, like CShowableAnim::BASE).
The inspector deliberately permits impossible combinations and is not a
game-state emulator or evidence of in-game click/upgrade testing.

## Remaining building interiors (0.3)

`prepare_building_inputs.py --data DATA --baseline layered-02 --out buildings-03`
decodes the 41 remaining base images, including every upgrade stage. It pads
each original onto a square magenta canvas for individual built-in image_gen
edits. Inspect the originals and generate one image per job, saving it to
`buildings-03/generated/<name>.png`; retain the exact prompts alongside them.

`refine_buildings.py --baseline layered-02 --inputs buildings-03 --out layered-03`
registers generated subject bounds to each original subject bounds, then blends
only interior pixels into the 2x base. The original alpha is authoritative.
For animated buildings, the union of all later overlay-frame alpha (expanded by
two 2x pixels) protects the base from texture changes in animated areas.
All 58 later frames are copied without modification. The castle and background
are inherited from the baseline, so all 42 town layers now have generated static
interior detail. Adventure-map images remain the prior conservative 2x versions.

Reopened files must retain alpha and dimensions exactly, have actual changed
interior pixels, and leave protected animation pixels unchanged. All unrelated
mod resources must remain byte-identical before updating mod version metadata.
The manifest records per-input/output hashes, registration bounds, blend coverage
and tool provenance. This preserves original footprints; it does not establish
pixel-exact agreement of generated internal architecture with the source.

For the gallery, copy `layer-review.html` to the new output as `index.html` and
the prompts to `prompts.md`. Copy each refined resource's previous `0_0.png` to
`before/<RESOURCE>.png` in the output. The previous/current toggle then compares
the same selected buildings with identical overlays. Local NumPy 2.0.2 was also
used to independently audit visible pixel changes, alpha and overlay equality.

## UI thumbnails (independent mod 0.1.0)

`extract_ui_references.py` reads the 44 HALLNECR slots and the Necropolis slots
58–71 in CPRSMALL/TWCRPORT. Preserve the native index offset: creature IDs are
not portrait frame indices. HALLNECR is shared by the construction list, building
details and fort recruitment window. The building frames contain 36 unique images.

```sh
.venv/bin/python town-art/extract_ui_references.py --lod "$ART_DATA/H3sprite.lod" --out "$ART_WORK/reference"
```

Generate each unique building separately using the built-in image tool and the
corresponding local reference. `ui-thumbnail-prompts.json` records the prompts;
image 2 is the generated first mage guild, used only for material/style consistency.
Save outputs as `hallnecr-NN.png`. These are generative repaints with some local
architectural changes, not exact restoration. No additional Meshy jobs are needed.

For portraits, `creature-art/render_ui_portraits.py` opens delivered Blender
scenes, retains their models/materials/poses and reframes the camera. Its input
manifest is an array with `name`, `scene`, `upperFraction`, optional `size`,
`fitWidth` and `centerFraction`. Use the names in `build_ui_thumbnails.py::NAMES`.
Large masters are 580×640, upperFraction 0.62. Small masters are 320×320,
upperFraction 0.40, fitWidth false; centerFraction 0.35 for liches, 0.70 for
dragons and 0.50 otherwise. Each output records scene, tool and PNG hashes.
Portraits intentionally crop the lower body; do not use full-body clipping checks.

```sh
blender --background --python creature-art/render_ui_portraits.py -- --manifest "$ART_WORK/portrait-scenes.json" --out "$ART_WORK/portraits"
blender --background --python creature-art/render_ui_portraits.py -- --manifest "$ART_WORK/small-portrait-scenes.json" --out "$ART_WORK/small-portraits"
.venv/bin/python town-art/build_ui_thumbnails.py --reference "$ART_WORK/reference" --buildings "$ART_WORK/generated" --portraits "$ART_WORK/portraits" --small-portraits "$ART_WORK/small-portraits" --backdrop "$ART_WORK/CRBKGNEC.png" --out "$ART_WORK/mod"
```

The pack supplies sparse animation JSON and exact-size 2×/3×/4× PNGs only.
No 1× DEF, creature config or unrelated faction frame is overridden. Small
portraits retain alpha; large portraits include the current creature backdrop.
HALLNECR uses 150×70 logical frames; CPRSMALL 32×32 and TWCRPORT 58×64.
The assembler reopens all outputs and validates dimensions, paths and indices.
The 0.1.0 package has 203 physical files. Install privately under `necropolis-ui-hd`
and enable it in the active VCMI mod preset. Published examples belong in the blog.

Native verification recorded 4× reads for small/large portraits and seven base
building thumbnails, plus a fort-screen visit. It does not establish manual
inspection of every slot. UI size and internal asset/render scale are separate;
a 4× file can still be downsampled when presented in a small on-screen frame.
