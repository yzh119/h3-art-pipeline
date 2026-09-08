#!/usr/bin/env python3
"""Build fixed-scale sheets, playable videos and a local motion review page.

Requires Pillow and ffmpeg. All crops share the holding camera's pixel origin.
"""

import argparse
import json
import html as html_module
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageOps


BACKGROUND = (28, 29, 33)


def tile(path, center, scale=2):
    with Image.open(path) as im:
        raw = im.convert('RGBA').crop((round(center-90*scale), 125*scale,
                                       round(center+90*scale), 278*scale))
    return raw


def center(path):
    with Image.open(path) as im:
        box = im.getbbox()
        return (box[0]+box[2])/2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--previous', type=Path, help='Previous motion output for a walking comparison')
    args = parser.parse_args()
    p = args.directory
    manifest = json.loads((p/'manifest.json').read_text())
    label = html_module.escape(manifest['profile'].get('label', 'Skeleton'))
    groups = [name.lower() for name in manifest['clips']]
    reference = json.loads((args.reference.parent/'layout.json').read_text())
    counts = {g['name']: len(g['frames']) for g in reference['groups']}
    for group in groups:
        expected = counts[group.upper()]
        assert manifest['profile']['clips'][group.upper()]['sprite_frames'] == expected
        for scale in [1, 2]:
            files = sorted((p/('sprites%dx' % scale)).glob(group+'_*.png'))
            assert len(files) == expected, (group, scale, len(files))
            for file in files:
                with Image.open(file) as im:
                    assert im.size == (450*scale, 400*scale), file
                    box = im.getbbox()
                    assert box and box[0] > 0 and box[1] > 0 and box[2] < im.width and box[3] < im.height, file
    output = p/'preview'
    output.mkdir(exist_ok=True)
    new_center = center(p/'sprites2x/holding_00.png')
    ref_center = center(args.reference/'holding_00.png')
    html = ['<!doctype html><html lang="en"><meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width,initial-scale=1">',
            f'<title>{label} motion review</title>',
            '<style>body{background:#1c1d21;color:#ddd;font:16px system-ui;max-width:1000px;margin:32px auto;padding:16px}video{width:360px;max-width:100%}img{max-width:100%}section{display:inline-block;vertical-align:top;margin:12px}p{line-height:1.6}</style>',
            f'<h1>{label} motion review</h1><p>Editable {label.lower()} clips. Videos show the 30 fps bake at 2× game scale. '
            'Pause or scrub to inspect. Body pass only; no in-game acceptance yet. '
            'Attack includes recovery to holding. Movement is shown in place.</p>']
    for group in groups:
        frames = []
        for source in sorted((p/'review'/group).glob('*.png')):
            raw = tile(source, new_center)
            image = Image.new('RGB', raw.size, BACKGROUND)
            image.paste(raw, (0, 0), raw)
            frames.append(image)
        fps = manifest['profile']['fps']
        # GIF durations use centiseconds; alternate 30/40 ms to retain 30 fps.
        durations = [10*(round((i+1)*100/fps)-round(i*100/fps)) for i in range(len(frames))]
        frames[0].save(output/(group+'.gif'), save_all=True, append_images=frames[1:],
                       duration=durations, loop=0, disposal=2)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', str(fps),
                        '-i', str(p/'review'/group/'%03d.png'), '-filter_complex',
                        ('[0:v]crop=360:306:%d:250[fg];'
                         'color=c=0x1c1d21:s=360x306:r=%d[bg];'
                         '[bg][fg]overlay=shortest=1,format=yuv420p') % (round(new_center-180), fps),
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18',
                        '-movflags', '+faststart', str(output/(group+'.mp4'))], check=True)
        count = counts[group.upper()]
        comparison = Image.new('RGB', (180*count, 350), BACKGROUND)
        labels = ImageDraw.Draw(comparison)
        for row, (label, source, offset) in enumerate([
                ('Original', args.reference, ref_center), ('Study', p/'sprites1x', new_center/2)]):
            for i in range(count):
                raw = tile(source/(group+'_%02d.png' % i), offset, 1)
                comparison.paste(raw, (180*i, row*175+22), raw)
                labels.text((180*i+4, row*175+4), '%s %s %d' % (label, group, i), fill='white')
        comparison.save(output/(group+'-frames.png'))
        html.append('<section><h2>%s</h2><video controls loop muted playsinline preload="metadata" poster="%s.gif" src="%s.mp4"></video><p><a href="%s-frames.png">Original / study frames</a></p></section>' % (group, group, group, group))
    if args.previous and 'moving' in groups:
        previous_center = center(args.previous/'sprites2x/holding_00.png')
        frames = []
        for i in range(counts['MOVING']):
            frame = Image.new('RGB', (1080, 330), BACKGROUND)
            labels = ImageDraw.Draw(frame)
            for column, (label, source, offset, scale) in enumerate([
                    ('Original', args.reference, ref_center, 1),
                    ('Previous', args.previous/'sprites2x', previous_center, 2),
                    ('Revised', p/'sprites2x', new_center, 2)]):
                raw = tile(source/('moving_%02d.png' % i), offset, scale)
                if scale == 1:
                    raw = raw.resize((360, 306), Image.Resampling.NEAREST)
                frame.paste(raw, (column*360, 24), raw)
                labels.text((column*360+8, 6), label, fill='white')
            frames.append(frame)
        frames[0].save(output/'walk-comparison.gif', save_all=True, append_images=frames[1:],
                       duration=100, loop=0, disposal=2)
        html.append('<h2>Walking comparison</h2><p>Original, previous and revised carriage. Eight game frames at a shared review rate, with a fixed crop for each version.</p><img src="walk-comparison.gif" alt="Original, previous and revised walk">')
    if 'turn_l' in groups and 'turn_r' in groups:
        # ReverseAnimation plays TURN_L, flips facing, then plays TURN_R.
        sequence = [('holding', 0, False)]*4 + [('turn_l', i, False) for i in range(counts['TURN_L'])]
        sequence += [('turn_r', i, True) for i in range(counts['TURN_R'])] + [('holding', 0, True)]*4
        frames = []
        for group, index, mirrored in sequence:
            raw = tile(p/'sprites2x'/('%s_%02d.png' % (group, index)), new_center)
            if mirrored:
                raw = ImageOps.mirror(raw)
            frame = Image.new('RGB', raw.size, BACKGROUND)
            frame.paste(raw, (0, 0), raw)
            frames.append(frame)
        frames[0].save(output/'turn-order.gif', save_all=True, append_images=frames[1:],
                       duration=100, loop=0, disposal=2)
        html.append('<h2>Turn sequence</h2><p>Native clips in engine order: TURN_L, facing flip, TURN_R. Holding bookends are added for inspection.</p><img src="turn-order.gif" alt="Combined turn sequence">')
    # Original-count frames, aligned by phase; not a claim of matched engine timing.
    width, height = 180, 175
    columns = max(counts[g.upper()] for g in groups[:3])
    sheet = Image.new('RGB', (columns*width, len(groups[:3])*2*height), BACKGROUND)
    draw = ImageDraw.Draw(sheet)
    for group_index, group in enumerate(groups[:3]):
        for version, source, offset in [('Original', args.reference, ref_center),
                                         ('Study', p/'sprites1x', new_center/2)]:
            row = group_index*2+(version == 'Study')
            for i in range(counts[group.upper()]):
                raw = tile(source/(group+'_%02d.png' % i), offset, 1)
                x, y = i*width, row*height
                sheet.paste(raw, (x, y+22), raw)
                draw.text((x+4, y+4), '%s %s %d' % (version, group, i), fill='white')
    sheet.save(output/'native-frames.png')
    sheet.resize((sheet.width*2, sheet.height*2), Image.Resampling.NEAREST).save(output/'frames-2x.png')
    html.append('<h2>Original-count frames at 1×</h2><p>Shared scale and crop per row; original attack frames are phase references. No individual frame fitting.</p><img src="native-frames.png" alt="Original and new native-frame sequences"></html>')
    (output/'index.html').write_text('\n'.join(html)+'\n')
    print(output/'index.html')


if __name__ == '__main__':
    main()
