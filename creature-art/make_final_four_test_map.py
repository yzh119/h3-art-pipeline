"""Create an isolated eight-tile diagnostic map from VCMI's MiniTest fixture."""
import argparse,json,zipfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--vcmi',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();assert not a.out.exists()
source=a.vcmi/'test/testdata/vcmi-test/content/test/MiniTest';header=json.loads((source/'header.json').read_text());objects=json.loads((source/'objects.json').read_text());header['name']='Necropolis final four animation check';header['description']='Isolated art diagnostic. Two adjacent armies; no changes to normal maps.'
for i,color in enumerate(['red','blue']):
 hero=objects[f'hero_{i}'];hero['x']=2+i*2;hero['y']=3;hero['options']['army']=[{'type':'core:'+n,'amount':12 if color=='red' else 5} for n in ['blackKnight','dreadKnight','boneDragon','ghostDragon']]+[{},{},{}];header['players'][color]['mainHero']=f'hero_{i}';header['players'][color]['heroes']={f'hero_{i}':{'type':hero['options']['type']}}
a.out.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(a.out,'w',zipfile.ZIP_DEFLATED) as z:
 for n,d in [('header.json',header),('objects.json',objects),('surface_terrain.json',json.loads((source/'surface_terrain.json').read_text()))]:z.writestr(n,json.dumps(d))
print(a.out)
