#!/usr/bin/env python3
"""Extract vanilla Necropolis references; compose layers without changing pixels.

The assembled town is a fully upgraded reference layout, not an engine screenshot.
Generated art belongs outside this repository. Requires Pillow.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'creature-art'))
import def_extract as defs


def pcx(data):
    size,width,height=struct.unpack_from('<III',data)
    if size==width*height*3:
        return Image.frombytes('RGB',(width,height),data[12:12+size],'raw','BGR')
    if size!=width*height:raise ValueError('Unrecognized H3 PCX')
    im=Image.frombytes('P',(width,height),data[12:12+size]);im.putpalette(data[-768:]);return im.convert('RGB')


def frame(data):
    definition=defs.DefFile(data);gid=min(definition.groups)
    head,rows=definition.frame_indices(gid,0);canvas=defs.to_canvas(head,rows)
    rgba=bytes(c for row in canvas for i in row for c in (defs.SPECIAL_PALETTE[i] if i<8 else (*definition.palette[i],255)))
    return Image.frombytes('RGBA',(head['fullWidth'],head['fullHeight']),rgba), {str(g):len(f) for g,f in definition.groups.items()}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--data',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--faction-config',type=Path,default=Path(__file__).resolve().parents[1]/'reference-config/necropolis.json');args=ap.parse_args()
    if args.out.exists() and any(args.out.iterdir()):raise ValueError('Output must be empty')
    args.out.mkdir(parents=True,exist_ok=True)
    bitmap,bi=defs.read_lod(args.data/'H3bitmap.lod');sprite,si=defs.read_lod(args.data/'H3sprite.lod')
    raw=defs.extract(bitmap,bi,'TBNCBACK.PCX');background=pcx(raw);background.save(args.out/'town-background.png');town=background.convert('RGBA')
    text=args.faction_config.read_text()
    config=json.loads(re.sub(r'//[^\n]*','',text))['necropolis']['town']
    names=['extraAnimation','mageGuild5','tavern','shipyard','castle','capitol','marketplace','resourceSilo','blacksmith','special1','special2','special3','grail','extraTownHall','extraCityHall','extraCapitol']+[f'dwellingUpLvl{i}' for i in range(1,8)]
    layers=[]
    for name in names:
        spec=config['structures'][name];image,counts=frame(defs.extract(sprite,si,spec['animation']))
        image.save(args.out/(name+'.png'));layers.append((name,spec,image,counts))
    # CBuildingRect compares z only; equal-z ordering in this offline reference
    # is selection order and is not a claim about a particular engine state.
    for name,spec,image,counts in sorted(layers,key=lambda row:row[1].get('z',0)):town.alpha_composite(image,(spec['x'],spec['y']))
    town.convert('RGB').save(args.out/'town-full-reference.png')
    manifest={'background':{'resource':'TBNCBACK.PCX','size':list(background.size),'sha256':hashlib.sha256(raw).hexdigest()},'structures':[{'name':name,'resource':spec['animation'],'position':[spec['x'],spec['y']],'z':spec.get('z',0),'size':list(im.size),'frames':counts} for name,spec,im,counts in layers],'map':{}}
    for label,name in [('village','AVCNECR0.DEF'),('fort','AVCNECX0.DEF'),('capitol','AVCNECZ0.DEF')]:
        image,counts=frame(defs.extract(sprite,si,name));image.save(args.out/('map-'+label+'.png'));manifest['map'][label]={'resource':name,'size':list(image.size),'frames':counts}
    (args.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'town':background.size,'layers':len(layers),'map':manifest['map']},indent=2))


if __name__=='__main__':main()
