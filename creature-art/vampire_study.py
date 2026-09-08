#!/usr/bin/env python3
"""Author humanoid vampire motion studies; flight and transitions are separate.

Uses anatomical joint heads from Meshy, rebuilding long imported bone tails.
Preserves generated texture and skin weights. Study exports cannot be installed.
"""
import argparse
import copy
import hashlib
import json
import math
import shutil
from pathlib import Path
import sys

import bpy
from mathutils import Vector, Quaternion
sys.path.insert(0,str(Path(__file__).resolve().parent))
import render_sprites as render
import lich_study as lich
import skeleton_study as study
import zombie_study as zombie
from skeleton_motion import linear_keys,smooth
from settle_equipment import lowest
from vcmi_anim import GROUP_NAMES


def rebuild(model, variant):
    meshes,camera,_=render.build_scene(str(model),(900,800),15,-45,534,168,24,3,.55)
    old=render.find_armature();source=max(meshes,key=lambda o:len(o.data.vertices))
    heads={b.name:old.matrix_world@b.head_local for b in old.data.bones}
    following={'Hips':'Spine02','Spine02':'Spine01','Spine01':'Spine','Spine':'neck','neck':'Head','Head':'head_end'}
    for side in ['Left','Right']:
        for x,y in [('Shoulder','Arm'),('Arm','ForeArm'),('ForeArm','Hand'),('UpLeg','Leg'),('Leg','Foot'),('Foot','ToeBase')]:following[side+x]=side+y
    landmarks={}
    for bone in old.data.bones:
        head=heads[bone.name];tail=heads[following[bone.name]] if bone.name in following else head+Vector((0,0,-.1))
        landmarks[bone.name]={'head':list(head),'tail':list(tail),'parent':bone.parent.name if bone.parent else None}
    arm=study.make_rig(landmarks);arm.name='VampireStudy'
    body=study.mesh_from_faces(source,lambda poly:True,'VampireSkin')
    for group in source.vertex_groups:body.vertex_groups.new(name=group.name)
    for i,vertex in enumerate(source.data.vertices):
        for group in vertex.groups:body.vertex_groups[group.group].add([i],group.weight,'REPLACE')
    body.modifiers.new('Vampire skin','ARMATURE').object=arm
    for obj in meshes+[old]:bpy.data.objects.remove(obj,do_unlink=True)
    controls={side+limb.title():study.make_ik(arm,side,limb) for side in ['Left','Right'] for limb in ['arm','leg']}
    root=study.empty('ZombieRoot',(0,0,0))
    for obj in [arm,body]+[c[k] for c in controls.values() for k in ['target','pole']]:obj.parent=root
    profile=json.loads(Path(__file__).with_name('profiles').joinpath('zombie-study.json').read_text())
    stance=profile['stance'];stance.update({'hips':list(heads['Hips']),'lean':5,'head_tilt':0,'root_pitch':0,'root_yaw':0,'floor_support':0})
    stance['hips'][2]-=.055
    for name,c in controls.items():stance[name]={'target':list(heads[c['end']]),'pole':list(c['pole'].location)}
    for side in ['Left','Right']:
        stance[side+'Arm']['target'][1]-=.17
        stance[side+'Arm']['target'][2]+=.12
    bpy.context.view_layer.update()
    return arm,root,controls,profile,{'landmarks':landmarks,'bodyVertices':len(body.data.vertices)}


