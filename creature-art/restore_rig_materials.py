"""Restore a single-material source GLB's PBR material after external rigging.

Blender --background --python-exit-code 1 --python restore_rig_materials.py -- \
    --source body.glb --rigged body-rigged.glb --out restored.blend

Requires unchanged triangle UVs. Refuses a changed atlas rather than silently
putting the old textures onto a new layout. Keeps the rig and animation intact.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

import bpy


def uv_signature(mesh):
    if not mesh.uv_layers.active:
        raise ValueError('Mesh has no active UV map')
    mesh.calc_loop_triangles()
    uv = mesh.uv_layers.active.data
    triangles = sorted(tuple(sorted(tuple(round(float(x), 5) for x in uv[i].uv)
                                   for i in triangle.loops))
                       for triangle in mesh.loop_triangles)
    digest = hashlib.sha256()
    for triangle in triangles:
        for point in triangle:
            digest.update(struct.pack('<2f', *point))
    return len(triangles), digest.hexdigest()


def import_objects(path):
    previous = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    return [obj for obj in bpy.data.objects if obj not in previous]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--rigged', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--glb-out', type=Path, help='optional restored GLB for motion-transfer tools')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    if args.out.suffix != '.blend' or args.out.exists():
        parser.error('--out must be a new .blend path')
    if args.glb_out and (args.glb_out.suffix != '.glb' or args.glb_out.exists()):
        parser.error('--glb-out must be a new .glb path')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source_objects = import_objects(args.source)
    sources = [obj for obj in source_objects if obj.type == 'MESH' and len(obj.data.vertices) > 100]
    if len(sources) != 1 or len(sources[0].data.materials) != 1:
        raise ValueError('Expected one source mesh with one material')
    source = sources[0]
    source_signature = uv_signature(source.data)
    material = source.data.materials[0].copy()
    rig_objects = import_objects(args.rigged)
    bodies = [obj for obj in rig_objects if obj.type == 'MESH' and len(obj.data.vertices) > 100]
    if len(bodies) != 1 or not any(obj.type == 'ARMATURE' for obj in rig_objects):
        raise ValueError('Expected one rigged body and its armature')
    body = bodies[0]
    rig_signature = uv_signature(body.data)
    if rig_signature != source_signature:
        raise ValueError(f'UV topology differs: source={source_signature}, rig={rig_signature}')
    body.data.materials.clear()
    body.data.materials.append(material)
    for polygon in body.data.polygons:
        polygon.material_index = 0
    for obj in source_objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    # Meshy's small unweighted preview proxy is not part of the character.
    proxies = [obj for obj in rig_objects if obj.type == 'MESH' and obj is not body]
    for obj in proxies:
        obj.hide_render = True
    args.out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(args.out))
    if args.glb_out:
        args.glb_out.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.object.select_all(action='DESELECT')
        for obj in rig_objects:
            if obj not in proxies:
                obj.select_set(True)
        bpy.ops.export_scene.gltf(filepath=str(args.glb_out), export_format='GLB',
                                  use_selection=True)
    report = {'source': str(args.source), 'rigged': str(args.rigged),
              'triangles': source_signature[0], 'uv_sha256': source_signature[1],
              'material': material.name, 'hidden_proxies': [obj.name for obj in proxies]}
    args.out.with_suffix('.material.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
