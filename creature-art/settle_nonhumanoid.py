"""Correct whole-model ground support in saved scenes and matching orthographic PNGs.

Blender: -- SOURCE OUT. Then Python: --apply-images OUT. Original exports retained.
PNG shifts are valid for these orthographic scenes with directional/ambient light;
this does not support perspective, point lights or rendered contact shadows.
"""
import json,math,sys,shutil,hashlib
from pathlib import Path

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def apply_images(root):
 from PIL import Image
 report=json.loads((root/'manifest.json').read_text());support=json.loads((root/'support.json').read_text())
 if report['checks'].get('supportSHA256'):raise ValueError('Image support correction already applied')
 for group,clip in report['clips'].items():
  for frame,shift in zip(clip['frames'],support[group]['imageShifts']):
   path=root/frame['file'];im=Image.open(path).convert('RGBA');image=im.transform(im.size,Image.Transform.AFFINE,(1,0,0,0,1,shift['pixelsUp']),resample=Image.Resampling.BICUBIC);image.save(path);frame['sha256']=digest(path);frame['bbox']=image.getbbox();assert frame['bbox'] and min(frame['bbox'][:2])>0 and frame['bbox'][2]<900 and frame['bbox'][3]<800
 report['checks']['groundSupport']='reopened scene root corrected at every integer tick; PNG translated by projected root difference';report['checks']['supportSHA256']=digest(root/'support.json');(root/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')

def scenes(source,out):
 import bpy
 from mathutils import Vector
 assert not out.exists();shutil.copytree(source,out,ignore=shutil.ignore_patterns('*.blend1'));report=json.loads((out/'manifest.json').read_text());support={};bpy.context.preferences.filepaths.save_version=0
 for group,clip in report['clips'].items():
  path=out/(group.lower()+'.blend');bpy.ops.wm.open_mainfile(filepath=str(path));scene=bpy.context.scene;arm=scene.objects['CreatureRig'];obj=scene.objects['Mesh_0'];supportRoot=bpy.data.objects.new('GroundSupport',None);scene.collection.objects.link(supportRoot);arm.parent=supportRoot;obj.parent=supportRoot;corrections=[];native=[]
  def at(frame):scene.frame_set(math.floor(frame),subframe=frame%1)
  for frame in clip['frames']:at(frame['frame']);native.append(float(supportRoot.location.z))
  last=max(scene.frame_end,math.ceil(max(f['frame'] for f in clip['frames'])))
  for tick in range(scene.frame_start,last+1):
   at(tick);evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh();low=min(v.co.z for v in mesh.vertices);evaluated.to_mesh_clear();delta=(.008-low if group=='DEATH' else max(0,.008-low));corrections.append((tick,float(supportRoot.location.z)+delta))
  for tick,z in corrections:supportRoot.location.z=z;supportRoot.keyframe_insert('location',index=2,frame=tick)
  # Avoid support overshoot between tightly sampled keys.
  action=supportRoot.animation_data.action
  for layer in action.layers:
   for strip in layer.strips:
    for bag in strip.channelbags:
     for curve in bag.fcurves:
      if curve.data_path=='location' and curve.array_index==2:
       for k in curve.keyframe_points:k.interpolation='LINEAR'
  pixels=[];camera=scene.camera;direction=camera.rotation_euler.to_matrix().transposed()@Vector((0,0,1));ppu=scene.render.resolution_x/camera.data.ortho_scale
  for old,frame in zip(native,clip['frames']):at(frame['frame']);delta=float(supportRoot.location.z)-old;pixels.append({'frame':frame['frame'],'worldZ':delta,'pixelsUp':delta*direction.y*ppu})
  at(1);bpy.ops.wm.save_as_mainfile(filepath=str(path));support[group]={'rootKeys':corrections,'imageShifts':pixels}
 (out/'support.json').write_text(json.dumps(support,indent=2)+'\n')

if __name__=='__main__':
 if '--apply-images' in sys.argv:apply_images(Path(sys.argv[sys.argv.index('--apply-images')+1]))
 else:
  i=sys.argv.index('--');scenes(Path(sys.argv[i+1]),Path(sys.argv[i+2]))
