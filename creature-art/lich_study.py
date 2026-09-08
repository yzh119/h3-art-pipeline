#!/usr/bin/env python3
"""Repair the textured lich rig, isolate its staff, and author native clips.

Uses anatomical joint heads from Meshy, rebuilding long imported bone tails.
Staff and nearby grip vertices follow the left hand rigidly. Blender only.
"""
import argparse
import copy
import hashlib
import json
import math
import statistics
import shutil
from pathlib import Path
import sys

import bpy
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
import render_sprites as render
import skeleton_study as study
import zombie_study as zombie
from skeleton_motion import linear_keys,smooth
from settle_equipment import lowest
from vcmi_anim import GROUP_NAMES


def rebuild(model, variant):
    meshes,camera,_=render.build_scene(str(model),(900,800),15,-45,534,182,32,3,.55)
    old=render.find_armature();source=max(meshes,key=lambda o:len(o.data.vertices))
    for mat in source.data.materials:
        if mat.use_nodes:
            for node in mat.node_tree.nodes:
                if node.type=='BSDF_PRINCIPLED':
                    for link in list(node.inputs['Emission Color'].links):mat.node_tree.links.remove(link)
                    tint=mat.node_tree.nodes.new('ShaderNodeMixRGB');tint.name='LichCastingTint';tint.blend_type='MULTIPLY'
                    tint.inputs[0].default_value=1;tint.inputs[2].default_value=(1,.008,.002,1)
                    base=node.inputs['Base Color']
                    if base.links:mat.node_tree.links.new(base.links[0].from_socket,tint.inputs[1])
                    else:tint.inputs[1].default_value=base.default_value
                    mat.node_tree.links.new(tint.outputs[0],node.inputs['Emission Color'])

    heads={b.name:old.matrix_world@b.head_local for b in old.data.bones};next_joint={'Hips':'Spine02','Spine02':'Spine01','Spine01':'Spine','Spine':'neck','neck':'Head','Head':'head_end'}
    for side in ['Left','Right']:
        for a,b in [('Shoulder','Arm'),('Arm','ForeArm'),('ForeArm','Hand'),('UpLeg','Leg'),('Leg','Foot'),('Foot','ToeBase')]:next_joint[side+a]=side+b
    landmarks={}
    for b in old.data.bones:
        h=heads[b.name];tail=heads[next_joint[b.name]] if b.name in next_joint else h+Vector((0,-.08,0) if b.name=='LeftHand' else (0,-.01,-.10))
        landmarks[b.name]={'head':list(h),'tail':list(tail),'parent':b.parent.name if b.parent else None}
    arm=study.make_rig(landmarks);arm.name='LichStudy'
    coords=[source.matrix_world@v.co for v in source.data.vertices]
    # Fit the shaft in an unobstructed low band. The crowned variant's
    # crescent/orb is isolated above the shoulders with a wider radius.
    band=[c for c in coords if .40<c.z<.60 and c.x>heads['LeftHand'].x-.04]
    if len(band)<20:raise ValueError('Cannot measure staff shaft')
    cx=statistics.median(c.x for c in band);cy=statistics.median(c.y for c in band)
    staff_faces=set()
    for poly in source.data.polygons:
        c=sum((coords[i] for i in poly.vertices),Vector())/len(poly.vertices)
        radius=.115 if variant=='power-lich' and c.z>1.40 else .034
        if math.hypot(c.x-cx,c.y-cy)<radius:staff_faces.add(poly.index)
    if not staff_faces:raise ValueError('Empty staff extraction')
    keep=lambda poly:poly.index not in staff_faces
    indices=sorted({i for poly in source.data.polygons if keep(poly) for i in poly.vertices})
    body=study.mesh_from_faces(source,keep,'LichSkin')
    for group in source.vertex_groups:body.vertex_groups.new(name=group.name)
    rigid_grip=0
    for i,old_index in enumerate(indices):
        c=coords[old_index]
        if (c-heads['LeftHand']).length<.075 and c.y<heads['LeftHand'].y+.055:
            body.vertex_groups['LeftHand'].add([i],1,'REPLACE');rigid_grip+=1
        else:
            for group in source.data.vertices[old_index].groups:body.vertex_groups[group.group].add([i],group.weight,'REPLACE')
    body.modifiers.new('Lich skin','ARMATURE').object=arm
    staff=study.mesh_from_faces(source,lambda poly:poly.index in staff_faces,'LichStaff')
    staff.data.transform(arm.data.bones['LeftHand'].matrix_local.inverted())
    socket=study.empty('LichStaffSocket',(0,0,0));constraint=socket.constraints.new('COPY_TRANSFORMS');constraint.target=arm;constraint.subtarget='LeftHand';staff.parent=socket
    for obj in meshes+[old]:bpy.data.objects.remove(obj,do_unlink=True)
    controls={side+limb.title():study.make_ik(arm,side,limb) for side in ['Left','Right'] for limb in ['arm','leg']}
    # Existing zombie pose/key helpers address this neutral root by name.
    root=study.empty('ZombieRoot',(0,0,0))
    for obj in [arm,body,socket]+[c[k] for c in controls.values() for k in ['target','pole']]:obj.parent=root
    profile=json.loads(Path(__file__).with_name('profiles').joinpath('zombie-study.json').read_text())
    stance=profile['stance'];stance['hips']=list(heads['Hips']);stance['lean']=0;stance['head_tilt']=0;stance['root_pitch']=0;stance['root_yaw']=0;stance['floor_support']=0
    for name,c in controls.items():stance[name]={'target':list(heads[c['end']]),'pole':list(c['pole'].location)}
    profile['walk'].update({'stride':.34,'hip_bob':.008,'right_lift':.055,'left_lift':.055,'arm_swing':.035,'stance_fraction':.62})
    bpy.context.view_layer.update()
    return arm,root,controls,profile,{'landmarks':landmarks,'shaftCenter':[cx,cy],'staffFaces':len(staff_faces),'rigidGripVertices':rigid_grip,'bodyVertices':len(body.data.vertices)}


