#!/usr/bin/env python3
"""Build a reversible 2x Necropolis resource mod and a layer inspection gallery.

Requires Pillow and original H3 data. Generated background/castle inputs are
optional. Other layers use conservative resampling, not generative restoration.
No faction configuration, hit masks, or adventure-map gameplay data is replaced.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from PIL import Image, ImageChops, ImageFilter

from export_necropolis_reference import pcx
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'creature-art'))
import def_extract as defs


def upscale(image):
    result = image.resize((image.width * 2, image.height * 2), Image.Resampling.BICUBIC)
    alpha = image.getchannel('A').resize(result.size, Image.Resampling.NEAREST)
    result = result.convert('RGB').filter(ImageFilter.UnsharpMask(1.0, 65, 4)).convert('RGBA')
    result.putalpha(alpha)
    return result


def register_castle(original, generated):
    """Keep original silhouette and use source pixels at uncertain/new edges."""
    generated = generated.convert('RGB')
    mask = Image.new('L', generated.size)
    mask.putdata([0 if r > g + 65 and b > g + 65 else 255 for r, g, b in generated.getdata()])
    generated = generated.resize(original.size, Image.Resampling.LANCZOS)
    mask = mask.resize(original.size, Image.Resampling.NEAREST)
    mask = ImageChops.multiply(mask, original.getchannel('A'))
    mask = mask.filter(ImageFilter.MinFilter(7)).filter(ImageFilter.GaussianBlur(1))
    result = Image.composite(generated, original.convert('RGB'), mask).convert('RGBA')
    result.putalpha(original.getchannel('A'))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--background', type=Path)
    parser.add_argument('--castle', type=Path)
    parser.add_argument('--faction-config', type=Path, default=Path(__file__).resolve().parents[1] / 'reference-config/necropolis.json')
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        raise ValueError('Output must be empty')
    sprites = args.out / 'mod/content/sprites2x'
    sprites.mkdir(parents=True)
    data = args.out / 'mod/content/data2x'
    data.mkdir()
    bitmap, bi = defs.read_lod(args.data / 'H3bitmap.lod')
    sprite, si = defs.read_lod(args.data / 'H3sprite.lod')
    config_path = args.faction_config
    config = json.loads(re.sub(r'//[^\n]*', '', config_path.read_text()))['necropolis']['town']
    background = pcx(defs.extract(bitmap, bi, 'TBNCBACK.PCX'))
    background.save(args.out / 'background-original.png')
    enhanced = Image.open(args.background).convert('RGB') if args.background else background
    enhanced.resize((1600, 748), Image.Resampling.LANCZOS).save(data / 'TBNCBACK.png')
    manifest = {'scale': 2, 'configSHA256': hashlib.sha256(config_path.read_bytes()).hexdigest(),
                'generatedInputs': {label: {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                                    for label, path in [('background', args.background), ('castle', args.castle)] if path},
                'backgroundGenerated': bool(args.background), 'castleGenerated': bool(args.castle),
                'structures': [], 'map': [], 'frames': 0,
                'stateLogic': 'Original engine config unchanged; gallery is an independent layer inspector.',
                'method': '2x bicubic + mild unsharp; generated castle interiors registered to original alpha.'}
    entries = [(name, spec, False) for name, spec in config['structures'].items()]
    entries += [(name, {'animation': resource}, True) for name, resource in
                [('village', 'AVCNECR0.DEF'), ('fort', 'AVCNECX0.DEF'), ('capitol', 'AVCNECZ0.DEF')]]
    for name, spec, is_map in entries:
        resource = spec['animation'].upper().removesuffix('.DEF')
        raw = defs.extract(sprite, si, spec['animation'])
        definition = defs.DefFile(raw)
        target = sprites / 'necropolis' / resource
        target.mkdir(parents=True)
        sequences = []
        for group, frames in definition.groups.items():
            names = []
            for index in range(len(frames)):
                head, rows = definition.frame_indices(group, index)
                canvas = defs.to_canvas(head, rows)
                size = (head['fullWidth'], head['fullHeight'])
                if is_map:
                    buffers = defs.split_layers(canvas, definition.palette)
                    layers = dict(zip(('', '-shadow', '-overlay'), buffers))
                else:
                    layers = {'': bytes(c for row in canvas for i in row for c in
                                       ((*definition.palette[i], 255) if i else (0, 0, 0, 0)))}
                filename = f'{group}_{index}.png'
                names.append(filename)
                for suffix, pixels in layers.items():
                    original = Image.frombytes('RGBA', size, bytes(pixels))
                    image = upscale(original)
                    if name == 'castle' and not is_map and args.castle:
                        image = register_castle(image, Image.open(args.castle))
                    # This is an exact footprint contract, independently checked on output.
                    image.save(target / f'{group}_{index}{suffix}.png')
                    loaded = Image.open(target / f'{group}_{index}{suffix}.png')
                    assert loaded.size == (size[0] * 2, size[1] * 2)
                    assert ImageChops.difference(loaded.getchannel('A'), original.getchannel('A').resize(loaded.size, Image.Resampling.NEAREST)).getbbox() is None
                manifest['frames'] += 1
            sequences.append({'group': group, 'frames': names})
        (sprites / (resource + '.json')).write_text(json.dumps({
            'basepath': f'necropolis/{resource}/', 'sequences': sequences}, indent=2) + '\n')
        entry = {'name': name, **spec, 'resource': resource, 'size': size,
                 'groups': {str(g): len(f) for g, f in definition.groups.items()},
                 'sourceSHA256': hashlib.sha256(raw).hexdigest()}
        manifest['map' if is_map else 'structures'].append(entry)
    (args.out / 'mod/mod.json').write_text(json.dumps({
        'name': 'Necropolis layered HD study', 'description': '2x original town/map layers; generated empty background and registered castle interior. Experimental art study.',
        'version': '0.2.0', 'author': 'yzh119', 'modType': 'Graphical'}, indent=2) + '\n')
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'structures': len(manifest['structures']), 'map': len(manifest['map']),
                      'frames': manifest['frames'], 'alphaAndDimensions': 'passed'}))


if __name__ == '__main__':
    main()
