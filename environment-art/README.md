# Battlefields, map towns, adventure-map and font rasterization

Tools only. Supply your own legally obtained H3 data and externally generated images.
Do not commit extracted references, production artwork, font files or complete mods.
Requires Python 3.9+, Pillow and NumPy. `font_probe.py` additionally requires SDL3
and SDL3_ttf (Homebrew library paths are the macOS fallback).

Run from this repository, using fresh output directories:

```sh
.venv/bin/python environment-art/export_references.py --data "$H3_DATA" --config "$VCMI_REPO/config/battlefields.json" --out "$ART_WORK/references"
.venv/bin/python environment-art/build_battlefields.py --references "$ART_WORK/references" --generated "$ART_WORK/battle-generated" --out "$ART_WORK/battle-package"
.venv/bin/python environment-art/build_map.py --data "$H3_DATA" --generated "$ART_WORK/map-generated" --out "$ART_WORK/map-package"
.venv/bin/python environment-art/build_adventure_assets.py --lod "$H3_SPRITE_LOD" --out "$ART_WORK/adventure-terrain" --scope terrain --scales 2 3 4
.venv/bin/python environment-art/build_adventure_assets.py --lod "$H3_SPRITE_LOD" --out "$ART_WORK/adventure-objects" --scope objects --prefix AVL --prefix AVX --prefix AVW --scales 2 3 4
.venv/bin/python environment-art/repaint_terrain.py --mod "$ART_WORK/adventure-mod" --terrain GRASTL --material "$ART_WORK/grass-material.png"
.venv/bin/python environment-art/font_probe.py --fonts "$CHINESE_FONT_DATA" --out "$ART_WORK/font-review" --display-scale 2.72
```

Define those task variables with paths on your machine. Battlefield input names
come from the reference manifest. Map inputs are `village.png`, `fort.png` and
`capitol.png`, with real alpha or a flat magenta background. Prompts are in
`prompts/`; generated outputs require human visual review and are not deterministic.
The fort checkerboard-repair prompt operates on the rejected first fort draft;
the capitol prompt takes the native capitol reference plus the accepted fort.

Battlefield output is exactly 1600×1112 at 2×. The September 2026 masters were
approximately 1505×1045, so this includes a small final resize. Map output is
384/576/768 square (2×/3×/4×), registered to original body bounds. Generated alpha
changes the visual edge; original game footprint configuration is untouched.
Native shadow pixels remain nearest-scaled. Ground ownership pennants are smooth
supersampled geometry at native pole attachments. The capitol's upper overlay
uses gold-color coverage in its top 9%; this heuristic needs review for each new
generation. Red and blue offline composites were inspected for the shipped set.

Merge the two package `content` directories into a local graphical mod depending
on `necropolis-layered-hd`, and enable it through the existing mod preset. Existing
`data2x` resource stems override BMP references with PNG files; map JSON and layers
are provided in `sprites2x`, `sprites3x`, and `sprites4x`. Keep a local backup before
installation. Audit JSON files record input hashes, crops and output sizes.

Font samples preserve WenQuanYi and LiSu, their logical sizes and VCMI's blended
SDL_ttf/mono-hinting path. The comparison uses an approximate final Pillow resize,
not a screenshot. Existing `video.upscalingFilter: "xbrz3"` rasterizes fonts at 3×
without changing font families. It affects the whole internal render scale and
increases memory demand. Existing 2× creature assets do not become new native 3×
art. Choose a display ratio appropriate to your screen; 2.72 is a local estimate.

`build_adventure_assets.py` preserves each source DEF's full canvas, animation
groups, frame counts and separate body/shadow/overlay layers. It changes no map
object template, anchor, visit mask or passability. `AVL` covers scenery and
terrain obstacles, `AVX` adventure buildings and `AVW` neutral creatures. Keep
`AVC` out of this pass when towns have a separately registered art treatment.
The script is a high-quality scaling baseline; use reviewed generated artwork for
individual landmarks only after preserving the same registration constraints.
`register_landmarks.py` fits reviewed transparent artwork into the native body
bounds and preserves the original canvas, JSON, shadow and overlay layers.
`repaint_terrain.py` uses a reviewed tileable material but retains the native
terrain tile selection, canvas, alpha and filenames. It is for a real material
redraw rather than a resolution-only upscale.

Validation distinguishes package checks, native asset-load logs, offline visual
inspection and user in-game acceptance. Loading a mod does not establish that all
14 battlefields or every ownership color have been visually tested in-game.
