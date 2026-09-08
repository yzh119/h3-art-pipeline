# Vampire and Vampire Lord

Local package0.11.0 adds CVAMP and CNOSFE without engine changes. CVAMP has13
used native groups/84frames per scale; CNOSFE has16/105. Both retain450x400
logical canvases and ground267, provide1x/2x bodies and precomputed effects, and
travel as bats. The animations and smoke are locally authored. Appearance and
battle timing still require native review; complete resource coverage is not
user acceptance.

## Mesh findings

The first Lord mesh had13,521boundary edges after welding coincident vertices.
OBJ and FBX from the same task also had extensive boundaries, ruling out a
GLB-only export issue. A second image-to-3D request reused the concept with
`--no-remesh`, adding30credits. The detailed result has1,950,534triangles and a
4096x4096color texture. Its clothing renders substantially more intact. A new
random reconstruction also changed, so this is not a controlled demonstration
that remeshing alone caused every defect.

The dense task's auto-rig request returnedHTTP400 without a task ID. Its face
count exceeds the documented300,000limit for task-ID rigging:
[Meshy rigging API](https://docs.meshy.ai/en/api/rigging). The local fallback uses
`transfer_rig.py`: simplify to160,000faces, fit height/ground to the old rig,
interpolate three nearby donor vertices' skin weights, then repair bone tails
and IK in`vampire_study.py`. GLB export retains the four highest influences and
renormalizes them. The exported result is reimported for motion checks.
Nearest donor distanceP95=.064101m, max=.093228m; this transfer is specific to
related models and still needs visual inspection, particularly cloth and hands.

The bat's welded boundary count fell196→52 after small simple loops were patched.
Only loops with3–16edges and diameter<.022model units are filled. UV corners come
from adjacent faces; larger/complex boundaries remain. This does not claim a
watertight mesh. A five-bone local rig controls body, wing roots and tips.

## Reproduction

All model paths below are external to the public repository. Generation and
rigging require account credits. See the root reproduction guide for setup.

```sh
.venv/bin/python creature-art/export_roster_reference.py \
  --lod "$H3_DATA/H3sprite.lod" --out "$ART_WORKSPACE/reference/manifest.json"
.venv/bin/python creature-art/gen_mesh.py "$ART_WORKSPACE/concept.png" \
  --out "$ART_WORKSPACE/lord-dense/model" --model meshy-7 --no-remesh \
  --texture-resolution 4k --no-image-enhancement --no-crop
blender -b --python-exit-code 1 --python creature-art/transfer_rig.py -- \
  --model "$ART_WORKSPACE/lord-dense/model.glb" \
  --donor "$ART_WORKSPACE/previous-lord/rigged.glb" \
  --out "$ART_WORKSPACE/lord-transfer"
blender -b --python-exit-code 1 --python creature-art/bat_study.py -- \
  --model "$ART_WORKSPACE/bat.glb" --out "$ART_WORKSPACE/bat-flight"
blender -b --python-exit-code 1 --python creature-art/vampire_study.py -- \
  --model "$ART_WORKSPACE/lord-transfer/rigged.glb" --variant vampire-lord \
  --references "$ART_WORKSPACE/reference/manifest.json" \
  --out "$ART_WORKSPACE/lord-human"
blender -b --python-exit-code 1 --python creature-art/vampire_flight.py -- \
  --human "$ART_WORKSPACE/lord-human/holding.blend" \
  --bat "$ART_WORKSPACE/bat-flight/flight.blend" \
  --out "$ART_WORKSPACE/lord-flight"
.venv/bin/python creature-art/assemble_vampire.py \
  --human "$ART_WORKSPACE/lord-human" --flight "$ART_WORKSPACE/lord-flight" \
  --references "$ART_WORKSPACE/reference/manifest.json" --variant vampireLord \
  --out "$ART_WORKSPACE/lord-complete"
```

`export_roster_reference.py` reads creature names and DEF identifiers from
`roster-necropolis.json` and writes a list of records with name, native groups/
frame counts, canvas and bounds derived from original DEFs.
Use`--preview-only` on the humanoid tool first. Human/flight intermediate exports
remain marked incomplete; the assembler checks every native group/count/hash,
canvas and alpha margin before producing a complete export for`roster_mod.py`.

## Checks and limitations

Saved humanoid scenes passed598base+781Lord integer/half-frame samples. Maximum
IK error=.000105531m; minimum death vertexZ=.00215019m. The original bat loop
passed49saved samples and a repeated-endpoint bounds check. Final flight is
retimed to the original level/down/level/up pattern; scale.68 and rootZ1.5bring
its span/height closer to the native reference.

Transform endpoints have identical alpha silhouettes to flight/holding. Separate
renders had small RGB sampling differences (mean<3levels on a0–255scale), so
assembly copies canonical holding/flight PNGs at joins and records original and
replacement hashes. Exported joins are pixel-identical. The intermediate scene
render can still differ slightly in RGB from that canonical exported PNG.

Smoke began as solid-looking spheres, then an expensive volume probe; the final
version uses38camera-facing procedural noise particles. This is an authored
visual transition, not fluid simulation or a geometric human-to-bat morph.
Death raises the hands and folds the body to the floor; it retains an intact
body and cloth, differing from the original compact heap. Lord special groups
use directional claw motions; no gameplay abilities are added.

The candidate validator reports238informational findings,0warnings,0errors.
This does not cover every battle contact, motion aesthetic or native timing.
