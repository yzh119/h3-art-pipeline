# Zombie motion study

`zombie_study.py` authors all thirteen CZOMBI battle clips, including
asymmetric movement, cleaver attacks, reactions, backward death and whole-body turns. The original carries a short
blade. The legacy creature profile described it as unarmed and merely scaled
skeleton animation deltas; this study has its own absolute targets and timing.
No new mesh-generation or rigging API calls are used.

## Source and rig

Pin the previously generated rigged zombie GLB outside the repository. Its SHA256
is recorded in `profiles/zombie-study.json`; the generator rejects other sources.
The inspected import has 25,898 body vertices. Joint heads have plausible world
positions, but the longest bone is 42.666362 model units for a roughly 1.7-unit
body. Reconstructing tails from the next joint head makes that chain 0.426664
units long. This repairs the rest rig for IK; it is not a claim that bone display
length alone was deforming the original FK animation.

24,400 vertices retain the source UVs and skin weights. The distal right hand is
replaced with a fleshy palm, four curled fingers and a right-side thumb. A short,
wide cleaver is parented to a socket constrained to RightHand; weapon vertices
have no skin weights. The left hand retains the textured open fingers. The body
uses preserve-volume skinning rather than the skeleton study's rigid limb pieces.
Joint heads, retained counts, source/profile/script hashes and render settings are
in the manifest. Packed `.blend` files, profile and code snapshots accompany each
fresh output directory.

The source silhouette is still gaunt and its cloth/skin treatment differs from
the original. The new grip has a simple material and fixed fingers. This is an
animation study, not an accepted final creature.

## Motion and original layout

| Clip | Native frames | Review duration |
|---|---:|---:|
| HOLDING | 8 | 2 seconds |
| MOVING | 10 | 1 second |
| ATTACK_FRONT, ATTACK_UP, ATTACK_DOWN | 7 each | 1.2 seconds each |
| MOVE_START, MOVE_END | 1 each | 0.2 seconds each |
| MOUSEON | 9 | 0.9 seconds |
| HITTED | 7 | 0.7 seconds |
| DEFENCE | 8 | 0.8 seconds |
| DEATH | 9 | 0.9 seconds |
| TURN_L, TURN_R | 3 each | 0.3 seconds each |

These counts come from CZOMBI.DEF, not the skeleton. Review timing is authored;
matching counts does not establish matching game playback speed. Each scale has
80 body frames, on 450×400 / 900×800 canvases. The camera is calibrated once on
holding, to 82 pixels tall and ground line 266 at 1x. There are 338 dense 30 fps
review frames, with endpoints for nonlooping clips. Original duplicate turn groups
9/10 are omitted. The one-frame native start/end clips sample transition midpoints;
the editable Actions keep the complete transition.

Walking uses a 0.38-unit stride with 68% stance duty. The right foot rises 0.035
units and the left 0.070. Hermite return motion matches the stance velocity at
toe-off and contact. Foot targets move backward in stance; checking them against
inferred forward motion measures sliding separately from in-place animation.
Hands swing slightly, and the blade remains raised. Attack poses raise the blade,
strike forward, follow through, then return to holding. They do not inherit the
skeleton's BASE or sword-swing deltas.

`ZombieRoot` parents the skin, rig, controls and cleaver socket. It rotates the
whole character for turns and tilts it backward during death. Death height is
corrected from evaluated geometry, then keyed; the corpse settles on its back
with flexed legs. Reaction and attack endpoints return to holding. TURN_L ends
at the same pose where TURN_R begins; preview inserts the engine facing flip.

## Reproduce

From `tools/creature-art`, with the existing Pillow environment:

```sh
.venv/bin/python def_extract.py export \
  "$HOME/Library/Application Support/vcmi/Data/H3sprite.lod" CZOMBI.DEF \
  --out ref/czombi --body-only

blender -b --python zombie_study.py -- \
  --model "$HOME/vcmi-art/zombie-study/source/zombie.glb" \
  --out "$HOME/vcmi-art/zombie-study/full-review-01" --samples 24

blender -b --python test_zombie_study.py -- \
  "$HOME/vcmi-art/zombie-study/full-review-01"

.venv/bin/python motion_preview.py \
  "$HOME/vcmi-art/zombie-study/full-review-01" --reference ref/czombi/body
```

Use a new empty output directory on every run. `--no-render` builds clips for
fast pose checks before committing to rendering. Do not edit the scripts/profile
while rendering. Preview generation validates the original counts, canvas and
unclipped alpha bounds. Its contact sheet now supports unequal group lengths;
the previous fixed eight-column assumption failed for the zombie's 10/7 split.

## Checks

Blender 5.2.1 reopened clips, 667 integer/half-frame samples:

| Measurement | Result (model units) |
|---|---:|
| Maximum IK error | 0.000094265 |
| Saved versus authored joint positions | 0.000000608 |
| Loop endpoint displacement | 0 |
| Maximum inferred stance drift | 0.000021750 |
| Blade length variation | 0.000000443 |
| Minimum evaluated skin Z | -0.001473490 |
| Blade tip Z, wind-up / forward strike | 2.084313 / 0.995809 |
| Strike tip Z, up / front / down | 1.857249 / 0.995809 / 0.390153 |
| Final corpse skin maximum Z | 0.588744 |

The first follow-through target exceeded arm reach by 0.075040 units; the IK
check rejected it. The corrected target keeps the elbow solvable throughout the
bake. Full-set checks also cover reaction endpoints, move transitions, a low
corpse, whole-body turn motion and the shared turn bridge. Ground tolerance is 0.002 units; the small negative minimum remains within
that tolerance and is not a claim of exact contact for every skin vertex.

Outstanding: visual acceptance of body proportions/hand material and gait,
shadow and owner-overlay passes, assembled-mod validation,
and movement timing/contact in an actual battle. The legacy zombie pose profile
is retained for reproducibility and is not the source for this study.
