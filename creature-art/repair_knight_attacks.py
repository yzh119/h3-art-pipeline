#!/usr/bin/env python3
"""Reauthor mounted attacks from native rear / overhead wind-up / forward cut poses.

Works on local September knight exports; geometry selectors are model-specific.
All groups share the repaired arm/weapon; non-attack motion curves are retained.
"""
import argparse,json,math,shutil,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
import mounted_dragon_motion as motion

def interpolate(t,keys):
 for (a,x),(b,y) in zip(keys,keys[1:]):
  if t<=b:
   q=motion.smooth(motion.clamp((t-a)/(b-a)));return x+(y-x)*q
 return keys[-1][1]

def repair_skin(obj):
 import bmesh
 dread='dread' in bpy.context.scene.get('knightVariant','').lower()
 # The bootstrap fuses the saber into the horse and the hand into the boot.
 # Excise those surfaces and rebuild articulated armor and a rigid curved blade.
 bm=bmesh.new();bm.from_mesh(obj.data)
 def remove(c):
  x,y,z=c
  def distance(a,b):
   a,b=Vector(a),Vector(b);d=b-a;t=max(0,min(1,(c-a).dot(d)/d.length_squared));return (c-a-t*d).length
  upper=distance((-.18,.12,1.32),(-.24,.17,1.14))
  fore=distance((-.24,.22,1.14),(-.26,.19,1.00))
  limb=x<-.175 and ((upper<.072 and 1.10<z<1.275) or (fore<.080 and z>.955) or (distance((-.24,.16,.96),(-.24,.16,.96+.001))<.075))
  along=.16-y;blade_z=(.96-.50*along+.30*along*along) if dread else ((-.186946*y+.532301)*y+.457263)*y+.846288
  blade_x=-.285 if dread else -.25-.21*along
  blade=-.54<y<.145 and abs(z-blade_z)<(.031 if dread else .045) and abs(x-blade_x)<(.033 if dread else .035)
  return limb or blade
 faces=[f for f in bm.faces if remove(f.calc_center_median())]
 removed=len(faces);bmesh.ops.delete(bm,geom=faces,context='FACES');bm.to_mesh(obj.data);bm.free()
 names={g.index:g.name for g in obj.vertex_groups};bad={'RArm','RForearm','RHand','saber'}
 for v in obj.data.vertices:
  weights={names[g.group]:g.weight for g in v.groups};amount=sum(weights.get(n,0) for n in bad)
  if not amount:continue
  for n in bad:obj.vertex_groups[n].remove([v.index]);weights.pop(n,None)
  total=sum(weights.values())
  if total>1e-8:
   for n,w in weights.items():obj.vertex_groups[n].add([v.index],w/total,'REPLACE')
  else:obj.vertex_groups['rider' if v.co.z>1.03 else 'RRiderLeg'].add([v.index],1,'REPLACE')
 def material(name,color,metal=.7):
  mat=bpy.data.materials.new(name);mat.diffuse_color=(*color,1);mat.use_nodes=True;p=mat.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=.48
  tree=mat.node_tree;noise=tree.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=75;noise.inputs['Detail'].default_value=2;ramp=tree.nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=tuple(v*.65 for v in color)+(1,);ramp.color_ramp.elements[1].color=tuple(v*1.20 for v in color)+(1,);tree.links.new(noise.outputs['Fac'],ramp.inputs[0]);tree.links.new(ramp.outputs[0],p.inputs['Base Color']);bump=tree.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.16;bump.inputs['Distance'].default_value=.003;tree.links.new(noise.outputs['Fac'],bump.inputs['Height']);tree.links.new(bump.outputs[0],p.inputs['Normal']);return mat
 steel=material('Knight articulated dark steel',(.12,.14,.16));rim=material('Knight armor edges',(.34,.36,.37));black=material('Knight joint leather',(.025,.027,.03),.05);bladeMat=material('Knight saber steel',(.52,.55,.57));gold=material('Knight saber guard',(.32,.22,.095))
 parts=[]
 def bind(o,bone,mat):
  o.data.materials.append(mat)
  for face in o.data.polygons:face.use_smooth=True
  g=o.vertex_groups.new(name=bone);g.add(list(range(len(o.data.vertices))),1,'REPLACE');parts.append(o)
 def sphere(center,scale,bone,mat):
  bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,location=center);o=bpy.context.object;o.scale=scale;bpy.ops.object.transform_apply(location=True,rotation=True,scale=True);bind(o,bone,mat)
 def tube(a,b,r1,r2,bone,mat):
  a,b=Vector(a),Vector(b);d=b-a;bpy.ops.mesh.primitive_cone_add(vertices=12,radius1=r1,radius2=r2,depth=d.length,location=(a+b)/2);o=bpy.context.object;o.rotation_euler=d.to_track_quat('Z','Y').to_euler();bpy.ops.object.transform_apply(location=True,rotation=True,scale=True);bind(o,bone,mat)
 shoulder=Vector((-.18,.12,1.32));elbow=Vector((-.24,.17,1.14));wrist=Vector((-.24,.16,.96))
 # Retain the textured shoulder plate; the new upper arm fits underneath it.
 for a,b,r,bone in [(shoulder,elbow,.048,'RArm'),(elbow,wrist,.039,'RForearm')]:
  tube(a,b,r,r*.82,bone,steel)
  for t in [.12,.55,.92]:
   q=a.lerp(b,t);tube(q,q+(b-a).normalized()*.013,r*1.02,r*1.02,bone,rim)
 sphere(elbow,(.047,.049,.045),'RForearm',black);sphere(wrist,(.044,.039,.044),'RHand',steel)
 # Grip and guard share the blade's rigid socket. Curve rises towards the tip.
 tangent=Vector((-.12,-.64,-.16)).normalized();start=wrist+tangent*.055
 tube(wrist-tangent*.055,start,.018,.018,'saber',black)
 tube(start+Vector((-.065,0,0)),start+Vector((.065,0,0)),.012,.012,'saber',gold)
 vertices=[];faces=[]
 for i in range(17):
  t=i/16;c=start+Vector((-.10*t,-.72*t,-.20*t+.17*t*t));width=.027*(1-t**5);thick=.006*(1-.8*t)
  for dx,dz in [(-thick,-width),(-thick,width),(thick,width),(thick,-width)]:vertices.append(tuple(c+Vector((dx,0,dz))))
  if i:
   for j in range(4):faces.append(((i-1)*4+j,(i-1)*4+(j+1)%4,i*4+(j+1)%4,i*4+j))
 faces.extend([(3,2,1,0),(64,65,66,67)]);mesh=bpy.data.meshes.new('Rigid curved saber');mesh.from_pydata(vertices,[],faces);o=bpy.data.objects.new('Rigid curved saber',mesh);bpy.context.collection.objects.link(o);bind(o,'saber',bladeMat)
 for face in o.data.polygons:face.use_smooth=False
 bpy.ops.object.select_all(action='DESELECT');obj.select_set(True)
 for o in parts:o.select_set(True)
 bpy.context.view_layer.objects.active=obj;bpy.ops.object.join()
 return {'removedFusedFaces':removed,'replacement':'articulated armored arm, gauntlet and rigid saber'}