def pose(profile,group,t):
    p=copy.deepcopy(profile['stance']);pulse=math.sin(math.pi*t)**2
    if group=='MOVING':p=zombie.pose(profile,'MOVING',t)
    elif group in ['MOVE_START','MOVE_END']:
        return zombie.mix(p,pose(profile,'MOVING',0),smooth(t if group=='MOVE_START' else 1-t))
    elif group=='HOLDING':p['head_tilt']=1*math.sin(math.tau*t)
    elif group=='MOUSEON':p['RightArm']['target'][2]+=.12*pulse;p['head_tilt']=-4*pulse
    elif group in ['HITTED','DEFENCE']:
        p['lean']=-12*pulse;p['hips'][1]+=.05*pulse;p['RightArm']['target'][2]+=.19*pulse
    elif group.startswith(('ATTACK','SHOOT')):
        height=.18 if group.endswith('UP') else (-.17 if group.endswith('DOWN') else 0)
        p['lean']=(10 if group.startswith('SHOOT') else 15)*pulse;p['hips'][2]-=(.12 if height<0 else 0)*pulse;p['LeftArm']['target'][1]-=.23*pulse;p['LeftArm']['target'][2]+=height*pulse
        p['RightArm']['target'][1]-=.23*pulse;p['RightArm']['target'][2]+=(.26+height)*pulse
    elif group in ['TURN_L','TURN_R']:
        p['root_yaw']=90*smooth(t) if group=='TURN_L' else -90*(1-smooth(t))
    elif group=='DEATH':
        fall=smooth(t);p['root_pitch']=75*fall;p['hips'][2]-=.48*fall;p['lean']=20*fall
        for side in ['Left','Right']:
            p[side+'Arm']['target'][2]-=.42*fall;p[side+'Arm']['target'][1]-=.10*fall;p[side+'Leg']['target'][1]-=.10*fall
    return p


def apply(arm,root,controls,spec,group,t):
    spec=copy.deepcopy(spec)
    # Solve a reachable hip height from each leg's measured two-bone length.
    # An imported straight standing leg cannot accept a forward foot target at
    # the same hip height without stretching.
    drop=0.0
    for side in ['Left','Right']:
        upper=arm.data.bones[side+'UpLeg'];lower=arm.data.bones[side+'Leg']
        head=Vector(spec['hips'])+upper.head_local-arm.data.bones['Hips'].head_local
        target=Vector(spec[side+'Leg']['target']);radius=upper.length+lower.length-.002
        horizontal=(head.x-target.x)**2+(head.y-target.y)**2
        if horizontal>=radius**2:raise ValueError('Leg target beyond horizontal reach')
        drop=max(drop,head.z-target.z-math.sqrt(radius**2-horizontal))
    spec['hips'][2]-=max(0,drop)
    zombie.apply(arm,controls,spec)
    reach_adjustment=0.0
    for side in ['Left','Right']:
        shoulder=arm.pose.bones[side+'Arm'].head
        target=controls[side+'Arm']['target']
        delta=target.location-shoulder
        radius=arm.data.bones[side+'Arm'].length+arm.data.bones[side+'ForeArm'].length-.002
        if delta.length>radius:
            reach_adjustment=max(reach_adjustment,delta.length-radius)
            target.location=shoulder+delta.normalized()*radius
    if reach_adjustment>.08:raise ValueError(f'Authored wrist exceeds reach by {reach_adjustment}')
    root['reachAdjustment']=reach_adjustment
    bpy.context.view_layer.update()
    # The staff is held in the LEFT hand of this generated model. Correct hand
    # orientation is independent of the old right-handed zombie weapon helper.
    angle=math.radians((75 if group.startswith('SHOOT') else 85)*math.sin(math.pi*t)**2) if group.startswith(('ATTACK','SHOOT')) else (-math.radians(15)*smooth(t) if group=='DEATH' else 0)
    rotation=Vector((0,0,1)).rotation_difference(Vector((0,-math.sin(angle),math.cos(angle))))
    controls['LeftArm']['target'].rotation_quaternion=rotation@arm.data.bones['LeftHand'].matrix_local.to_quaternion()
    controls['RightArm']['target'].rotation_quaternion=arm.data.bones['RightHand'].matrix_local.to_quaternion()
    bpy.context.view_layer.update()
    if group=='DEATH':root.location.z+=max(0,.003-lowest());bpy.context.view_layer.update()
    # Original ranged attacks flash red. Keep texture detail with a keyed
    # emission contribution; no new mesh or gameplay projectile is introduced.
    for mat in bpy.data.materials:
        if mat.use_nodes:
            for node in mat.node_tree.nodes:
                if node.type=='BSDF_PRINCIPLED':
                    node.inputs['Emission Color'].default_value=(1,.008,.002,1)
                    node.inputs['Emission Strength'].default_value=(1.0*math.sin(math.pi*t)**8 if group.startswith('SHOOT') else 0)



