# Skeleton rig and hand study

The full CSKELE set passed file-format checks while its hands overlapped and its
stance still read incorrectly. This study checks four independent poses before
authoring another full animation: holding, walk contact, wind-up and strike.
It does not change `poses.py` or assemble a replacement mod.

## Asset and rig

`profiles/skeleton-study.json` is specific to the inspected Meshy v4 skeleton.
Its SHA-256 must match the input GLB. Source artwork is not checked into this
repository. On the development machine the source is retained at
`~/vcmi-art/skeleton-study/source/skeleton.glb`.

The study retains complete textured skull, chest and pelvis components. Some
source limb components contain long triangles spanning anatomical joints;
reweighting those faces produced spikes. Both arms, both legs, feet and hands are
therefore reconstructed as separate bone-shaped pieces. The hands have four
fingers and a thumb with opposite chirality. Their geometry is a simplified study,
not a claim of finished anatomical sculpting. Fingers have fixed open/gripping
shapes and are not individually animated yet.

The new rig uses measured rest landmarks and real joint-to-joint bone lengths.
Four two-bone IK chains have explicit wrist/ankle targets and elbow/knee poles.
Target rotations control the hands and feet independently of the IK chain.
`Hips`, `Chest`, `Neck` and `Head` are ordinary editable pose bones.

The profile explicitly selects anatomical `RightHand` for the weapon, placing it
on the near side of the chosen game camera. This intentionally differs from the
source mesh's left-handed grip. `WeaponGrip` copies that bone's transform; grip,
guard and blade are separate child meshes with no skin weights. Handedness is
independent of whether a weight-repair function happened to change anything.

## Run

```sh
blender -b --python-exit-code 1 --python creature-art/skeleton_study.py -- \
  --model "$HOME/vcmi-art/skeleton-study/source/skeleton.glb" \
  --out "$HOME/vcmi-art/skeleton-study/review-01"

creature-art/.venv/bin/python creature-art/study_preview.py \
  "$HOME/vcmi-art/skeleton-study/review-01" \
  --reference creature-art/ref/cskele/body

blender -b --python-exit-code 1 --python creature-art/test_skeleton_study.py -- \
  "$HOME/vcmi-art/skeleton-study/review-01"
```

Use a fresh output directory for each revision. Do not edit the script/profile
during a run. The manifest records the source/profile, Blender version, script
hashes, fixed camera and actual endpoint measurements. Each key pose is saved as
its own `.blend`, with embedded source textures and editable target objects.
The scripts used by the run are copied into its `code/` directory before rendering.

`comparison.png` shows original / previous implementation / study at 2x.
`native-size.png` shows a 1x preview, downsampled from the study's 2x renders.
Each row uses a single horizontal offset from its holding pose, and the same
camera across its four poses. Individual frames are never scaled to fit a tile.
The previous implementation retains its -40 degree azimuth / 30 degree elevation;
the study uses -75 / 15 for a more side-on silhouette. This comparison includes a
camera and geometry change, not an isolated rig-only experiment. Original attack
frames are phase references; the study has not matched the full frame timing.

`hands.png` isolates the two hands under local inspection lighting. This lighting
is separate from the game-camera renders. `test_skeleton_study.py` checks saved
files, IK endpoints, normalized weights, weapon rigidity, control edits, pose reset
and packed textures. It cannot certify artistic quality or animation continuity.

## Remaining work

The [continuous motion follow-up](skeleton-motion.md) now refines the limbs and
adds holding/walking/attack cycles plus start/end transitions. The notes below
describe the boundary of this original four-pose stage.

- Refine the simplified limb surfaces and proportions against the retained torso.
- Review the wind-up, free hand and weight transfer at actual game size.
- Add finger articulation if the action calls for releasing or changing the grip.
- Author transitions and full cycles; four independent poses are not animation.
- Render body/shadow/overlay layers and validate the assembled mod only after the
  motion has passed visual review.
