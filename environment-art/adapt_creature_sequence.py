#!/usr/bin/env python3
"""Adapt a rendered Blender creature loop to an animated adventure-map resource.

The source must contain body and ``-shadow`` PNG frames rendered from the same
3D scene. Each target's native canvas and per-frame bounding boxes are retained,
so VCMI resource geometry and the original idle motion envelope are preserved.
"""
import argparse
from pathlib import Path

from PIL import Image


def alpha_bbox(image):
    bbox = image.convert("RGBA").getchannel("A").getbbox()
    if not bbox:
        raise ValueError("image has no visible alpha")
    return bbox


def source_frames(directory, prefix, suffix=""):
    frames = sorted(directory.glob(f"{prefix}_*{suffix}.png"))
    if not suffix:
        frames = [frame for frame in frames if not frame.name.endswith("-shadow.png") and not frame.name.endswith("-overlay.png")]
    if not frames:
        raise ValueError(f"no source frames matching {prefix}_*{suffix}.png in {directory}")
    return frames


def target_frames(directory):
    frames = []
    for candidate in directory.glob("0_*.png"):
        name = candidate.name
        if name.endswith("-shadow.png") or name.endswith("-overlay.png"):
            continue
        if candidate.stem.split("_")[-1].isdigit():
            frames.append(candidate)
    return sorted(frames, key=lambda path: int(path.stem.split("_")[-1]))


def fit(source, native):
    source = source.convert("RGBA")
    native = native.convert("RGBA")
    crop = source.crop(alpha_bbox(source))
    left, top, right, bottom = alpha_bbox(native)
    width, height = right - left, bottom - top
    factor = min(width / crop.width, height / crop.height)
    size = (max(1, round(crop.width * factor)), max(1, round(crop.height * factor)))
    crop = crop.resize(size, Image.Resampling.LANCZOS)
    out = Image.new("RGBA", native.size)
    out.alpha_composite(crop, (left + (width - crop.width) // 2, bottom - crop.height))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mod", type=Path, required=True)
    parser.add_argument("--stem", required=True)
    parser.add_argument("--source", type=Path, required=True, help="Blender-rendered creature frame directory")
    parser.add_argument("--prefix", default="holding", help="Source animation prefix (default: holding)")
    args = parser.parse_args()

    body_sources = source_frames(args.source, args.prefix)
    shadow_sources = source_frames(args.source, args.prefix, "-shadow")
    if len(body_sources) != len(shadow_sources):
        raise ValueError("body and shadow source frame counts differ")

    for scale in (2, 3, 4):
        directory = args.mod / "content" / f"sprites{scale}x" / "adventure-hd" / args.stem
        targets = target_frames(directory)
        if len(targets) < 2:
            raise ValueError(f"{args.stem} at {scale}x is not an animated target")
        for index, target in enumerate(targets):
            source_index = index % len(body_sources)
            native = Image.open(target)
            body = fit(Image.open(body_sources[source_index]), native)
            body.save(target)
            shadow_target = target.with_name(target.stem + "-shadow.png")
            if not shadow_target.is_file():
                raise ValueError(f"missing target shadow: {shadow_target}")
            shadow = fit(Image.open(shadow_sources[source_index]), Image.open(shadow_target))
            shadow.save(shadow_target)
        print(f"adapted {args.stem} {scale}x: {len(targets)} targets from {len(body_sources)} Blender frames")


if __name__ == "__main__":
    main()
