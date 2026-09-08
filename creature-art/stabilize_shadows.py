#!/usr/bin/env python3
"""Bake soft sheared shadows on a fixed ground plane, preserving all body frames.

Requires Pillow and NumPy. Uses 2x continuous alpha instead of a binary threshold,
then derives 1x shadows from the same projection. No temporal averaging or motion
retiming. Ground coordinates are supplied in logical canvas pixels.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image, ImageFilter

from vcmi_anim import load_json


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_shadow(alpha, ground, softness=0.8):
    """Project a 2x body alpha using logical-pixel ground/softness parameters."""
    projected = alpha.transform(alpha.size, Image.Transform.AFFINE,
        (1, -1, 2 * ground, 0, 2, -2 * ground), resample=Image.Resampling.BILINEAR)
    projected = projected.point(lambda v: round(v * 0.5))
    return projected.filter(ImageFilter.GaussianBlur(softness * 2))


def churn(frames, loop):
    arrays = [np.asarray(frame, dtype=float) / 255 for frame in frames]
    pairs = list(zip(arrays, arrays[1:]))
    if loop:
        pairs.append((arrays[-1], arrays[0]))
    return max((float(np.abs(b - a).sum() / max(1, a.sum())) for a, b in pairs), default=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-mod', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--ground', action='append', required=True, help='CSKELE=267')
    parser.add_argument('--softness', type=float, default=0.8, help='Logical-pixel blur radius')
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('Output must not exist')
    shutil.copytree(args.source_mod, args.out)
    records, metrics = [], []
    for entry in args.ground:
        creature, value = entry.split('=')
        ground = float(value)
        config = load_json(args.source_mod / 'content/Sprites2x' / (creature.upper() + '.json'))
        for sequence in config['sequences']:
            before, after, old_anchors = [], [], []
            for name in sequence['frames']:
                relative = Path(config['basepath']) / name
                body = args.source_mod / 'content/Sprites2x' / relative
                alpha = Image.open(body).convert('RGBA').getchannel('A')
                old_anchors.append((alpha.getbbox()[3] - 1) / 2)
                # Inverse of x'=x+0.5*y-0.5*ground, y'=0.5*y+0.5*ground.
                projected = project_shadow(alpha, ground, args.softness)
                shadow_name = relative.with_name(relative.stem + '-shadow.png')
                before.append(Image.open(args.source_mod / 'content/Sprites2x' / shadow_name).getchannel('A'))
                after.append(projected)
                for scale, folder in [(1, 'Sprites'), (2, 'Sprites2x')]:
                    layer = projected if scale == 2 else projected.resize(
                        (alpha.width // 2, alpha.height // 2), Image.Resampling.LANCZOS)
                    image = Image.new('RGBA', layer.size)
                    image.putalpha(layer)
                    path = args.out / 'content' / folder / shadow_name
                    image.save(path)
                    records.append({'file': str(path.relative_to(args.out)), 'sha256': digest(path)})
            metrics.append({'creature': creature, 'group': sequence['group'],
                'previousAnchorRange': max(old_anchors) - min(old_anchors), 'newAnchorRange': 0,
                'fixedGround': ground, 'previousMaxAlphaChurn': churn(before, sequence['group'] in (0, 2)),
                'newMaxAlphaChurn': churn(after, sequence['group'] in (0, 2))})
    changed = {r['file'] for r in records}
    preserved = 0
    for p in args.source_mod.rglob('*'):
        if p.is_file() and str(p.relative_to(args.source_mod)) not in changed:
            if digest(p) != digest(args.out / p.relative_to(args.source_mod)):
                raise ValueError(f'Unexpected change: {p}')
            preserved += 1
    report = {'method': 'Fixed ground, continuous alpha, bilinear projection, spatial blur; no temporal averaging',
              'softnessLogicalPixels': args.softness, 'preservedFiles': preserved,
              'metrics': metrics, 'files': records}
    (args.out / 'shadow-provenance.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'shadows': len(records), 'preservedFiles': preserved, 'metrics': metrics}))


if __name__ == '__main__':
    main()
