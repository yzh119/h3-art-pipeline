# Mounted knights and skeletal dragons

## Animation delivery 0.12.0

All four units are now
installed: 13/16/13/13 groups and 86/119/78/82 body frames, respectively. Native
9/10 duplicate-turn groups are explicitly unused by VCMI. Existing ten creatures'
files remain unchanged. Final support parent moves mesh and armature together.

Reproduction continues from the reviewed scenes:

```sh
blender --background --python creature-art/prepare_mounted_dragon.py -- "$ART_WORK/review/normalized.blend" "$ART_WORK/prepared"
blender --background --python creature-art/mounted_dragon_motion.py -- --source "$ART_WORK/prepared/prepared.blend" --out "$ART_WORK/motion" --variant blackKnight --references "$ART_WORK/references.json"
blender --background --python creature-art/settle_nonhumanoid.py -- "$ART_WORK/motion" "$ART_WORK/supported"
.venv/bin/python creature-art/settle_nonhumanoid.py --apply-images "$ART_WORK/supported"
blender --background --python creature-art/check_nonhumanoid_motion.py -- --source "$ART_WORK/supported" --out "$ART_WORK/motion-check.json"
```

Use the matching mesh and variant for each creature; Ghost Dragon shares the bone
mesh. Ground PNG shifts assume orthographic projection and directional/ambient
light. A fresh render of one hit pose agreed at alpha IoU 0.9956 and mean opaque
RGB error 2.82/255. The earlier armature-only support version failed this check.

`roster_mod.py --motion-check CREATURE=CHECK_JSON` checks saved-scene hashes,
manifest hashes, floor bounds and large tears before append-only packaging.
`cache_creature_scale.py --mod MOD --scale 3 --unit CBKNIG ...` adds a Lanczos
cache from 2x PNGs, not new 3x detail. All55clips use precomputed stable-ground
shadows. The package validator found zero errors/warnings. Reopened native-frame
and midpoint checks sampled675poses without large tears or ground penetration.

`make_final_four_test_map.py --vcmi VCMI_REPO --out CHECK.vmap` creates a separate
map from VCMI's MiniTest fixture. Native `--testmap Maps/CHECK.vmap --onlyAI
--spectate` allows resource-load checks without changing normal maps. The installed
client read allfour3xsets and started dragon movement/attack. No claim of complete
manual gameplay review. Death is a folded body, not the original bone scatter;
ghost wing membranes remain visually solid. Those are explicit art limitations.

The repair_* scripts preserve how the earlier prototype scenes were brought into
range; a new export with the current main generator already includes these motion
limits and mounted transition changes. Do not apply range multipliers twice.

## Historical bootstrap notes

The following records the pre-animation stage; its unfinished work was the plan at that time.

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