def pose(profile,group,t):
    p=copy.deepcopy(profile['stance']);pulse=math.sin(math.pi*t)**2
    if group=='HOLDING':
        p['head_tilt']=1.5*math.sin(math.tau*t)
        for side in ['Left','Right']:p[side+'Arm']['target'][2]+=.012*math.sin(math.tau*t)
    elif group=='MOUSEON':
        p['lean']=10*pulse+5
        for side in ['Left','Right']:p[side+'Arm']['target'][2]+=.13*pulse
    elif group in ['HITTED','DEFENCE']:
        p['lean']-=16*pulse
        for side in ['Left','Right']:p[side+'Arm']['target'][2]+=.12*pulse
    elif group.startswith(('ATTACK','SHOOT','SPECIAL')):
        height=.14 if group.endswith('UP') else (-.18 if group.endswith('DOWN') else 0)
        p['hips'][2]-=.10*pulse;p['hips'][1]-=.04*pulse;p['lean']+=18*pulse
        for side,amount in [('Right',.22),('Left',.13)]:
            p[side+'Arm']['target'][1]-=amount*pulse;p[side+'Arm']['target'][2]+=(.16+height)*pulse
    elif group in ['TURN_L','TURN_R']:
        p['root_yaw']=90*smooth(t) if group=='TURN_L' else -90*(1-smooth(t))
    elif group=='DEATH':
        fall=smooth(max(0,(t-.40)/.60));lift=math.sin(math.pi*min(1,t/.70))**2
        p['root_pitch']=75*fall;p['hips'][2]-=.47*fall;p['lean']+=18*fall
        for side in ['Left','Right']:
            p[side+'Arm']['target'][2]+=.65*lift-.4*fall;p[side+'Arm']['target'][1]-=.08*fall;p[side+'Leg']['target'][1]-=.10*fall
    return p


