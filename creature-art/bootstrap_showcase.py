#!/usr/bin/env python3
"""Calibrate a bootstrap scene to the native creature showcase canvas.

Static appearance review only. It does not imply a rigged or installed creature.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
import render_sprites as render


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scene',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--height-px',type=int,required=True);p.add_argument('--ground',type=int,required=True)
    p.add_argument('--azimuth',type=float,default=-45)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.out.exists():raise ValueError('Output must be new')
    args.out.mkdir(parents=True)
    bpy.ops.wm.open_mainfile(filepath=str(args.scene));s=bpy.context.scene;c=s.camera
    s.render.resolution_x=900;s.render.resolution_y=800
    s.world.node_tree.nodes['Background'].inputs[1].default_value=.55
    fill=bpy.data.objects['fill'];fill.data.energy=2;fill.rotation_euler=(math.radians(78),0,0)
    c.rotation_euler=(math.radians(75),0,math.radians(args.azimuth))
    c.location=Vector((0,0,.85))+c.rotation_euler.to_matrix()@Vector((0,0,10));c.data.ortho_scale=5
    render.calibrate_camera(c,(900,800),args.ground*2,args.height_px*2,str(args.out/'calibration.png'))
    c.data.shift_x+=50/900
    render.render_to(str(args.out/'body2x.png'))
    box=render.measure_alpha_bbox(str(args.out/'body2x.png'))
    if box is None or abs(box[3]-box[1]-args.height_px*2)>2 or abs(box[3]-args.ground*2)>2:
        raise ValueError(f'Final showcase calibration outside one logical pixel: {box}')
    (args.out/'audit.json').write_text(json.dumps({'bbox':box,'canvas':[900,800],
        'originalHeight':args.height_px,'ground':args.ground,'azimuth':args.azimuth,'elevation':15,'previewOnly':True},indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(args.out/'showcase.blend'))


if __name__=='__main__':main()
