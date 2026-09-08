# Mounted knights and skeletal dragons

September 2026 bootstrap stage: Black Knight, Dread Knight and Bone Dragon have
textured Meshy reconstructions and eight-view Blender inspections. Ghost Dragon
uses the Bone Dragon geometry with an experimental pale material. None of these
four has a delivered animation or installed replacement yet.

Native references require intact black horses, seated riders and curved swords.
Dread Knight adds horse barding. Dragons stand on hind legs, have two forearms
separate from two torn wings, and fly during movement. The original dragon death
collapses into bones. Do not substitute a walking dragon or humanoid autorig.

Prompts live in `profiles/final-four/`. Use built-in image generation and review
against native references. Two upgrade drafts painted checkerboards into RGB;
those were rejected and edited to flat magenta for local keying. The ghost concept
is a material target; its separate mesh was not submitted. Three image-to-3D jobs
cost 30 credits each. All meshes and editable Blender scenes remain local.

```sh
.venv/bin/python creature-art/gen_mesh.py "$ART_WORK/concept.png" --out "$ART_WORK/bootstrap/model" --no-remesh --no-image-enhancement
blender --background --python creature-art/bootstrap_review.py -- --model "$ART_WORK/bootstrap/model.glb" --out "$ART_WORK/review" --samples 16
blender --background --python creature-art/bootstrap_material_still.py -- --source "$ART_WORK/review/normalized.blend" --out "$ART_WORK/still"
# For the ghost material study, add --spectral to the previous command.
```

Raw meshes have roughly 1.9 million triangles each. Before skinning, inspect
seams, weld coincident vertices while retaining corner UVs, reduce geometry and
compare silhouettes from all review views. High-resolution static renders do not
validate deformation.

Planned mounted rig: horse pelvis/spine/neck/head, four independent leg chains,
tail; rider pelvis attached to saddle with an independent torso, arms and legs;
rigid saber attached to its gripping hand. Verify diagonal gait phase, grounded
hoof contacts, saddle contact and weapon clearance before producing native clips.

Planned dragon rig: hind legs, torso, neck chain, jaw, two small arms, paired wing
chains and tail. Review wing/body separation in both standing and flight poses.
Ghost material currently recolors texture luminance and adds restrained emission;
wing translucency and battle-background legibility remain unfinished.

`bootstrap_material_still.py` creates a separate packed scene and a 1400×1600 PNG.
It does not change source geometry or install a mod. Its material experiment is
not a finished spectral effect. Existing animation-count and frame-bound validators
remain required when a real sequence is produced.
