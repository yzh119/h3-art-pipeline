"""Regenerate mounted move transitions from saved rigs, matching idle/gait endpoints."""
import bpy,numpy as np,json,sys,math,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import mounted_dragon_motion as motion
root=Path(sys.argv[sys.argv.index('--')+1]);report=json.loads((root/'manifest.json').read_text());assert report['variant'] in ['blackKnight','dreadKnight']
for group in ['MOVE_START','MOVE_END']:
 path=root/(group.lower()+'.blend');bpy.ops.wm.open_mainfile(filepath=str(path));scene=bpy.context.scene;arm=scene.objects['CreatureRig'];mesh=scene.objects['Mesh_0'];specs=report['landmarks'];segments={}
 for s in ['R','L']:
  for part in ['Front','Hind']:
   prefix=s+part
   for a,b in [('Upper','Lower'),('Lower','Foot')]:segments[prefix+a]=(np.array(arm.data.bones[prefix+a].head_local),np.array(arm.data.bones[prefix+b].head_local))
 arm.animation_data_clear();ticks=scene.frame_end-1
 for k in range(ticks+1):
  scene.frame_set(k+1);motion.pose(arm,mesh,specs,segments,False,group,k/ticks);arm.keyframe_insert('location',frame=k+1)
  for b in arm.pose.bones:
   for field in ['location','rotation_euler','scale']:b.keyframe_insert(field,frame=k+1)
 scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(path))
 for frame in report['clips'][group]['frames']:
  tick=frame['frame'];scene.frame_set(math.floor(tick),subframe=tick%1);out=root/frame['file'];motion.render.render_to(str(out));frame['sha256']=motion.digest(out);frame['bbox']=motion.render.measure_alpha_bbox(str(out))
report['checks']['mountedTransitionPoseRepair']=True;(root/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copy2(Path(motion.__file__),root/'mounted_dragon_motion.py')
