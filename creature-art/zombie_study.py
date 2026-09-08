#!/usr/bin/env python3
"""Thirteen editable zombie battle animations with a skin rig and cleaver.

Run with Blender --background --python zombie_study.py -- --model ... --out ...
Uses the existing textured skin, reconstructs anatomical rest bones from joint
heads, and replaces the weapon hand with a closed grip. No generation API calls.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys

import bpy
from mathutils import Matrix, Vector
sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_sprites as render
import skeleton_study as study
from skeleton_motion import linear_keys


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rebuild(source, old):
    """Preserve skin weights/UVs, replace unusable imported bone tails.

    Imported head positions are in metres after object scaling, but tails extend
    tens of metres. IK must use anatomical chains. Rest skin is unchanged by
    assigning the original vertex groups to a new rest armature.
    """
    heads = {b.name: old.matrix_world @ b.head_local for b in old.data.bones}
    next_joint = {'Hips':'Spine02','Spine02':'Spine01','Spine01':'Spine',
                  'Spine':'neck','neck':'Head','Head':'head_end'}
    for side in ['Left','Right']:
        for a,b in [('Shoulder','Arm'),('Arm','ForeArm'),('ForeArm','Hand'),
                    ('UpLeg','Leg'),('Leg','Foot'),('Foot','ToeBase')]:
            next_joint[side+a] = side+b
    landmarks = {}
    for b in old.data.bones:
        head = heads[b.name]
        tail = heads[next_joint[b.name]] if b.name in next_joint else head + Vector(
            (0,-.018,-.12) if b.name.endswith('Hand') else (0,-.09,0))
        landmarks[b.name] = {'head':list(head),'tail':list(tail),
                             'parent':b.parent.name if b.parent else None}
    arm = study.make_rig(landmarks)
    arm.name = 'ZombieStudy'
    arm.data.name = 'ZombieStudy'
    # Cut only the distal right hand; the left keeps its textured open fingers.
    wrist = heads['RightHand']
    removed = {v.index for v in source.data.vertices
               if (source.matrix_world @ v.co).x < -.27
               and (source.matrix_world @ v.co).z < wrist.z-.014}
    keep = lambda p: not any(i in removed for i in p.vertices)
    indices = sorted({i for p in source.data.polygons if keep(p) for i in p.vertices})
    body = study.mesh_from_faces(source, keep, 'ZombieSkin')
    for g in source.vertex_groups:
        body.vertex_groups.new(name=g.name)
    for new,old_index in enumerate(indices):
        for g in source.data.vertices[old_index].groups:
            body.vertex_groups[g.group].add([new],g.weight,'REPLACE')
    mod = body.modifiers.new('ZombieSkin','ARMATURE')
    mod.object = arm
    mod.use_deform_preserve_volume = True
    audit = {'source_vertices':len(source.data.vertices),'retained_vertices':len(indices),
             'original_max_bone_length':max((old.matrix_world.to_3x3() @ (b.tail_local-b.head_local)).length for b in old.data.bones),
             'new_max_bone_length':max(b.length for b in arm.data.bones),
             'landmarks':landmarks}
    bpy.data.objects.remove(source,do_unlink=True)
    bpy.data.objects.remove(old,do_unlink=True)
    return arm,body,audit


def make_grip(arm):
    skin = study.material('Grip skin',(.19,.21,.14),.9)
    g = study.Geometry()
    g.joint((0,.042,0),(.044,.055,.028))
    for x in [-.029,-.010,.010,.029]:
        points = [(x,.065,0),(x,.105,-.009),(x,.122,.022),(x,.099,.049)]
        for a,b in zip(points,points[1:]):
            g.bone(a,b,.011)
        g.joint(points[1],(.012,.013,.012))
    for a,b in zip([(-.036,.025,0),(-.055,.064,.025),(-.027,.093,.044)],
                   [(-.055,.064,.025),(-.027,.093,.044),(-.005,.099,.042)]):
        g.bone(a,b,.014)
    hand = g.object('RightGrip',skin,arm.data.bones['RightHand'].matrix_local)
    hand.vertex_groups.new(name='RightHand').add(list(range(len(hand.data.vertices))),1,'REPLACE')
    hand.modifiers.new('ZombieStudy','ARMATURE').object=arm
    socket = study.empty('CleaverSocket',(0,0,0))
    c = socket.constraints.new('COPY_TRANSFORMS'); c.target=arm; c.subtarget='RightHand'
    wood = study.material('Cleaver handle',(.045,.022,.009),.9)
    iron = study.material('Cleaver iron',(.17,.18,.16),.6,.55)
    g=study.Geometry(); g.bone((.053,.102,.025),(-.085,.102,.025),.017,12)
    grip=g.object('CleaverHandle',wood); grip.parent=socket
    # Broad short blade, bevelled tip; all geometry lives in the hand socket.
    outline=[(-.075,.079),(-.35,.068),(-.40,.092),(-.365,.183),(-.11,.17)]
    verts=[(x,y,z) for z in [.013,.037] for x,y in outline]
    n=len(outline); faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    mesh=bpy.data.meshes.new('CleaverBlade');mesh.from_pydata(verts,[],faces);mesh.materials.append(iron)
    blade=bpy.data.objects.new('CleaverBlade',mesh);bpy.context.collection.objects.link(blade);blade.parent=socket
    bevel=blade.modifiers.new('Worn edge','BEVEL');bevel.width=.003;bevel.segments=2
    return hand,socket,blade


def merge(base,changes):
    result=copy.deepcopy(base)
    for k,v in changes.items():
        result[k]=merge(result[k],v) if isinstance(v,dict) else copy.deepcopy(v)
    return result


def mix(a,b,t):
    if isinstance(a,dict): return {k:mix(v,b[k],t) for k,v in a.items()}
    if isinstance(a,list): return [mix(x,y,t) for x,y in zip(a,b)]
    return a+(b-a)*t


def pose(profile,group,t):
    p=copy.deepcopy(profile['stance'])
    if group=='HOLDING':
        p['lean'] += .8*math.sin(math.tau*t)
        p['head_tilt'] += 1.5*math.sin(math.tau*t)
    elif group=='MOVING':
        w=profile['walk'];p['hips'][2]-=w['hip_bob']*(1-math.cos(math.tau*t))
        p['lean']+=2*math.sin(math.tau*t)
        for side,offset in [('Right',0),('Left',.5)]:
            phase=(t+offset)%1;d=w['stance_fraction'];stride=w['stride']
            if phase<d: travel=stride*(.5-phase/d);lift=0
            else:
                u=(phase-d)/(1-d)
                tangent=-stride/d*(1-d)
                travel=(2*u**3-3*u**2+1)*(-stride/2)+(u**3-2*u**2+u)*tangent+(-2*u**3+3*u**2)*(stride/2)+(u**3-u**2)*tangent
                lift=w[side.lower()+'_lift']*math.sin(math.pi*u)**2
            p[side+'Leg']['target'][1]-=travel
            p[side+'Leg']['target'][2]+=lift
            p[side+'Arm']['target'][1]+=w['arm_swing']*math.cos(math.tau*(t+offset))
            p[side+'Arm']['pole'][1]+=.5*w['arm_swing']*math.cos(math.tau*(t+offset))
        p['blade_elevation']+=5*math.cos(math.tau*t)
    elif group in ['MOVE_START','MOVE_END']:
        u=t*t*(3-2*t)
        start,end=(profile['stance'],pose(profile,'MOVING',0))
        if group=='MOVE_END':start,end=end,start
        p=mix(start,end,u)
    elif group in ['TURN_L','TURN_R']:
        u=t*t*(3-2*t)
        p['root_yaw']=-65*(u if group=='TURN_L' else 1-u)
    elif group=='ATTACK_FRONT' or group in profile['action_keys']:
        keys=profile['attack_keys'] if group=='ATTACK_FRONT' else profile['action_keys'][group]
        for (ta,a),(tb,b) in zip(keys,keys[1:]):
            if ta<=t<=tb:
                u=(t-ta)/(tb-ta);u=u*u*(3-2*u)
                p=mix(merge(p,a),merge(p,b),u);break
    return p


def apply(arm,controls,p):
    root=bpy.data.objects.get('ZombieRoot')
    if root:
        root.matrix_world=Matrix.Identity(4)
        bpy.context.view_layer.update()
    for b in arm.pose.bones:b.matrix_basis=Matrix.Identity(4)
    hips=arm.pose.bones['Hips'];hips.matrix=Matrix.Translation(Vector(p['hips'])) @ arm.data.bones['Hips'].matrix_local.to_3x3().to_4x4()
    bpy.context.view_layer.update()
    rest=arm.data.bones['Spine02'].matrix_local.to_3x3()
    study.orient_bone(arm,'Spine02',Matrix.Rotation(math.radians(p['lean']),3,'X') @ rest)
    head=arm.pose.bones['Head']
    study.orient_bone(arm,'Head',Matrix.Rotation(math.radians(p['head_tilt']),3,'Y') @ head.matrix.to_3x3())
    for name,c in controls.items():
        c['target'].location=p[name]['target'];c['pole'].location=p[name]['pole']
        c['target'].rotation_mode='QUATERNION'
        c['target'].rotation_quaternion=arm.data.bones[c['end']].matrix_local.to_quaternion()
    bpy.context.view_layer.update()
    for side in ['Right','Left']:
        forearm=arm.pose.bones[side+'ForeArm']
        if side=='Right':
            a=math.radians(p['blade_elevation']);x=-Vector((0,-math.cos(a),math.sin(a)))
            along=(forearm.tail-forearm.head).normalized();y=(along-x*along.dot(x)).normalized();z=x.cross(y).normalized()
            rotation=Matrix((x,y,z)).transposed().to_quaternion()
        else: rotation=forearm.matrix.to_quaternion()
        controls[side+'Arm']['target'].rotation_quaternion=rotation
    bpy.context.view_layer.update()
    if root:
        root.rotation_euler=(math.radians(p['root_pitch']),0,math.radians(p['root_yaw']))
        pivot=Vector(p['hips'])
        root.location=pivot-root.rotation_euler.to_matrix() @ pivot
        bpy.context.view_layer.update()
        if p['floor_support']:
            vertices=render.world_vertices([o for o in bpy.context.scene.objects if o.type=='MESH'],bpy.context.evaluated_depsgraph_get())
            root.location.z+=(.003-min(v.z for v in vertices))*p['floor_support']
            bpy.context.view_layer.update()


def key(arm,controls,frame,previous):
    root=bpy.data.objects['ZombieRoot']
    root.keyframe_insert('location',frame=frame)
    root.keyframe_insert('rotation_euler',frame=frame)
    objects=[c[k] for c in controls.values() for k in ['target','pole']]
    for b in arm.pose.bones:
        b.rotation_mode='QUATERNION'
        b.keyframe_insert('location',frame=frame)
        q=b.rotation_quaternion.copy()
        if b.name in previous and q.dot(previous[b.name])<0:q.negate()
        b.rotation_quaternion=q;previous[b.name]=q.copy()
        b.keyframe_insert('rotation_quaternion',frame=frame)
    for obj in objects:
        obj.keyframe_insert('location',frame=frame)
        if obj.rotation_mode=='QUATERNION':
            q=obj.rotation_quaternion.copy()
            if obj.name in previous and q.dot(previous[obj.name])<0:q.negate()
            obj.rotation_quaternion=q;previous[obj.name]=q.copy()
            obj.keyframe_insert('rotation_quaternion',frame=frame)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--profile',type=Path,default=Path(__file__).with_name('profiles')/'zombie-study.json')
    ap.add_argument('--samples',type=int,default=24);ap.add_argument('--no-render',action='store_true')
    args=ap.parse_args(sys.argv[sys.argv.index('--')+1:]);p=json.loads(args.profile.read_text())
    if digest(args.model)!=p['source_sha256']:raise ValueError('Source hash differs from profile')
    if args.out.exists() and any(args.out.iterdir()):raise ValueError('Output must be empty')
    args.out.mkdir(parents=True,exist_ok=True);(args.out/'code').mkdir()
    hashes={}
    for name in ['zombie_study.py','skeleton_study.py','skeleton_motion.py','skeleton_geometry.py','render_sprites.py','poses.py','vcmi_anim.py','test_zombie_study.py','motion_preview.py']:
        path=Path(__file__).with_name(name);shutil.copy2(path,args.out/'code'/name);hashes[name]=digest(path)
    shutil.copy2(args.profile,args.out/'profile.json')
    cam=p['camera'];meshes,camera,_=render.build_scene(str(args.model),(900,800),cam['elevation'],cam['azimuth'],cam['ground']*2,cam['height']*2,args.samples)
    old=render.find_armature();old.animation_data_clear()
    source=max(meshes,key=lambda o:len(o.data.vertices))
    for o in list(bpy.data.objects):
        if o.type=='MESH' and o!=source:bpy.data.objects.remove(o,do_unlink=True)
    arm,body,audit=rebuild(source,old);hand,socket,blade=make_grip(arm)
    controls={side+limb:study.make_ik(arm,side,'arm' if limb=='Arm' else 'leg') for side in ['Right','Left'] for limb in ['Arm','Leg']}
    root=study.empty('ZombieRoot',(0,0,0))
    for obj in list(bpy.context.scene.objects):
        if obj!=root and obj.type not in ['CAMERA','LIGHT'] and obj.parent is None:obj.parent=root
    apply(arm,controls,pose(p,'HOLDING',0))
    scene=bpy.context.scene;scene.render.fps=p['fps']
    if not args.no_render:render.calibrate_camera(camera,(900,800),cam['ground']*2,cam['height']*2,str(args.out/'calibration.png'))
    bpy.ops.file.pack_all()
    manifest={'profile':p,'profile_sha256':digest(args.profile),'source_sha256':digest(args.model),'scripts':hashes,'audit':audit,'clips':{},'body_only':True,'blender':bpy.app.version_string,'samples':args.samples}
    for group,spec in p['clips'].items():
        for o in [arm,root]+[c[k] for c in controls.values() for k in ['target','pole']]:o.animation_data_clear()
        ticks=round(spec['seconds']*p['fps']);previous={}
        for tick in range(ticks+1):
            apply(arm,controls,pose(p,group,tick/ticks));key(arm,controls,tick+1,previous)
        for o in [arm,root]+[c[k] for c in controls.values() for k in ['target','pole']]:linear_keys(o.animation_data.action)
        scene.frame_start=1;scene.frame_end=ticks if spec['loop'] else ticks+1;scene.frame_set(1)
        bpy.ops.wm.save_as_mainfile(filepath=str(args.out/(group.lower()+'.blend')))
        manifest['clips'][group]={'ticks':ticks,'blend':group.lower()+'.blend'}
        if not args.no_render:
            folder=args.out/'review'/group.lower();folder.mkdir(parents=True)
            for i in range(scene.frame_end):
                scene.frame_set(i+1);render.render_to(str(folder/('%03d.png'%i)))
            n=spec['sprite_frames']
            for scale in [1,2]:
                folder=args.out/('sprites%dx'%scale);folder.mkdir(exist_ok=True)
                scene.render.resolution_percentage=50*scale
                for i in range(n):
                    f=1+ticks*(.5 if n==1 else i/(n if spec['loop'] else n-1))
                    scene.frame_set(int(f),subframe=f-int(f));render.render_to(str(folder/('%s_%02d.png'%(group.lower(),i))))
            scene.render.resolution_percentage=100
    (args.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':main()
