# Concept brief — Skeleton (`CSKELE`)

First creature. Everything here is measured from the original art with
`def_extract.py`, not estimated. The style section is the only part that is a
choice rather than a constraint.

## Hard constraints

These come from the engine and the original `.def`. A concept that violates them
cannot be used, however good it looks.

| | |
|---|---|
| Canvas | **450 × 400** px at 1x, identical for every frame |
| Ground line | **y = 267** — the feet sit here, held to the pixel across idle frames |
| Creature size | **42 × 79** px idle; **158 × 136** across all actions (the sword swing sets the width) |
| Scale reference | The battle hex step is 44 px, so the skeleton is about **one hex wide and under two hexes tall** |
| Animation groups | 13 groups, 82 frames — see `def_extract.py info` |
| Facing | One direction only; the engine mirrors for the other side |
| Layers | Three per frame: body, ground shadow, white overlay silhouette |

### What 42 × 79 actually means

This is the number that should govern every design decision. In the original, the
ribcage detail you see when zoomed in occupies **two or three pixels** in game. It
is texture, not shape — it contributes a value break, nothing more.

So the design has to survive being reduced to:

- one silhouette
- three or four value masses inside it

Anything finer is noise that will alias differently every frame. Check any candidate
with `preview.py readability` before committing to it.

## What the original reads as

Stripped to silhouette — which is most of what a player perceives at this size:

- a **hunched, forward-leaning** humanoid, head thrust ahead of the shoulders
- **thin limbs** with visible gaps between them; the silhouette is porous, not solid
- a **long diagonal sword** that is a major part of the read in every pose, and the
  single biggest shape in the attack frames
- a wide, low stance — the legs are always split, never together

The palette is 223 distinct colours dominated by desaturated bone tones
(`#7B7B63`, `#84846B`, `#636352`). Note what this means: **the original is not
limited-palette pixel art.** Heroes III's creatures were pre-rendered from 3D. A 3D
pipeline is a return to the original method, not a departure from it.

## Style direction

**Silhouette-first stylised.** Chosen over dark realism and faithful modernisation.

- **Exaggerate proportions for readability.** Heavier skull, broader shoulder and
  pelvis masses, longer sword. Thin parts should be *fewer and thicker* rather than
  many and thin — a forearm that is one pixel wide disappears.
- **Three value masses, high contrast.** Bone reads light; the gaps and undersides
  read dark; one mid tone ties them. Decide the values before any detail.
- **Keep the original's posture and sword line.** That is what makes it recognisable
  as this unit; it is also what the acceptance test measures.
- **Silhouette must be readable with the fill removed.** If the pure black shape is
  ambiguous, the design fails regardless of how it looks at 4x.
- Reference points: Darkest Dungeon, Battle Brothers — bold shape language, strong
  value structure, detail subordinated to read.

Deliberately *not*: photoreal decay, fine cloth and rust texture, busy silhouettes.
They look excellent at 4x and turn to mush at 42 × 79.

## Concept deliverable

What the mesh step needs is a clean character image the reconstruction can read.

1. **Primary view** — three-quarter front, matching the original's stance:
   weight forward, sword held low and diagonal across the body.
2. **Side view** — same pose, for multi-image reconstruction. Meshy's
   Multi Image to 3D takes both and produces a better mesh than either alone.
3. Neutral even lighting, plain background, no ground shadow baked in, no motion
   blur, no dramatic rim light. Anything baked into the concept fights the render
   step, which lights and shadows the model itself.

A starting prompt, to be iterated rather than used as-is:

> Stylised fantasy skeleton warrior, three-quarter front view, full body, standing
> hunched forward with head thrust ahead of the shoulders, holding a long sword low
> and diagonal across the body, wide low stance with legs split. Bold readable
> silhouette, exaggerated skull and pelvis masses, thick simplified limbs, three
> strong value masses, desaturated bone palette. Flat even lighting, plain
> background, no ground shadow, no motion blur. Game character concept sheet.

## Acceptance test

Before a concept goes to the mesh step:

```bash
LOD=~/"Library/Application Support/vcmi/Data/H3sprite.lod"
python3 creature-art/preview.py readability concept.png \
    --height 79 --lod "$LOD" --against CSKELE.DEF --out check.png
```

This renders the candidate at 1x / 2x / 4x, extracts its silhouette at in-game size,
and scores overlap against the original:

- **≥ 70 %** — reads as the same unit
- **50–70 %** — a redesign that still fits its hex
- **< 50 %** — will not be recognised in play

Look at `check.png` as well as the number. The 1x tile is what players see; if the
design only works in the 4x tile, it is not finished.

## After the concept

3. mesh — Meshy Multi Image to 3D from the two views
4. rig — the skeleton is humanoid, so Meshy's rigging API covers this one; the wider
   roster will need Tripo
5. animate — 13 groups; library retargeting for `MOVING` / `HOLDING` / `DEATH`, the
   three `ATTACK_*` hand-keyed, since no library matches H3's poses
6. render — Blender, orthographic, camera solved by matching against
   `def_extract.py export` reference frames, three passes per frame
7. validate — `validate_creature_animation.py`, which fails on canvas, anchor drift
   and missing overlays

See [`asset-generation-survey.md`](asset-generation-survey.md) for the service
comparison behind those choices.
