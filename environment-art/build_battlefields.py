"""Package independently redrawn common battlefields at VCMI's exact 2x size."""
import argparse,hashlib,json
from pathlib import Path
from PIL import Image

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--references',type=Path,required=True);p.add_argument('--generated',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if a.out.exists():raise ValueError('Use a new output directory')
 target=a.out/'content/data2x';target.mkdir(parents=True);records=[]
 for ref in json.loads((a.references/'manifest.json').read_text()):
  path=a.generated/(ref['name']+'.png');im=Image.open(path)
  if 'A' in im.getbands() and im.getchannel('A').getextrema()!=(255,255):raise ValueError('Battlefield must be opaque')
  size=tuple(x*2 for x in ref['size']);aspect=im.width/im.height
  if abs(aspect-size[0]/size[1])>.02:raise ValueError('Aspect ratio changed')
  export=im.convert('RGB').resize(size,Image.Resampling.LANCZOS);dest=target/(Path(ref['resource']).stem+'.png');export.save(dest);check=Image.open(dest)
  assert check.size==size and check.mode=='RGB'
  records.append({**ref,'generatedSize':im.size,'outputSize':size,'generatedSHA256':hashlib.sha256(path.read_bytes()).hexdigest(),'outputSHA256':hashlib.sha256(dest.read_bytes()).hexdigest(),'method':'generated detail, resized to exact 2x canvas; not native 3x/4x generation'})
 (a.out/'battle-audit.json').write_text(json.dumps(records,indent=2)+'\n');print('Packaged',len(records),'battlefields')
if __name__=='__main__':main()
