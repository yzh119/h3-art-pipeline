#!/usr/bin/env python3
"""Register reviewed transparent landmark art into an existing HD adventure mod.

The supplied artwork is fitted into the native body's bounding rectangle and
bottom-aligned. It deliberately leaves the native canvas, shadows, overlays,
JSON sequences and object template untouched.
"""
import argparse
from pathlib import Path

from PIL import Image


def alpha_bbox(image, threshold=1):
    alpha = image.getchannel("A")
    if threshold > 1:
        alpha = alpha.point(lambda value: 255 if value >= threshold else 0)
    bbox = alpha.getbbox()
    if not bbox:
        raise ValueError("generated artwork has no visible pixels")
    return bbox


def fit_landmark(source, native):
    source = source.convert("RGBA")
    # Generators occasionally leave near-zero pixels across an otherwise
    # transparent image. Ignore that fringe when locating the new artwork.
    crop = source.crop(alpha_bbox(source, threshold=8))
    target_box = alpha_bbox(native)
    target_width = target_box[2] - target_box[0]
    target_height = target_box[3] - target_box[1]
    factor = min(target_width / crop.width, target_height / crop.height)
    size = (max(1, round(crop.width * factor)), max(1, round(crop.height * factor)))
    crop = crop.resize(size, Image.Resampling.LANCZOS)
    result = Image.new("RGBA", native.size)
    x = target_box[0] + (target_width - crop.width) // 2
    y = target_box[3] - crop.height
    result.alpha_composite(crop, (x, y))
    return result


def parse_source(value):
    stem, separator, filename = value.partition("=")
    if not separator or not stem or not filename:
        raise argparse.ArgumentTypeError("use STEM=/absolute/path/to/generated.png")
    return stem.upper(), Path(filename)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mod", type=Path, required=True)
    parser.add_argument("--art", type=parse_source, action="append", required=True)
    args = parser.parse_args()

    for stem, filename in args.art:
        if not filename.is_file():
            raise ValueError(f"missing generated artwork: {filename}")
        source = Image.open(filename)
        for scale in (2, 3, 4):
            target = args.mod / "content" / f"sprites{scale}x" / "adventure-hd" / stem / "0_0.png"
            if not target.is_file():
                raise ValueError(f"missing native target: {target}")
            native = Image.open(target).convert("RGBA")
            registered = fit_landmark(source, native)
            registered.save(target)
            if registered.size != native.size:
                raise ValueError(f"changed canvas for {target}")
        print(f"registered {stem}")


if __name__ == "__main__":
    main()