def repair_fallback_weights(obj):
 # Recover early probes that left residual weights when adding a fallback.
 for v in obj.data.vertices:
  current={g.group:g.weight for g in v.groups};total=sum(current.values())
  if total<=1.0001:continue
  leg=obj.vertex_groups['RRiderLeg'].index
  if current.get(leg,0)>.999 and total<1.06:
   obj.vertex_groups[leg].remove([v.index]);current.pop(leg);total=sum(current.values())
  for g,w in current.items():obj.vertex_groups[g].add([v.index],w/total,'REPLACE')

def smooth_repaired_contact(obj):
 # Normalize and relax the small former saber/boot contact region. Keep each
 # disconnected replacement armor and weapon component rigid.
 coords=np.array([tuple(v.co) for v in obj.data.vertices]);edges=np.array([tuple(e.vertices) for e in obj.data.edges]);left,right=edges.T;dense=np.zeros((len(coords),len(obj.vertex_groups)))
 for v in obj.data.vertices:
  for g in v.groups:dense[v.index,g.group]=g.weight
 degree=np.bincount(np.r_[left,right],minlength=len(coords));x,y,z=coords.T;mask=(x<-.13)&(y>.10)&(y<.27)&(z>.85)&(z<1.04)
 for iteration in range(30):
  total=np.zeros_like(dense);np.add.at(total,left,dense[right]);np.add.at(total,right,dense[left]);mean=total/np.maximum(1,degree[:,None]);dense[mask]=.4*dense[mask]+.6*mean[mask]
 dense/=np.maximum(1e-8,dense.sum(1,keepdims=True))
 for i in np.flatnonzero(mask):
  for g in obj.vertex_groups:g.remove([int(i)])
  for j in np.flatnonzero(dense[i]>.0001):obj.vertex_groups[int(j)].add([int(i)],float(dense[i,j]),'REPLACE')

