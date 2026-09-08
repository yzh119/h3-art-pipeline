#!/usr/bin/env python3
"""Prepare padded square original references for individual building edits."""
import argparse
import json
from pathlib import Path
import sys

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'creature-art'))
import def_extract as defs


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data', type=Path, required=True)
    ap.add_argument('--baseline', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    if args.out.exists():
        raise ValueError('Output must not exist')
    (args.out / 'inputs').mkdir(parents=True)
    (args.out / 'generated').mkdir()
    manifest = json.loads((args.baseline / 'manifest.json').read_text())
    data, index = defs.read_lod(args.data / 'H3sprite.lod')
    jobs = []
    for spec in manifest['structures']:
        if spec['name'] == 'castle':
            continue  # Already refined in the baseline.
        definition = defs.DefFile(defs.extract(data, index, spec['animation']))
        head, rows = definition.frame_indices(0, 0)
        canvas = defs.to_canvas(head, rows)
        size = (head['fullWidth'], head['fullHeight'])
        rgba = bytes(v for row in canvas for i in row for v in
                     ((*definition.palette[i], 255) if i else (0, 0, 0, 0)))
        original = Image.frombytes('RGBA', size, rgba)
        original.save(args.out / 'inputs' / (spec['name'] + '-original.png'))
        side = max(size) + 48
        reference = Image.new('RGB', (side, side), (255, 0, 255))
        reference.paste(original, (24, 24), original)
        reference.resize((1024, 1024), Image.Resampling.NEAREST).save(args.out / 'inputs' / (spec['name'] + '.png'))
        jobs.append({'name': spec['name'], 'size': size, 'side': side,
                     'offset': [24, 24], 'frames': spec['groups']['0']})
    (args.out / 'jobs.json').write_text(json.dumps(jobs, indent=2) + '\n')


if __name__ == '__main__':
    main()
