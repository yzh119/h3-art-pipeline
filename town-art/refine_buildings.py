#!/usr/bin/env python3
"""Register generated town building interiors onto a validated layered mod.

Use one generated square-magenta image for each job. Exact original alpha and
all overlay animation frames remain unchanged. Animated overlay support is
excluded from the generated base so effects never alternate between textures.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from PIL import Image, ImageChops, ImageFilter


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def register(original, generated, protected):
    rgb = generated.convert('RGB')
    key = Image.new('L', rgb.size)
    key.putdata([0 if r > g + 65 and b > g + 65 else 255 for r, g, b in rgb.getdata()])
    box = key.getbbox()
    target = original.getchannel('A').getbbox()
    if box is None or target is None:
        raise ValueError('Empty generated or original silhouette')
    size = (target[2] - target[0], target[3] - target[1])
    detail = Image.new('RGB', original.size)
    detail.paste(rgb.crop(box).resize(size, Image.Resampling.LANCZOS), target[:2])
    valid = Image.new('L', original.size)
    valid.paste(key.crop(box).resize(size, Image.Resampling.NEAREST), target[:2])
    alpha = original.getchannel('A')
    valid = ImageChops.multiply(valid, alpha)
    valid = ImageChops.subtract(valid, protected)
    valid = valid.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(.5))
    # Blur must not leak into protected animation support.
    valid = ImageChops.subtract(valid, protected)
    result = Image.composite(detail, original.convert('RGB'), valid).convert('RGBA')
    result.putalpha(alpha)
    coverage = sum(valid.getdata()) / max(1, sum(alpha.getdata()))
    return result, {'generatedBox': box, 'targetBox': target, 'interiorCoverage': coverage}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline', required=True, type=Path)
    ap.add_argument('--inputs', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    args = ap.parse_args()
    if args.out.exists():
        raise ValueError('Output must not exist')
    jobs = json.loads((args.inputs / 'jobs.json').read_text())
    missing = [j['name'] for j in jobs if not (args.inputs / 'generated' / (j['name'] + '.png')).is_file()]
    if missing:
        raise ValueError(f'Missing generated assets: {missing}')
    shutil.copytree(args.baseline / 'mod', args.out / 'mod')
    shutil.copy2(args.baseline / 'background-original.png', args.out / 'background-original.png')
    manifest = json.loads((args.baseline / 'manifest.json').read_text())
    by_name = {s['name']: s for s in manifest['structures']}
    report = []
    for job in jobs:
        name = job['name']
        spec = by_name[name]
        folder = Path('mod/content/sprites2x/necropolis') / spec['resource']
        original = Image.open(args.baseline / folder / '0_0.png').convert('RGBA')
        protected = Image.new('L', original.size)
        for index in range(1, spec['groups']['0']):
            overlay = Image.open(args.baseline / folder / f'0_{index}.png')
            protected = ImageChops.lighter(protected, overlay.getchannel('A'))
        protected = protected.filter(ImageFilter.MaxFilter(5))
        generated = args.inputs / 'generated' / (name + '.png')
        result, metrics = register(original, Image.open(generated), protected)
        dest = args.out / folder / '0_0.png'
        result.save(dest)
        loaded = Image.open(dest)
        assert loaded.size == original.size
        assert ImageChops.difference(loaded.getchannel('A'), original.getchannel('A')).getbbox() is None
        diff = ImageChops.difference(loaded.convert('RGB'), original.convert('RGB'))
        assert diff.getbbox() is not None, f'No generated detail applied: {name}'
        assert ImageChops.multiply(diff, Image.merge('RGB', (protected,) * 3)).getbbox() is None
        report.append({'name': name, **metrics, 'inputSHA256': digest(generated),
                       'outputSHA256': digest(dest), 'preservedOverlayFrames': spec['groups']['0'] - 1})
        spec['detailMethod'] = 'generated interior; original alpha and animated support'
    changed = {Path('content/sprites2x/necropolis') / by_name[j['name']]['resource'] / '0_0.png' for j in jobs}
    for source in (args.baseline / 'mod').rglob('*'):
        relative = source.relative_to(args.baseline / 'mod')
        if source.is_file() and relative not in changed:
            assert digest(source) == digest(args.out / 'mod' / relative), relative
    manifest['method'] = 'Generated static interiors for all 42 town layers; original alpha and 58 overlay frames preserved. Map variants unchanged.'
    manifest['buildingRefinement'] = report
    manifest['refinementToolSHA256'] = digest(Path(__file__))
    manifest['baselineManifestSHA256'] = digest(args.baseline / 'manifest.json')
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    mod_path = args.out / 'mod/mod.json'
    mod = json.loads(mod_path.read_text())
    mod.update(version='0.3.0', description='Generated interiors across all 42 Necropolis town layers, preserving original silhouettes and animated overlays; conservative 2x map variants.')
    mod_path.write_text(json.dumps(mod, indent=2) + '\n')
    print(json.dumps({'refined': len(report), 'preservedOverlayFrames': sum(r['preservedOverlayFrames'] for r in report),
                      'minimumInteriorCoverage': min(r['interiorCoverage'] for r in report),
                      'alphaDimensionsProtectedPixelsUnchanged': True}, indent=2))


if __name__ == '__main__':
    main()
