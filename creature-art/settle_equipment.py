#!/usr/bin/env python3
"""Re-bake corpse ground contact after adding equipment to an existing rig.

Run in Blender. Changes only the DEATH root's vertical keys and its body frames;
samples evaluated vertices rather than rotated bounding-box corners.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys

import bpy
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent))
from skeleton_motion import linear_keys
from render_sprites import render_to


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def lowest():
    graph=bpy.context.evaluated_depsgraph_get();result=float('inf')
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH' or obj.hide_render:continue
        evaluated=obj.evaluated_get(graph);mesh=evaluated.to_mesh()
        coords=np.empty(len(mesh.vertices)*3,dtype=np.float32);mesh.vertices.foreach_get('co',coords)
        matrix=np.array(evaluated.matrix_world)
        points=coords.reshape(-1,3)
        z=points[:,0]*matrix[2,0]+points[:,1]*matrix[2,1]+points[:,2]*matrix[2,2]+matrix[2,3]
        if len(z):result=min(result,float(z.min()))
        evaluated.to_mesh_clear()
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.out.exists():raise ValueError('Output must be new')
    shutil.copytree(args.source,args.out)
    manifest=json.loads((args.out/'manifest.json').read_text())
    bpy.ops.wm.open_mainfile(filepath=str(args.source/'death.blend'))
    scene=bpy.context.scene;root=bpy.data.objects.get('MotionRoot') or bpy.data.objects['ZombieRoot']
    frames=np.arange(scene.frame_start,scene.frame_end+.25,.5);baseline=[]
    for frame in frames:
        scene.frame_set(math.floor(frame),subframe=frame%1);baseline.append(root.location.z)
    report=[]
    for frame,z in zip(frames,baseline):
        scene.frame_set(math.floor(frame),subframe=frame%1);root.location.z=z;bpy.context.view_layer.update()
        before=lowest();lift=.003-before if before<-.001 else 0
        root.location.z=z+lift;root.keyframe_insert('location',index=2,frame=frame)
        bpy.context.view_layer.update();after=lowest()
        if after<-.0011:raise ValueError('Ground correction failed')
        report.append({'frame':float(frame),'beforeMinimumZ':before,'lift':lift,'afterMinimumZ':after})
    linear_keys(root.animation_data.action)
    scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(args.out/'death.blend'))
    # Check the saved scene, including every native output sample.
    bpy.ops.wm.open_mainfile(filepath=str(args.out/'death.blend'));scene=bpy.context.scene
    for entry in manifest['clips']['DEATH']['frames']:
        f=entry['frame'];scene.frame_set(math.floor(f),subframe=f%1)
        if lowest()<-.002:raise ValueError('Reopened native frame penetrates floor')
        path=args.out/entry['file'];render_to(str(path));entry['sha256']=digest(path)
    manifest['equipmentContact']={'toolSHA256':digest(Path(__file__)),'sourceExportManifestSHA256':digest(args.source/'manifest.json'),
        'maximumLift':max(r['lift'] for r in report),'samples':report}
    (args.out/'settle_equipment.py').write_bytes(Path(__file__).read_bytes())
    (args.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':main()
