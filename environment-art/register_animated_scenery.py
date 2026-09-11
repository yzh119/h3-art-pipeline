#!/usr/bin/env python3
"""Register an animated sequence into a native adventure-map sprite.

The adventure-map DEF remains authoritative for canvas placement, shadows,
overlays and animation timing. This tool replaces only body layers. By default
there must be one reviewed source frame for each destination frame; cycling is
available only when deliberately requested for non-animated scenery.
"""
import argparse
import re
from pathlib import Path

from PIL import Image, ImageChops

from register_landmarks import remove_solid_black_backdrop


def numeric_key(path: Path):
    match = re.search(r"_(\d+)$", path.stem)
    return int(match.group(1)) if match else -1


def alpha_bbox(image: Image.Image, threshold=8):
    alpha = image.convert("RGBA").getchannel("A")
    if threshold > 1:
        alpha = alpha.point(lambda value: 255 if value >= threshold else 0)
    bbox = alpha.getbbox()
    if not bbox:
        raise ValueError("sprite has no visible pixels")
    return bbox


def fit(source: Image.Image, native: Image.Image, constrain_native_alpha: bool):
    source = remove_solid_black_backdrop(source)
    source = source.crop(alpha_bbox(source))
    box = alpha_bbox(native)
    width, height = box[2] - box[0], box[3] - box[1]
    factor = min(width / source.width, height / source.height)
    source = source.resize(
        (max(1, round(source.width * factor)), max(1, round(source.height * factor))),
        Image.Resampling.LANCZOS,
    )
    result = Image.new("RGBA", native.size)
    result.alpha_composite(source, (box[0] + (width - source.width) // 2, box[3] - source.height))
    if constrain_native_alpha:
        result.putalpha(ImageChops.multiply(result.getchannel("A"), native.getchannel("A")))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mod", type=Path, required=True)
    parser.add_argument("--stem", required=True)
    parser.add_argument("--frames", type=Path, required=True, help="Directory of source body PNG frames")
    parser.add_argument("--pattern", default="*.png")
    parser.add_argument("--cycle-sources", action="store_true", help="Repeat supplied frames when this is explicitly intended")
    parser.add_argument("--constrain-native-alpha", action="store_true", help="Clip each replacement to the original frame silhouette")
    args = parser.parse_args()

    sources = [path for path in sorted(args.frames.glob(args.pattern)) if not path.stem.endswith(("-shadow", "-overlay"))]
    if not sources:
        raise ValueError(f"no source body frames in {args.frames}")
    source_images = [Image.open(path).convert("RGBA") for path in sources]
    stem = args.stem.upper()
    for scale in (2, 3, 4):
        folder = args.mod / "content" / f"sprites{scale}x" / "adventure-hd" / stem
        targets = [path for path in sorted(folder.glob("0_*.png"), key=numeric_key) if not path.stem.endswith(("-shadow", "-overlay"))]
        if not targets:
            raise ValueError(f"no destination body frames in {folder}")
        if not args.cycle_sources and len(source_images) != len(targets):
            raise ValueError(
                f"{stem} has {len(targets)} destination frames but {len(source_images)} source frames; "
                "supply a frame-for-frame sequence or pass --cycle-sources deliberately"
            )
        for index, target in enumerate(targets):
            native = Image.open(target).convert("RGBA")
            replacement = fit(source_images[index % len(source_images)], native, args.constrain_native_alpha)
            if replacement.size != native.size:
                raise ValueError(f"canvas changed for {target}")
            replacement.save(target)
        print(f"registered {stem} at {scale}x: {len(targets)} destination frames from {len(sources)} source frames")


if __name__ == "__main__":
    main()
