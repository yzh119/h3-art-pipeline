#!/usr/bin/env python3
"""Compute skin weights on a voxel proxy and transfer them to an existing mesh.

Blender --background --python-exit-code 1 --python proxy_skin.py -- \
  --source assembled.blend --body Body --armature Rig --out binding-review \
  --exclude-bone Root --exclude-prefix Wing.

The supplied skeleton must already fit the mesh in its rest pose. Geometry,
UVs and materials on the detailed body are preserved. A hidden proxy and an
audit remain in the output scene. This is a binding step, not motion approval.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

import bpy
from mathutils import Matrix
from mathutils.kdtree import KDTree


def geometry_signature(mesh):
    digest = hashlib.sha256()
    for vertex in mesh.vertices:
        digest.update(struct.pack('<3f', *vertex.co))
    for polygon in mesh.polygons:
        digest.update(struct.pack('<I', len(polygon.vertices)))
        for index in polygon.vertices:
            digest.update(struct.pack('<I', index))
    for layer in mesh.uv_layers:
        digest.update(layer.name.encode())
        for uv in layer.data:
            digest.update(struct.pack('<2f', *uv.uv))
    return digest.hexdigest()


def bind_proxy(body, armature, voxel, excluded, max_fill_fraction, max_fill_distance):
    signature = geometry_signature(body.data)
    materials = tuple(body.data.materials)
    previous_deform = {bone.name: bone.use_deform for bone in armature.data.bones}
    previous_pose = armature.data.pose_position
    proxy = body.copy()
    proxy.data = body.data.copy()
    proxy.name = body.name + ' weight proxy'
    bpy.context.scene.collection.objects.link(proxy)
    world = proxy.matrix_world.copy()
    proxy.parent = None
    proxy.data.transform(world)
    proxy.matrix_world = Matrix.Identity(4)
    proxy.modifiers.clear()
    proxy.vertex_groups.clear()
    proxy.animation_data_clear()
    try:
        armature.data.pose_position = 'REST'
        for bone in armature.data.bones:
            bone.use_deform = previous_deform[bone.name] and bone.name not in excluded
        bpy.ops.object.select_all(action='DESELECT')
        proxy.hide_set(False)
        proxy.hide_viewport = False
        proxy.select_set(True)
        bpy.context.view_layer.objects.active = proxy
        proxy.data.remesh_voxel_size = voxel
        proxy.data.use_remesh_preserve_volume = True
        bpy.ops.object.voxel_remesh()
        if len(proxy.data.vertices) < 4:
            raise ValueError('Voxel proxy is empty or too small')
        modifier = proxy.modifiers.new('Proxy smoothing', 'SMOOTH')
        modifier.factor = 1
        modifier.iterations = 4
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        armature.select_set(True)
        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')
        bpy.context.view_layer.update()
        valid = {group.index: group.name for group in proxy.vertex_groups
                 if group.name in armature.data.bones
                 and armature.data.bones[group.name].use_deform}
        proxy_weights = []
        for vertex in proxy.data.vertices:
            row = {valid[group.group]: group.weight for group in vertex.groups
                   if group.group in valid and group.weight > 1e-7}
            total = sum(row.values())
            proxy_weights.append({name: weight / total for name, weight in row.items()}
                                 if total else {})
        weighted_count = sum(bool(row) for row in proxy_weights)
        missing = len(proxy_weights) - weighted_count
        if not weighted_count or missing / len(proxy_weights) > max_fill_fraction:
            raise ValueError(f'Heat solve left {missing}/{len(proxy_weights)} vertices unweighted')
        weighted_tree = KDTree(weighted_count)
        for index, row in enumerate(proxy_weights):
            if row:
                weighted_tree.insert(proxy.matrix_world @ proxy.data.vertices[index].co, index)
        weighted_tree.balance()
        fill_distances = []
        for index, row in enumerate(proxy_weights):
            if row:
                continue
            _, nearest, distance = weighted_tree.find(
                proxy.matrix_world @ proxy.data.vertices[index].co)
            if distance > max_fill_distance:
                raise ValueError(f'Unweighted proxy island is {distance:.6f} m from valid weights')
            proxy_weights[index] = dict(proxy_weights[nearest])
            fill_distances.append(distance)
        tree = KDTree(len(proxy.data.vertices))
        for vertex in proxy.data.vertices:
            tree.insert(proxy.matrix_world @ vertex.co, vertex.index)
        tree.balance()
        # Preserve unrelated vertex groups; replace only this armature's skin groups.
        for group in list(body.vertex_groups):
            if group.name in armature.data.bones:
                body.vertex_groups.remove(group)
        names = sorted({name for row in proxy_weights for name in row})
        groups = {name: body.vertex_groups.new(name=name) for name in names}
        max_error = 0
        max_distance = 0
        for vertex in body.data.vertices:
            neighbors = tree.find_n(body.matrix_world @ vertex.co, 4)
            row = {}
            total = 0
            max_distance = max(max_distance, neighbors[0][2])
            for _, index, distance in neighbors:
                factor = 1 / max(distance, voxel * .1) ** 2
                total += factor
                for name, weight in proxy_weights[index].items():
                    row[name] = row.get(name, 0) + factor * weight
            row = {name: weight / total for name, weight in row.items()}
            max_error = max(max_error, abs(sum(row.values()) - 1))
            for name, weight in row.items():
                if weight > 0:
                    groups[name].add([vertex.index], weight, 'REPLACE')
        if not any(mod.type == 'ARMATURE' and mod.object == armature for mod in body.modifiers):
            body.modifiers.new('Proxy-transferred skin', 'ARMATURE').object = armature
        assert geometry_signature(body.data) == signature, 'Detailed mesh or UVs changed'
        assert tuple(body.data.materials) == materials, 'Detailed materials changed'
        proxy.hide_render = True
        proxy.hide_set(True)
        return {
            'body': body.name, 'armature': armature.name, 'proxy': proxy.name,
            'bodyVertices': len(body.data.vertices), 'proxyVertices': len(proxy.data.vertices),
            'voxelMeters': voxel, 'unweightedProxyVerticesFilled': missing,
            'maximumFillDistance': max(fill_distances, default=0),
            'maximumBodyToProxyDistance': max_distance,
            'weightSumMaximumError': max_error,
            'geometryAndUVSignature': signature,
            'excludedBones': sorted(excluded),
            'scope': 'Rest binding and unchanged body geometry/UV/materials; motion and appearance require review',
        }
    finally:
        armature.data.pose_position = previous_pose
        for bone in armature.data.bones:
            bone.use_deform = previous_deform[bone.name]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--body', required=True)
    parser.add_argument('--armature', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--voxel', type=float, default=.018)
    parser.add_argument('--exclude-bone', action='append', default=[])
    parser.add_argument('--exclude-prefix', action='append', default=[])
    parser.add_argument('--max-fill-fraction', type=float, default=.01)
    parser.add_argument('--max-fill-distance', type=float, default=.072)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    if args.out.exists() or args.voxel <= 0:
        parser.error('Use a new output directory and positive voxel size')
    if not 0 <= args.max_fill_fraction <= 1 or args.max_fill_distance < 0:
        parser.error('Invalid unweighted-island limits')
    bpy.ops.wm.open_mainfile(filepath=str(args.source))
    body = bpy.data.objects[args.body]
    armature = bpy.data.objects[args.armature]
    if body.type != 'MESH' or armature.type != 'ARMATURE':
        parser.error('Expected a mesh body and an armature')
    excluded = set(args.exclude_bone)
    excluded.update(bone.name for bone in armature.data.bones
                    if any(bone.name.startswith(prefix) for prefix in args.exclude_prefix))
    report = bind_proxy(body, armature, args.voxel, excluded,
                        args.max_fill_fraction, args.max_fill_distance)
    args.out.mkdir(parents=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.out / 'source.blend'))
    report['sourceSHA256'] = hashlib.sha256(args.source.read_bytes()).hexdigest()
    (args.out / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
