#!/usr/bin/env python3
"""Extract only Necropolis building/portrait references from a local H3sprite.lod.

COLORKEY decoding preserves all palette colours except transparent index zero.
Original artwork is local input, never a file to commit into this tools repository.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'creature-art'))
import def_extract as defs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lod', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('Use a fresh reference directory')
    blob, entries = defs.read_lod(args.lod)
    report = {}
    duplicates = {}
    for name in ('HALLNECR', 'CPRSMALL', 'TWCRPORT'):
        raw = defs.extract(blob, entries, name + '.DEF')
        definition = defs.DefFile(raw)
        folder = args.out / name
        folder.mkdir(parents=True)
        indices = range(44) if name == 'HALLNECR' else range(58, 72)
        report[name] = {'defSHA256': hashlib.sha256(raw).hexdigest(),
                        'nativeFrames': len(definition.groups[0]), 'exportedFrames': list(indices)}
        for index in indices:
            header, rows = definition.frame_indices(0, index)
            canvas = defs.to_canvas(header, rows)
            rgba = bytes(c for row in canvas for i in row
                         for c in ((*definition.palette[i], 255) if i else (0, 0, 0, 0)))
            image = Image.frombytes('RGBA', (header['fullWidth'], header['fullHeight']), rgba)
            path = folder / f'0_{index}.png'
            image.save(path)
            if name == 'HALLNECR':
                duplicates.setdefault(hashlib.sha256(path.read_bytes()).hexdigest(), []).append(index)
    (args.out / 'building-duplicates.json').write_text(json.dumps(list(duplicates.values()), indent=2) + '\n')
    (args.out / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
