#!/usr/bin/env python3
"""Combine complete humanoid and flight exports after native-count verification."""
import argparse,hashlib,json,shutil
from pathlib import Path
from PIL import Image
import numpy as np
from vcmi_anim import GROUP_NAMES


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--human',type=Path,required=True);p.add_argument('--flight',type=Path,required=True);p.add_argument('--references',type=Path,required=True)
    p.add_argument('--variant',choices=['vampire','vampireLord'],required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--skin-checks',type=Path,required=True)
    args=p.parse_args()
    if args.out.exists():raise ValueError('Use fresh output directory')
    reference=next(r for r in json.loads(args.references.read_text()) if r['name']==args.variant)
    sources=[(folder,json.loads((folder/'manifest.json').read_text())) for folder in (args.human,args.flight)]
    checks=sources[0][1]['checks']
    if checks['maximumSavedIKError']>.008 or checks['minimumDeathZ']<-.002:raise ValueError('Humanoid constraint failure')
    if any(m.get('artisticallyRejected') for _,m in sources):raise ValueError('Rejected source')
    skin=json.loads(args.skin_checks.read_text())
    if skin['largeStretchedEdges']:raise ValueError('Skin deformation check failed')
    checked={r['scene']:r['sourceSHA256'] for r in skin['samples']}
    for scene in args.human.glob('*.blend'):
        if checked.get(scene.name)!=digest(scene):raise ValueError(f'Missing/stale skin check: {scene.name}')
    clips={};pending=[]
    for gid,count in reference['groups'].items():
        group=GROUP_NAMES.get(int(gid))
        if not group:continue
        matches=[(folder,m['clips'][group]) for folder,m in sources if group in m['clips']]
        if len(matches)!=1:raise ValueError(f'Missing/ambiguous group {group}')
        folder,clip=matches[0]
        if len(clip['frames'])!=count:raise ValueError(f'Native count mismatch {group}')
        clip=json.loads(json.dumps(clip));clips[group]=clip
        for i,frame in enumerate(clip['frames']):
            path=folder/frame['file'];expected=f'sprites2x/{group.lower()}_{i:02}.png'
            if frame['file']!=expected or digest(path)!=frame['sha256']:raise ValueError(f'Source frame mismatch {path}')
            with Image.open(path) as im:
                box=im.getchannel('A').getbbox()
                if im.size!=(900,800) or not box or min(box[:2])<=0 or box[2]>=900 or box[3]>=800:raise ValueError('Bad canvas or alpha')
            pending.append((path,expected))
    # Separate scene renders have small path-sampling differences despite
    # identical silhouettes. Verify joins, then use one canonical endpoint PNG.
    flight=args.flight/'sprites2x';human=args.human/'sprites2x'
    joins=[(flight/'move_start_04.png',flight/'moving_00.png'),
           (flight/'move_end_00.png',flight/'moving_00.png'),
           (flight/'move_start_00.png',human/'holding_00.png'),
           (flight/'move_end_04.png',human/'holding_00.png')]
    endpoint_checks=[]
    for a,b in joins:
        x=np.array(Image.open(a).convert('RGBA'));y=np.array(Image.open(b).convert('RGBA'))
        if not np.array_equal(x[:,:,3],y[:,:,3]):raise ValueError(f'Transition silhouette mismatch {a.name}/{b.name}')
        mask=y[:,:,3]>0;error=float(np.abs(x[:,:,:3].astype(float)-y[:,:,:3])[mask].mean())
        if error>3:raise ValueError(f'Transition color mismatch {error}')
        endpoint_checks.append({'frame':a.name,'canonical':b.name,'preCanonicalRGBMeanError':error})
    args.out.mkdir(parents=True);(args.out/'sprites2x').mkdir()
    for path,rel in pending:shutil.copy2(path,args.out/rel)
    for target,canonical in joins:
        path=args.out/'sprites2x'/target.name;shutil.copy2(canonical,path)
        for clip in clips.values():
            for frame in clip['frames']:
                if Path(frame['file']).name==target.name:
                    frame['sourceSHA256']=frame['sha256'];frame['sha256']=digest(path)
    for folder,_ in sources:
        for path in folder.glob('*.blend'):shutil.copy2(path,args.out/path.name)
    report={'variant':args.variant,'previewOnly':False,'clips':clips,'checks':checks,'nativeCountsVerified':True,'skinChecksSHA256':digest(args.skin_checks),'skinCheckSamples':len(skin['samples']),'transitionEndpointsMatch':True,'endpointCanonicalization':endpoint_checks,'sources':[{'manifestSHA256':digest(f/'manifest.json')} for f,_ in sources]}
    (args.out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'variant':args.variant,'groups':len(clips),'frames':len(pending)}))

if __name__=='__main__':main()
