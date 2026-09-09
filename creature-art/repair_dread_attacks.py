"""Bound Dread Knight attack excursions to the reviewed armor skin range."""
import bpy,json,sys,math,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import mounted_dragon_motion as motion
root=Path(sys.argv[sys.argv.index('--')+1]);report=json.loads((root/'manifest.json').read_text());assert report['variant']=='dreadKnight'
for group,clip in report['clips'].items():
 if not group.startswith(('ATTACK','SPECIAL')):continue
 path=root/(group.lower()+'.blend');bpy.ops.wm.open_mainfile(filepath=str(path));scene=bpy.context.scene;arm=scene.objects['CreatureRig'];action=arm.animation_data.action;target=.44 if group.startswith('SPECIAL') else .70;factor=target/clip.get('armorMotionScale',1)
 if abs(factor-1)<1e-8:continue
 for layer in action.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    for c in bag.fcurves:
     if any(c.data_path==f'pose.bones["{n}"].rotation_euler' for n in ['RArm','RForearm','RHand']):
      for k in c.keyframe_points:k.co.y*=factor;k.handle_left.y*=factor;k.handle_right.y*=factor
 scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(path));clip['armorMotionScale']=target
 for frame in clip['frames']:
  tick=frame['frame'];scene.frame_set(math.floor(tick),subframe=tick%1);out=root/frame['file'];motion.render.render_to(str(out));frame['sha256']=motion.digest(out);frame['bbox']=motion.render.measure_alpha_bbox(str(out))
report['checks']['armorAttackRangeRepair']=True;(root/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