def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--model',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--references',type=Path,required=True);p.add_argument('--preview-only',action='store_true');p.add_argument('--no-render',action='store_true');p.add_argument('--variant',choices=['lich','power-lich'],default='lich')
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.out.exists():raise ValueError('Output must be new')
    args.out.mkdir(parents=True)
    code=args.out/'code';code.mkdir()
    scripts={}
    for name in ['lich_study.py','zombie_study.py','skeleton_study.py','skeleton_motion.py','skeleton_geometry.py','render_sprites.py','settle_equipment.py','vcmi_anim.py','poses.py']:
        source=Path(__file__).with_name(name);shutil.copy2(source,code/name);scripts[name]=hashlib.sha256(source.read_bytes()).hexdigest()
    ref=next(x for x in json.loads(args.references.read_text()) if x['name']==('powerLich' if args.variant=='power-lich' else 'lich'))
    arm,root,controls,profile,repair=rebuild(args.model,args.variant);scene=bpy.context.scene
    scene.render.threads_mode='FIXED';scene.render.threads=4;scene.cycles.use_animated_seed=False;scene.cycles.seed=0
    fill=bpy.data.objects['fill'];fill.data.energy=2;fill.rotation_euler=(math.radians(78),0,0)
    apply(arm,root,controls,pose(profile,'HOLDING',0),'HOLDING',0)
    camera=scene.camera;camera.location=Vector((0,0,.85))+camera.rotation_euler.to_matrix()@Vector((0,0,10));camera.data.ortho_scale=5
    if not args.no_render:render.calibrate_camera(camera,(900,800),534,210 if args.variant=='power-lich' else 182,str(args.out/'calibration.png'))
    camera.data.shift_x+=50/900
    scene.render.fps=30;bpy.ops.file.pack_all();report={'variant':args.variant,'previewOnly':args.preview_only or args.no_render,'scripts':scripts,'referenceSHA256':hashlib.sha256(args.references.read_bytes()).hexdigest(),'sourceSHA256':hashlib.sha256(args.model.read_bytes()).hexdigest(),'repair':repair,'clips':{}}
    for gid,count in ref['groups'].items():
        if int(gid) not in GROUP_NAMES:continue
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
        arm=bpy.data.objects['LichStudy'];root=bpy.data.objects['ZombieRoot']
        controls={name:{k:(bpy.data.objects[v] if k in ['target','pole'] else v) for k,v in c.items()} for name,c in control_names.items()}
        saved_errors=[];floors=[];grip_errors=[]
        for step in range(ticks*2+1):
            frame=1+step*.5;scene.frame_set(math.floor(frame),subframe=frame%1)
            error=max((arm.matrix_world@arm.pose.bones[c['end']].head-c['target'].matrix_world.translation).length for c in controls.values());saved_errors.append(error)
            if error>.008:raise ValueError(f'Saved {group} frame {frame} IK error {error}')
            grip=(bpy.data.objects['LichStaffSocket'].matrix_world.translation-arm.matrix_world@arm.pose.bones['LeftHand'].head).length;grip_errors.append(grip)
            if grip>1e-5:raise ValueError('Staff socket lost hand')
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
        report['clips'][group]={'frames':frames,'seconds':seconds,'loop':loop,'maximumReachAdjustment':max(reach_adjustments),'maximumIKError':max(errors),'savedSamples':len(saved_errors),'maximumSavedIKError':max(saved_errors),'maximumGripError':max(grip_errors),'minimumDeathZ':min(floors) if floors else None}
    report['checks']={'savedSamples':sum(c['savedSamples'] for c in report['clips'].values()),'maximumSavedIKError':max(c['maximumSavedIKError'] for c in report['clips'].values()),'maximumGripError':max(c['maximumGripError'] for c in report['clips'].values()),'minimumDeathZ':report['clips']['DEATH']['minimumDeathZ']}
    (args.out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');(args.out/'lich_study.py').write_bytes(Path(__file__).read_bytes())


if __name__=='__main__':main()