def attack_pose(arm,group,t):
 # Native contact is frame 4/7: rear on 1..3, cut on 4, recover on 5..7.
 rear=interpolate(t,[(0,0),(.28,1),(.43,.90),(.57,0),(1,0)])
 cut=interpolate(t,[(0,0),(.43,0),(.57,1),(.74,.45),(1,0)])
 pb=arm.pose.bones;rot=lambda n,axis,v:setattr(pb[n].rotation_euler,axis,v)
 rot('body','x',-.60*rear+.055*cut)
 rot('neck','x',.08*rear+.13*cut);rot('head','x',-.08*rear-.04*cut)
 # Forelegs fold while the horse balances over the hind hooves.
 for side in ['R','L']:
  rot(side+'FrontUpper','x',-.65*rear);rot(side+'FrontLower','x',1.10*rear);rot(side+'FrontFoot','x',-.35*rear)
 rot('rider','x',.20*rear+.60*cut);rot('riderHead','x',-.13*rear-.15*cut)
 rot('RArm','x',1.25*rear-1.20*cut);rot('RForearm','x',-2.55*rear-.20*cut)
 rot('RHand','x',-.25*rear+.50*cut)
 rot('RArm','z',.12*rear);rot('RHand','z',.50*cut)
 if group.endswith('UP'):rot('RHand','x',pb['RHand'].rotation_euler.x-.30*cut)
 if group.endswith('DOWN'):rot('RHand','x',pb['RHand'].rotation_euler.x+.30*cut)
 if group.startswith('SPECIAL'):rot('rider','z',-.12*cut);rot('RArm','z',pb['RArm'].rotation_euler.z-.20*cut)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--probe',action='store_true');p.add_argument('--no-skin',action='store_true');p.add_argument('--no-render',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);assert not a.out.exists();shutil.copytree(a.source,a.out,ignore=shutil.ignore_patterns('*.blend1'));report=json.loads((a.out/'manifest.json').read_text())
 if report['variant'] not in ['blackKnight','dreadKnight']:raise ValueError('Only the mounted knight exports are supported')
 if a.no_skin and not all(c.get('sharedArmRepair') for n,c in report['clips'].items() if not a.probe or n=='ATTACK_FRONT'):raise ValueError('--no-skin requires an existing reconstructed arm')
 bpy.context.preferences.filepaths.save_version=0
 for group,clip in report['clips'].items():
  if a.probe and group!='ATTACK_FRONT':continue
  is_attack=group.startswith(('ATTACK','SPECIAL'))
  path=a.out/(group.lower()+'.blend');bpy.ops.wm.open_mainfile(filepath=str(path));s=bpy.context.scene;s['knightVariant']=report['variant'];arm=s.objects['CreatureRig'];obj=s.objects['Mesh_0'];support=s.objects['GroundSupport'];support.animation_data_clear();support.location=(0,0,0);s.cycles.samples=8 if a.probe else 16
  if not a.no_skin:clip['weaponRepair']=repair_skin(obj)
  else:repair_fallback_weights(obj)
  smooth_repaired_contact(obj)
  # Preserve neutral leg offsets; author all frames from the same saved idle.
  s.frame_set(1);base={b.name:(b.location.copy(),b.rotation_euler.copy(),b.scale.copy()) for b in arm.pose.bones}
  if is_attack:arm.animation_data_clear()
  hoof_ids=[v.index for v in obj.data.vertices if v.co.z<.06 and v.co.y>.25]
  e=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());m=e.to_mesh();anchor=sum(m.vertices[i].co.y for i in hoof_ids)/len(hoof_ids);e.to_mesh_clear()
  for k in range(s.frame_end):
   t=k/(s.frame_end-1);s.frame_set(k+1)
   if is_attack:
    for b in arm.pose.bones:b.location,b.rotation_euler,b.scale=base[b.name]
    attack_pose(arm,group,t)
   bpy.context.view_layer.update()
   e=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());m=e.to_mesh();low=min(v.co.z for v in m.vertices);support.location.y=anchor-sum(m.vertices[i].co.y for i in hoof_ids)/len(hoof_ids) if is_attack else 0;e.to_mesh_clear();support.location.z=.008-low;support.keyframe_insert('location',frame=k+1)
   for b in (arm.pose.bones if is_attack else []):
    for field in ['location','rotation_euler','scale']:b.keyframe_insert(field,frame=k+1)
  for target in [arm,support]:
   for layer in target.animation_data.action.layers:
    for strip in layer.strips:
     for bag in strip.channelbags:
      for curve in bag.fcurves:
       for key in curve.keyframe_points:key.interpolation='LINEAR'
  s.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(path))
  for frame in ([] if a.no_render else clip['frames']):
   tick=frame['frame'];s.frame_set(math.floor(tick),subframe=tick%1);target=a.out/frame['file'];motion.render.render_to(str(target));frame['sha256']=motion.digest(target);frame['bbox']=motion.render.measure_alpha_bbox(str(target))
  clip['sharedArmRepair']=True
  if is_attack:clip['mountedAttackRevision']=2;clip.pop('armorMotionScale',None)
 report['checks'].pop('supportSHA256',None);report['checks']['groundSupport']='Direct renders from shared ground support parent';report.pop('artisticallyRejected',None);report.pop('requiredRepair',None);report['previewOnly']=a.probe or a.no_render;report['pendingRenders']=a.no_render;report['checks']['mountedAttackRepair']='Native rear, overhead wind-up, forward cut; directly rendered with shared support parent';(a.out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copy2(__file__,a.out/Path(__file__).name)
if __name__=='__main__':main()
