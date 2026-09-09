# H3 art pipeline

Standalone art tools for Heroes III graphical mods running on VCMI. Creature
geometry repair, rigging, authored animation, static portraits, native-count
sprite export, town layers, effects and validation live here rather than inside
the engine repository.

- [Creature tools](creature-art/README.md) and [mounted knight / dragon workflow](creature-art/docs/necropolis-final-four.md)
- [Vampire workflow](creature-art/docs/necropolis-vampires.md)
- [Town tools](town-art/README.md)
- [Environment and font tools](environment-art/README.md)
- [Reproduce the workflow](docs/REPRODUCING.md)

## Project blog and visual results

The bilingual series documents the workflow, failed attempts, Blender renders,
animation reviews and in-game results:
[用生成式ai增强英雄无敌3（中文）](https://yzh119.github.io/zh/series/用生成式ai增强英雄无敌3/)
· [Enhancing Heroes III with Generative AI (English)](https://yzh119.github.io/series/enhancing-heroes-iii-with-generative-ai/).

| Topic | 中文 | English |
| --- | --- | --- |
| Skeleton rig repair and the Opus → Astra migration | [骷髅绑定与模型迁移](https://yzh119.github.io/zh/posts/skeleton-rig-study/) | [Skeleton rig study](https://yzh119.github.io/posts/skeleton-rig-study/) |
| Zombie modeling and animation | [僵尸制作](https://yzh119.github.io/zh/posts/zombie-study/) | [Zombie study](https://yzh119.github.io/posts/zombie-study/) |
| Wight and Wraith local rigs | [幽灵与阴魂](https://yzh119.github.io/zh/posts/necropolis-ghosts/) | [Wight and Wraith](https://yzh119.github.io/posts/necropolis-ghosts/) |
| Lich and Power Lich animation | [尸巫与尸巫王](https://yzh119.github.io/zh/posts/necropolis-liches/) | [Lich and Power Lich](https://yzh119.github.io/posts/necropolis-liches/) |
| Vampire transformation and rig repair | [吸血鬼与吸血鬼王](https://yzh119.github.io/zh/posts/necropolis-vampires/) | [Vampires](https://yzh119.github.io/posts/necropolis-vampires/) |
| Mounted knights, skeletal dragons and attack corrections | [骑士与骨龙动画](https://yzh119.github.io/zh/posts/necropolis-final-four/) | [Knights and dragons](https://yzh119.github.io/posts/necropolis-final-four/) |
| Layered town artwork | [墓园城镇高清化](https://yzh119.github.io/zh/posts/necropolis-hd/) | [Necropolis town artwork](https://yzh119.github.io/posts/necropolis-hd/) |
| Battlefields, adventure-map towns and fonts | [环境与字体高清化](https://yzh119.github.io/zh/posts/h3-environment-hd/) | [Environment and fonts](https://yzh119.github.io/posts/h3-environment-hd/) |
| Creature portraits and building thumbnails | [城镇界面缩略图](https://yzh119.github.io/zh/posts/necropolis-ui-thumbnails/) | [UI thumbnails](https://yzh119.github.io/posts/necropolis-ui-thumbnails/) |

This repository publishes reusable tools and prompts. Complete mods, models and
extracted game assets remain local; the blog provides visual demonstrations.

## Setup

Python 3.9 or later, Blender (tested with 5.2.1), and ffmpeg for video previews.
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
