#!/usr/bin/env python3
"""Append complete native-count creature exports to a copied graphical mod.

Pillow and NumPy required. Derives 1x bodies from 2x and bakes fixed-ground shadows
and idle hover outlines. Existing resources are never silently replaced.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

from new_creature_mod import layout_from_def, build_animation
from stabilize_shadows import project_shadow
from vcmi_anim import GROUP_NAMES, OVERLAY_GROUPS


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def outline(alpha):
    values=np.asarray(alpha)
    padded=np.pad(values,1)
    neighbors=np.maximum.reduce([padded[:-2,1:-1],padded[2:,1:-1],
                                  padded[1:-1,:-2],padded[1:-1,2:]])
    return Image.fromarray(np.where(values==0,neighbors,0).astype('uint8'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-mod',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--lod',type=Path,required=True)
    p.add_argument('--unit',action='append',required=True,help='CWSKEL=EXPORT_DIRECTORY=267')
    p.add_argument('--version',required=True)
    p.add_argument('--motion-check',action='append',default=[],help='CREATURE=REOPENED_CHECK_JSON')
    args=p.parse_args()
    if args.out.exists():raise ValueError('Output must be new')
    shutil.copytree(args.source_mod,args.out)
    checks=dict(x.split('=',1) for x in args.motion_check)
    report={'toolSHA256':digest(Path(__file__)),'shadowToolSHA256':digest(Path(__file__).with_name('stabilize_shadows.py')),
            'units':[]}
    for spec in args.unit:
        creature,directory,ground=spec.split('=');creature=creature.upper();directory=Path(directory);ground=float(ground)
        export=json.loads((directory/'manifest.json').read_text())
        if export.get('previewOnly') or export.get('artisticallyRejected'):
            raise ValueError(f'Incomplete or rejected appearance export: {directory}')
        if creature in checks:
            checked=json.loads(Path(checks[creature]).read_text())
            if checked['largeStretchedEdges'] or checked['sourceManifestSHA256']!=digest(directory/'manifest.json'):raise ValueError('Missing or stale deformation check')
            for sample in checked['samples']:
                scene=directory/(sample['group'].lower()+'.blend')
                if digest(scene)!=sample['sceneSHA256'] or sample['minimumZ']<-.002:raise ValueError('Changed scene or ground penetration')
        layout,canvas,skipped=layout_from_def(args.lod,creature)
        config=build_animation(creature,layout,'creatures/'+creature.lower()+'/',0,False)
        unit={'creature':creature,'sourceManifestSHA256':digest(directory/'manifest.json'),
              'ground':ground,'groups':layout,'canvas':canvas,'files':[]}
        for scale in [1,2]:
            folder=args.out/'content'/('Sprites' if scale==1 else 'Sprites2x')
            target=folder/(creature+'.json')
            if target.exists():raise ValueError(f'Existing creature: {creature}')
            target.write_text(json.dumps(config,indent=2)+'\n')
            (folder/config['basepath']).mkdir(parents=True)
        for gid,count in layout.items():
            for i in range(count):
                name=GROUP_NAMES[gid].lower()+'_%02d'%i
                source=directory/'sprites2x'/(name+'.png')
                entry=export['clips'][GROUP_NAMES[gid]]['frames'][i]
                if len(export['clips'][GROUP_NAMES[gid]]['frames'])!=count or digest(source)!=entry['sha256']:raise ValueError('Frame count/hash mismatch')
                body=Image.open(source).convert('RGBA')
                if body.size!=(canvas[0]*2,canvas[1]*2):raise ValueError(f'Wrong canvas: {source}')
                bbox=body.getchannel('A').getbbox()
                if not bbox or bbox[0]<=0 or bbox[1]<=0 or bbox[2]>=body.width or bbox[3]>=body.height:
                    raise ValueError(f'Empty/clipped body: {source}')
                shadow=project_shadow(body.getchannel('A'),ground)
                for scale in [1,2]:
                    folder=args.out/'content'/('Sprites' if scale==1 else 'Sprites2x')/config['basepath']
                    image=body if scale==2 else body.resize(canvas,Image.Resampling.LANCZOS)
                    path=folder/(name+'.png')
                    if scale==2:shutil.copy2(source,path)
                    else:image.save(path)
                    a=shadow if scale==2 else shadow.resize(canvas,Image.Resampling.LANCZOS)
                    layer=Image.new('RGBA',image.size);layer.putalpha(a)
                    layer.save(folder/(name+'-shadow.png'))
                    if gid in OVERLAY_GROUPS:
                        layer=Image.new('RGBA',image.size,(255,255,255,0))
                        layer.putalpha(outline(image.getchannel('A')))
                        layer.save(folder/(name+'-overlay.png'))
                    for target in sorted(folder.glob(name+'*.png')):
                        unit['files'].append({'file':str(target.relative_to(args.out)),'sha256':digest(target)})
        report['units'].append(unit)
    for source in args.source_mod.rglob('*'):
        if source.is_file() and digest(source)!=digest(args.out/source.relative_to(args.source_mod)):
            raise ValueError(f'Existing mod file changed: {source}')
    metadata=args.out/'mod.json';config=json.loads(metadata.read_text());config['version']=args.version
    config['description']='Necropolis creature graphics with native animation groups, precomputed stable-ground effects, registered canvases, and HD showcase backgrounds.'
    metadata.write_text(json.dumps(config,indent=2)+'\n')
    (args.out/('roster-provenance-'+args.version+'.json')).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'addedCreatures':[u['creature'] for u in report['units']],
                      'bodyFrames':sum(sum(u['groups'].values())*2 for u in report['units'])}))


if __name__=='__main__':main()
