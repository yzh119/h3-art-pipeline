# Wight and Wraith delivery

User accepted the new generated appearance, then explicitly accepted Wight
("幽灵完美交付"). Preserve its current model/motion. Wraith is installed alongside
it; do not attribute the same explicit individual acceptance to Wraith.

Installed mod0.9.0 adds CWIGHT/CWRAIT to the four previous units. Each has16native
groups and98frames/scale, including the native unused SHOOT groups (no mechanics
change). All2324installedfiles match the candidate,1462previousnonmetadatafiles
unchanged. Original-DEF validator132infos0warnings0errors. A fresh client reports
Loading mod OK. Installed0.8backup: necropolis-roster/installed-08-backup-20260908-103527.
Hash audit installation-09.json, installed-09-validation.json, installed-09-client.log.

Sources: ~/vcmi-art/necropolis-roster/wight-bootstrap-01/bind-01/bound.blend,
wight-motion-full-01, wraith-motion-full-01. bootstrap_bind.py creates12upperbody/
clothbones with normalized local geometric weights. wight_motion.py authors FK
float/lunge/turn/collapse on the generated textured mesh; no humanoid auto-rig or
leg gait for this footless creature. Wraith darkens cloth tones while retaining
pale bone. Both have1x/2x prebaked stable-ground shadows and hover outlines.

Death is an authored spectral collapse (cloth folds plus root compression), not
cloth simulation/ragdoll.73reopened integer/half-frame death samples perunit give
minimumZ0.00298628. Other clips have native-frame nonempty/canvas checks; don't
claim exhaustive collision/deformation checks or the old prototype's334IK checks.

roster_preview.py creates offline showcase crops and fixed-canvas gray-background
videos: holding4fps, others8fps. These are review speeds, not runtime timing.
Gallery /demos/necropolis-ghosts-01/, bilingualpost necropolis-ghosts. Failed
procedural/initialbootstrap history remains in necropolis-bootstrap.

Lich/PowerLich and remaining families continue separately. No further changes to
accepted Wight without a concrete issue or user feedback.

High-resolution static renders are now provided separately from the concepts:
`ghost-portraits-01/wight.png` and `wraith.png`, 1400x1600,64samples. The reusable
`render_portrait.py` opens the delivered holding scenes, reframes the camera,
renders transparent PNGs and verifies source hashes remain unchanged. The blog
provides both neutral-background JPEGs and original transparent PNGs. These are
new 3D renders, not upscaled native frames; no Wight model/motion change.
