#!/usr/bin/env python3
"""Apply a reviewed generated terrain material while retaining H3 tile layout.

The native terrain DEF determines tile selection and transition geometry. This
tool replaces only the painted surface within each full-canvas body layer,
preserving every filename, canvas, alpha channel and animation sequence.
"""
import argparse
import hashlib
from pathlib import Path

import numpy as np
from PIL import Image


def seeded_crop(texture, size, key):
    """Crop a repeatable offset from a wrapped material texture."""
    width, height = size
    texture = np.asarray(texture.convert("RGB"), dtype=np.float32) / 255.0
    source_height, source_width = texture.shape[:2]
    digest = hashlib.sha256(key.encode()).digest()
    offset_x = int.from_bytes(digest[:4], "little") % source_width
    offset_y = int.from_bytes(digest[4:8], "little") % source_height
    xs = (np.arange(width) + offset_x) % source_width
    ys = (np.arange(height) + offset_y) % source_height
    return texture[np.ix_(ys, xs)]


def repaint(source, texture, key):
    rgba = np.asarray(source.convert("RGBA"), dtype=np.float32)
    old = rgba[..., :3] / 255.0
    material = seeded_crop(texture, source.size, key)
    luminance = old @ np.array((0.2126, 0.7152, 0.0722))
    # Retain the original tile's broad lighting and transition value while the
    # new material supplies visible grass, soil and stone detail.
    shading = np.clip(0.60 + luminance * 0.65, 0.48, 1.22)[..., None]
    rgb = np.clip(material * shading * 0.89 + old * 0.11, 0, 1)
    result = np.empty_like(rgba)
    result[..., :3] = rgb * 255.0
    result[..., 3] = rgba[..., 3]
    return Image.fromarray(result.astype(np.uint8))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mod", type=Path, required=True)
    parser.add_argument("--terrain", required=True, help="Terrain DEF stem, e.g. GRASTL")
    parser.add_argument("--material", type=Path, required=True)
    args = parser.parse_args()

    if not args.material.is_file():
        raise ValueError(f"missing material: {args.material}")
    texture = Image.open(args.material)
    terrain = args.terrain.upper()
    count = 0
    for scale in (2, 3, 4):
        folder = args.mod / "content" / f"sprites{scale}x" / "adventure-hd" / terrain
        for target in sorted(folder.glob("*_*.png")):
            if target.stem.endswith(("-shadow", "-overlay")):
                continue
            original = Image.open(target).convert("RGBA")
            updated = repaint(original, texture, f"{terrain}:{scale}:{target.name}")
            if updated.size != original.size:
                raise ValueError(f"canvas changed: {target}")
            updated.save(target)
            count += 1
    print(f"repainted {terrain}: {count} body frames")


if __name__ == "__main__":
    main()
