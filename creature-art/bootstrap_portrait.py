#!/usr/bin/env python3
"""Save an editable GLB inspection scene and render a high-resolution still.

This shows imported geometry in its supplied pose, not an animation delivery.
Run with Blender; all outputs belong outside the public source repository.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_sprites as render
import render_portrait


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--azimuth', type=float, default=20)
    parser.add_argument('--elevation', type=float, default=8)
    parser.add_argument('--fill', type=float, default=.1, help='Fill/key light ratio')
    parser.add_argument('--width', type=int, default=1400)
    parser.add_argument('--height', type=int, default=1600)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    if args.out.exists():
        raise ValueError('Use a fresh output directory')
    source_hash = hashlib.sha256(args.model.read_bytes()).hexdigest()
    args.out.mkdir(parents=True)
    meshes, camera, _ = render.build_scene(
        str(args.model), (args.width, args.height), args.elevation,
        args.azimuth, 0, 0, 64, 3, .16)
    scene = bpy.context.scene
    scene.objects['fill'].data.energy = 3 * args.fill
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 4
    scene.cycles.seed = 0
    scene.cycles.use_animated_seed = False
    scene.frame_set(1)
    points = render.world_vertices(meshes, bpy.context.evaluated_depsgraph_get())
    if not points:
        raise ValueError('Model contains no evaluated mesh vertices')
    report = {
        'stage': 'imported static bootstrap; motion not validated',
        'sourceSHA256': source_hash,
        'bounds': [[min(v[i] for v in points) for i in range(3)],
                   [max(v[i] for v in points) for i in range(3)]],
        'camera': {'azimuth': args.azimuth, 'elevation': args.elevation},
        'lighting': {'key': 3, 'fillRatio': args.fill, 'ambient': .16},
        'meshes': [{'name': o.name, 'vertices': len(o.data.vertices),
                    'faces': len(o.data.polygons)} for o in meshes],
        'textures': [{'name': i.name, 'size': list(i.size)}
                     for i in bpy.data.images if i.source == 'FILE'],
        'blender': bpy.app.version_string,
    }
    bpy.ops.file.pack_all()
    source = args.out / 'inspection.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(source))
    sys.argv = ['blender', '--', '--source', str(source), '--out',
                str(args.out / 'portrait.png'), '--width', str(args.width),
                '--height', str(args.height)]
    render_portrait.main()
    if hashlib.sha256(args.model.read_bytes()).hexdigest() != source_hash:
        raise ValueError('Input model changed')
    (args.out / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
    for name in ('bootstrap_portrait.py', 'render_portrait.py', 'render_sprites.py'):
        (args.out / name).write_bytes(Path(__file__).with_name(name).read_bytes())


if __name__ == '__main__':
    main()
