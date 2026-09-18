# Relative shape-key isolation

Create independent corrections with `obj.shape_key_add(name=..., from_mix=False)`.
Blender defaults `from_mix` to true: adding a second correction can capture the
first correction's currently evaluated deformation. Driving both keys then applies
that deformation twice. Zeroing only animation controls is insufficient if another
driver or key remains active.

Check each key against its own vertex mask, not the union of both hands:

```json
{"Character": {"LeftGrip": [0, 1, 2], "RightGrip": [3, 4, 5]}}
```

Use real vertex indices from the private asset. Run:

```sh
blender --background --python-exit-code 1 \
  --python creature-art/check_shape_key_isolation.py -- \
  --scene /path/to/private/character.blend \
  --masks /path/to/private/masks.json \
  --out /path/to/private/isolation-report.json
```

The report records source hashes, each key's relative reference, and displacement
outside its individual mask in mesh-local units. Nonzero violations fail the
process. Only named keys are checked; the tool does not infer intended masks.
It does not test driver behavior, posed anatomy, finger contact, or collisions.

Validated on a failing two-hand correction where the right key carried 862 left
hand vertices, and on its regenerated `from_mix=False` counterpart. The former
fails; the latter passes both individual masks. Both still require art review.
