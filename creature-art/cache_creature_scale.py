"""Precompute a display-scale cache from 2x sprites; does not add source detail."""
import argparse,json,hashlib
from pathlib import Path
from PIL import Image
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mod',type=Path,required=True);p.add_argument('--scale',type=int,choices=[3,4],default=3);p.add_argument('--unit',action='append',required=True);a=p.parse_args();root=a.mod/'content';out=root/f'Sprites{a.scale}x';out.mkdir(exist_ok=True);records=[]
for unit in a.unit:
 unit=unit.upper();layout=root/'Sprites2x'/(unit+'.json');data=json.loads(layout.read_text());target=out/(unit+'.json');assert not target.exists();target.write_bytes(layout.read_bytes());dest=out/data['basepath'];dest.mkdir(parents=True)
 for path in sorted((root/'Sprites2x'/data['basepath']).glob('*.png')):
  im=Image.open(path).convert('RGBA');size=(im.width*a.scale//2,im.height*a.scale//2);image=im.resize(size,Image.Resampling.LANCZOS);output=dest/path.name;image.save(output);records.append({'file':str(output.relative_to(a.mod)),'sourceSHA256':hashlib.sha256(path.read_bytes()).hexdigest(),'outputSHA256':hashlib.sha256(output.read_bytes()).hexdigest()})
(a.mod/f'display-cache-{a.scale}x.json').write_text(json.dumps({'method':'Lanczos cache of 2x artwork, not native higher-resolution rendering','files':records},indent=2)+'\n');print('Cached',len(records),'images')
