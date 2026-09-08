#!/usr/bin/env python3
"""Make a fixed-scale comparison sheet for the four skeleton study poses.

Requires Pillow. Each row uses one horizontal offset derived from its idle;
frames are never individually resized or fitted to their own bounding boxes.
"""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


FRAMES = {
    'holding': 'holding_00.png',
    'walk_contact': 'moving_00.png',
    'windup': 'attack_front_01.png',
    'strike': 'attack_front_03.png',
}


def sheet(study, reference, scale):
    sources = [('Original', reference, 1), ('Previous rig / poses', study / 'before', 2),
               ('Skeleton study', study, 2)]
    width, height = 180, 145
    label_height = 22
    result = Image.new('RGB', (width*4*scale, (height+label_height)*3*scale), (28, 29, 33))
    draw = ImageDraw.Draw(result)
    for row, (label, directory, native_scale) in enumerate(sources):
        idle_name = FRAMES['holding'] if row == 0 else 'holding.png'
        with Image.open(directory / idle_name) as idle:
            bbox = idle.getbbox()
            center = (bbox[0] + bbox[2]) / (2*native_scale)
        for col, (name, original) in enumerate(FRAMES.items()):
            filename = original if row == 0 else name + '.png'
            with Image.open(directory / filename) as raw:
                x = round(center - width/2)
                tile = raw.convert('RGBA').crop((x*native_scale, 130*native_scale,
                           (x+width)*native_scale, 275*native_scale))
                filtering = Image.Resampling.NEAREST if scale >= native_scale else Image.Resampling.LANCZOS
                tile = tile.resize((width*scale, height*scale), filtering)
            left, top = col*width*scale, row*(height+label_height)*scale
            draw.text((left+6, top+5), label + ' / ' + name, fill=(220, 220, 215))
            result.paste(tile, (left, top+label_height*scale), tile)
    result.save(study / ('comparison.png' if scale == 2 else 'native-size.png'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('study', type=Path)
    parser.add_argument('--reference', type=Path, required=True,
                        help='body directory from def_extract.py export')
    args = parser.parse_args()
    for scale in [1, 2]:
        sheet(args.study, args.reference, scale)
    result = Image.new('RGB', (1400, 630), (28, 29, 33))
    draw = ImageDraw.Draw(result)
    for index, side in enumerate(['right', 'left']):
        with Image.open(args.study / (side + '-hand.png')) as im:
            result.paste(im, (index*700, 30), im)
        draw.text((index*700+12, 8), side.title() + (' hand / grip' if side == 'right' else ' hand / free'),
                  fill=(220, 220, 215))
    result.save(args.study / 'hands.png')
    manifest = json.loads((args.study / 'manifest.json').read_text())
    report = manifest['measurements']
    for name, values in report.items():
        error = max(v['target_error'] for v in values.values() if isinstance(v, dict))
        print('%s: max IK error %.6f, blade %.6f, socket %.6f' % (
            name, error, values['blade_length'], values['socket_error']))


if __name__ == '__main__':
    main()
