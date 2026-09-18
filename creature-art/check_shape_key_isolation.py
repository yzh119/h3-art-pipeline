#!/usr/bin/env python3
"""Check each relative shape key against its own allowed vertex mask.

Run with Blender --background --python-exit-code 1 --python this_file --
--scene scene.blend --masks masks.json --out report.json.
Masks are {"object name": {"key name": [vertex indices]}}. Assets and masks
remain private. This checks authored coordinates, not anatomy or collisions.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', type=Path, required=True)
    parser.add_argument('--masks', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--tolerance', type=float, default=1e-6,
                        help='Allowed displacement in mesh-local units')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    if not math.isfinite(args.tolerance) or args.tolerance < 0:
        raise ValueError('Tolerance must be finite and nonnegative')
    masks = json.loads(args.masks.read_text())
    if not masks:
        raise ValueError('At least one object and shape key are required')
    bpy.ops.wm.open_mainfile(filepath=str(args.scene.resolve()))
    rows = []
    for object_name, keys in masks.items():
        obj = bpy.data.objects[object_name]
        if obj.type != 'MESH' or not obj.data.shape_keys or not keys:
            raise ValueError(f'{object_name}: expected a mesh with named keys')
        if not obj.data.shape_keys.use_relative:
            raise ValueError('Absolute shape keys are not supported')
        count = len(obj.data.vertices)
        for key_name, indices in keys.items():
            if not indices or any(type(i) is not int or not 0 <= i < count
                                  for i in indices):
                raise ValueError(f'{object_name}/{key_name}: invalid vertex mask')
            key = obj.data.shape_keys.key_blocks[key_name]
            reference = key.relative_key
            if key == reference:
                raise ValueError('The reference key cannot be checked against itself')
            allowed = set(indices)
            outside = []
            maximum = 0.0
            for i, vertex in enumerate(key.data):
                if i in allowed:
                    continue
                distance = (vertex.co - reference.data[i].co).length
                maximum = max(maximum, distance)
                if distance > args.tolerance:
                    outside.append(i)
            rows.append({'object': object_name, 'key': key_name,
                         'relativeKey': reference.name,
                         'allowedVertices': len(allowed),
                         'outsideMaskChanged': len(outside),
                         'outsideMaskMaxLocalDisplacement': maximum,
                         'firstOutsideIndices': outside[:20]})
    passed = all(row['outsideMaskChanged'] == 0 for row in rows)
    report = {'passed': passed, 'toleranceMeshLocal': args.tolerance,
              'sceneSHA256': hashlib.sha256(args.scene.read_bytes()).hexdigest(),
              'masksSHA256': hashlib.sha256(args.masks.read_bytes()).hexdigest(),
              'scope': 'Only the listed relative keys; each checked separately. '
                       'Does not establish pose, driver, anatomy or contact correctness.',
              'keys': rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': passed, 'checkedKeys': len(rows)}))
    if not passed:
        raise RuntimeError('Shape-key changes escape their individual masks; see report')


if __name__ == '__main__':
    main()
