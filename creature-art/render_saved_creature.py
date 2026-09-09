#!/usr/bin/env python3
"""Render every native frame from checked, already-authored creature scenes.

Separates inexpensive pose checks from rendering. Never edits source scenes.
Run in Blender after check_nonhumanoid_motion.py has accepted the staged export.
"""
import argparse,hashlib,json,math,shutil,sys
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from mounted_dragon_motion import digest
import render_sprites as render

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--check',type=Path,required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
 report=json.loads((a.source/'manifest.json').read_text());check=json.loads(a.check.read_text())
 if not report.get('pendingRenders') or not all(c.get('sharedArmRepair') for c in report['clips'].values()):raise ValueError('Expected a complete staged scene export')
 if check['sourceManifestSHA256']!=digest(a.source/'manifest.json') or check['largeStretchedEdges']:raise ValueError('Missing or stale passing pose check')
 samples={r['group']:r for r in check['samples']}
 for name in report['clips']:
  if digest(a.source/(name.lower()+'.blend'))!=samples[name]['sceneSHA256'] or samples[name]['minimumZ']<-.002:raise ValueError('Changed scene or ground penetration')
 if a.out.exists():raise ValueError('Use a new output directory')
 shutil.copytree(a.source,a.out,ignore=shutil.ignore_patterns('*.blend1'))
 for name,clip in report['clips'].items():
  path=a.out/(name.lower()+'.blend');bpy.ops.wm.open_mainfile(filepath=str(path));scene=bpy.context.scene
  for frame in clip['frames']:
   tick=frame['frame'];scene.frame_set(math.floor(tick),subframe=tick%1);target=a.out/frame['file'];render.render_to(str(target));bounds=render.measure_alpha_bbox(str(target))
   if not bounds or min(bounds[:2])<=0 or bounds[2]>=scene.render.resolution_x or bounds[3]>=scene.render.resolution_y:raise ValueError('Empty or clipped frame')
   frame.update(sha256=digest(target),bbox=bounds)
 report['pendingRenders']=False;report['previewOnly']=False;report['checks']['stagedPoseCheckSHA256']=digest(a.check);report['checks']['renderToolSHA256']=digest(Path(__file__));(a.out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copy2(__file__,a.out/Path(__file__).name)
if __name__=='__main__':main()
