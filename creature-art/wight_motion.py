#!/usr/bin/env python3
"""Author native-count motion on the textured footless wight bootstrap rig.

Blender only. Includes floating garment controls and a spectral collapse; no
bipedal gait or physical ragdoll is implied. Review before installing exports.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
import render_sprites as render
from skeleton_motion import smooth,linear_keys
from settle_equipment import lowest
from vcmi_anim import GROUP_NAMES


def pose(group,t):
    wave=math.sin(math.tau*t);pulse=math.sin(math.pi*t)**2
    p={'location':[0,0,.008*wave],'rotation':[0,0,0],'scale':[1,1,1],'bones':{'Head':[.02*wave,0,0],'Tail1':[.035*wave,0,0],'Tail2':[.025*math.sin(math.tau*t+.7),0,0],'Tail3':[.03*math.sin(math.tau*t+1.4),0,0]}}
    if group=='MOVING':
        p['location'][2]=.025*wave
        p['bones'].update({'Torso':[.12,0,0],'Tail1':[.40+.08*wave,0,0],'Tail2':[.25+.05*math.sin(math.tau*t-.6),0,.025*wave],'Tail3':[.14+.09*math.sin(math.tau*t-1.2),0,-.02*wave]})
    elif group in ['MOVE_START','MOVE_END']:
        a=pose('HOLDING',0);b=pose('MOVING',0);u=smooth(t if group=='MOVE_START' else 1-t)
        for field in ['location','rotation','scale']:p[field]=[x+(y-x)*u for x,y in zip(a[field],b[field])]
        p['bones']={name:[a['bones'].get(name,[0,0,0])[i]+(b['bones'].get(name,[0,0,0])[i]-a['bones'].get(name,[0,0,0])[i])*u for i in range(3)] for name in a['bones'].keys()|b['bones'].keys()}
    elif group=='MOUSEON':p['bones'].update({'Head':[-.12*pulse,0,.07*pulse],'LeftForeArm':[.4*pulse,0,0]})
    elif group in ['DEFENCE','HITTED']:
        p['rotation'][0]=(-.22 if group=='HITTED' else -.12)*pulse;p['location'][1]=.08*pulse
        p['bones'].update({'LeftForeArm':[.55*pulse,0,0],'RightForeArm':[.55*pulse,0,0],'Tail1':[.12*pulse,0,0]})
    elif group.startswith(('ATTACK','SHOOT')):
        wind=math.sin(math.pi*min(1,t/.4))**2 if t<.4 else 0
        strike=math.sin(math.pi*max(0,(t-.2)/.8))**2
        height=.13 if group.endswith('UP') else (-.13 if group.endswith('DOWN') else 0)
        p['rotation'][0]=-.12*wind+.88*strike;p['location'][1]=-.22*strike;p['location'][2]+=height*strike
        p['bones'].update({'RightUpperArm':[.25*strike,0,.1*wind],'LeftUpperArm':[.20*strike,0,-.12*wind],
            'RightForeArm':[.65*wind+.15*strike,0,0],'LeftForeArm':[.35*wind+.10*strike,0,0],
            'Tail1':[.1*strike,0,0],'Tail2':[.12*strike,0,0]})
    elif group in ['TURN_L','TURN_R']:
        p['rotation'][2]=math.pi/2*smooth(t) if group=='TURN_L' else -math.pi/2*(1-smooth(t))
    elif group=='DEATH':
        fall=smooth(t);p['location']=[0,0,0];p['scale']=[1+.35*fall,1+.35*fall,1-.78*fall]
        p['bones'].update({'Torso':[.35*fall,0,0],'Head':[-.12*fall,0,0],
            'LeftUpperArm':[.4*math.sin(math.pi*t),0,-.6*math.sin(math.pi*t)],'RightUpperArm':[.4*math.sin(math.pi*t),0,.6*math.sin(math.pi*t)],
            'Tail1':[.4*fall,0,.25*fall],'Tail2':[.35*fall,0,-.35*fall],'Tail3':[.35*fall,0,.4*fall]})
    return p


def apply(arm,root,spec):
    root.location=(0,0,0);root.rotation_euler=spec['rotation'];root.scale=spec['scale']
    # Rotate attacks about the upper garment rather than the end of its hem.
    pivot=Vector((0,0,1.02));root.location=pivot-root.rotation_euler.to_matrix()@pivot+Vector(spec['location'])
    if spec['scale']!=[1,1,1]:root.location=spec['location']
    for b in arm.pose.bones:b.rotation_mode='XYZ';b.rotation_euler=spec['bones'].get(b.name,[0,0,0])
    bpy.context.view_layer.update()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--references',type=Path,required=True);p.add_argument('--variant',choices=['wight','wraith'],default='wight');p.add_argument('--preview-only',action='store_true')
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.out.exists():raise ValueError('Output must be new')
    args.out.mkdir(parents=True)
    ref=next(x for x in json.loads(args.references.read_text()) if x['name']==args.variant)
    bpy.ops.wm.open_mainfile(filepath=str(args.source));scene=bpy.context.scene
    arm=bpy.data.objects['WightBootstrapRig'];root=bpy.data.objects['WightRoot']
    if args.variant=='wraith':
        # Preserve pale bone while reducing warm, low-value burial-cloth colors.
        import numpy as np
        for image in bpy.data.images:
            if image.size[0]<1024:continue
            rgba=np.empty(image.size[0]*image.size[1]*4,dtype=np.float32);image.pixels.foreach_get(rgba);a=rgba.reshape(-1,4);rgb=a[:,:3]
            warm=np.clip((rgb[:,0]-rgb[:,2]-.015)/.08,0,1);dark=np.clip((.65-rgb.mean(axis=1))/.25,0,1);mask=warm*dark
            gray=rgb.mean(axis=1);rgb[:]=rgb*(1-mask[:,None]*.70)+gray[:,None]*mask[:,None]*.08
            image.pixels.foreach_set(rgba);image.update();image.pack()
    apply(arm,root,pose('HOLDING',0));scene.render.fps=30
    report={'variant':args.variant,'previewOnly':args.preview_only,'sourceSHA256':hashlib.sha256(args.source.read_bytes()).hexdigest(),'nativeReference':ref,'clips':{}}
    for gid,count in ref['groups'].items():
        if int(gid) not in GROUP_NAMES:continue
        group=GROUP_NAMES[int(gid)]
        if args.preview_only and group not in ['HOLDING','MOVING','ATTACK_FRONT','DEATH']:continue
        for o in [arm,root]:o.animation_data_clear()
        loop=group in ['HOLDING','MOVING'];seconds=2 if group=='HOLDING' else (1.2 if group=='DEATH' else (.3 if group.startswith(('TURN','MOVE_')) else 1))
        ticks=round(seconds*30)
        for tick in range(ticks+1):
            scene.frame_set(tick+1);apply(arm,root,pose(group,tick/ticks))
            if group=='DEATH':root.location.z+=max(0,.003-lowest());bpy.context.view_layer.update()
            for field in ['location','rotation_euler','scale']:root.keyframe_insert(field,frame=tick+1)
            for bone in arm.pose.bones:bone.keyframe_insert('rotation_euler',frame=tick+1)
        for o in [arm,root]:linear_keys(o.animation_data.action)
        scene.frame_start=1;scene.frame_end=ticks if loop else ticks+1;scene.frame_set(1)
        bpy.ops.wm.save_as_mainfile(filepath=str(args.out/(group.lower()+'.blend')))
        bpy.ops.wm.open_mainfile(filepath=str(args.out/(group.lower()+'.blend')));scene=bpy.context.scene
        arm=bpy.data.objects['WightBootstrapRig'];root=bpy.data.objects['WightRoot']
        floors=[]
        if group=='DEATH':
            for step in range(ticks*2+1):
                frame=1+step*.5;scene.frame_set(math.floor(frame),subframe=frame%1);z=lowest();floors.append(z)
                if z<-.002:raise ValueError(f'Death penetration at {frame}: {z}')
        frames=[];n=(1 if group=='HOLDING' else 5) if args.preview_only else count
        for i in range(n):
            t=(0 if args.preview_only and group=='HOLDING' else .5) if n==1 else i/(n if loop else n-1);frame=1+ticks*t
            scene.frame_set(math.floor(frame),subframe=frame%1);folder=args.out/'sprites2x';folder.mkdir(exist_ok=True);path=folder/(group.lower()+f'_{i:02}.png')
            render.render_to(str(path));box=render.measure_alpha_bbox(str(path))
            if not box or min(box[:2])<=0 or box[2]>=900 or box[3]>=800:raise ValueError('Empty/clipped render')
            frames.append({'frame':frame,'file':str(path.relative_to(args.out)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        report['clips'][group]={'frames':frames,'seconds':seconds,'loop':loop,'savedDeathSamples':len(floors),'minimumDeathZ':min(floors) if floors else None}
    report['checks']={'minimumDeathZ':report['clips']['DEATH']['minimumDeathZ'],'deathSamples':report['clips']['DEATH']['savedDeathSamples']}
    (args.out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');(args.out/'wight_motion.py').write_bytes(Path(__file__).read_bytes())


if __name__=='__main__':main()
