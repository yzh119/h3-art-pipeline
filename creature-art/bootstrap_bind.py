#!/usr/bin/env python3
"""Experimental upper-body/cloth binding for the generated footless wight.

Render a neutral pose and small deformations before authoring full animations.
No installation or visual acceptance is implied by successful weight checks.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
import render_sprites as render


def distance(points,a,b):
    a=np.array(a);b=np.array(b);v=b-a
    t=np.clip(((points-a)*v).sum(axis=1)/(v*v).sum(),0,1)
    return np.linalg.norm(points-a-t[:,None]*v,axis=1)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.out.exists():raise ValueError('Output must be new')
    args.out.mkdir(parents=True)
    bpy.ops.wm.open_mainfile(filepath=str(args.source));scene=bpy.context.scene
    body=next(o for o in scene.objects if o.type=='MESH')
    specs={
      'Torso':((0,.015,.83),(0,0,1.25),None),
      'Neck':((0,0,1.25),(0,-.025,1.40),'Torso'),
      'Head':((0,-.025,1.40),(0,-.035,1.62),'Neck'),
      'Tail1':((0,.015,.83),(0,.025,.55),'Torso'),
      'Tail2':((0,.025,.55),(0,.025,.28),'Tail1'),
      'Tail3':((0,.025,.28),(0,.025,.025),'Tail2')}
    for side,sign in [('Left',1),('Right',-1)]:
        specs[side+'UpperArm']=((sign*.14,0,1.27),(sign*.17,-.035,1.12),'Torso')
        specs[side+'ForeArm']=((sign*.17,-.035,1.12),(sign*.13,-.145,1.09),side+'UpperArm')
        specs[side+'Hand']=((sign*.13,-.145,1.09),(sign*.14,-.19,.98),side+'ForeArm')
    data=bpy.data.armatures.new('WightBootstrapRig');arm=bpy.data.objects.new('WightBootstrapRig',data);scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active=arm;arm.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    for name,(a,b,parent) in specs.items():
        bone=data.edit_bones.new(name);bone.head=a;bone.tail=b
        if parent:bone.parent=data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    coords=np.empty(len(body.data.vertices)*3,dtype=np.float32);body.data.vertices.foreach_get('co',coords);points=coords.reshape(-1,3)
    names=list(specs);dist=np.stack([distance(points,*specs[name][:2]) for name in names],axis=1)
    # Prevent robe-front vertices from reaching across to an unrelated hand.
    for j,name in enumerate(names):
        if name.startswith(('Left','Right')):
            sign=1 if name.startswith('Left') else -1
            dist[(points[:,0]*sign<.065)|(points[:,2]<.88),j]=100
        elif name.startswith('Tail'):
            dist[points[:,2]>1.0,j]=100
        elif name in ['Head','Neck']:
            dist[points[:,2]<1.18,j]=100
    weights=1/np.maximum(dist,.015)**6
    nearest=np.argsort(weights,axis=1)[:,-3:];mask=np.zeros_like(weights,dtype=bool)
    np.put_along_axis(mask,nearest,True,axis=1);weights=np.where(mask,weights,0);weights/=weights.sum(axis=1)[:,None]
    body.vertex_groups.clear()
    for j,name in enumerate(names):
        group=body.vertex_groups.new(name=name)
        for i in np.flatnonzero(weights[:,j]>.0001):group.add([int(i)],float(weights[i,j]),'REPLACE')
    body.modifiers.new('Wight skin','ARMATURE').object=arm
    root=bpy.data.objects.new('WightRoot',None);scene.collection.objects.link(root);arm.parent=root;body.parent=root
    report={'prototype':True,'vertices':len(points),'weightSumMaximumError':float(np.abs(weights.sum(axis=1)-1).max()),'landmarks':specs,'poses':{}}
    poses={'neutral':{},'hands':{'LeftForeArm':(.28,0,0),'RightForeArm':(.28,0,0)},
           'cloth':{'Tail1':(.25,0,0),'Tail2':(.18,0,.08),'Tail3':(.15,0,-.06)},
           'reach':{'Torso':(.20,0,0),'LeftUpperArm':(.25,0,-.12),'RightUpperArm':(.25,0,.12)}}
    for label,pose in poses.items():
        for bone in arm.pose.bones:bone.rotation_mode='XYZ';bone.rotation_euler=(0,0,0)
        for name,rotation in pose.items():arm.pose.bones[name].rotation_euler=rotation
        bpy.context.view_layer.update();render.render_to(str(args.out/(label+'.png')))
        report['poses'][label]={'bbox':render.measure_alpha_bbox(str(args.out/(label+'.png')))}
    for bone in arm.pose.bones:bone.rotation_euler=(0,0,0)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.out/'bound.blend'))
    (args.out/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    (args.out/'bootstrap_bind.py').write_bytes(Path(__file__).read_bytes())


if __name__=='__main__':main()