def apply(arm,root,controls,spec,group,t):
    lich.apply(arm,root,controls,spec,group,t)
    for side in ['Left','Right']:
        rotation=Quaternion((1,0,0),math.radians(-55))
        controls[side+'Arm']['target'].rotation_quaternion=rotation@arm.data.bones[side+'Hand'].matrix_local.to_quaternion()
    bpy.context.view_layer.update()
    if group=='DEATH':root.location.z+=max(0,.003-lowest());bpy.context.view_layer.update()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--model',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--references',type=Path,required=True);p.add_argument('--preview-only',action='store_true');p.add_argument('--no-render',action='store_true');p.add_argument('--variant',choices=['vampire','vampire-lord'],default='vampire')
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.out.exists():raise ValueError('Output must be new')
    args.out.mkdir(parents=True)
    code=args.out/'code';code.mkdir()
    scripts={}
    for name in ['vampire_study.py','lich_study.py','zombie_study.py','skeleton_study.py','skeleton_motion.py','skeleton_geometry.py','render_sprites.py','settle_equipment.py','vcmi_anim.py','poses.py']:
        source=Path(__file__).with_name(name);shutil.copy2(source,code/name);scripts[name]=hashlib.sha256(source.read_bytes()).hexdigest()
    ref=next(x for x in json.loads(args.references.read_text()) if x['name']==('vampireLord' if args.variant=='vampire-lord' else 'vampire'))
    arm,root,controls,profile,repair=rebuild(args.model,args.variant);scene=bpy.context.scene
    scene.render.threads_mode='FIXED';scene.render.threads=4;scene.cycles.use_animated_seed=False;scene.cycles.seed=0
    fill=bpy.data.objects['fill'];fill.data.energy=2;fill.rotation_euler=(math.radians(78),0,0)
    apply(arm,root,controls,pose(profile,'HOLDING',0),'HOLDING',0)
    camera=scene.camera;camera.location=Vector((0,0,.85))+camera.rotation_euler.to_matrix()@Vector((0,0,10));camera.data.ortho_scale=5
    if not args.no_render:render.calibrate_camera(camera,(900,800),534,174 if args.variant=='vampire-lord' else 168,str(args.out/'calibration.png'))
    camera.data.shift_x+=50/900
    scene.render.fps=30;bpy.ops.file.pack_all();report={'variant':args.variant,'previewOnly':True,'scripts':scripts,'referenceSHA256':hashlib.sha256(args.references.read_bytes()).hexdigest(),'sourceSHA256':hashlib.sha256(args.model.read_bytes()).hexdigest(),'repair':repair,'clips':{}}
    for gid,count in ref['groups'].items():
        if int(gid) not in GROUP_NAMES or int(gid) in [0,20,21]:continue
        group=GROUP_NAMES[int(gid)]
        for obj in scene.objects:obj.animation_data_clear()
        for mat in bpy.data.materials:
            if mat.use_nodes:mat.node_tree.animation_data_clear()
        loop=group in ['HOLDING','MOVING'];seconds=2 if group=='HOLDING' else (1.2 if group=='DEATH' else (.3 if group.startswith(('TURN','MOVE_')) else 1))
        ticks=round(seconds*30);previous={};errors=[];reach_adjustments=[]
        for tick in range(ticks+1):
            scene.frame_set(tick+1);apply(arm,root,controls,pose(profile,group,tick/ticks),group,tick/ticks);zombie.key(arm,controls,tick+1,previous)
            for mat in bpy.data.materials:
                if mat.use_nodes:
                    for node in mat.node_tree.nodes:
                        if node.type=='BSDF_PRINCIPLED':node.inputs['Emission Strength'].keyframe_insert('default_value',frame=tick+1)
            reach_adjustments.append(root['reachAdjustment'])
            error=max((arm.matrix_world@arm.pose.bones[c['end']].head-c['target'].matrix_world.translation).length for c in controls.values());errors.append(error)
            if error>.008:raise ValueError(f'{group} frame{tick+1} IK errors '+str({name:(arm.matrix_world@arm.pose.bones[c['end']].head-c['target'].matrix_world.translation).length for name,c in controls.items()}))
        for obj in scene.objects:
            if obj.animation_data and obj.animation_data.action:linear_keys(obj.animation_data.action)
        scene.frame_start=1;scene.frame_end=ticks if loop else ticks+1;scene.frame_set(1)
        bpy.ops.wm.save_as_mainfile(filepath=str(args.out/(group.lower()+'.blend')))
        control_names={name:{k:(v.name if k in ['target','pole'] else v) for k,v in c.items()} for name,c in controls.items()}
        bpy.ops.wm.open_mainfile(filepath=str(args.out/(group.lower()+'.blend')));scene=bpy.context.scene
        arm=bpy.data.objects['VampireStudy'];root=bpy.data.objects['ZombieRoot']
        controls={name:{k:(bpy.data.objects[v] if k in ['target','pole'] else v) for k,v in c.items()} for name,c in control_names.items()}
        saved_errors=[];floors=[]
        for step in range(ticks*2+1):
            frame=1+step*.5;scene.frame_set(math.floor(frame),subframe=frame%1)
            error=max((arm.matrix_world@arm.pose.bones[c['end']].head-c['target'].matrix_world.translation).length for c in controls.values());saved_errors.append(error)
            if error>.008:raise ValueError(f'Saved {group} frame {frame} IK error {error}')
            if group=='DEATH':
                floors.append(lowest())
                if floors[-1]<-.002:raise ValueError(f'Saved death below ground: {floors[-1]}')
        frames=[];n=(1 if group=='HOLDING' else 3) if args.preview_only else count
        for i in range(0 if args.no_render else n):
            t=(0 if args.preview_only else .5) if n==1 else i/(n if loop else n-1);frame=1+ticks*t
            scene.frame_set(math.floor(frame),subframe=frame%1);folder=args.out/'sprites2x';folder.mkdir(exist_ok=True);path=folder/(group.lower()+f'_{i:02}.png');render.render_to(str(path))
            box=render.measure_alpha_bbox(str(path))
            if not box or min(box[:2])<=0 or box[2]>=900 or box[3]>=800:raise ValueError('Empty/clipped render')
            frames.append({'frame':frame,'file':str(path.relative_to(args.out)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        report['clips'][group]={'frames':frames,'seconds':seconds,'loop':loop,'maximumReachAdjustment':max(reach_adjustments),'maximumIKError':max(errors),'savedSamples':len(saved_errors),'maximumSavedIKError':max(saved_errors),'minimumDeathZ':min(floors) if floors else None}
    report['checks']={'savedSamples':sum(c['savedSamples'] for c in report['clips'].values()),'maximumSavedIKError':max(c['maximumSavedIKError'] for c in report['clips'].values()),'minimumDeathZ':report['clips']['DEATH']['minimumDeathZ']}
    (args.out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');(args.out/'vampire_study.py').write_bytes(Path(__file__).read_bytes())


if __name__=='__main__':main()
