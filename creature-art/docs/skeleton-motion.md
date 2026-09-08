# Skeleton continuous motion

This extends the [four-pose study](skeleton-study.md) with curved limb shafts,
paired forearm/lower-leg bones and wider anatomical joint ends. Procedural bone
shading uses a rest-position attribute, so the surface noise follows the mesh.
The textured skull/chest/pelvis and source fingerprint remain the same. Hands
retain their fixed finger shapes and explicit right-hand weapon socket.

Thirteen editable clips are generated, totaling 82 original-count body frames
per scale. The attack includes anticipation, a lifted front
foot, wind-up, strike and recovery to holding. The rear foot stays planted.
Weapon orientations interpolate between key quaternions to avoid a hand-basis
flip as the forearm passes the blade direction. Start/end movement clips relocate
one foot at a time. Their endpoints join the authored phase-zero walk; arbitrary
interrupted movement still needs in-game review.

Walking arms now oppose the same-side feet. The previous independent cosine
advanced the right wrist and right foot together. Each foot's authored fore/aft
position now drives the corresponding arm in the opposite direction; wrist and
elbow-pole travel remain coordinated. Shoulder-relative wrist travel is 0.352680
model units, elbow travel 0.333438 and shoulder swing 101.659 degrees.

The user clarified that sword-up applies to forward arm carriage. Blade elevation
now follows wrist travel from 0 degrees behind the body to 65 degrees in front,
replacing the earlier all-cycle 57–73-degree constraint. Start/end movement share
the revised walk endpoint. The free hand remains low and torso lean unchanged.

A saved-frame test measures same-side arm/leg fore-aft correlation in the travel
direction. Right correlation changes from +0.922559 to -0.998697, and left from
+0.328537 to -0.983086. Both must be below -0.8. Blade checks require a low rear
carriage, a raised front carriage and higher mean elevation during forward arm
travel. This tests coordination, not exact original-frame reconstruction.

## Full clip set

| Groups | Frames per group | Behavior |
|---|---:|---|
| HOLDING, MOVING | 8 | Idle and opposed-arm walk loops |
| MOVE_START, MOVE_END | 2 | Enter and leave the phase-zero walk |
| MOUSEON | 11 | Raise sword and free hand, then return |
| HITTED | 6 | Recoil, settle forward, return |
| DEFENCE | 11 | Raise guard, absorb impact, recover |
| DEATH | 6 | Recoil, kneel, fold and settle prone |
| TURN_L, TURN_R | 2 | Whole-body half-turn clips around a facing flip |
| ATTACK_UP, ATTACK_FRONT, ATTACK_DOWN | 8 | Separate high, frontal and low strikes |

`MotionRoot` parents the rig, controls and geometry. Its native keyed rotation
turns the whole character; it does not substitute a spine twist. VCMI plays
TURN_L, flips the rendered facing, then plays TURN_R. The shared frontal pose
bridges the two clips. The preview includes their native frame order with that
flip. Original DEF groups 9/10 are unused duplicate turns and are not exported.

Death keeps the weapon attached and finishes prone, with a held final pose.
During the collapse, a vertical root correction prevents the evaluated geometry
from penetrating the ground. This is authored motion, not a rigid-body simulation
or the original disintegrating bone pile. Other transient actions return to
holding. Directional strikes have independently authored wrist and torso targets.

## Timing and foot contact

`client/battle/CreatureAnimation.cpp` sets melee attack playback to
`10 * speedFactor` frames/second. `attackAnimationTime` does not set melee timing.
Movement uses `10 * speedFactor / walkAnimationTime` frames/second and translates
at `2 * speedFactor / walkAnimationTime` hexes/second. An eight-frame movement
cycle therefore covers 1.6 hexes, or 70.4 pixels on a horizontal 44-pixel hex step.

The walk profile converts that displacement through the fixed orthographic
camera. During stance an ankle moves backward by exactly the corresponding
forward root displacement. Checks add the hypothetical root motion back and
measure the world ankle's drift. This checks straight horizontal movement;
diagonal paths, direction flips and interrupted cycles require engine review.

Dense review uses 30 fps, with key spans of 2 s holding, 0.8 s walk/attack and
0.2 s start/end. Nonloop videos retain the endpoint for one additional frame.
It is **not** substituted for the original sprite counts. Body exports retain
the counts above, at 450x400 and 900x800. Actual game speed still depends on its
animation settings. Loop exports omit the duplicate closure frame. Nonloop
exports include both endpoints.

Python `keyframe_insert` produced Bezier keys even with the UI preference set to
linear in Blender 5.2.1. Explicitly setting every Action key to linear reduced
measured stance drift at subframes from 0.008757 to 0.000061 model units
(about 0.47 to 0.0033 base pixels). Always test the saved Action at subframes.

## Reproduce

```sh
blender -b --python-exit-code 1 --python creature-art/skeleton_motion.py -- \
  --model "$HOME/vcmi-art/skeleton-study/source/skeleton.glb" \
  --out "$HOME/vcmi-art/skeleton-motion/full-review-03"

blender -b --python-exit-code 1 --python creature-art/test_skeleton_motion.py -- \
  "$HOME/vcmi-art/skeleton-motion/full-review-03"

creature-art/.venv/bin/python creature-art/motion_preview.py \
  "$HOME/vcmi-art/skeleton-motion/full-review-03" \
  --reference creature-art/ref/cskele/body \
  --previous "$HOME/vcmi-art/skeleton-motion/full-review-02"
```

Use a fresh output directory and do not edit sources during a render. `--no-render`
still calibrates the camera, bakes/saves all clips and records measurements, but
skips review and sprite frames. Each `.blend` contains ordinary editable native
Actions, IK controls, packed textures and a closure frame. The manifest retains
the source hash, both profiles, code hashes/snapshots, camera and measurements.

`test_skeleton_motion.py` reopens all thirteen clips and checks 577 frame/subframe
samples for IK reach, saved-versus-authored positions, ground penetration,
weapon rigidity, straight-line stance drift, loop and transition endpoints,
rest-position attributes and embedded textures. Ground tolerance is 0.0002 model
units (about 0.011 base pixels), allowing numerical IK error. Death additionally
checks every mesh at subframes against a 0.002-unit floor tolerance and requires
a low final pose. Tests compare world transforms across the turn bridge and
verify distinct sword-tip heights at directional strikes. A downward-strike
interpolation initially exceeded reach by 0.002186 units; moving the free wrist
closer reduced the full-set maximum IK error to 0.00009017.

`motion_preview.py` checks counts against the extracted original layout, canvas
dimensions and unclipped alpha bounds. It creates GIFs, scrub-able MP4s and
`preview/index.html`, plus an original/new contact sheet at actual 1x scale.
`--previous` additionally creates an original/previous/revised eight-frame walk
comparison at a shared review rate. The contact sheet compares phases; it does not synchronize original game timing.

## Remaining skeleton work

Review all thirteen clips artistically, including silhouette at native size,
the fixed free-hand pose and the mirrored turn bridge. Render shadow/overlay
layers, assemble and validate the full mod, and inspect actual battles.
These exports currently contain the body pass and are not installed as a mod.

The next creature is the zombie (`CZOMBI`). Reuse the inspection, explicit
handedness, controls, motion checks and render pipeline; zombie proportions and
gait need their own authored profile. A second character will inform whether the
Blender tooling warrants a separate repository. No new Meshy call was needed for
this skeleton stage.
