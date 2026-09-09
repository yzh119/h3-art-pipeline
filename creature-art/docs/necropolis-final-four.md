# Mounted knights and skeletal dragons

## Mounted attack and panel correction, 0.12.1

In-game feedback rejected the 0.12.0 mounted attacks. The horse barely moved,
while reducing arm excursions hid skin problems and also erased the attack.
The saber selector missed its curved tip and mixed weapon weights into the horse
and rider boot. Keep the rejected probes for visual comparison.

`repair_knight_attacks.py` removes the fused right-arm/blade surfaces and builds
articulated armor, a gauntlet, guard and rigid curved saber. All knight clips use
this geometry. Non-attack motion is retained; attacks now rear over the hind
hooves, raise the sword, lean into a cut and recover. The small former weapon/boot
contact region receives local weight relaxation. Meshy still supplies the horse
and remaining rider; no new service call is required.

Continue the legacy seed workflow below with:

```sh
blender --background --python creature-art/repair_knight_attacks.py -- --source "$ART_WORK/supported" --out "$ART_WORK/knight-scenes" --no-render
blender --background --python creature-art/check_nonhumanoid_motion.py -- --source "$ART_WORK/knight-scenes" --out "$ART_WORK/scene-check.json"
blender --background --python creature-art/render_saved_creature.py -- --source "$ART_WORK/knight-scenes" --out "$ART_WORK/knight-final" --check "$ART_WORK/scene-check.json"
blender --background --python creature-art/check_nonhumanoid_motion.py -- --source "$ART_WORK/knight-final" --out "$ART_WORK/knight-final-check.json"
```

A broader initial surface selector damaged waist cloth and left a crude faceted
shoulder. Final selectors follow the arm segments and curved blade, retaining
the original textured shoulder plate. These failed static renders are retained
alongside the earlier fused-weapon probe.

`--no-render` stages scenes with an incomplete-export flag. The separate renderer
requires matching scene/manifest hashes and a passing deformation/ground check,
then renders the saved poses without reauthoring them.

`--probe` renders only the forward attack and marks the export incomplete.
`--no-skin` is solely for existing exports with the reconstructed arm; it repairs
an early fallback-weight defect without reconstructing that geometry again.
The legacy generator marks its knight seeds rejected until this repair is run.

`roster_mod.py --replace-existing` replaces only explicitly named creature
resources, including removing their stale higher-scale caches. Unrelated files
must remain byte-identical. Rebuild those caches before installation. Original
frame counts remain 13 groups/86 frames for Black Knight and 16/119 for Dread.

VCMI `CCreaturePic` crops double-wide creatures at logical x=170, versus x=150
for single-wide units. The previous offline gallery wrongly used the single-wide
crop for these four creatures. `roster_preview.py --double-wide CBLORD` (repeat for
each relevant unit) reproduces the real crop. Bone Dragon and Dread Knight were
centered near x=30 in their 100-pixel panels. `offset_animation.py --offset-x 20`
shifts their bodies, shadows and outlines to center near x=50, preserving every
visible pixel at every scale. This also translates battle sprites; no separate
panel-offset setting exists in this engine path. Their new canvas centers are
close to the original double-wide sprite centers. Do not describe this as UI-only.

## Historical animation delivery 0.12.0

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
