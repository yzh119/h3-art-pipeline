"""Register generated map-town artwork to native canvases and bounds.

Native canvas, body bounds, shadows and DEF frame counts remain fixed.
Generated body alpha replaces the old pixel silhouette. Generated RGB is bounded by its real alpha or a solid magenta key.
"""
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'creature-art'))
import def_extract as defs

def prepare(path):
 im=Image.open(path).convert('RGBA');v=np.array(im)
 if v[:,:,3].min()==255:
  rgb=v[:,:,:3].astype(int);key=(rgb[:,:,0]>rgb[:,:,1]+32)&(rgb[:,:,2]>rgb[:,:,1]+32)
  if key.mean()<.15:raise ValueError(f'{path}: no real transparency or magenta key; refuse checkerboard')
  v[:,:,3]=np.where(key,0,255);im=Image.fromarray(v)
 mask=im.getchannel('A').point(lambda x:255 if x>200 else 0);bounds=mask.getbbox()
 if not bounds:raise ValueError('Empty generated image')
 return im.crop(bounds),bounds

def registered(original,source,scale):
 size=tuple(n*scale for n in original.size);bounds=original.getchannel('A').getbbox()
 x0,y0,x1,y1=[v*scale for v in bounds];art=source.resize((x1-x0,y1-y0),Image.Resampling.LANCZOS)
 layer=Image.new('RGBA',size);layer.paste(art,(x0,y0));return layer


def owner_flags(original, body, scale, capitol):
 # Rebuild native ground pennants as smooth cloth geometry. Keep the pole
 # attachment and footprint; supersample coverage, not the old pixel mask.
 alpha=np.array(original)[:,:,3]; seen=set(); boxes=[]
 for y,x in zip(*np.where(alpha>0)):
  if (x,y) in seen:continue
  stack=[(x,y)];seen.add((x,y));component=[]
  while stack:
   px,py=stack.pop();component.append((px,py))
   for nx,ny in [(px-1,py),(px+1,py),(px,py-1),(px,py+1)]:
    if 0<=nx<original.width and 0<=ny<original.height and alpha[ny,nx] and (nx,ny) not in seen:
     seen.add((nx,ny));stack.append((nx,ny))
  xs,ys=zip(*component);boxes.append((min(xs),min(ys),max(xs)+1,max(ys)+1))
 high=8; mask=Image.new('L',(original.width*scale*high,original.height*scale*high));draw=ImageDraw.Draw(mask)
 for x0,y0,x1,y1 in boxes:
  if y0<original.height//2:continue
  right=alpha[y0,x0]>0
  points=[(0,0),(.40,.10),(1,.50),(.40,.90),(0,1),(.10,.50)]
  points=[((x0+(u if right else 1-u)*(x1-x0))*scale*high,(y0+v*(y1-y0))*scale*high) for u,v in points]
  draw.polygon(points,fill=255)
 mask=mask.resize(body.size,Image.Resampling.LANCZOS)
 arr=np.zeros((body.height,body.width,4),dtype=np.uint8)
 yy=np.arange(body.height)[:,None]/scale
 shade=np.broadcast_to(220+30*np.cos(yy*1.4),(body.height,body.width)).astype(np.uint8)
 arr[:,:,:3]=shade[:,:,None];arr[:,:,3]=np.array(mask)
 if capitol:
  rgb=np.array(body)[:,:,:3].astype(float);a=np.array(body)[:,:,3]
  coverage=np.clip(np.minimum(rgb[:,:,0]-rgb[:,:,2]-20,rgb[:,:,1]-rgb[:,:,2]-12)/20,0,1)*a
  coverage[int(original.height*scale*.09):,:]=0
  assert coverage.max()>200
  top=coverage>0;arr[top,:3]=np.clip(rgb[top].mean(axis=1)*1.15,130,255).astype(np.uint8)[:,None];arr[top,3]=coverage[top].astype(np.uint8)
 return Image.fromarray(arr)


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,required=True);p.add_argument('--generated',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--variants',nargs='+',default=['village','fort','capitol']);a=p.parse_args()
 if a.out.exists():raise ValueError('Use a fresh output directory')
 a.out.mkdir(parents=True);lod,index=defs.read_lod(a.data/'H3sprite.lod');records=[]
 for name in a.variants:
  res={'village':'AVCNECR0','fort':'AVCNECX0','capitol':'AVCNECZ0'}[name];raw=defs.extract(lod,index,res+'.DEF');definition=defs.DefFile(raw);source,crop=prepare(a.generated/(name+'.png'))
  for scale in [2,3,4]:
   sprites=a.out/f'content/sprites{scale}x';target=sprites/'necropolis-map'/res;target.mkdir(parents=True);seq=[]
   for group,frames in definition.groups.items():
    names=[]
    for frame in range(len(frames)):
     header,rows=definition.frame_indices(group,frame);size=(header['fullWidth'],header['fullHeight']);layers=defs.split_layers(defs.to_canvas(header,rows),definition.palette);stem=f'{group}_{frame}';names.append(stem+'.png')
     for suffix,pixels in zip(['','-shadow','-overlay'],layers):
      original=Image.frombytes('RGBA',size,bytes(pixels))
      if not suffix:image=registered(original,source,scale)
      else:
       image=original.resize(tuple(n*scale for n in size),Image.Resampling.NEAREST)
       if suffix=='-overlay':image=owner_flags(original,Image.open(target/(stem+'.png')),scale,name=='capitol')
      path=target/(stem+suffix+'.png');image.save(path);check=Image.open(path)
      assert check.size==tuple(n*scale for n in size)
      if not suffix:
       bounds=check.getbbox();native=tuple(v*scale for v in original.getbbox());assert all(abs(a-b)<=scale for a,b in zip(bounds,native))
       rgba=np.array(check);assert not ((rgba[:,:,0]>rgba[:,:,1].astype(int)+40)&(rgba[:,:,2]>rgba[:,:,1].astype(int)+40)&(rgba[:,:,3]>200)).any()
      if suffix=='-shadow':assert check.tobytes()==original.resize(check.size,Image.Resampling.NEAREST).tobytes()
      if suffix=='-overlay':assert check.getchannel('A').getbbox() is not None
    seq.append({'group':group,'frames':names})
   (sprites/(res+'.json')).write_text(json.dumps({'basepath':f'necropolis-map/{res}/','sequences':seq},indent=2)+'\n')
  records.append({'name':name,'resource':res,'nativeSHA256':hashlib.sha256(raw).hexdigest(),'generatedSHA256':hashlib.sha256((a.generated/(name+'.png')).read_bytes()).hexdigest(),'generatedCrop':crop,'scales':[2,3,4],'canvasBoundsAndEffects':'passed','bodyAlpha':'generated transparent edge; native game footprint config unchanged','ownerOverlay':'supersampled ground pennants at native pole attachments; capitol top follows generated gold with soft coverage'})
 (a.out/'map-audit.json').write_text(json.dumps(records,indent=2)+'\n');print(json.dumps(records))
if __name__=='__main__':main()
