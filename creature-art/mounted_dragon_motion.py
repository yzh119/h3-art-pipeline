#!/usr/bin/env python3
"""Landmark-based pivot rigs and native-count clips for reviewed knight/dragon meshes.

Landmarks are specific to the September bootstrap set, not a general autorigger.
"""
import argparse,hashlib,json,math,sys,shutil
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
import render_sprites as render
from vcmi_anim import GROUP_NAMES

def smooth(t):return t*t*(3-2*t)
def clamp(t):return min(1,max(0,t))
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def build(source,dragon,spectral):
 bpy.ops.wm.open_mainfile(filepath=str(source));scene=bpy.context.scene;mesh=next(o for o in scene.objects if o.type=='MESH')
 specs={};segments={}
 def add(n,h,parent='body',end=None):specs[n]=(tuple(h),parent);segments[n]=(np.array(h),np.array(end if end is not None else (h[0],h[1],h[2]+.12)))
 if dragon:
  add('body',(0,-.28,.68),None,(0,-.43,1.03));add('neck',(0,-.43,1.03),end=(0,-.45,1.35));add('head',(0,-.45,1.35),'neck',(0,-.68,1.43));add('jaw',(0,-.51,1.33),'head',(0,-.73,1.30))
  add('tail',(0,-.10,.35),end=(0,.38,.09));add('tailEnd',(0,.38,.09),'tail',(0,.85,.08))
  for sign,s in [(-1,'R'),(1,'L')]:
   x=.16*sign
   add(s+'Upper',(x,-.20,.64),end=(x,-.43,.44));add(s+'Lower',(x,-.43,.44),s+'Upper',(x,-.27,.17));add(s+'Foot',(x,-.27,.17),s+'Lower',(x,-.40,.055))
   add(s+'Wing',(.12*sign,-.32,1.02),end=(.30*sign,-.1,1.42));add(s+'WingTip',(.30*sign,-.1,1.42),s+'Wing',(.38*sign,.30,.36))
   add(s+'Arm',(.19*sign,-.45,.84),end=(.24*sign,-.64,.79));add(s+'Hand',(.24*sign,-.64,.79),s+'Arm',(.25*sign,-.73,.66))
 else:
  add('body',(0,.08,.78),None,(0,-.22,.85));add('neck',(0,-.27,.85),end=(0,-.55,1.19));add('head',(0,-.55,1.19),'neck',(0,-.70,1.02));add('tail',(0,.54,.85),end=(0,.64,.40))
  add('rider',(0,.06,1.03),end=(0,.10,1.32));add('riderHead',(0,.10,1.40),'rider',(0,.09,1.58))
  for sign,s in [(-1,'R'),(1,'L')]:
   x=.14*sign
   for part,y in [('Front',-.25),('Hind',.47)]:
    # Match each foot's actual rest position from low vertices.
    coords=np.array([tuple(v.co) for v in mesh.data.vertices]);m=(coords[:,2]<.11)&(coords[:,0]*sign>0)&((coords[:,1]<0) if part=='Front' else (coords[:,1]>.18));foot=np.median(coords[m],axis=0)
    a=(x,y,.64);b=(x,float(foot[1])+.015,.32);c=(float(foot[0]),float(foot[1]),.07)
    add(s+part+'Upper',a,end=b);add(s+part+'Lower',b,s+part+'Upper',c);add(s+part+'Foot',c,s+part+'Lower',(c[0],c[1]-.07,.025))
   shoulder=(.18*sign,.12,1.32);elbow=(.24*sign,.17,1.14);wrist=(.24*sign,.16,.96) if s=='R' else (.23*sign,-.08,1.15)
   add(s+'Arm',shoulder,'rider',elbow);add(s+'Forearm',elbow,s+'Arm',wrist);add(s+'Hand',wrist,s+'Forearm',(wrist[0],wrist[1]-.10,wrist[2]))
   add(s+'RiderLeg',(.20*sign,.05,1.0),'rider',(.23*sign,-.04,.73));add(s+'RiderBoot',(.23*sign,-.04,.73),s+'RiderLeg',(.25*sign,-.10,.57))
  add('saber',(-.24,.16,.96),'RHand',(-.24,-.48,.80))
 bpy.ops.object.select_all(action='DESELECT');data=bpy.data.armatures.new('CreatureRig');arm=bpy.data.objects.new('CreatureRig',data);scene.collection.objects.link(arm);bpy.context.view_layer.objects.active=arm;arm.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
 for n,(h,parent) in specs.items():
  bone=data.edit_bones.new(n);bone.head=h;bone.tail=Vector(h)+Vector((0,.08,0))
  if parent:bone.parent=data.edit_bones[parent]
 bpy.ops.object.mode_set(mode='OBJECT');arm.show_in_front=True
 coords=np.array([tuple(v.co) for v in mesh.data.vertices]);weights={n:[] for n in specs};assignment=[]
 def distance(c,n):
  a,b=segments[n];d=b-a;t=np.clip(np.dot(c-a,d)/np.dot(d,d),0,1);return np.linalg.norm(c-(a+t*d))
 for i,c in enumerate(coords):
  x,y,z=c;s='R' if x<0 else 'L'
  if dragon:
   if y>-.18 and z<.30:candidates=['tail','tailEnd']
   elif y>-.20 and z>.30 and abs(x)>.065:candidates=[s+'Wing',s+'WingTip']
   elif z>1.29:candidates=['head','neck','jaw']
   elif z>1.03:candidates=['neck','body']
   elif z<.66 and y<-.13:candidates=[s+'Upper',s+'Lower',s+'Foot','body']
   elif y<-.53 and .60<z<.95:candidates=[s+'Arm',s+'Hand']
   else:candidates=['body',s+'Wing',s+'Arm']
  else:
   sword=distance(c,'saber')<.085 and x<-.14 and y<.16 and .73<z<1.02
   if sword:candidates=['saber']
   elif z>1.40:candidates=['riderHead']
   elif z>1.03 and y>-.26:
    candidates=['rider',s+'Arm',s+'Forearm',s+'Hand'] if abs(x)>.13 else ['rider']
   elif abs(x)>.18 and -.17<y<.20 and z>.54:candidates=[s+'RiderLeg',s+'RiderBoot',s+'Hand','body']
   elif z<.59:
    candidates=[s+('Front' if y<.05 else 'Hind')+v for v in ['Upper','Lower','Foot']]
    if y>.57:candidates+=['tail']
   elif y<-.30:candidates=['neck','head','body']
   elif y>.55:candidates=['tail','body']
   else:candidates=['body']
  ds=sorted((distance(c,n),n) for n in candidates);nearest=ds[0][1];assignment.append(nearest)
  if len(ds)==1 or nearest=='saber':weights[nearest].append((i,1.0))
  else:
   pair=ds[:2];a,b=[max(.012,d)**-4 for d,n in pair];weights[pair[0][1]].append((i,a/(a+b)));weights[pair[1][1]].append((i,b/(a+b)))
 # Diffuse initial semantic weights over welded surface adjacency. Hard
 # spatial partitions otherwise pull a shared triangle across unrelated limbs.
 names=list(weights);dense=np.zeros((len(coords),len(names)),dtype=np.float32)
 for j,n in enumerate(names):
  for i,w in weights[n]:dense[i,j]=w
 edge=np.array([tuple(e.vertices) for e in mesh.data.edges]);left,right=edge[:,0],edge[:,1]
 degree=np.bincount(np.r_[left,right],minlength=len(coords)).astype(np.float32)
 for iteration in range(65):
  total=np.zeros_like(dense);np.add.at(total,left,dense[right]);np.add.at(total,right,dense[left]);mean=total/np.maximum(1,degree[:,None]);dense=.40*dense+.60*mean
 dense/=np.maximum(1e-8,dense.sum(axis=1,keepdims=True))
 for j,n in enumerate(names):
  g=mesh.vertex_groups.new(name=n)
  for i in np.flatnonzero(dense[:,j]>.0001):g.add([int(i)],float(dense[i,j]),'REPLACE')
 mesh.modifiers.new('Creature deformation','ARMATURE').object=arm
 if spectral:
  for mat in mesh.data.materials:
   if not mat.use_nodes:continue
   tree=mat.node_tree
   for node in list(tree.nodes):
    if node.type!='BSDF_PRINCIPLED':continue
    color=node.inputs['Base Color'];incoming=list(color.links);gray=tree.nodes.new('ShaderNodeRGBToBW')
    if incoming:tree.links.new(incoming[0].from_socket,gray.inputs[0])
    ramp=tree.nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=(.18,.22,.28,1);ramp.color_ramp.elements[1].color=(.75,.86,.95,1);tree.links.new(gray.outputs[0],ramp.inputs[0]);tree.links.new(ramp.outputs[0],color);tree.links.new(ramp.outputs[0],node.inputs['Emission Color']);node.inputs['Emission Strength'].default_value=.10
 return arm,mesh,specs,segments

