#!/usr/bin/env python3
"""Translate one creature's PNGs inside fixed canvases, without engine changes.

Copies a source mod to a new directory. Uses logical pixel offsets at every
scale, rejects clipped visible pixels, and records all changed frame hashes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from PIL import Image

from vcmi_anim import SCALE_DIRS, load_json


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source-mod', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--creature', required=True)
    ap.add_argument('--offset-x', type=int, required=True)
    ap.add_argument('--offset-y', type=int, default=0)
    args = ap.parse_args()
    if args.out.exists():
        raise ValueError('Output must not exist')
    shutil.copytree(args.source_mod, args.out)
    report = []
    for scale, folder in SCALE_DIRS.items():
        animation = args.source_mod / 'content' / folder / (args.creature.upper() + '.json')
        if not animation.exists():
            continue
        config = load_json(animation)
        files = set()
        for sequence in config['sequences']:
            for name in sequence['frames']:
                path = animation.parent / config['basepath'] / name
                files.add(path)
                for suffix in ('-shadow', '-overlay'):
                    layer = path.with_name(path.stem + suffix + path.suffix)
                    if layer.exists():
                        files.add(layer)
        dx, dy = args.offset_x * scale, args.offset_y * scale
        for source in sorted(files):
            original = Image.open(source).convert('RGBA')
            bounds = original.getchannel('A').getbbox()
            if bounds and not (bounds[0] + dx >= 0 and bounds[1] + dy >= 0 and
                               bounds[2] + dx <= original.width and bounds[3] + dy <= original.height):
                raise ValueError(f'Offset clips visible pixels: {source}')
            shifted = Image.new('RGBA', original.size)
            shifted.paste(original, (dx, dy))
            dest = args.out / source.relative_to(args.source_mod)
            shifted.save(dest)
            reloaded = Image.open(dest)
            if bounds:
                translated = (bounds[0] + dx, bounds[1] + dy, bounds[2] + dx, bounds[3] + dy)
                assert original.crop(bounds).tobytes() == reloaded.crop(translated).tobytes()
            assert original.getchannel('A').histogram() == reloaded.getchannel('A').histogram()
            report.append({'file': str(source.relative_to(args.source_mod)), 'offset': [dx, dy],
                           'sourceSHA256': digest(source), 'outputSHA256': digest(dest)})
    if not report:
        raise ValueError('No animation frames found')
    provenance = args.out / 'offset-provenance.json'
    previous = json.loads(provenance.read_text()) if provenance.exists() else []
    provenance.write_text(json.dumps(previous + report, indent=2) + '\n')
    print(json.dumps({'translatedFrames': len(report), 'offset1x': [args.offset_x, args.offset_y],
                      'visiblePixelsPreserved': True}))


if __name__ == '__main__':
    main()
