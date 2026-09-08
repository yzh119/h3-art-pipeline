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


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--height',type=float,default=1.7);p.add_argument('--samples',type=int,default=32)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.out.exists():raise ValueError('Output must be new')
    args.out.mkdir(parents=True)
    meshes,camera,_=render.build_scene(str(args.model),(768,768),12,0,680,580,args.samples,3,.16)
    scene=bpy.context.scene;scene.render.threads_mode='FIXED';scene.render.threads=4
    scene.cycles.seed=0;scene.cycles.use_animated_seed=False
    points=render.world_vertices(meshes,bpy.context.evaluated_depsgraph_get())
    lo=Vector(tuple(min(v[i] for v in points) for i in range(3)));hi=Vector(tuple(max(v[i] for v in points) for i in range(3)))
    scale=args.height/(hi.z-lo.z);center=Vector(((lo.x+hi.x)/2,(lo.y+hi.y)/2,lo.z))
    transform=Matrix.Scale(scale,4)@Matrix.Translation(-center)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in meshes:
        world=transform@obj.matrix_world;obj.parent=None;obj.matrix_world=world
        bpy.context.view_layer.objects.active=obj;obj.select_set(True)
        bpy.ops.object.transform_apply(location=True,rotation=True,scale=True);obj.select_set(False)
    bpy.context.view_layer.update()
    report={'sourceSHA256':hashlib.sha256(args.model.read_bytes()).hexdigest(),'sourceBounds':[list(lo),list(hi)],'height':args.height,'objects':[]}
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
