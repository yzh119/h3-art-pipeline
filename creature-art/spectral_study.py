#!/usr/bin/env python3
"""REJECTED appearance prototype: procedural hooded ghosts and armoured liches.

Retained to reproduce failed design experiments; do not install these exports.
Run in Blender. Reuses the reviewed skeletal anatomy, authors distinct motion,
cloth and equipment, and exports every native group at its original frame count.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
import skeleton_study as study
import skeleton_motion as motionlib
import render_sprites as render
from upgrade_study import textured,attach
from settle_equipment import lowest
from vcmi_anim import GROUP_NAMES


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def weighted_surface(name,vertices,faces,weights,arm,material):
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.materials.append(material)
    for face in mesh.polygons:face.use_smooth=True
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj);obj.parent=arm.parent
    groups={name:obj.vertex_groups.new(name=name) for name in {k for row in weights for k in row}}
    for i,row in enumerate(weights):
        for bone,value in row.items():groups[bone].add([i],value,'REPLACE')
    obj.modifiers.new('Deform with skeleton','ARMATURE').object=arm
    return obj


def garment(arm,material,ghost):
    vertices=[];faces=[];weights=[];rows=20;segments=40
    for row in range(rows):
        t=row/(rows-1);z=(.13+1.26*t) if ghost else (.26+.82*t)
        radius=(.065+.19*math.sin(math.pi*t*.8)) if ghost else (.21-.05*t)
        for i in range(segments):
            a=math.tau*i/segments;fold=.012*math.cos(10*a)+.006*math.cos(17*a)
            hem=(.07*math.sin(7*a)+.05*math.sin(11*a))*(1-t)**5 if ghost else 0
            vertices.append(((radius+fold)*math.cos(a),.025+(radius*.76+fold)*math.sin(a),z+hem))
            upper=max(0,min(1,(z-1.02)/.27)) if ghost else 0
            weights.append({'Chest':upper,'Hips':1-upper})
    for row in range(rows-1):
        for i in range(segments):
            j=(i+1)%segments;faces.append((row*segments+i,row*segments+j,(row+1)*segments+j,(row+1)*segments+i))
    obj=weighted_surface('RaggedRobe' if ghost else 'ChainmailSkirt',vertices,faces,weights,arm,material)
    obj.shape_key_add(name='Basis');trail=obj.shape_key_add(name='Trail');collapse=obj.shape_key_add(name='Collapse');lunge=obj.shape_key_add(name='Lunge')
    for i,v in enumerate(vertices):
        x,y,z=v;tail=max(0,1-z/1.35)**2
        trail.data[i].co.y+=.36*tail;trail.data[i].co.z+=.15*tail
        collapse.data[i].co=(x*1.25,y*1.3,.82+.045*math.cos(i*.7))
        angle=math.radians(72)
        lunge.data[i].co=(x,.025+(y-.025)*math.cos(angle)-(z-1.35)*math.sin(angle),1.35+(y-.025)*math.sin(angle)+(z-1.35)*math.cos(angle))
    trail.value=0;collapse.value=0;lunge.value=0
    solid=obj.modifiers.new('Cloth thickness','SOLIDIFY');solid.thickness=.006
    return obj


def hood(arm,material):
    g=study.Geometry();rows=20;segments=40
    for row in range(rows+1):
        p=math.pi*row/rows
        for i in range(segments):
            a=math.tau*i/segments
            g.vertices.append(Vector((.14*math.sin(p)*math.cos(a),.025+.15*math.sin(p)*math.sin(a),1.59+.20*math.cos(p)+.045*max(0,math.cos(p))**4)))
    for row in range(rows):
        for i in range(segments):
            j=(i+1)%segments;face=(row*segments+i,(row+1)*segments+i,(row+1)*segments+j,row*segments+j)
            c=sum((g.vertices[k] for k in face),Vector())/4
            if c.y<.015 and (c.x/.145)**2+((c.z-1.58)/.175)**2<1.15:continue
            g.faces.append(face)
    obj=attach(g,'SpectralHood',arm,'Head',material)
    obj.modifiers.new('Hood thickness','SOLIDIFY').thickness=.009
    # Draped shoulder cowl covers the neck seam; front edges leave the jaw visible.
    g=study.Geometry()
    for row in range(10):
        t=row/9
        for i in range(40):
            a=math.tau*i/40;r=.125+.13*t
            g.vertices.append(Vector((r*math.cos(a),.025+r*.7*math.sin(a),1.51-.20*t+.008*math.cos(9*a))))
    for row in range(9):
        for i in range(40):
            j=(i+1)%40
            g.faces.append((row*40+i,(row+1)*40+i,(row+1)*40+j,row*40+j))
    obj=attach(g,'ShoulderCowl',arm,'Chest',material)
    obj.modifiers.new('Cowl thickness','SOLIDIFY').thickness=.008


def sleeves(arm,material):
    for side in ['Left','Right']:
        for part,start_radius,end_radius in [('Arm',.095,.10),('ForeArm',.10,.045)]:
            b=arm.data.bones[side+part];a,bend=b.head_local,b.tail_local;axis=(bend-a).normalized()
            u=axis.orthogonal().normalized();v=axis.cross(u);g=study.Geometry();segments=24
            for row in range(8):
                t=row/7;center=a.lerp(bend,t);radius=start_radius*(1-t)+end_radius*t
                for i in range(segments):
                    theta=math.tau*i/segments;r=radius*(1+.09*math.cos(7*theta))
                    g.vertices.append(center+u*r*math.cos(theta)+v*r*math.sin(theta))
            for row in range(7):
                for i in range(segments):
                    j=(i+1)%segments;g.faces.append((row*segments+i,row*segments+j,(row+1)*segments+j,(row+1)*segments+i))
            attach(g,side+part+'Sleeve',arm,side+part,material)


def lich_equipment(arm,power):
    steel=textured('Lich chainmail',(.21,.235,.255),.78,.5)
    gold=textured('Lich gold trim',(.42,.255,.065),.7,.4)
    dark=textured('Lich dark metal',(.075,.075,.085),.6,.5)
    robe=garment(arm,steel,False)
    g=study.Geometry();g.joint((0,.03,1.29),(.147,.083,.13));attach(g,'LichBreastplate',arm,'Chest',dark)
    for side,sign in [('Left',1),('Right',-1)]:
        g=study.Geometry();g.joint(arm.data.bones[side+'Arm'].head_local,(.087,.078,.036));attach(g,side+'LichPauldron',arm,side+'Arm',gold)
        g=study.Geometry();g.bone((sign*.125,-.054,1.37),(sign*.11,-.072,1.15),.013,10);attach(g,side+'ChestTrim',arm,'Chest',gold)
    g=study.Geometry();segments=32;lo=1.64;hi=1.85 if not power else 1.99
    for z,r in [(lo,.10),(hi-.03,.098),(hi,.095)]:
        for i in range(segments):
            a=math.tau*i/segments;g.vertices.append(Vector((r*math.cos(a),.02+r*math.sin(a),z)))
    for row in range(2):
        for i in range(segments):
            j=(i+1)%segments;g.faces.append((row*segments+i,row*segments+j,(row+1)*segments+j,(row+1)*segments+i))
    g.faces.append(tuple(2*segments+i for i in range(segments)))
    attach(g,'LichHeaddress',arm,'Head',gold if power else steel)
    g=study.Geometry()
    for z in [lo,hi]:
        for i in range(32):
            a,b=math.tau*i/32,math.tau*(i+1)/32
            g.bone((.102*math.cos(a),.02+.102*math.sin(a),z),(.102*math.cos(b),.02+.102*math.sin(b),z),.012,8)
    if power:
        for sign in [-1,1]:
            g.bone((sign*.105,.02,1.77),(sign*.16,.02,1.99),.016,10)
            g.joint((sign*.16,.02,2.01),(.031,.031,.035))
    attach(g,'HeaddressTrim',arm,'Head',gold)
    eye=study.material('Lich red eyes',(.7,.018,.005),.5)
    shader=eye.node_tree.nodes.get('Principled BSDF');shader.inputs['Emission Color'].default_value=(1,.01,0,1);shader.inputs['Emission Strength'].default_value=1
    g=study.Geometry()
    for x in [-.036,.036]:g.joint((x,-.083,1.64),(.011,.011,.009))
    attach(g,'LichEyes',arm,'Head',eye)
    socket=bpy.data.objects['WeaponGrip'];g=study.Geometry()
    # Right-hand local -X is the requested blade direction; grip offset matches
    # the reviewed hand mesh. Both ends stay rigidly attached through the socket.
    end=-1.02 if power else -.86
    g.bone((.9,.099,.018),(end,.099,.018),.013,16)
    staff=g.object('LichStaff',dark);staff.parent=socket
    g=study.Geometry()
    for x in [.88,end]:g.joint((x,.099,.018),(.025,.027,.027))
    if power:
        for i in range(32):
            a,b=math.tau*i/32,math.tau*(i+1)/32
            g.bone((end-.10+.10*math.cos(a),.099+.10*math.sin(a),.018),
                   (end-.10+.10*math.cos(b),.099+.10*math.sin(b),.018),.014,8)
    trim=g.object('StaffGold',gold);trim.parent=socket
    return robe


def configure(args):
    bpy.ops.wm.open_mainfile(filepath=str(args.source/'holding.blend'));scene=bpy.context.scene;scene.frame_set(1)
    for obj in scene.objects:obj.animation_data_clear()
    arm=bpy.data.objects['SkeletonStudy'];root=bpy.data.objects['MotionRoot'];root.location=(0,0,0);root.rotation_euler=(0,0,0)
    controls={side+limb:{'target':bpy.data.objects[side+('Hand' if limb=='Arm' else 'Foot')+'Target'],'pole':bpy.data.objects[side+('ForeArm' if limb=='Arm' else 'Leg')+'Pole'],
              'end':side+('Hand' if limb=='Arm' else 'Foot')} for side in ['Left','Right'] for limb in ['Arm','Leg']}
    for name in ['SwordGrip','SwordGuard','SwordBlade']:bpy.data.objects.remove(bpy.data.objects[name],do_unlink=True)
    ghost=args.variant in ['wight','wraith']
    if ghost:
        arm['weapon_hand']='None'
        for side in ['Left','Right']:
            for part in ['UpLeg','Leg','Foot']:bpy.data.objects.remove(bpy.data.objects[side+part+'Geometry'],do_unlink=True)
        old=bpy.data.objects['RightHandGeometry'];bpy.data.objects.remove(old,do_unlink=True)
        mat=study.material('Ghost hand bone',(.46,.43,.32));hand=study.make_hand(arm,'Right',False,mat);hand.parent=root
        cloth=textured('Ghost cloth',(.105,.068,.034) if args.variant=='wight' else (.027,.025,.022),0,.95)
        robe=garment(arm,cloth,True);hood(arm,cloth);sleeves(arm,cloth)
    else:robe=lich_equipment(arm,args.variant=='power-lich')
    return scene,arm,root,controls,robe


def pose(profile,walk,group,t,ghost):
    base=copy.deepcopy(profile['poses']['holding'])
    pulse=math.sin(math.pi*t)**2
    if group=='MOVING' and not ghost:base=walk.pose('MOVING',t)
    elif group in ['MOVE_START','MOVE_END']:
        a=pose(profile,walk,'HOLDING',0,ghost);b=pose(profile,walk,'MOVING',0,ghost)
        return motionlib.mix(a,b,motionlib.smooth(t if group=='MOVE_START' else 1-t))
    base.pop('weapon_quaternion',None);base.pop('floor_support',None)
    base['hips'][2]=(.99+.012*math.sin(math.tau*t)) if ghost else (.90 if group=='MOVING' else .96)
    base['lean']=8+(2*math.sin(math.tau*t) if group=='HOLDING' else 0);base['neck']=0
    base['blade_direction']=[0,0,1]
    for side,sign in [('Left',1),('Right',-1)]:
        base[side+'Arm']['target']=[sign*.18,-.21,1.13 if ghost else 1.04]
        base[side+'Arm']['pole']=[sign*.43,.04,1.22]
    if group=='MOVING' and ghost:
        base['hips'][2]+=.025*math.sin(math.tau*t);base['lean']=13
    if group=='MOUSEON':
        base['neck']=-8*pulse;base['LeftArm']['target'][2]+=.14*pulse
    if group in ['HITTED','DEFENCE']:
        base['lean']-=18*pulse;base['hips'][1]+=.045*pulse
        for side in ['Left','Right']:base[side+'Arm']['target'][2]+=.17*pulse
    if group.startswith(('ATTACK','SHOOT','CAST')):
        height=.20 if group.endswith('UP') else (-.19 if group.endswith('DOWN') else 0)
        base['lean']+=(57 if ghost else 18)*pulse;base['hips'][1]-=(.16 if ghost else .06)*pulse
        base['RightArm']['target']=[-.18,-.21-(.54 if ghost else .34)*pulse,1.13+height*pulse]
        base['LeftArm']['target']=[.18,-.21-(.44 if ghost else .24)*pulse,1.13+height*pulse]
        if not ghost:
            angle=math.radians((62 if group.startswith('ATTACK') else 40)*pulse)
            base['blade_direction']=[0,-math.sin(angle),math.cos(angle)]
    if group=='TURN_L':base['root_yaw']=90*motionlib.smooth(t)
    if group=='TURN_R':base['root_yaw']=-90*(1-motionlib.smooth(t))
    if group=='DEATH':
        fall=motionlib.smooth(t)
        base['hips']=[0,.05,(.99 if ghost else .96)-.88*fall];base['lean']=8+77*fall;base['neck']=-20*fall
        for side,sign in [('Left',1),('Right',-1)]:base[side+'Arm']['target']=[sign*(.18+.12*fall),-.21+.08*fall,1.13-.95*fall]
        base['blade_direction']=[0,-math.sin(math.pi*.5*fall),math.cos(math.pi*.5*fall)]
    return base


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--variant',choices=['wight','wraith','lich','power-lich'],required=True)
    p.add_argument('--references',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--samples',type=int,default=24);p.add_argument('--preview-only',action='store_true');p.add_argument('--groups',default='HOLDING,MOVING,ATTACK_FRONT,DEATH')
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.out.exists():raise ValueError('Output must be new')
    args.out.mkdir(parents=True)
    names={'wight':'wight','wraith':'wraith','lich':'lich','power-lich':'powerLich'}
    ref=next(x for x in json.loads(args.references.read_text()) if x['name']==names[args.variant])
    profile=json.loads((args.source/'manifest.json').read_text())['profile']
    scene,arm,root,controls,robe=configure(args);ghost=args.variant in ['wight','wraith']
    direction=scene.camera.rotation_euler.to_matrix().col[0].copy();direction.z=0;direction.normalize()
    walk=motionlib.Motion(profile,{'Left':.07,'Right':.07},direction,1)
    scene.cycles.samples=args.samples;scene.cycles.use_animated_seed=False;scene.cycles.seed=0
    scene.render.threads_mode='FIXED';scene.render.threads=4;scene.render.resolution_x=900;scene.render.resolution_y=800;scene.render.resolution_percentage=100
    for key in robe.data.shape_keys.key_blocks:key.value=0
    bpy.context.view_layer.update()
    motionlib.apply_pose(arm,controls,pose(profile,walk,'HOLDING',0,ghost))
    render.calibrate_camera(scene.camera,(900,800),ref['bbox'][3]*2,(ref['bbox'][3]-ref['bbox'][1])*2,str(args.out/'calibration.png'))
    scene.camera.data.shift_x+=50/900
    walk.stride=70.4*scene.camera.data.ortho_scale/450
    scene.render.fps=30;bpy.ops.file.pack_all()
    report={'artisticallyRejected':True,'variant':args.variant,'nativeReference':ref,'sourceManifestSHA256':digest(args.source/'manifest.json'),
            'scripts':{name:digest(Path(__file__).with_name(name)) for name in ['spectral_study.py','skeleton_study.py','skeleton_motion.py','upgrade_study.py','settle_equipment.py']},'previewOnly':args.preview_only,'clips':{}}
    for gid_text,n in ref['groups'].items():
        gid=int(gid_text)
        if gid not in GROUP_NAMES:continue
        group=GROUP_NAMES[gid]
        if args.preview_only and group not in args.groups.split(','):continue
        loop=group in ['HOLDING','MOVING'];seconds=2 if group=='HOLDING' else (1.5 if group=='DEATH' else (.3 if group in ['TURN_L','TURN_R','MOVE_START','MOVE_END'] else 1))
        ticks=round(seconds*30)
        for obj in scene.objects:obj.animation_data_clear()
        robe.data.shape_keys.animation_data_clear();previous={};samples=[]
        for tick in range(ticks+1):
            t=tick/ticks;scene.frame_set(tick+1)
            trail=(.6+.2*math.sin(math.tau*t)) if group=='MOVING' else (.6*motionlib.smooth(t if group=='MOVE_START' else 1-t) if group in ['MOVE_START','MOVE_END'] else 0)
            robe.data.shape_keys.key_blocks['Trail'].value=trail if ghost else 0
            robe.data.shape_keys.key_blocks['Collapse'].value=motionlib.smooth(t) if group=='DEATH' else 0
            robe.data.shape_keys.key_blocks['Lunge'].value=math.sin(math.pi*t)**2 if ghost and group.startswith(('ATTACK','SHOOT','CAST')) else 0
            motionlib.apply_pose(arm,controls,pose(profile,walk,group,t,ghost))
            if group=='DEATH':
                if ghost:
                    fall=motionlib.smooth(t);root.scale=(1+.2*fall,1+.2*fall,1-.65*fall);bpy.context.view_layer.update()
                root.location.z+=max(0,.003-lowest());bpy.context.view_layer.update()
            motionlib.key_pose(arm,controls,tick+1,previous)
            root.keyframe_insert('scale',frame=tick+1)
            for key in robe.data.shape_keys.key_blocks:
                if key.name!='Basis':key.keyframe_insert('value',frame=tick+1)
            errors={side:(arm.matrix_world@arm.pose.bones[side+'Hand'].head-controls[side+'Arm']['target'].matrix_world.translation).length for side in ['Left','Right']}
            samples.append({'frame':tick+1,'armTargetErrors':errors})
        for obj in scene.objects:
            if obj.animation_data and obj.animation_data.action:motionlib.linear_keys(obj.animation_data.action)
        motionlib.linear_keys(robe.data.shape_keys.animation_data.action)
        scene.frame_start=1;scene.frame_end=ticks if loop else ticks+1;scene.frame_set(1)
        bpy.ops.wm.save_as_mainfile(filepath=str(args.out/(group.lower()+'.blend')))
        # Reopen the saved result, then sample half frames to catch serialization
        # and interpolation failures rather than only the authored key poses.
        bpy.ops.wm.open_mainfile(filepath=str(args.out/(group.lower()+'.blend')))
        scene=bpy.context.scene;arm=bpy.data.objects['SkeletonStudy'];root=bpy.data.objects['MotionRoot']
        controls={side+limb:{'target':bpy.data.objects[side+('Hand' if limb=='Arm' else 'Foot')+'Target'],'pole':bpy.data.objects[side+('ForeArm' if limb=='Arm' else 'Leg')+'Pole'],'end':side+('Hand' if limb=='Arm' else 'Foot')} for side in ['Left','Right'] for limb in ['Arm','Leg']}
        robe=bpy.data.objects['RaggedRobe' if ghost else 'ChainmailSkirt']
        saved=[]
        for step in range(2*ticks+1):
            frame=1+step/2;scene.frame_set(math.floor(frame),subframe=frame%1)
            error=max((arm.matrix_world@arm.pose.bones[side+'Hand'].head-controls[side+'Arm']['target'].matrix_world.translation).length for side in ['Left','Right'])
            floor=lowest() if group=='DEATH' else None
            if error>.002:raise ValueError(f'{group} frame {frame}: hand IK error {error}')
            if floor is not None and floor<-.002:raise ValueError(f'{group} frame {frame}: floor penetration {floor}')
            saved.append({'frame':frame,'maximumArmError':error,'minimumZ':floor})
        frames=[];count=(1 if group=='HOLDING' else 3) if args.preview_only else n
        for i in range(count):
            t=(0 if group=='HOLDING' else .5) if count==1 else i/(count if loop else count-1);f=1+ticks*t
            scene.frame_set(math.floor(f),subframe=f%1);folder=args.out/'sprites2x';folder.mkdir(exist_ok=True)
            path=folder/(group.lower()+'_%02d.png'%i);render.render_to(str(path));frames.append({'frame':f,'file':str(path.relative_to(args.out)),'sha256':digest(path)})
        report['clips'][group]={'frames':frames,'samples':samples,'savedSamples':saved,'seconds':seconds,'loop':loop}
    report['checks']={'savedSamples':sum(len(c['savedSamples']) for c in report['clips'].values()),'maximumArmError':max(s['maximumArmError'] for c in report['clips'].values() for s in c['savedSamples']),'minimumDeathZ':min((s['minimumZ'] for c in report['clips'].values() for s in c['savedSamples'] if s['minimumZ'] is not None),default=None)}
    (args.out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    for name in report['scripts']:(args.out/name).write_bytes(Path(__file__).with_name(name).read_bytes())


if __name__=='__main__':main()
