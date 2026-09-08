#!/usr/bin/env python3
"""Extract native roster dimensions and group counts from the user's H3 data."""
import argparse,json
from pathlib import Path
from def_extract import read_lod,extract,DefFile,to_canvas,content_bbox


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lod',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--roster',type=Path,default=Path(__file__).with_name('docs')/'roster-necropolis.json')
    args=p.parse_args()
    if args.out.exists():raise ValueError('Output already exists')
    blob,entries=read_lod(args.lod);result=[]
    for unit in json.loads(args.roster.read_text())['creatures']:
        data=DefFile(extract(blob,entries,unit['def']));head,rows=data.frame_indices(2,0)
        result.append({'name':unit['name'],'def':unit['def'],'canvas':[head['fullWidth'],head['fullHeight']],'bbox':content_bbox(to_canvas(head,rows)),'groups':{str(k):len(v) for k,v in data.groups.items()}})
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
