# Reproducing the art workflow

This repository publishes the tools, configuration and text prompts. It does not
ship original H3 data, ready-made mod artwork, generated GLBs or packed Blender
scenes. The blog shows the art and records failed attempts. Generative requests
can return different geometry for the same prompt; saved hashes identify the
particular local source an animation was authored against.

## Starting with an AI coding assistant

Clone this repository, open it in your coding assistant, and provide your local
paths and the creature you want to work on. This starter task is reusable:

> Read AGENTS.md, this reproduction guide, and the relevant character study.
> My Heroes III data is at `<H3_DATA>` and outputs belong in `<ART_WORKSPACE>`.
> Work on `<CREATURE>` using its original frame counts and movement reference.
> First inspect available local models and saved scenes. Reuse existing API task
> metadata instead of submitting duplicate jobs. Record any new request, prompt,
> parameters and source hashes in the external workspace.
> Produce a pose review before a full animation export. Inspect hands, equipment,
> silhouettes and floor contact; adapt mesh-specific landmarks when necessary.
> Preserve editable scenes, export native-count frames, then validate the local
> mod. Report what was verified and what still needs visual review. Keep images,
> models, game data and credentials outside the public repository.

Start with a single creature. The [Lich study](../creature-art/docs/necropolis-liches.md),
[ghost study](../creature-art/docs/necropolis-ghosts.md), and
[skeleton motion study](../creature-art/docs/skeleton-motion.md) record different
rigging approaches and their checks. Their historical source snapshots describe
specific generated meshes; the tools are not a universal automatic character rig.

## Local environment and reference data

Install Blender and ffmpeg, then create the Python environment from the root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
export H3_DATA="/path/to/your/vcmi/Data"
export ART_WORKSPACE="/path/to/your/art-workspace"
.venv/bin/python creature-art/def_extract.py export "$H3_DATA/H3sprite.lod" \
  CVAMP.DEF --out "$ART_WORKSPACE/reference-vampire" --body-only
.venv/bin/python town-art/export_necropolis_reference.py --data "$H3_DATA" \
  --out "$ART_WORKSPACE/reference-necropolis"
```

Town tools default to the included, source-pinned faction configuration. To use a
different version, pass `--faction-config /path/to/necropolis.json`. The config is
read-only input; no engine checkout is needed by these commands.

## Concept, textured mesh and optional humanoid rig

Use the original as a proportion/equipment/motion reference and the text files in
`prompts/` as concept-generation recipes. Project concepts use the built-in
imagegen tool. Save the selected image in the external workspace; inspect it
before submitting it for reconstruction. Model scripts in `creature-art/` include
legacy FLUX tooling as historical alternatives, not a current mandatory stage.

Meshy calls require `MESHY_API_KEY` in the environment and consume account credits.
Never put the key in a config or commit. A typical request is:

```sh
.venv/bin/python creature-art/gen_mesh.py "$ART_WORKSPACE/concept.png" \
  --out "$ART_WORKSPACE/mesh/character" --model meshy-7 --polycount 40000 \
  --texture-resolution 4k --no-image-enhancement --no-crop
.venv/bin/python creature-art/rig_mesh.py \
  --input-meta "$ART_WORKSPACE/mesh/character.json" \
  --out "$ART_WORKSPACE/mesh/rigged"
```

`rig_mesh.py --resume` reuses its persisted task ID. `gen_mesh.py` records a pending
task but does not yet have a resume CLI: do not blindly rerun a paid mesh request
when only polling/download failed. The requested polygon count is not the actual
imported face count. Inspect returned geometry, textures, hands and held props.

Footless/flying/nonhuman models need an appropriate local rig instead of the
humanoid auto-rig. Existing character scripts describe the particular mesh they
repair; arbitrary new geometry may need new landmarks and equipment selection.

## Author, inspect, export

The character documents give the exact parameters and saved-scene checks for each
published study. Start with the corresponding pose preview, inspect actual game
scale, and use a fresh output directory for every revision. Do not edit a script
while a render using it is running. Preserve source hashes and script snapshots.

For a high-resolution still from any reviewed scene:

```sh
blender -b --python-exit-code 1 --python creature-art/render_portrait.py -- \
  --source "$ART_WORKSPACE/holding.blend" \
  --out "$ART_WORKSPACE/portraits/character.png"
```

For a newly generated mesh without a reviewed Blender scene:

```sh
blender -b --python-exit-code 1 --python creature-art/bootstrap_portrait.py -- \
  --model "$ART_WORKSPACE/mesh/character.glb" \
  --out "$ART_WORKSPACE/inspection-01"
```

This saves a packed inspection scene and renders the supplied pose, without
claiming that the model is animation-ready. Use `--azimuth`, `--elevation`,
`--width`, `--height` and `--fill` to inspect broad wings or unusual silhouettes.
The material setup removes imported emission and unlinked metallic values using
the existing sprite renderer. The source GLB remains unchanged. Every run needs
a new output directory and records mesh counts, texture sizes and source hashes.

This re-renders the scene at 1400x1600 without overwriting the source. Native frame
counts and canvas sizes must remain those of the original creature. Higher review
fps is not the game's animation timing. Never package an appearance-rejected or
incomplete probe as a finished replacement.

## Assemble and validate locally

`new_creature_mod.py` scaffolds native-count resources. `roster_mod.py` appends
complete exports to a copied local mod, derives 1x from 2x, and prebakes shadows and
hover outlines. `stabilize_shadows.py` provides the current fixed-ground effect
implementation without a compiled engine dependency.

```sh
.venv/bin/python creature-art/validate_creature_animation.py /path/to/local/mod \
  --lod "$H3_DATA/H3sprite.lod" --shooter CLICH,CPLICH
```

Keep a backup before replacing an installed mod. Asset validation, geometry
checks, native startup and user appearance review are separate checks. Do not
infer final visual acceptance from a zero-error validator result.

## Publication boundary

Code is GPL-2.0-or-later, with source provenance in MIGRATION.json. That license
does not license third-party artwork. Generated assets, source-game extractions
and full mod packages stay outside this public source repository. Project
articles distinguish concepts, actual Blender stills, offline composites and
native game captures. Older mistaken statements are struck through and annotated
rather than removed.
