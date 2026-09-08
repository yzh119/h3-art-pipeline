#!/usr/bin/env python3
"""Add native-size Necropolis showcase backgrounds to a copied creature mod.

Requires Pillow. The generated master is a 10:13 full-bleed environment without
UI or creatures. The 120px variant removes the bottom 10 logical pixels, keeping
the horizon and background architecture registered between showcase sizes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from PIL import Image


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-mod', type=Path, required=True)
    parser.add_argument('--master', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--version', default='0.4.0')
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('Output must not already exist')
    master = Image.open(args.master).convert('RGB')
    if master.width < 400 or master.height < 520:
        raise ValueError('Master must contain at least 4x resolution')
    if abs(master.width / master.height - 10 / 13) > 0.01:
        raise ValueError('Master must have a 10:13 aspect ratio')
    shutil.copytree(args.source_mod, args.out)
    files = []
    for scale in range(1, 5):
        folder = args.out / 'content' / ('Data' if scale == 1 else f'Data{scale}x')
        folder.mkdir(exist_ok=True)
        large = master.resize((100 * scale, 130 * scale), Image.Resampling.LANCZOS)
        for name, height in [('CRBKGNEC', 130), ('TPCASNEC', 120)]:
            path = folder / (name + '.png')
            if path.exists():
                raise ValueError(f'Existing backdrop would be overwritten: {path}')
            result = large.crop((0, 0, 100 * scale, height * scale))
            result.save(path)
            with Image.open(path) as saved:
                if saved.size != result.size or saved.tobytes() != result.tobytes():
                    raise ValueError(f'PNG round-trip failed: {path}')
            files.append({'file': str(path.relative_to(args.out)),
                          'logicalSize': [100, height], 'scale': scale,
                          'size': list(result.size), 'sha256': digest(path)})
    # Ensure the animation optimization and registration survive packaging.
    preserved = 0
    for source in args.source_mod.rglob('*'):
        if source.is_file():
            if digest(source) != digest(args.out / source.relative_to(args.source_mod)):
                raise ValueError(f'Existing mod content changed: {source}')
            preserved += 1
    metadata = args.out / 'mod.json'
    config = json.loads(metadata.read_text())
    config['version'] = args.version
    config['description'] += ' Necropolis creature showcase backgrounds at 1x/2x/3x/4x.'
    metadata.write_text(json.dumps(config, indent=2) + '\n')
    report = {'masterSHA256': digest(args.master), 'masterSize': list(master.size),
              'smallVariant': 'Bottom 10 logical pixels cropped from 130px master',
              'preservedSourceFiles': preserved, 'files': files}
    (args.out / 'backdrop-provenance.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'backgrounds': len(files), 'preservedSourceFiles': preserved}))


if __name__ == '__main__':
    main()
