#!/usr/bin/env python3
"""Combine reviewed humanoid and bat scenes for native flight/transform studies."""
import argparse,hashlib,json,math,random,sys
from pathlib import Path
import bpy
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
import render_sprites as render
from skeleton_motion import linear_keys,smooth


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--human',type=Path,required=True);p.add_argument('--bat',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.out.exists():raise ValueError('Use fresh output directory')
    args.out.mkdir(parents=True);report={'previewOnly':True,'sourceHashes':{str(p.name):hashlib.sha256(p.read_bytes()).hexdigest() for p in (args.human,args.bat)},'clips':{}}
    for group in ('MOVING','MOVE_START','MOVE_END'):
        bpy.ops.wm.open_mainfile(filepath=str(args.human));scene=bpy.context.scene;scene.frame_set(1)
        humans=[o for o in scene.objects if o.type=='MESH'];root=bpy.data.objects['ZombieRoot']
        for o in scene.objects:o.animation_data_clear()
        with bpy.data.libraries.load(str(args.bat),link=False) as (source,target):target.objects=source.objects
        bat=[]
        for o in target.objects:
            if o and o.type in ('MESH','ARMATURE'):scene.collection.objects.link(o);bat.append(o)
        batroot=bpy.data.objects.new('BatFlightRoot',None);scene.collection.objects.link(batroot);batroot.location=(0,0,1.5)
        for o in bat:o.parent=batroot
        # The native six-frame cycle goes level, down, level, then up.
        # Resample the authored cycle before clearing its original action.
        rig=next(o for o in bat if o.type=='ARMATURE')
        timing=[(0,.75),(1/6,1),(2/6,1.25),(.5,1.38),(2/3,1.5),(5/6,1.65),(1,1.75)]
        poses=[]
        for f in range(1,26):
            t=(f-1)/24 if group=='MOVING' else 0
            for (a,x),(b,y) in zip(timing,timing[1:]):
                if a<=t<=b:phase=x+(y-x)*(t-a)/(b-a);break
            sample=1+24*(phase%1);scene.frame_set(math.floor(sample),subframe=sample%1)
            poses.append({bone.name:(bone.rotation_quaternion.copy(),bone.location.copy()) for bone in rig.pose.bones})
        rig.animation_data_clear()
        for f,pose in enumerate(poses,1):
            for name,(q,loc) in pose.items():
                bone=rig.pose.bones[name];bone.rotation_mode='QUATERNION';bone.rotation_quaternion=q;bone.location=loc;bone.keyframe_insert('rotation_quaternion',frame=f);bone.keyframe_insert('location',frame=f)
        smoke=[];rng=random.Random(19)
        if group!='MOVING':
            for i in range(38):
                x,y,z=rng.uniform(-.23,.23),rng.uniform(-.23,.23),rng.uniform(.25,1.5)
                bpy.ops.mesh.primitive_plane_add(size=rng.uniform(.24,.48),location=(x,y,z));o=bpy.context.object;o.name=f'TransformSmoke{i}';o.rotation_euler=scene.camera.rotation_euler
                for poly in o.data.polygons:poly.use_smooth=True
                mat=bpy.data.materials.new(o.name);mat.use_nodes=True;nodes=mat.node_tree.nodes;nodes.clear()
                output=nodes.new('ShaderNodeOutputMaterial');emission=nodes.new('ShaderNodeEmission');shade=rng.uniform(.4,.8);emission.inputs[0].default_value=(shade,shade,shade,1)
                transparent=nodes.new('ShaderNodeBsdfTransparent');mix=nodes.new('ShaderNodeMixShader')
                tex=nodes.new('ShaderNodeTexCoord');noise=nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=7;noise.inputs['Detail'].default_value=3
                centered=nodes.new('ShaderNodeVectorMath');centered.operation='SUBTRACT';centered.inputs[1].default_value=(.5,.5,0)
                length=nodes.new('ShaderNodeVectorMath');length.operation='LENGTH'
                edge=nodes.new('ShaderNodeMapRange');edge.clamp=True;edge.inputs['From Min'].default_value=.12;edge.inputs['From Max'].default_value=.5;edge.inputs['To Min'].default_value=1;edge.inputs['To Max'].default_value=0
                texture=nodes.new('ShaderNodeMapRange');texture.clamp=True;texture.inputs['From Min'].default_value=.35;texture.inputs['From Max'].default_value=.7
                mask=nodes.new('ShaderNodeMath');mask.operation='MULTIPLY'
                density=nodes.new('ShaderNodeMath');density.operation='MULTIPLY';density.inputs[0].default_value=0;density.use_clamp=True
                links=mat.node_tree.links
                links.new(tex.outputs['UV'],noise.inputs['Vector']);links.new(tex.outputs['UV'],centered.inputs[0]);links.new(centered.outputs[0],length.inputs[0]);links.new(length.outputs['Value'],edge.inputs['Value']);links.new(noise.outputs['Fac'],texture.inputs['Value']);links.new(edge.outputs[0],mask.inputs[0]);links.new(texture.outputs[0],mask.inputs[1]);links.new(mask.outputs[0],density.inputs[1]);links.new(density.outputs[0],mix.inputs[0]);links.new(transparent.outputs[0],mix.inputs[1]);links.new(emission.outputs[0],mix.inputs[2]);links.new(mix.outputs[0],output.inputs['Surface']);o.data.materials.append(mat);smoke.append((o,density))
        for f in range(1,26):
            t=(f-1)/24;phase=t if group=='MOVE_START' else 1-t
            h=0 if group=='MOVING' else 1-smooth(min(1,max(0,(phase-.22)/.43)))
            b=1 if group=='MOVING' else smooth(min(1,max(0,(phase-.35)/.40)))
            root.scale=(max(h,.001),)*3;root.keyframe_insert('scale',frame=f)
            batroot.scale=(.68*max(b,.001),)*3;batroot.keyframe_insert('scale',frame=f)
            for o in humans:o.hide_render=h<.01;o.keyframe_insert('hide_render',frame=f)
            for o in bat:
                if o.type=='MESH':o.hide_render=b<.01;o.keyframe_insert('hide_render',frame=f)
            for o,mix in smoke:
                opacity=math.sin(math.pi*t)**1.5
                o.scale=(.4+1.1*opacity,)*3;o.keyframe_insert('scale',frame=f)
                mix.inputs[0].default_value=2.0*opacity;mix.inputs[0].keyframe_insert('default_value',frame=f)
        for o in scene.objects:
            if o.animation_data and o.animation_data.action:linear_keys(o.animation_data.action)
        scene.render.threads_mode='FIXED';scene.render.threads=4;scene.cycles.samples=24;scene.cycles.seed=0;scene.cycles.use_animated_seed=False;scene.frame_start=1;scene.frame_end=24 if group=='MOVING' else 25
        scene.frame_set(1);bpy.ops.file.pack_all();source=args.out/(group.lower()+'.blend');bpy.ops.wm.save_as_mainfile(filepath=str(source));bpy.ops.wm.open_mainfile(filepath=str(source));scene=bpy.context.scene
        n=6 if group=='MOVING' else 5;frames=[]
        folder=args.out/'sprites2x';folder.mkdir(exist_ok=True)
        for i in range(n):
            f=1+24*i/(n if group=='MOVING' else n-1);scene.frame_set(math.floor(f),subframe=f%1);path=folder/f'{group.lower()}_{i:02}.png';render.render_to(str(path));box=render.measure_alpha_bbox(str(path))
            if not box or min(box[:2])<=0 or box[2]>=900 or box[3]>=800:raise ValueError('Empty or clipped flight frame')
            frames.append({'file':str(path.relative_to(args.out)),'frame':f,'alphaBounds':box,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        report['clips'][group]={'frames':frames,'loop':group=='MOVING'}
    (args.out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');(args.out/'vampire_flight.py').write_bytes(Path(__file__).read_bytes())

if __name__=='__main__':main()
