# Necropolis upgrades

`upgrade_study.py` adds bone-bound equipment to the reviewed SkeletonStudy and
ZombieStudy clips. `settle_equipment.py` checks evaluated death-mesh vertices and
corrects vertical root position when new gear passes below the ground.
`roster_mod.py` appends original-count 1x/2x resources with baked shadows/outlines.
No engine changes or new Meshy calls are needed for these two upgrades.

Reviewed exports: `~/vcmi-art/necropolis-roster/skeleton-warrior-full-02` and
`zombie-upgrade-full-02`. Each has 13 groups; respectively 82 and 80 body frames at
2x, with 1x derived during packaging. Skeleton death minimum Z before correction
was -0.07261699; maximum root lift 0.07561699; after correction the sampled minimum
is -0.00003193. Zombie evaluated minimum is -0.00026583, requiring no lift.
Rotated bounding-box corners must not substitute for actual mesh vertices.

Candidate `~/vcmi-art/necropolis-roster/mod-08-final` validates against H3sprite.lod:
84 informational findings, zero warnings/errors. Previous creature/background
files remain byte-identical before package metadata is updated. The 0.8.0 package is now installed: all 1,463 files match the candidate, and
installed-copy validation also reports 84 infos, zero warnings/errors. A fresh
client reports `Loading mod: OK (necropolis-creature-animations)`. Complete battle
contact/timing acceptance remains pending. Previous 0.7.0 backup is under
`~/vcmi-art/necropolis-roster/installed-07-backup-20260908-094525`; file hashes and
client logs are alongside in `installation-08.json` and `installed-08-client.log`.

Reproduce packaging after the Blender exports:

```sh
python roster_mod.py --source-mod ~/vcmi-art/creature-game-05/mod \
  --out /tmp/necropolis-08 \
  --lod "$HOME/Library/Application Support/vcmi/Data/H3sprite.lod" \
  --unit CWSKEL=$HOME/vcmi-art/necropolis-roster/skeleton-warrior-full-02=267 \
  --unit CZOMLO=$HOME/vcmi-art/necropolis-roster/zombie-upgrade-full-02=266 \
  --version 0.8.0
```

Bilingual post: `/posts/necropolis-upgrades/` and `/zh/posts/necropolis-upgrades/`.
Gallery `/demos/necropolis-upgrades-01/` contains all 26 native-count clips,
offline composites at a deliberately separate review rate (holding 4 fps, others
8 fps). They are not game captures or runtime timing verification.

The other ten Necropolis entries have reference audits, not completed replacement
animations. Wight/wraith and lich scripts are still under development; vampires,
mounted knights, and dragons require their own characteristic movement.
