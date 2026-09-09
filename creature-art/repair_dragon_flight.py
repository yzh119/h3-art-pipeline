"""Regenerate flight clips from saved dragon rigs after reviewed amplitude changes."""
import bpy,json,sys,math,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import mounted_dragon_motion as motion
root=Path(sys.argv[sys.argv.index('--')+1]);report=json.loads((root/'manifest.json').read_text());assert report['variant'] in ['boneDragon','ghostDragon']
for group in ['MOVING','MOVE_START','MOVE_END']:
 path=root/(group.lower()+'.blend');bpy.ops.wm.open_mainfile(filepath=str(path));scene=bpy.context.scene;arm=scene.objects['CreatureRig'];mesh=scene.objects['Mesh_0'];arm.animation_data_clear();ticks=round(report['clips'][group]['seconds']*30)
 for k in range(ticks+1):
  scene.frame_set(k+1);motion.pose(arm,mesh,{}, {},True,group,k/ticks);arm.keyframe_insert('location',frame=k+1)
  for b in arm.pose.bones:
   for field in ['location','rotation_euler','scale']:b.keyframe_insert(field,frame=k+1)
 scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(path))
 for frame in report['clips'][group]['frames']:
  tick=frame['frame'];scene.frame_set(math.floor(tick),subframe=tick%1);out=root/frame['file'];motion.render.render_to(str(out));frame['sha256']=motion.digest(out);frame['bbox']=motion.render.measure_alpha_bbox(str(out))
report['checks']['reviewedFlightAmplitude']=True;(root/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copy2(Path(motion.__file__),root/'mounted_dragon_motion.py')
