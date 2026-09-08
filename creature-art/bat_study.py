#!/usr/bin/env python3
"""Repair small bat surface holes and author a local wing animation study."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import bpy
import bmesh
from mathutils import Vector, Quaternion
sys.path.insert(0,str(Path(__file__).resolve().parent))
import render_sprites as render
import skeleton_study as study
from skeleton_motion import linear_keys


def repair(obj):
    bm=bmesh.new();bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
    before=sum(e.is_boundary for e in bm.edges)
    edges={e for e in bm.edges if e.is_boundary};filled=[]
    while edges:
        todo=[edges.pop()];part=[]
        while todo:
            edge=todo.pop();part.append(edge)
            for v in edge.verts:
                for e in v.link_edges:
                    if e in edges:edges.remove(e);todo.append(e)
        verts={v for e in part for v in e.verts}
        diameter=max(max(v.co[i] for v in verts)-min(v.co[i] for v in verts) for i in range(3))
        if not (3<=len(part)<=16 and diameter<.022 and all(sum(e.is_boundary for e in v.link_edges)==2 for v in verts)):continue
        # New face corners inherit UVs from adjoining surface corners.
        uv=bm.loops.layers.uv.active
        uv_by_vertex={v:next((loop[uv].uv.copy() for loop in v.link_loops),Vector((0,0))) for v in verts} if uv else {}
        faces=bmesh.ops.holes_fill(bm,edges=part,sides=16)['faces']
        for f in faces:
            f.smooth=True
            if uv:
                for loop in f.loops:loop[uv].uv=uv_by_vertex[loop.vert]
        filled.append({'edges':len(part),'diameter':diameter,'faces':len(faces)})
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    after=sum(e.is_boundary for e in bm.edges);bm.to_mesh(obj.data);bm.free();obj.data.update()
    return {'boundaryBefore':before,'boundaryAfter':after,'patches':filled}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.out.exists():raise ValueError('Use a new output directory')
    args.out.mkdir(parents=True)
    meshes,camera,_=render.build_scene(str(args.model),(1000,800),25,-25,0,0,32,3,.5)
    obj=max(meshes,key=lambda o:len(o.data.vertices));report={'repair':repair(obj),'sourceSHA256':hashlib.sha256(args.model.read_bytes()).hexdigest()}
    bpy.context.view_layer.objects.active=obj;obj.select_set(True)
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    bones={'Body':{'head':[0,0,0],'tail':[0,-.2,0],'parent':None}}
    for side,sign in [('Left',1),('Right',-1)]:
        bones[side+'Wing']={'head':[sign*.15,.02,.035],'tail':[sign*.52,.03,.08],'parent':'Body'}
        bones[side+'Tip']={'head':[sign*.52,.03,.08],'tail':[sign*.94,.05,.03],'parent':side+'Wing'}
    arm=study.make_rig(bones);arm.name='BatRig'
    for name in bones:obj.vertex_groups.new(name=name)
    for v in obj.data.vertices:
        x=abs(v.co.x);side='Left' if v.co.x>=0 else 'Right'
        wing=max(0,min(1,(x-.12)/.12));tip=max(0,min(1,(x-.43)/.20))
        for name,w in [('Body',1-wing),(side+'Wing',wing*(1-tip)),(side+'Tip',wing*tip)]:
            if w>0:obj.vertex_groups[name].add([v.index],w,'REPLACE')
    obj.modifiers.new('Bat wing skin','ARMATURE').object=arm
    scene=bpy.context.scene;scene.render.threads_mode='FIXED';scene.render.threads=4;scene.cycles.use_animated_seed=False;scene.cycles.seed=0
    scene.objects['fill'].data.energy=2;scene.objects['fill'].rotation_euler=(math.radians(78),0,0)
    camera.data.ortho_scale=2.6;camera.location=camera.rotation_euler.to_matrix()@Vector((0,0,10))
    scene.render.fps=24
    for f in range(1,26):
        t=(f-1)/24
        for side,sign in [('Left',1),('Right',-1)]:
            for part,angle in [('Wing',sign*(12+34*math.cos(math.tau*t))),('Tip',sign*(8+15*math.cos(math.tau*t-.5)))]:
                name=side+part;b=arm.pose.bones[name];rest=arm.data.bones[name].matrix_local.to_quaternion()
                rotation=Quaternion((0,1,0),math.radians(angle))
                b.rotation_mode='QUATERNION';b.rotation_quaternion=rest.inverted()@rotation@rest;b.keyframe_insert('rotation_quaternion',frame=f)
        b=arm.pose.bones['Body'];b.location.z=.022*math.sin(math.tau*t);b.keyframe_insert('location',frame=f)
    linear_keys(arm.animation_data.action);scene.frame_start=1;scene.frame_end=24;scene.frame_set(1)
    bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(args.out/'flight.blend'))
    bpy.ops.wm.open_mainfile(filepath=str(args.out/'flight.blend'));scene=bpy.context.scene
    samples=[]
    for k in range(49):
        f=1+k*.5;scene.frame_set(math.floor(f),subframe=f%1)
        points=render.world_vertices([o for o in scene.objects if o.type=='MESH'],bpy.context.evaluated_depsgraph_get())
        if not all(math.isfinite(c) for v in points for c in v):raise ValueError('Nonfinite geometry')
        samples.append([[min(v[i] for v in points) for i in range(3)],[max(v[i] for v in points) for i in range(3)]])
    report['savedSamples']=len(samples);report['sampleBounds']=samples;report['loopBoundsError']=max(abs(samples[0][a][i]-samples[-1][a][i]) for a in range(2) for i in range(3))
    if report['loopBoundsError']>1e-5:raise ValueError('Loop discontinuity')
    for f in range(1,25):
        scene.frame_set(f);path=args.out/f'flight-{f:03}.png';render.render_to(str(path));box=render.measure_alpha_bbox(str(path))
        if not box or min(box[:2])<=0 or box[2]>=1000 or box[3]>=800:raise ValueError('Clipped flight frame')
    (args.out/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    (args.out/'bat_study.py').write_bytes(Path(__file__).read_bytes())

if __name__=='__main__':main()
