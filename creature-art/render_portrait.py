#!/usr/bin/env python3
"""Render a full-resolution static portrait from an existing editable scene.

Reframes the camera for a still image, without changing or overwriting the source
model, materials, pose or animation. Run in Blender. PNG retains transparency.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
import render_sprites as render


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--frame',type=float,default=1);p.add_argument('--width',type=int,default=1400);p.add_argument('--height',type=int,default=1600)
    p.add_argument('--samples',type=int,default=64)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.out.exists():raise ValueError('Portrait output already exists')
    source_hash=hashlib.sha256(args.source.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(args.source));scene=bpy.context.scene
    scene.frame_set(int(args.frame),subframe=args.frame%1)
    meshes=[o for o in scene.objects if o.type=='MESH' and not o.hide_render]
    points=render.world_vertices(meshes,bpy.context.evaluated_depsgraph_get())
    camera=scene.camera;rotation=camera.rotation_euler.to_matrix();inverse=rotation.transposed()
    projected=[inverse@v for v in points]
    lo=Vector([min(v[i] for v in projected) for i in range(3)]);hi=Vector([max(v[i] for v in projected) for i in range(3)])
    target=rotation@((lo+hi)*.5);camera.location=target+rotation@Vector((0,0,10))
    camera.data.shift_x=0;camera.data.shift_y=0
    aspect=args.width/args.height
    camera.data.ortho_scale=max(hi.y-lo.y,(hi.x-lo.x)/aspect)*1.12*max(1,aspect)
    scene.render.resolution_x=args.width;scene.render.resolution_y=args.height;scene.render.resolution_percentage=100
    scene.render.threads_mode='FIXED';scene.render.threads=4;scene.cycles.samples=args.samples;scene.cycles.use_animated_seed=False
    args.out.parent.mkdir(parents=True,exist_ok=True);render.render_to(str(args.out))
    box=render.measure_alpha_bbox(str(args.out))
    if not box or min(box[:2])<=0 or box[2]>=args.width or box[3]>=args.height:raise ValueError('Empty or clipped portrait')
    if hashlib.sha256(args.source.read_bytes()).hexdigest()!=source_hash:raise ValueError('Source changed')
    args.out.with_suffix('.json').write_text(json.dumps({'sourceSHA256':source_hash,'frame':args.frame,'size':[args.width,args.height],'alphaBounds':box,'blender':bpy.app.version_string,'toolSHA256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'renderSHA256':hashlib.sha256(args.out.read_bytes()).hexdigest()},indent=2)+'\n')


if __name__=='__main__':main()
