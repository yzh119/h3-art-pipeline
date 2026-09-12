#!/usr/bin/env python3
"""Register reviewed *single-frame* landmark art into an existing HD adventure mod.

The supplied artwork is fitted into the native body's bounding rectangle and
bottom-aligned. It deliberately leaves the native canvas, shadows, overlays,
JSON sequences and object template untouched. Multi-frame scenery must be
modelled and rendered as a complete Blender animation sequence instead.
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


def remove_solid_black_backdrop(image):
    """Turn a generator's border-connected pure-black backdrop transparent.

    Some generators return an opaque RGB image even when asked for a transparent
    asset.  Their #000 backdrop must not be fitted as part of the landmark.  We
    only remove pixels reachable from the canvas edge, so dark details enclosed
    by the painting are retained.
    """
    image = image.convert("RGBA")
    if image.getchannel("A").getextrema()[0] != 255:
        return image

    width, height = image.size
    pixels = image.load()
    seen = bytearray(width * height)
    queue = []

    def is_black(x, y):
        red, green, blue, _ = pixels[x, y]
        return red <= 3 and green <= 3 and blue <= 3

    def add(x, y):
        index = y * width + x
        if not seen[index] and is_black(x, y):
            seen[index] = 1
            queue.append((x, y))

    for x in range(width):
        add(x, 0)
        add(x, height - 1)
    for y in range(1, height - 1):
        add(0, y)
        add(width - 1, y)

    for x, y in queue:
        for next_x, next_y in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= next_x < width and 0 <= next_y < height:
                add(next_x, next_y)

    alpha = image.getchannel("A")
    alpha_data = bytearray(alpha.tobytes())
    for index, value in enumerate(seen):
        if value:
            alpha_data[index] = 0
    image.putalpha(Image.frombytes("L", image.size, bytes(alpha_data)))
    return image


def fit_landmark(source, native, constrain_native_alpha=False):
    source = remove_solid_black_backdrop(source)
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
    if constrain_native_alpha:
        # The native alpha channel defines the original object footprint,
        # including enclosed opaque openings. Reusing it exactly keeps
        # occlusion and click geometry stable despite source resampling.
        result.putalpha(native.getchannel("A"))
    return result


def body_frame_count(directory):
    """Return the number of base body frames, excluding shadow/overlay layers."""
    return sum(
        1
        for candidate in directory.glob("*_*.png")
        if candidate.stem.split("_")[-1].isdigit()
        and not candidate.name.endswith("-shadow.png")
        and not candidate.name.endswith("-overlay.png")
    )


def require_single_frame_target(mod, stem):
    for scale in (2, 3, 4):
        directory = mod / "content" / f"sprites{scale}x" / "adventure-hd" / stem
        count = body_frame_count(directory)
        if count != 1:
            raise ValueError(
                f"{stem} has {count} body frames at {scale}x; "
                "static registration is forbidden. Use the Blender sequence workflow."
            )


def parse_source(value):
    stem, separator, filename = value.partition("=")
    if not separator or not stem or not filename:
        raise argparse.ArgumentTypeError("use STEM=/absolute/path/to/generated.png")
    return stem.upper(), Path(filename)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mod", type=Path, required=True)
    parser.add_argument("--art", type=parse_source, action="append", required=True)
    parser.add_argument("--constrain-native-alpha", action="store_true", help="Clip generated pixels to the original body silhouette.")
    args = parser.parse_args()

    for stem, filename in args.art:
        if not filename.is_file():
            raise ValueError(f"missing generated artwork: {filename}")
        require_single_frame_target(args.mod, stem)
        source = Image.open(filename)
        for scale in (2, 3, 4):
            target = args.mod / "content" / f"sprites{scale}x" / "adventure-hd" / stem / "0_0.png"
            if not target.is_file():
                raise ValueError(f"missing native target: {target}")
            native = Image.open(target).convert("RGBA")
            registered = fit_landmark(source, native, args.constrain_native_alpha)
            registered.save(target)
            if registered.size != native.size:
                raise ValueError(f"changed canvas for {target}")
        print(f"registered {stem}")


if __name__ == "__main__":
    main()
