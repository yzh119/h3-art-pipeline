# Asset generation: options survey

Surveyed 2026-09-05. Prices and model versions move fast — re-check before committing
budget. This document exists to make the choice, not to make it look already made.

## What already exists (do not rebuild)

| | |
|---|---|
| [`vcmi-mods/hd-remastered`](https://github.com/vcmi-mods/hd-remastered) | Community HD project, ported to VCMI, everything already in PNG. The reference mod for layout and naming. |
| `modders-tool-pack` (VCMI launcher) | Ships `vcmiextract` and `def2json` — converts `.lod`/`.def` to PNG + JSON. **This replaces the `.def` introspection item on our roadmap.** |
| [`Laserlicht/vcmi_hd_mod`](https://github.com/Laserlicht/vcmi_hd_mod) | HD Edition → VCMI mod converter. Obsolete (the engine reads `.pak` natively now, `client/render/hdEdition/`) but useful as a reference. |
| Cagney's H3 HD Reskin Project ([ModDB](https://www.moddb.com/mods/cagneys-heroes-3-hd-reskin-project)) | **Direct precedent.** Blender-modelled creatures rendered to HD sprites for VCMI, one unit at a time — and it also started with the skeleton. Worth contacting before duplicating effort. |
| Remastered Portraits (in the launcher's Portraits Pack) | Hero portraits already redone with AI + manual touch-up. Portraits are done; skip them. |

Note on upstream appetite: an [older forum thread](https://forum.vcmi.eu/t/heroes-iii-hd-remake/918/40)
records the developers as sceptical of HD assets, citing hardcoded UI positioning. That
predates the current engine, which ships `docs/modders/HD_Graphics.md`, per-scale sprite
trees and native HD Edition `.pak` loading. The practical reading: **this belongs as a mod,
and tooling that touches no engine code is uncontroversial.** That is how this directory is
built.

---

## Lane A — 3D reconstruct → rig → animate → render

The only lane that solves frame coherence structurally rather than statistically: frames
are renders of one model, so they cannot disagree. It also yields the shadow and overlay
layers as extra render passes, which the engine requires anyway.

### A1. Image-to-3D

| Service | Notes | Price |
|---|---|---|
| **Tripo** | Generally ranked first for overall pipeline in 2026 round-ups. Fast, clean topology, and — decisively for us — the only one with documented **non-humanoid rig coverage**. Full REST API. | 20 cr untextured / 30 cr textured; **1 cr = $0.01** |
| **Meshy** | Strongest mainstream generation quality (Meshy 6/7) and the cheapest per mesh, with a full REST API. **But its rigging is humanoid-only — see below.** | see the Meshy breakdown |
| **Rodin (Hyper3D)** | Highest geometry fidelity of the hosted options. Most expensive, slowest on low-poly. | ~$0.40–$1.50 per model depending on route/complexity |
| **Hunyuan3D** (Tencent) | Open weights, self-hostable, quality comparable to hosted tools. No per-asset cost, no vendor lock, but you own the GPU and the ops. | free / your hardware |

#### Meshy in detail

Worth its own section because the answer splits cleanly: Meshy is an excellent **mesh**
vendor for this project and a useless **rig/animation** vendor for it.

Useful to us:

| Endpoint | Credits | Why it matters here |
|---|---|---|
| Image to 3D | 20 (raw) / 30 (textured) / 35 (8K) on Meshy-6/7; **5 / 15 / 20 on Smart Topology** | The Smart Topology tier is the cheapest credible mesh in the survey. |
| Multi Image to 3D | same | H3 gives us a second genuine viewpoint per creature for free: the adventure-map animation (`graphics.map`) shows the same unit from a different angle than the battle `.def`. Feeding both should measurably improve reconstruction. |
| Remesh | 5 | Poly-count and quad-topology control before rigging. Cheap enough to run on everything. |
| Retexture | 10 (2K/4K) / 15 (8K) | **The art-direction iteration lever.** Restyle a locked mesh without regenerating geometry — so silhouette stays fixed and approved while you try five looks. |

Not useful to us:

- **Rigging API — humanoid only.** The docs state it plainly: unsuitable for "non-humanoid
  assets". Requirements are a textured humanoid facing +Z with clear limbs, ≤300k faces.
- **Animation — walk and run.** In the UI, quadrupeds are supported via Smart Rig (Beta),
  but *walking is the only animation available for them*.

Heroes III's bestiary is majority non-humanoid — dragons, hydras, beholders, serpents,
elementals, behemoths. Meshy cannot rig or animate them.

At the Pro tier (~$20/mo for 1000 credits, i.e. ~$0.02/credit) a textured Smart Topology
mesh is ~$0.30 and a Meshy-6 textured mesh ~$0.60.

**Verdict:** use Meshy for mesh generation and retexture iteration; get the rig elsewhere.
Since H3's poses need hand-keying regardless (below), pairing Meshy meshes with Blender
rigging is a coherent choice — you are not really losing anything you were going to use.

### A2. Rigging and animation

This is where H3 punishes the naive choice. The bestiary is mostly **not** humanoid —
dragons, hydras, beholders, serpents, elementals. Mixamo-class humanoid-only rigging is
useless for the majority of the roster.

- **Tripo auto-rig** — `v2.5-20260210` documents quadruped, hexapod, octopod, serpentine,
  aquatic and avian skeletons. 25 cr to rig, 10 cr per retargeted animation. The only
  hosted service in this survey that covers H3's actual bestiary.
- **Meshy auto-rig** — humanoid only (5 cr rig, 3 cr animation). Ruled out for creatures.
- **Anything World** — explicitly built for non-bipedal and low-poly rigging.
- **Sorceress 3D Studio** — browser auto-rig, humanoid + non-humanoid, weight-paint
  refinement, FBX/GLB export. Closest 1:1 Mixamo replacement.
- **AccuRig** — free, solid, humanoid-leaning.

Caveat worth stating plainly: **retargeted library animations will not match H3's poses.**
H3's attack/defend/turn animations are stylised and specific. Expect library retargeting to
carry `MOVING`, `HOLDING`, `DEATH`, and expect `ATTACK_*` to need hand-keying per creature
archetype. That is the real labour in this lane, and no service removes it.

### A3. Render

Self-hosted Blender, headless, driven by the manifest `new_creature_mod.py` emits. Prior
art to crib from rather than write:
[`dbarton-uk/blender-sprite-render`](https://github.com/dbarton-uk/blender-sprite-render)
(orthographic, configurable angle, RGBA out),
[`pekkavaa/SpriteBatchRender`](https://github.com/pekkavaa/SpriteBatchRender),
[`johnferley/Game-Sprite-Creator`](https://github.com/johnferley/Game-Sprite-Creator).

Three passes per frame, straight into the layout the validator expects:

1. beauty → `holding_00.png`
2. shadow catcher only → `holding_00-shadow.png`
3. unlit white material → `holding_00-overlay.png`

Camera angle should be derived empirically — match renders against extracted original
frames until silhouettes line up — not guessed. Orthographic, fixed, with the ground line
pinned to the canvas position the original `.def` used.

### Cost, Lane A, via Tripo

Per creature: image-to-3D textured 30 cr + auto-rig 25 cr + HD texture 20 cr + ~11
retargets × 10 cr = **~185 cr ≈ $1.85**.

**Across ~150 creatures: roughly $280 in API spend.** Render time is your own hardware.

That number is the point of this survey. Generation is not the constraint. Art direction
and per-creature review are the entire cost, and they are human hours.

---

## Lane B — 2D repaint, reference-pinned diffusion

No 3D. Pin identity with a reference image or a per-creature LoRA, generate each frame.

- **Flux Kontext + character LoRA** — the standard 2026 recipe for character sheets.
- **Qwen-Image-Edit** — strong identity preservation across angle/style changes.
- **Nano Banana (Gemini)** — stable identity latent, edits without drifting the character.
- **Retro Diffusion `rd-animation`** ([Replicate](https://replicate.com/retro-diffusion/rd-animation))
  — trained specifically on multi-frame sprite sheets, outputs frame grids. The only one
  in this lane targeting animation rather than stills.

Honest assessment: identity holds well; **inter-frame coherence still does not**, outside
`rd-animation`'s low frame counts. Sub-pixel wobble across 8 idle frames is exactly what
the validator's drift check exists to catch, and in this lane you will trip it constantly.

Good fit for: portraits, UI, adventure-map objects, anything static.
Poor fit for: battle animations, which is most of the work.

---

## Lane C — superresolution only

Keep the original art, raise the resolution. No repaint.

- **Upscayl** — recommended by VCMI's Laserlicht over xBRZ as an editing base; noted as
  clearly better than xBRZ, still short of hand-crafted, and strongest on buildings.
- **Real-ESRGAN / SwinIR** — same family, scriptable.

Cheapest by far, community-proven, and it composes with the others: use it as the base
layer and repaint selectively on top.

---

## Recommendation

Not a decision — a default to argue with.

**Lane A, one creature, before anything else.** The skeleton, because it is
structurally simple, has every animation group, and Cagney has already proven the route.

Split the vendors rather than picking one:

- **mesh** — Meshy (cheapest credible, and Multi-Image-to-3D can eat both the battle and
  adventure-map views), or Hunyuan3D if you would rather self-host
- **rig** — Tripo, the only one covering non-humanoids; or Blender directly, since the
  poses need hand-keying anyway
- **animate + render** — Blender, headless, driven by the render manifest
- **gate** — this directory's validator

The skeleton is humanoid, so it is the one creature where Meshy end-to-end would also
work. Do not read that as evidence the roster will.

Then look at the result and decide whether the remaining 149 are worth it. The API spend
to find out is under five dollars.

Lane C is worth running in parallel regardless — it is nearly free and improves everything
that Lane A will not reach for years.

## Decisions (2026-09-05)

Settled by the project owner:

| | |
|---|---|
| **Style** | **Modern redesign**, not a faithful high-fidelity upscale. Original sprites are silhouette and anchor reference only, not conditioning input. |
| **Scope** | **Battle animations only.** No adventure map, no town screens — so the seamless-tiling problem is out of scope entirely. |
| **Hosting** | **Hosted services**, not self-hosted. Hunyuan3D is off the table for now. |
| **First target** | **The skeleton (`CSKELE.DEF`) alone**, end to end, before anything else is attempted. |

Two consequences worth naming:

**Redesign makes the licensing question much easier.** Faithful upscaling produces a
derivative work of Ubisoft's art. A modern redesign that reuses only the silhouette and
the anchor position is original art that happens to fit H3's layout — distributable as a
normal mod. This removes the "ship a local conversion tool" constraint that Lane C
carries. It does not remove the need to keep original pixels out of the generation input;
`def_extract.py`'s reference frames are for *matching against*, not for feeding to a model.

**Redesign raises the art-direction bar, not the technical one.** With faithful upscaling
the target is objective — does it look like the original, sharper. With redesign there is
no target until someone defines one. The concept pass for the skeleton is now the first
real deliverable, and it gates everything downstream.

### Resulting pipeline for `CSKELE`

Real numbers, read from `H3sprite.lod`:

- canvas **450x400**, all 15 groups agree
- ground line **y = 267**, held to the pixel across idle groups
- **82 frames** across the 13 groups the engine knows (groups 9 and 10 are unused
  duplicates of `TURN_L`/`TURN_R` and are skipped)

Steps:

1. **Concept** — a modern skeleton design, front and side, matching the original
   silhouette proportions closely enough that it reads as the same unit on the hex.
2. **Mesh** — Meshy image-to-3D from the concept. Multi-Image-to-3D if the concept is
   produced as multiple views. ~$0.30-0.60.
3. **Rig** — the skeleton is humanoid, so Meshy's rigging API works here. Note this is the
   one creature where that is true; the roster at large needs Tripo.
4. **Animate** — 13 groups. Library retargeting for `MOVING`/`HOLDING`/`DEATH`; the three
   `ATTACK_*` directions hand-keyed, since no library matches H3's poses.
5. **Render** — Blender, orthographic, camera solved by matching against
   `def_extract.py export` reference frames. Three passes per frame: beauty, shadow
   catcher, unlit white.
6. **Validate** — `validate_creature_animation.py`, which will fail loudly on canvas,
   anchor drift, and missing overlay layers.

Total API spend for this creature: **under $2.**
