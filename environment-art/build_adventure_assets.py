#!/usr/bin/env python3
"""Create sparse HD overrides for original adventure-map DEF resources.

The output retains every source canvas, animation group, frame count and
body/shadow/overlay layer. It deliberately does not alter VCMI object templates:
map coordinates, passability, click masks and ownership handling therefore stay
with the original game configuration.

This is a high-quality scaling baseline, not a generative repaint. Use separate
registered art passes for objects whose design should be changed.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "creature-art"))
import def_extract as defs


TERRAIN_DEFS = ("DIRTTL", "SANDTL", "GRASTL", "SNOWTL", "SWMPTL", "ROUGTL", "SUBBTL", "ROCKTL")
ROAD_DEFS = ("DIRTRD", "GRAVRD", "COBBRD")
RIVER_DEFS = ("ICYRVR",)
EXCLUDED_PREFIXES = ("AVC",)  # Towns have separate registered generated map art.


def rgba(layer, size):
    return Image.frombytes("RGBA", size, bytes(layer))


def scale_layer(source, scale, sharpen):
    size = (source.width * scale, source.height * scale)
    alpha = source.getchannel("A").resize(size, Image.Resampling.LANCZOS)
    rgb = source.convert("RGB").resize(size, Image.Resampling.LANCZOS)
    if sharpen:
        rgb = rgb.filter(ImageFilter.UnsharpMask(radius=0.65 * scale, percent=65, threshold=4))
    rgb.putalpha(alpha)
    return rgb


def selected_defs(entries, scope, prefixes):
    adventure = sorted(
        name[:-4] for name in entries
        if name.startswith("AV") and name.endswith(".DEF")
        and not name.startswith(EXCLUDED_PREFIXES)
    )
    if prefixes:
        adventure = [stem for stem in adventure if stem.startswith(tuple(prefixes))]
    if scope == "objects":
        return adventure
    if scope == "terrain":
        return list(TERRAIN_DEFS + ROAD_DEFS + RIVER_DEFS)
    return sorted(set(adventure + list(TERRAIN_DEFS + ROAD_DEFS + RIVER_DEFS)))


def export_def(blob, entries, stem, destination, scales, sharpen):
    raw = defs.extract(blob, entries, stem + ".DEF")
    definition = defs.DefFile(raw)
    record = {"resource": stem, "nativeSHA256": hashlib.sha256(raw).hexdigest(), "groups": {}}
    for scale in scales:
        root = destination / "content" / f"sprites{scale}x"
        folder = root / "adventure-hd" / stem
        folder.mkdir(parents=True, exist_ok=True)
        sequences = []
        for group, frames in definition.groups.items():
            names = []
            for frame in range(len(frames)):
                header, rows = definition.frame_indices(group, frame)
                size = (header["fullWidth"], header["fullHeight"])
                layers = defs.split_layers(defs.to_canvas(header, rows), definition.palette)
                basename = f"{group}_{frame}"
                names.append(basename + ".png")
                for suffix, layer in zip(("", "-shadow", "-overlay"), layers):
                    original = rgba(layer, size)
                    # Keep effect coverage pixel-registered. A Lanczos alpha edge would
                    # move sparse shadow/flag pixels when reduced back to native size.
                    image = (scale_layer(original, scale, sharpen) if not suffix
                             else original.resize((size[0] * scale, size[1] * scale), Image.Resampling.NEAREST))
                    target = folder / (basename + suffix + ".png")
                    image.save(target)
                    check = Image.open(target)
                    if check.size != (size[0] * scale, size[1] * scale):
                        raise ValueError(f"unexpected output size: {target}")
                    if suffix and check.getchannel("A").getbbox() != original.getchannel("A").getbbox():
                        # Alpha coordinates scale, so compare after a nearest reduction.
                        reduced = check.getchannel("A").resize(size, Image.Resampling.NEAREST)
                        if reduced.getbbox() != original.getchannel("A").getbbox():
                            raise ValueError(f"effect registration changed: {target}")
            sequences.append({"group": group, "frames": names})
        (root / f"{stem}.json").write_text(json.dumps({
            "basepath": f"adventure-hd/{stem}/", "sequences": sequences
        }, indent=2) + "\n")
        record["groups"][str(scale)] = {str(group): len(frames) for group, frames in definition.groups.items()}
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lod", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--scope", choices=("objects", "terrain", "all"), default="all")
    parser.add_argument(
        "--prefix",
        action="append",
        default=[],
        help="Limit adventure objects to a DEF prefix; repeatable (for example AVL, AVX, AVW).",
    )
    parser.add_argument("--scales", type=int, nargs="+", default=(2, 3, 4))
    parser.add_argument("--no-sharpen", action="store_true")
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Use a new output directory")
    blob, entries = defs.read_lod(args.lod)
    prefixes = tuple(prefix.upper() for prefix in args.prefix)
    stems = selected_defs(entries, args.scope, prefixes)
    missing = [stem for stem in stems if stem + ".DEF" not in entries]
    if missing:
        raise ValueError(f"missing original DEFs: {missing}")
    args.out.mkdir(parents=True)
    records = [export_def(blob, entries, stem, args.out, args.scales, not args.no_sharpen) for stem in stems]
    files = list((args.out / "content").rglob("*.png"))
    audit = {
        "scope": args.scope,
        "resources": len(records),
        "pngFiles": len(files),
        "scales": args.scales,
        "preserved": ["canvas", "animation groups", "frame counts", "shadow and overlay layers", "object templates"],
        "excluded": {"AVC": "map towns use the existing registered generated artwork"},
        "selection": {"prefixes": prefixes},
        "records": records,
        "toolSHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (args.out / "adventure-audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps({k: audit[k] for k in ("scope", "resources", "pngFiles", "scales")}, indent=2))


if __name__ == "__main__":
    main()
