#!/usr/bin/env python3
"""Request a Meshy humanoid rig for a completed textured mesh task.

Footless ghosts and other non-bipedal assets need separate local controls.
Persists the task ID before polling; --resume never submits another paid task.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import urllib.request
import gen_mesh


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-meta',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--height',type=float,default=1.7);p.add_argument('--resume',action='store_true')
    args=p.parse_args();key=os.environ.get('MESHY_API_KEY')
    if not key:p.error('MESHY_API_KEY is not set')
    if args.height<=0:p.error('Height must be positive')
    gen_mesh.API='https://api.meshy.ai/openapi/v1/rigging'
    pending=args.out.with_suffix('.pending.json');model=args.out.with_suffix('.glb')
    if model.exists():p.error('Output model already exists')
    if args.resume:
        record=json.loads(pending.read_text());task_id=record['task_id']
    else:
        if pending.exists():p.error('Task already submitted; use --resume')
        payload={'input_task_id':json.loads(args.input_meta.read_text())['task_id'],'height_meters':args.height}
        task_id=gen_mesh.request(gen_mesh.API,key,payload)['result']
        record={'task_id':task_id,'parameters':payload};pending.parent.mkdir(parents=True,exist_ok=True)
        pending.write_text(json.dumps(record,indent=2)+'\n')
    print('rig task '+task_id,flush=True);task=gen_mesh.poll(task_id,key)
    url=task['result']['rigged_character_glb_url']
    with urllib.request.urlopen(url,timeout=300) as response:model.write_bytes(response.read())
    record.update({'status':task['status'],'consumed_credits':task.get('consumed_credits'),'sha256':hashlib.sha256(model.read_bytes()).hexdigest()})
    args.out.with_suffix('.json').write_text(json.dumps(record,indent=2)+'\n')
    print(str(model)+' credits='+str(record['consumed_credits']),flush=True)


if __name__=='__main__':main()
