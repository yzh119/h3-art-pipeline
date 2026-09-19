#!/usr/bin/env python3
"""Normalize a generated mesh and render fixed-scale turnarounds in Blender.

No rigging or installation is implied. Save the normalized editable scene,
material/mesh audit, and eight orthographic views for bootstrap inspection.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
import render_sprites as render


def without_bone_widgets(meshes):
    """Exclude custom bone display objects from physical model measurements."""
    rigs = set()
    for mesh in meshes:
        rigs.update(mod.object for mod in mesh.modifiers
                    if mod.type == 'ARMATURE' and mod.object is not None)
        parent = mesh.parent
        while parent is not None:
            if parent.type == 'ARMATURE':
                rigs.add(parent)
            parent = parent.parent
    widgets = {bone.custom_shape for rig in rigs for bone in rig.pose.bones
               if bone.custom_shape is not None}
    return [mesh for mesh in meshes if mesh not in widgets]


def normalize_hierarchy(meshes, height):
    """Transform the imported hierarchy together, preserving skin bind spaces."""
    meshes = without_bone_widgets(meshes)
    points = render.world_vertices(meshes, bpy.context.evaluated_depsgraph_get())
    if not points or not math.isfinite(height) or height <= 0:
        raise ValueError('A nonempty model and positive finite height are required')
    lo = Vector(tuple(min(v[i] for v in points) for i in range(3)))
    hi = Vector(tuple(max(v[i] for v in points) for i in range(3)))
    if hi.z - lo.z <= 1e-8:
        raise ValueError('Model has no measurable height')
    center = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    transform = Matrix.Scale(height / (hi.z - lo.z), 4) @ Matrix.Translation(-center)
    roots = set()
    related = list(meshes)
    for mesh in meshes:
        related.extend(mod.object for mod in mesh.modifiers
                       if mod.type == 'ARMATURE' and mod.object is not None)
    for obj in related:
        while obj.parent is not None:
            obj = obj.parent
        roots.add(obj)
    carrier = bpy.data.objects.new('ModelNormalization', None)
    bpy.context.scene.collection.objects.link(carrier)
    for obj in sorted(roots, key=lambda obj: obj.name):
        world = obj.matrix_world.copy()
        obj.parent = carrier
        obj.matrix_parent_inverse = Matrix.Identity(4)
        obj.matrix_world = world
    carrier.matrix_world = transform
    bpy.context.view_layer.update()
    return lo, hi, carrier


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--height',type=float,default=1.7);p.add_argument('--samples',type=int,default=32)
    p.add_argument('--exclude-object', action='append', default=[],
                   help='Explicitly remove a reviewed placeholder mesh before measuring bounds')
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.out.exists():raise ValueError('Output must be new')
    args.out.mkdir(parents=True)
    meshes,camera,_=render.build_scene(str(args.model),(768,768),12,0,680,580,args.samples,3,.16)
    for name in args.exclude_object:
        obj = next((obj for obj in meshes if obj.name == name), None)
        if obj is None or obj.children:
            raise ValueError('Excluded object must be an imported mesh without children: ' + name)
        meshes.remove(obj)
        bpy.data.objects.remove(obj, do_unlink=True)
    scene=bpy.context.scene;scene.render.threads_mode='FIXED';scene.render.threads=4
    scene.cycles.seed=0;scene.cycles.use_animated_seed=False
    measured_meshes = without_bone_widgets(meshes)
    ignored_widgets = [obj.name for obj in meshes if obj not in measured_meshes]
    meshes = measured_meshes
    lo,hi,carrier=normalize_hierarchy(meshes,args.height)
    report={'sourceSHA256':hashlib.sha256(args.model.read_bytes()).hexdigest(),'sourceBounds':[list(lo),list(hi)],'height':args.height,'normalizationCarrier':carrier.name,'excludedObjects':args.exclude_object,'ignoredBoneWidgets':ignored_widgets,'objects':[]}
    for obj in meshes:
        report['objects'].append({'name':obj.name,'vertices':len(obj.data.vertices),'faces':len(obj.data.polygons),
            'components':sorted([len(c) for c in render.connected_components(obj.data)],reverse=True),'materials':[m.name for m in obj.data.materials if m]})
    target=Vector((0,0,args.height*.5));camera.data.ortho_scale=2.25
    for yaw in range(0,360,45):
        camera.rotation_euler=(math.radians(78),0,math.radians(yaw))
        camera.location=target+camera.rotation_euler.to_matrix()@Vector((0,0,10))
        render.render_to(str(args.out/f'view-{yaw:03}.png'))
    camera.rotation_euler=(math.radians(78),0,math.radians(45));camera.location=target+camera.rotation_euler.to_matrix()@Vector((0,0,10))
    bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(args.out/'normalized.blend'))
    (args.out/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    (args.out/'bootstrap_review.py').write_bytes(Path(__file__).read_bytes())


if __name__=='__main__':main()
