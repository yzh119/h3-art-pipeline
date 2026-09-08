# H3 art pipeline

Standalone art tools for Heroes III graphical mods running on VCMI. Creature
geometry repair, rigging, authored animation, static portraits, native-count
sprite export, town layers, effects and validation live here rather than inside
the engine repository.

- [Creature tools](creature-art/README.md) and [current Lich workflow](creature-art/docs/necropolis-liches.md)
- [Town tools](town-art/README.md)
- [Reproduce the workflow](docs/REPRODUCING.md)
- [Project articles](https://yzh119.github.io/zh/series/英雄无敌3/)

## Setup

Python 3.9 or later, Blender (tested with5.2.1), and ffmpeg for video previews.
The Python environment needs Pillow and NumPy; Blender uses its own Python.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python creature-art/def_extract.py info /path/to/H3sprite.lod CSKELE.DEF
.venv/bin/python creature-art/validate_creature_animation.py /path/to/mod \
  --lod /path/to/H3sprite.lod --shooter CLICH,CPLICH
```

Original Heroes III data must come from the user's local installation. Do not put
LOD archives, extracted references, credentials or large working scenes in Git.
Generated sources and `.blend` exports remain in an external art workspace.

## Current division of work

Imagegen produces visual concepts. Meshy still supplies textured base geometry
and suitable humanoid auto-rigs. Astra writes local repair, rigging, motion,
rendering and packaging tools. Footless Wight uses a local rig. Native group
counts come from each original creature; they are not universally thirteen.
Current effects are fixed-ground shadows and hover outlines baked offline.

Most tools need no VCMI checkout or build. The town tools include a pinned
`reference-config/necropolis.json`; `--faction-config` accepts another compatible
configuration explicitly. `creature-art/bake_effects.cpp` is a historical native
algorithm comparison helper requiring an external VCMI build. It is not needed by
the current Python packaging path.

## Migration and license

These tools were extracted from
[yzh119/vcmi](https://github.com/yzh119/vcmi/pull/10). `MIGRATION.json` records the
source commit and SHA256 of every copied file before portability changes. The
original Git history remains available in that repository; work now continues
here. Existing saved exports retain their own historical source snapshots.

Code and the VCMI reference configuration are provided under **GPL-2.0-or-later**;
see [LICENSE](LICENSE). Preserve existing notices and source attribution. This
license does not license Heroes III artwork, trademarks, or service-generated
assets. No original game images or generated model binaries are included here. Complete
mod assets are kept locally; visual results are presented in the project blog.
