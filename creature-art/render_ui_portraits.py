#!/usr/bin/env python3
"""Render UI portrait masters from delivered Blender scenes without changing them.

Run in Blender with --manifest JSON --out DIRECTORY. Manifest rows specify
name, scene and upperFraction (fraction of projected model height to retain).
The intentional bust crop may cut the lower torso; the camera retains top margin.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector
sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_sprites as render


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    args.out.mkdir(parents=True, exist_ok=True)
    for spec in json.loads(args.manifest.read_text()):
        source = Path(spec['scene'])
        target = args.out / (spec['name'] + '.png')
        if target.exists():
            raise ValueError(f'Output exists: {target}')
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        bpy.ops.wm.open_mainfile(filepath=str(source))
        scene = bpy.context.scene
        scene.frame_set(1)
        meshes = [o for o in scene.objects if o.type == 'MESH' and not o.hide_render]
        points = render.world_vertices(meshes, bpy.context.evaluated_depsgraph_get())
        camera = scene.camera
        rotation = camera.rotation_euler.to_matrix()
        projected = [rotation.transposed() @ v for v in points]
        ymin = min(v.y for v in projected)
        ymax = max(v.y for v in projected)
        height = (ymax - ymin) * spec.get('upperFraction', 0.62)
        cropped = [v for v in projected if v.y >= ymax - height]
        xmin, xmax = min(v.x for v in cropped), max(v.x for v in cropped)
        center = Vector((xmin + (xmax - xmin) * spec.get('centerFraction', 0.5), ymax - height / 2, 0))
        camera.location = rotation @ center + rotation @ Vector((0, 0, 10))
        camera.data.shift_x = camera.data.shift_y = 0
        width, pixel_height = spec.get('size', [580, 640])
        camera.data.ortho_scale = height * 1.10
        if spec.get('fitWidth', True):
            camera.data.ortho_scale = max(camera.data.ortho_scale, (xmax - xmin) / (width / pixel_height) * 1.06)
        camera.data.ortho_scale *= max(1, width / pixel_height)
        scene.render.resolution_x = width
        scene.render.resolution_y = pixel_height
        scene.render.resolution_percentage = 100
        scene.render.film_transparent = True
        scene.render.image_settings.file_format = 'PNG'
        scene.render.image_settings.color_mode = 'RGBA'
        scene.render.threads_mode = 'FIXED'
        scene.render.threads = 4
        scene.cycles.samples = 32
        scene.cycles.use_animated_seed = False
        render.render_to(str(target))
        assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
        target.with_suffix('.json').write_text(json.dumps({
            'sourceSHA256': source_hash, 'specification': spec,
            'size': [width, pixel_height], 'blender': bpy.app.version_string,
            'outputSHA256': hashlib.sha256(target.read_bytes()).hexdigest(),
            'toolSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        }, indent=2) + '\n')


if __name__ == '__main__':
    main()
