#!/usr/bin/env python3
"""Author equipped Necropolis upgrades on the reviewed editable source clips.

Run in Blender. Reuses the source's motion, camera scale and skin weights, adds
bone-bound equipment, and exports original-count 2x bodies. roster_mod.py derives the 1x bodies.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skeleton_study as study
import render_sprites as render


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def textured(name, color, metallic=0, roughness=.7):
    mat = study.material(name, color, roughness, metallic)
    tree = mat.node_tree
    shader = tree.nodes.get('Principled BSDF')
    texture = tree.nodes.new('ShaderNodeTexNoise')
    texture.inputs['Scale'].default_value = 35
    texture.inputs['Detail'].default_value = 2
    coords = tree.nodes.new('ShaderNodeTexCoord')
    tree.links.new(coords.outputs['Generated'], texture.inputs['Vector'])
    ramp = tree.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = tuple(v*.65 for v in color)+(1,)
    ramp.color_ramp.elements[1].color = tuple(min(1,v*1.25) for v in color)+(1,)
    tree.links.new(texture.outputs['Fac'], ramp.inputs['Fac'])
    tree.links.new(ramp.outputs['Color'], shader.inputs['Base Color'])
    return mat


def attach(g, name, arm, bone, mat):
    obj = study.rigid_geometry(g, name, arm, bone, mat)
    obj.parent = arm.parent
    obj['equipment_bone'] = bone
    return obj


def dome(arm, z, height, mat, rim_mat):
    g = study.Geometry()
    rings, segments = 8, 32
    for row in range(rings+1):
        a = math.pi*.5*row/rings
        for i in range(segments):
            t = math.tau*i/segments
            g.vertices.append(Vector((.108*math.sin(a)*math.cos(t),
                                      .018+.10*math.sin(a)*math.sin(t), z+height*math.cos(a))))
    for row in range(rings):
        for i in range(segments):
            j=(i+1)%segments
            g.faces.append((row*segments+i,(row+1)*segments+i,(row+1)*segments+j,row*segments+j))
    attach(g, 'UpgradeHelmet', arm, 'Head', mat)
    g=study.Geometry()
    for i in range(32):
        a,b=math.tau*i/32,math.tau*(i+1)/32
        g.bone((.109*math.cos(a),.018+.101*math.sin(a),z),
               (.109*math.cos(b),.018+.101*math.sin(b),z),.008,8)
    attach(g,'HelmetRim',arm,'Head',rim_mat)


def skeleton_equipment(arm):
    iron=textured('Warrior blackened iron',(.075,.08,.082),.72,.4)
    edge=textured('Worn iron edges',(.23,.22,.18),.65,.45)
    wood=textured('Shield dark oak',(.17,.09,.035),0,.8)
    dome(arm,1.64,.13,iron,edge)
    g=study.Geometry();g.bone((0,.018,1.755),(0,.027,1.825),.012,12)
    g.bone((0,-.084,1.638),(0,-.089,1.568),.007,8)
    attach(g,'HelmetCrestAndNasal',arm,'Head',iron)
    g=study.Geometry();g.joint((0,.027,1.28),(.139,.08,.14))
    attach(g,'WarriorCuirass',arm,'Chest',iron)
    for side in ['Left','Right']:
        b=arm.data.bones[side+'Arm'];g=study.Geometry()
        g.joint(b.head_local+Vector((0,0,.01)),(.075,.07,.035))
        attach(g,side+'Pauldron',arm,side+'Arm',iron)
        b=arm.data.bones[side+'Leg'];g=study.Geometry()
        g.bone(b.head_local.lerp(b.tail_local,.45),b.head_local.lerp(b.tail_local,.95),.039,16)
        attach(g,side+'Greave',arm,side+'Leg',iron)
        bpy.data.objects[side+'FootGeometry'].data.materials.clear()
        bpy.data.objects[side+'FootGeometry'].data.materials.append(iron)
    # Rest-space attachment derived from the reviewed holding pose, shared by
    # every clip. Re-solving this per clip would make the shield jump at changes.
    center=arm.data.bones['LeftHand'].head_local+Vector((-.042964,.011723,-.034859))
    normal=Vector((-.598457,-.054162,-.799321)).normalized();u=normal.orthogonal().normalized();v=normal.cross(u)
    g=study.Geometry();segments=32
    for radius,depth in [(0,.035),(.075,.028),(.158,0)]:
        for i in range(segments):
            t=math.tau*i/segments
            g.vertices.append(center+u*(radius*math.cos(t))+v*(radius*math.sin(t))+normal*depth)
    for row in range(2):
        for i in range(segments):
            j=(i+1)%segments
            g.faces.append((row*segments+i,(row+1)*segments+i,(row+1)*segments+j,row*segments+j))
    attach(g,'RoundShield',arm,'LeftHand',wood)
    g=study.Geometry()
    for i in range(32):
        a,b=math.tau*i/32,math.tau*(i+1)/32
        g.bone(center+.16*(u*math.cos(a)+v*math.sin(a)),
               center+.16*(u*math.cos(b)+v*math.sin(b)),.011,8)
    g.joint(center+normal*.035,(.03,.03,.03))
    attach(g,'ShieldIronRim',arm,'LeftHand',edge)


def zombie_equipment(arm):
    leather=textured('Zombie worn jerkin',(.12,.063,.026),0,.85)
    trousers=textured('Zombie dark trousers',(.13,.075,.033),0,.95)
    boots=textured('Zombie boots',(.025,.022,.016),0,.9)
    iron=textured('Zombie iron helmet',(.11,.09,.058),.55,.55)
    edge=textured('Zombie helmet rim',(.22,.18,.105),.55,.5)
    body=bpy.data.objects['ZombieSkin']
    slots=[]
    for mat in [leather,trousers,boots]:
        slots.append(len(body.data.materials));body.data.materials.append(mat)
    for poly in body.data.polygons:
        center=sum((body.data.vertices[i].co for i in poly.vertices),Vector())/len(poly.vertices)
        if (.94<center.z<1.38 and abs(center.x)<.18) or (1.18<center.z<1.37 and abs(center.x)<.29):
            poly.material_index=slots[0]
        elif .36<center.z<.96:
            poly.material_index=slots[1]
        elif center.z<.25:
            poly.material_index=slots[2]
    dome(arm,1.65,.085,iron,edge)
    # Reinforce the jerkin over the spine without changing the skin weights.
    g=study.Geometry();g.bone((-.105,-.075,1.36),(.10,-.09,1.02),.024,12)
    attach(g,'ZombieHarness',arm,'Spine02',leather)
    blade=bpy.data.objects['CleaverBlade']
    for vert in blade.data.vertices:
        vert.co.x=-.075+(vert.co.x+.075)*1.25
        vert.co.y=.08+(vert.co.y-.08)*1.25


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--variant',choices=['skeleton-warrior','zombie'],required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--samples',type=int,default=24)
    parser.add_argument('--preview-only',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.out.exists():raise ValueError('Output must be new')
    args.out.mkdir(parents=True)
    profile=json.loads((args.source/'profile.json').read_text()) if (args.source/'profile.json').exists() else json.loads((args.source/'manifest.json').read_text())['profile']
    report={'variant':args.variant,'source':str(args.source),'sourceManifestSHA256':digest(args.source/'manifest.json'),
            'codeSHA256':digest(Path(__file__)),'previewOnly':args.preview_only,'clips':{}}
    (args.out/'upgrade_study.py').write_bytes(Path(__file__).read_bytes())
    for group,spec in profile['clips'].items():
        if args.preview_only and group!='HOLDING':continue
        source=args.source/(group.lower()+'.blend');bpy.ops.wm.open_mainfile(filepath=str(source))
        scene=bpy.context.scene;scene.frame_set(1)
        arm=next(o for o in scene.objects if o.type=='ARMATURE')
        (skeleton_equipment if args.variant=='skeleton-warrior' else zombie_equipment)(arm)
        scene.cycles.samples=args.samples;scene.cycles.use_animated_seed=False;scene.cycles.seed=0
        scene.render.threads_mode='FIXED';scene.render.threads=4
        scene.render.resolution_x=900;scene.render.resolution_y=800;scene.render.resolution_percentage=100
        # Preserve source camera scale/stride and register the shared canvas.
        scene.camera.data.shift_x+=50/900
        bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(args.out/(group.lower()+'.blend')))
        count=1 if args.preview_only else spec['sprite_frames'];ticks=round(spec['seconds']*profile['fps'])
        entries=[]
        for i in range(count):
            t=0 if args.preview_only else (.5 if count==1 else i/(count if spec['loop'] else count-1))
            frame=1+ticks*t;scene.frame_set(math.floor(frame),subframe=frame%1)
            folder=args.out/'sprites2x';folder.mkdir(exist_ok=True)
            path=folder/('%s_%02d.png'%(group.lower(),i));render.render_to(str(path))
            entries.append({'frame':frame,'file':str(path.relative_to(args.out)),'sha256':digest(path)})
        report['clips'][group]={'sourceBlendSHA256':digest(source),'frames':entries}
    (args.out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
