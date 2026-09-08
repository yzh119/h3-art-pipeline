"""Extract native common battlefield images for an external art workspace."""
import argparse,hashlib,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'creature-art'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'town-art'))
import def_extract as defs
from export_necropolis_reference import pcx

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,required=True);p.add_argument('--config',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if a.out.exists():raise ValueError('Use a new output directory')
 config=json.loads(re.sub(r'//[^\n]*','',a.config.read_text()));names=['dirt_birches','dirt_hills','dirt_pines','sand_mesas','sand_shore','grass_hills','grass_pines','snow_mountains','snow_trees','swamp_trees','rough','subterranean','lava','ship']
 lod,index=defs.read_lod(a.data/'H3bitmap.lod');a.out.mkdir(parents=True);records=[]
 for name in names:
  resource=config[name]['graphics'];raw=defs.extract(lod,index,Path(resource).stem+'.PCX');im=pcx(raw);im.save(a.out/(name+'.png'));records.append(dict(name=name,resource=resource,size=im.size,sha256=hashlib.sha256(raw).hexdigest()))
 (a.out/'manifest.json').write_text(json.dumps(records,indent=2)+'\n');print(json.dumps(records,indent=2))
if __name__=='__main__':main()
