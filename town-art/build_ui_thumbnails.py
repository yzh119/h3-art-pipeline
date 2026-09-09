#!/usr/bin/env python3
"""Package generated buildings and Blender portraits as sparse VCMI HD UI overrides.

Original 1x DEFs remain authoritative for logical dimensions, unmodified factions,
selection markers, player colours and absent HD scales. Inputs remain outside git.
"""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image

NAMES = ['skeleton', 'skeleton-warrior', 'walking-dead', 'zombie', 'wight', 'wraith',
         'vampire', 'vampire-lord', 'lich', 'power-lich', 'black-knight', 'dread-knight',
         'bone-dragon', 'ghost-dragon']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(args):
    if args.out.exists():
        raise ValueError('Use a fresh output directory')
    duplicate_groups = json.loads((args.reference / 'building-duplicates.json').read_text())
    canonical = {i: group[0] for group in duplicate_groups for i in group}
    assert set(canonical) == set(range(44))
    inputs = []
    for index in sorted(set(canonical.values())):
        path = args.buildings / f'hallnecr-{index:02}.png'
        with Image.open(path) as im:
            assert im.width >= 600 and im.height >= 280, (path, im.size)
            assert abs(im.width / im.height - 150 / 70) < 0.03, (path, im.size)
        inputs.append({'file': str(path), 'sha256': sha(path)})
    for folder in (args.portraits, args.small_portraits):
        for name in NAMES:
            path = folder / (name + '.png')
            with Image.open(path) as im:
                assert im.mode == 'RGBA' and im.width >= 320 and im.height >= 320
                assert im.getchannel('A').getbbox()
            inputs.append({'file': str(path), 'sha256': sha(path)})
    inputs.append({'file': str(args.backdrop), 'sha256': sha(args.backdrop)})
    backdrop = Image.open(args.backdrop).convert('RGBA')
    rows = []
    for scale in (2, 3, 4):
        root = args.out / 'content' / f'sprites{scale}x'
        images = root / 'necropolis-ui'
        images.mkdir(parents=True)
        configs = {name: {'images': []} for name in ('HALLNECR', 'CPRSMALL', 'TWCRPORT')}
        for index in sorted(set(canonical.values())):
            with Image.open(args.buildings / f'hallnecr-{index:02}.png') as source:
                target = images / f'building-{index:02}.png'
                source.convert('RGB').resize((150 * scale, 70 * scale), Image.Resampling.LANCZOS).save(target)
        for index in range(44):
            configs['HALLNECR']['images'].append({'group': 0, 'frame': index, 'file': f'necropolis-ui/building-{canonical[index]:02}.png'})
        for offset, name in enumerate(NAMES):
            for animation, folder, size, suffix in (
                ('CPRSMALL', args.small_portraits, (32, 32), 'small'),
                ('TWCRPORT', args.portraits, (58, 64), 'large'),
            ):
                original = args.reference / animation / f'0_{58 + offset}.png'
                with Image.open(original) as im:
                    assert im.size == size, (animation, im.size)
                pixels = (size[0] * scale, size[1] * scale)
                with Image.open(folder / (name + '.png')) as master:
                    portrait = master.resize(pixels, Image.Resampling.LANCZOS)
                if animation == 'TWCRPORT':
                    canvas = backdrop.resize(pixels, Image.Resampling.LANCZOS)
                    canvas.alpha_composite(portrait)
                    portrait = canvas.convert('RGB')
                filename = f'{name}-{suffix}.png'
                portrait.save(images / filename)
                configs[animation]['images'].append({'group': 0, 'frame': 58 + offset, 'file': 'necropolis-ui/' + filename})
        for animation, config in configs.items():
            (root / (animation + '.json')).write_text(json.dumps(config, indent=2) + '\n')
            expected = range(44) if animation == 'HALLNECR' else range(58, 72)
            assert [r['frame'] for r in config['images']] == list(expected)
            logical_size = (150, 70) if animation == 'HALLNECR' else (32, 32) if animation == 'CPRSMALL' else (58, 64)
            for row in config['images']:
                path = root / row['file']
                with Image.open(path) as image:
                    assert image.size == tuple(n * scale for n in logical_size)
                rows.append(dict(animation=animation, frame=row['frame'], scale=scale,
                                 file=str(path.relative_to(args.out)), sha256=sha(path)))
    (args.out / 'mod.json').write_text(json.dumps({
        'name': 'Necropolis HD UI thumbnails', 'version': '0.1.0',
        'description': 'Generated building thumbnails and portraits rendered from delivered creature models. 2x, 3x and 4x UI graphics; native logical sizes and 1x fallback.',
        'author': 'yzh119', 'modType': 'Graphical',
    }, indent=2) + '\n')
    assert not (args.out / 'content/sprites').exists()
    report = {'version': '0.1.0', 'errors': [], 'warnings': [], 'buildingSlots': 44,
              'uniqueBuildingMasters': len(set(canonical.values())), 'creatures': 14,
              'scales': [2, 3, 4], 'original1xPreserved': True, 'inputs': inputs,
              'resources': rows, 'toolSHA256': sha(Path(__file__))}
    (args.out / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('inputs', 'resources')}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('reference', 'buildings', 'portraits', 'small-portraits', 'backdrop', 'out'):
        parser.add_argument('--' + option, type=Path, required=True)
    build(parser.parse_args())


if __name__ == '__main__':
    main()