def ik(arm,specs,segments,prefix,target):
 a,b=segments[prefix+'Upper'];_,c=segments[prefix+'Lower'];a=a.copy();b=b.copy();c=c.copy();t=np.array(target);v=t[1:]-a[1:];dist=np.linalg.norm(v);l1=np.linalg.norm(b[1:]-a[1:]);l2=np.linalg.norm(c[1:]-b[1:]);safe=min(l1+l2-.0001,max(abs(l1-l2)+.0001,dist));direction=v/max(dist,.0001);along=(l1*l1-l2*l2+safe*safe)/(2*safe);height=math.sqrt(max(0,l1*l1-along*along));normal=np.array([-direction[1],direction[0]]);base=a[1:]+direction*along;p=[base+normal*height,base-normal*height];k=(min(p,key=lambda q:q[0]) if 'Front' in prefix else max(p,key=lambda q:q[0]));t2=a[1:]+direction*safe
 angle=lambda v:math.atan2(v[0],v[1]);upper=angle(b[1:]-a[1:])-angle(k-a[1:]);lower=angle(c[1:]-b[1:])-angle(t2-k)-upper
 arm.pose.bones[prefix+'Upper'].rotation_euler.x=upper;arm.pose.bones[prefix+'Lower'].rotation_euler.x=lower;arm.pose.bones[prefix+'Foot'].rotation_euler.x=-upper-lower
 return abs(dist-safe)

