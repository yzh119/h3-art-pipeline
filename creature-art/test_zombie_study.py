#!/usr/bin/env python3
"""Reopen baked zombie clips; verify IK, loop seams, attack and planted feet."""
import json
import math
from pathlib import Path
import sys
import bpy
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
import zombie_study as z


def controls():
    return {s+l:{'target':bpy.data.objects[s+e+'Target'],'pole':bpy.data.objects[s+j+'Pole'],'end':s+e}
            for s in ['Right','Left'] for l,e,j in [('Arm','Hand','ForeArm'),('Leg','Foot','Leg')]}


def points(arm):
    return [arm.matrix_world @ b.head for b in arm.pose.bones]


def main():
    out=Path(sys.argv[sys.argv.index('--')+1]);manifest=json.loads((out/'manifest.json').read_text());p=manifest['profile']
    endpoints={}
    strike_heights={}
    result={'samples':0,'max_ik_error':0.,'max_saved_pose_error':0.,'max_loop_seam':0.,'min_mesh_z':1.,'max_blade_length_change':0.,'max_stance_drift':0.}
    for group,spec in p['clips'].items():
        path=str(out/(group.lower()+'.blend'));bpy.ops.wm.open_mainfile(filepath=path)
        arm=bpy.data.objects['ZombieStudy'];cs=controls();scene=bpy.context.scene;ticks=manifest['clips'][group]['ticks']
        baked={};stance={};lengths=[]
        for half in range(ticks*2+1):
            f=1+half/2;scene.frame_set(int(f),subframe=f-int(f));t=half/(2*ticks)
            result['samples']+=1
            if half%2==0:baked[half//2]=points(arm)
            for c in cs.values():
                err=(arm.matrix_world @ arm.pose.bones[c['end']].head-c['target'].matrix_world.translation).length
                result['max_ik_error']=max(result['max_ik_error'],err)
            mesh=bpy.data.objects['ZombieSkin'].evaluated_get(bpy.context.evaluated_depsgraph_get());data=mesh.to_mesh()
            result['min_mesh_z']=min(result['min_mesh_z'],min((mesh.matrix_world@v.co).z for v in data.vertices));mesh.to_mesh_clear()
            blade=bpy.data.objects['CleaverBlade'];pts=[blade.matrix_world@v.co for v in blade.data.vertices]
            lengths.append((pts[0]-pts[2]).length)
            if group=='MOVING':
                w=p['walk'];d=w['stance_fraction'];root=w['stride']/d*t
                for side,offset in [('Right',0),('Left',.5)]:
                    phase=(t+offset)%1
                    if phase<d:
                        position=arm.matrix_world @ arm.pose.bones[side+'Foot'].head;position.y-=root
                        k=(side,math.floor(t+offset))
                        if k not in stance:stance[k]=position
                        result['max_stance_drift']=max(result['max_stance_drift'],(position-stance[k]).length)
        result['max_blade_length_change']=max(result['max_blade_length_change'],max(lengths)-min(lengths))
        if spec['loop']:
            result['max_loop_seam']=max(result['max_loop_seam'],max((a-b).length for a,b in zip(baked[0],baked[ticks])))
        endpoints[group]=(baked[0],baked[ticks])
        if group=='DEATH':
            result['corpse_height']=max((mesh.matrix_world@v.co).z for v in mesh.data.vertices)
        for o in [arm,bpy.data.objects['ZombieRoot']]+[c[k] for c in cs.values() for k in ['target','pole']]:o.animation_data_clear()
        for tick,expected in baked.items():
            z.apply(arm,cs,z.pose(p,group,tick/ticks))
            result['max_saved_pose_error']=max(result['max_saved_pose_error'],max((a-b).length for a,b in zip(expected,points(arm))))
        if group.startswith('ATTACK_'):
            z.apply(arm,cs,z.pose(p,group,.46))
            blade=bpy.data.objects['CleaverBlade']
            strike_heights[group]=(blade.matrix_world@blade.data.vertices[2].co).z
        if group=='ATTACK_FRONT':
            heights=[]
            for t in [.25,.46]:
                z.apply(arm,cs,z.pose(p,group,t));blade=bpy.data.objects['CleaverBlade']
                heights.append((blade.matrix_world@blade.data.vertices[2].co).z)
            result['attack_tip_z']=heights
            assert heights[0]>1.9 and heights[1]<1.3,heights
    result['strike_heights']=strike_heights
    assert strike_heights['ATTACK_UP']>strike_heights['ATTACK_FRONT']+.3
    assert strike_heights['ATTACK_DOWN']<strike_heights['ATTACK_FRONT']-.3
    idle=endpoints['HOLDING'][0]
    for group in ['MOUSEON','HITTED','DEFENCE','ATTACK_FRONT','ATTACK_UP','ATTACK_DOWN']:
        assert max((a-b).length for a,b in zip(endpoints[group][1],idle))<.00001,group
    for a,b in [(endpoints['MOVE_START'][0],idle),(endpoints['MOVE_START'][1],endpoints['MOVING'][0]),(endpoints['MOVE_END'][0],endpoints['MOVING'][0]),(endpoints['MOVE_END'][1],idle),(endpoints['TURN_L'][1],endpoints['TURN_R'][0]),(endpoints['TURN_R'][1],idle)]:
        assert max((x-y).length for x,y in zip(a,b))<.00001
    assert max((a-b).length for a,b in zip(endpoints['TURN_L'][0],endpoints['TURN_L'][1]))>.2
    assert result['corpse_height']<.65,result
    print(json.dumps(result,indent=2))
    (out/'checks.json').write_text(json.dumps(result,indent=2)+'\n')
    assert result['max_ik_error']<.001,result
    assert result['max_saved_pose_error']<.00001,result
    assert result['max_loop_seam']<.00001,result
    assert result['max_blade_length_change']<.00001,result
    assert result['min_mesh_z']>-.002,result
    assert result['max_stance_drift']<.001,result


if __name__=='__main__':main()
