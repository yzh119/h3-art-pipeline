#!/usr/bin/env python3
"""Reduce a completed Meshy model before rigging; retain recoverable task IDs.

Requires MESHY_API_KEY. New submissions consume account credits. Use --resume
with the same output prefix after an interrupted poll or download.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import urllib.request
import gen_mesh

API = 'https://api.meshy.ai/openapi/v1/remesh'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-meta', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--polycount', type=int, default=50000)
    parser.add_argument('--topology', choices=['quad', 'triangle'], default='quad')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args(argv)
    if not 100 <= args.polycount <= 300000:
        parser.error('Polycount must be between 100 and 300000')
    key = os.environ.get('MESHY_API_KEY')
    if not key:
        parser.error('MESHY_API_KEY is not set')
    pending = args.out.with_suffix('.pending.json')
    target = args.out.with_suffix('.glb')
    if target.exists():
        parser.error('Output model already exists')
    if pending.exists() and not args.resume:
        parser.error('Task already submitted; use --resume')
    if args.resume and not pending.exists():
        parser.error('No pending task to resume')
    source = json.loads(args.input_meta.read_text())['task_id']
    if args.resume:
        record = json.loads(pending.read_text())
        if record['parameters']['input_task_id'] != source:
            parser.error('Resume input task differs from submitted source')
    else:
        parameters = {'input_task_id': source, 'target_formats': ['glb'],
                      'topology': args.topology, 'target_polycount': args.polycount}
        args.out.parent.mkdir(parents=True, exist_ok=True)
        record = {'task_id': gen_mesh.request(API, key, parameters)['result'],
                  'parameters': parameters}
        pending.write_text(json.dumps(record, indent=2) + '\n')
    print('remesh task ' + record['task_id'], flush=True)
    previous_api = gen_mesh.API
    try:
        gen_mesh.API = API
        task = gen_mesh.poll(record['task_id'], key)
    finally:
        gen_mesh.API = previous_api
    # Complete download before exposing the final output path.
    temporary = target.with_suffix('.glb.part')
    with urllib.request.urlopen(task['model_urls']['glb'], timeout=300) as response:
        temporary.write_bytes(response.read())
    record.update(status=task['status'], consumed_credits=task.get('consumed_credits'),
                  sha256=hashlib.sha256(temporary.read_bytes()).hexdigest())
    args.out.with_suffix('.json').write_text(json.dumps(record, indent=2) + '\n')
    temporary.replace(target)
    print(str(target), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