def pose(arm,mesh,specs,segments,dragon,group,t):
 for b in arm.pose.bones:b.location=(0,0,0);b.rotation_mode='XYZ';b.rotation_euler=(0,0,0);b.scale=(1,1,1)
 arm.location=(0,0,0);body=arm.pose.bones['body'];rot=lambda n,axis,v:setattr(arm.pose.bones[n].rotation_euler,axis,v)
 wave=math.sin(2*math.pi*t);attack=group.startswith(('ATTACK','SPECIAL'));hit=math.sin(math.pi*t);moving=group=='MOVING';flight=1 if moving else (smooth(t) if group=='MOVE_START' else (1-smooth(t) if group=='MOVE_END' else 0));error=0
 if dragon:
  body.rotation_euler.x=.80*flight;body.location.z=.38*flight+.018*wave*(1-flight)
  for sign,s in [(-1,'R'),(1,'L')]:
   rot(s+'Wing','z',sign*(.9*flight));rot(s+'Wing','y',sign*(.42*math.cos(2*math.pi*t)*flight+.035*wave*(1-flight)));rot(s+'WingTip','z',sign*.10*flight)
   rot(s+'Upper','x',-.32*flight);rot(s+'Lower','x',.5*flight);rot(s+'Arm','x',-.14*flight);rot(s+'Hand','x',.10*wave)
  rot('tail','x',-.14*flight);rot('tailEnd','z',.09*wave);rot('neck','x',-.25*flight+.035*wave);rot('jaw','x',-.10*max(0,wave))
  if attack:
   level=.15 if group.endswith('UP') else (-.12 if group.endswith('DOWN') else 0)
   pulse=math.sin(math.pi*t)**2;rot('neck','x',.45*pulse-level*pulse);rot('head','x',-.10*pulse);rot('jaw','x',-.60*pulse);body.location.y=-.12*pulse
   for s in ['R','L']:rot(s+'Arm','x',-.30*pulse)
 else:
  gait=1 if moving else (smooth(t) if group=='MOVE_START' else (1-smooth(t) if group=='MOVE_END' else 0));gait_time=t if moving else 0
  bob=-.022+gait*.009*math.cos(4*math.pi*gait_time)+(1-gait)*.002*wave;body.location.z=bob
  for sign,s in [(-1,'R'),(1,'L')]:
   for part in ['Front','Hind']:
    prefix=s+part;target=segments[prefix+'Lower'][1].copy();phase=(gait_time+(0 if (s=='L')==(part=='Front') else .5))%1
    if gait:
     if phase<.60:target[1]+=gait*(-.085+.17*phase/.60)
     else:target[1]+=gait*(.085-.17*smooth((phase-.60)/.4));target[2]+=gait*.085*math.sin(math.pi*(phase-.60)/.4)
    target[2]-=bob;error=max(error,ik(arm,specs,segments,prefix,target))
  rot('neck','x',.025*wave);rot('head','x',-.018*wave);rot('tail','y',.06*wave);rot('rider','x',.018*wave);rot('riderHead','x',-.018*wave)
  if attack:
   lift=smooth(clamp(t/.35));strike=smooth(clamp((t-.35)/.3));recover=smooth(clamp((t-.65)/.35));angle=(-1.7*lift+2.15*strike)*(1-recover)
   rot('RArm','x',angle*.50);rot('RForearm','x',angle*.50);rot('RHand','x',-.15*hit);rot('rider','z',-.12*hit);rot('neck','x',-.06*hit)
   if group.endswith('UP'):rot('RArm','y',-.15*hit)
   if group.endswith('DOWN'):rot('RArm','y',.22*hit)
   if group.startswith('SPECIAL'):rot('RArm','x',angle*.75);rot('RForearm','x',angle*.65)
 if group=='MOUSEON':rot('head' if dragon else 'riderHead','z',.12*wave)
 if group in ['HITTED','DEFENCE']:
  body.rotation_euler.x=-.10*hit;body.location.y=.05*hit
  if dragon:rot('neck','x',-.12*hit)
  else:rot('RArm','x',-.45*hit)
 if group.startswith('TURN'):body.rotation_euler.z=(1 if group=='TURN_L' else -1)*.28*hit
 if group=='DEATH':
  f=smooth(t);body.rotation_euler.y=(1.35 if not dragon else 1.15)*f;body.rotation_euler.x=.35*f
  if dragon:
   rot('neck','x',1.0*f);rot('tail','x',.50*f)
   for sign,s in [(-1,'R'),(1,'L')]:rot(s+'Wing','z',sign*.5*f);rot(s+'Upper','x',-.7*f);rot(s+'Lower','x',1.1*f)
  else:rot('rider','y',.3*f);rot('head','x',.35*f)
  bpy.context.view_layer.update();evaluated=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());low=min(v.co.z for v in evaluated.data.vertices);arm.location.z=.006-low
 bpy.context.view_layer.update();return error

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--variant',required=True,choices=['blackKnight','dreadKnight','boneDragon','ghostDragon']);p.add_argument('--references',type=Path,required=True);p.add_argument('--probe',action='store_true');p.add_argument('--samples',type=int,default=16);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);assert not a.out.exists();a.out.mkdir(parents=True)
 dragon='Dragon' in a.variant;arm,mesh,specs,segments=build(a.source,dragon,a.variant=='ghostDragon');scene=bpy.context.scene;scene.render.resolution_x=900;scene.render.resolution_y=800;scene.cycles.samples=a.samples;scene.cycles.use_animated_seed=False;scene.cycles.seed=0;scene.render.threads_mode='FIXED';scene.render.threads=4;scene.objects['sun'].data.energy=5;scene.objects['fill'].data.energy=1.8
 camera=scene.camera;camera.rotation_euler=(math.radians(78),0,math.radians(315));camera.location=Vector((0,0,.85))+camera.rotation_euler.to_matrix()@Vector((0,0,10));camera.data.ortho_scale=5;camera.data.shift_x=0;camera.data.shift_y=0
 ref=next(r for r in json.loads(a.references.read_text()) if r['name']==a.variant);height=(ref['bbox'][3]-ref['bbox'][1])*2;pose(arm,mesh,specs,segments,dragon,'HOLDING',0);render.calibrate_camera(camera,(900,800),534,height,str(a.out/'calibration.png'));camera.data.shift_x+=50/900
 scene.render.fps=30;bpy.ops.file.pack_all();report={'variant':a.variant,'previewOnly':a.probe,'sourceSHA256':digest(a.source),'landmarks':specs,'clips':{},'checks':{}}
 chosen={'HOLDING','MOVING','ATTACK_FRONT','DEATH','MOVE_START','MOVE_END'}
 for gid,count in ref['groups'].items():
  if int(gid) not in GROUP_NAMES:continue
  group=GROUP_NAMES[int(gid)]
  if a.probe and group not in chosen:continue
  arm.animation_data_clear();loop=group in ['HOLDING','MOVING'];seconds=2 if group=='HOLDING' else (1.1 if group=='DEATH' else (.35 if group.startswith(('MOVE_','TURN')) else .85));ticks=round(seconds*30);errors=[]
  for k in range(ticks+1):
   scene.frame_set(k+1);errors.append(pose(arm,mesh,specs,segments,dragon,group,k/ticks))
   if a.variant=='dreadKnight' and group.startswith(('ATTACK','SPECIAL')):
    factor=.44 if group.startswith('SPECIAL') else .70
    for n in ['RArm','RForearm','RHand']:arm.pose.bones[n].rotation_euler=tuple(v*factor for v in arm.pose.bones[n].rotation_euler)
   arm.keyframe_insert('location',frame=k+1)
   for b in arm.pose.bones:
    for field in ['location','rotation_euler','scale']:b.keyframe_insert(field,frame=k+1)
  scene.frame_start=1;scene.frame_end=ticks if loop else ticks+1;scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(a.out/(group.lower()+'.blend')))
  frames=[];n=min(3,count) if a.probe else count
  for i in range(n):
   t=i/(n if loop else max(1,n-1));frame=1+t*ticks;scene.frame_set(math.floor(frame),subframe=frame%1);path=a.out/'sprites2x'/(group.lower()+f'_{i:02}.png');path.parent.mkdir(exist_ok=True);render.render_to(str(path));bounds=render.measure_alpha_bbox(str(path));assert bounds and min(bounds[:2])>0 and bounds[2]<900 and bounds[3]<800, (group,bounds)
   frames.append({'file':str(path.relative_to(a.out)),'frame':frame,'sha256':digest(path),'bbox':bounds})
  report['clips'][group]={'frames':frames,'seconds':seconds,'loop':loop,'maximumReachClamp':max(errors)}
 report['checks']['maximumReachClamp']=max(c['maximumReachClamp'] for c in report['clips'].values());(a.out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copy2(__file__,a.out/Path(__file__).name)
if __name__=='__main__':main()
