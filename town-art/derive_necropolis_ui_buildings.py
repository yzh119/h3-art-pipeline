#!/usr/bin/env python3
"""Derive Necropolis UI building masters from the installed town layers.

This keeps construction-list thumbnails visually tied to the town screen rather
than asking a generator to reinterpret each building. The source assets stay
outside this tools repository.
"""
import argparse
from pathlib import Path

from PIL import Image


# HALLNECR canonical frames. Slot 18 is the native empty construction marker;
# it intentionally stays with the original UI reference.
SOURCES = {
    0: "TBNCMAGE", 1: "TBNCMAG2", 2: "TBNCMAG3", 3: "TBNCMAG4", 4: "TBNCMAG5",
    5: "TBNCTVRN", 6: "TBNCDOCK", 7: "TBNCCSTL", 8: "TBNCCAS2", 9: "TBNCCAS3",
    10: "TBNCHALL", 11: "TBNCHAL2", 12: "TBNCHAL3", 13: "TBNCHAL4",
    14: "TBNCMARK", 15: "TBNCSILO", 16: "TBNCEXT0", 17: "TBNCSPEC",
    21: "TBNCEXT0", 22: "TBNCEXT1", 26: "TBNCHOLY",
    30: "TBNCDW_0", 31: "TBNCDW_1", 32: "TBNCDW_2", 33: "TBNCDW_3",
    34: "TBNCDW_4", 35: "TBNCDW_5", 36: "TBNCDW_6",
    37: "TBNCUP_0", 38: "TBNCUP_1", 39: "TBNCUP_2", 40: "TBNCUP_3",
    41: "TBNCUP_4", 42: "TBNCUP_5", 43: "TBNCUP_6",
}


def master_from_layer(source):
    """Place one town building layer in the 150:70 thumbnail master frame."""
    source = source.convert("RGBA")
    canvas = Image.new("RGBA", (1800, 840))
    scale = min(1540 / source.width, 760 / source.height)
    size = (max(1, round(source.width * scale)), max(1, round(source.height * scale)))
    source = source.resize(size, Image.Resampling.LANCZOS)
    canvas.alpha_composite(source, ((canvas.width - source.width) // 2, canvas.height - source.height))
    return canvas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--town-layers", type=Path, required=True,
                        help=".../content/sprites2x/necropolis")
    parser.add_argument("--fallback", type=Path, required=True,
                        help="existing generated masters; used only for slot 18")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    # The packer consumes one master per canonical frame; duplicated HALLNECR
    # slots reference that same exported file through building-duplicates.json.
    for frame in sorted(set(SOURCES) | {18}):
        source_name = SOURCES.get(frame)
        if source_name is None:
            source = args.fallback / f"hallnecr-{frame:02}.png"
        else:
            source = args.town_layers / source_name / "0_0.png"
        if not source.is_file():
            raise FileNotFoundError(source)
        if source_name is None:
            image = Image.open(source).convert("RGBA")
        else:
            image = master_from_layer(Image.open(source))
        image.save(args.out / f"hallnecr-{frame:02}.png")
    print(f"derived {len(SOURCES)} town-layer masters; retained 1 native fallback")


if __name__ == "__main__":
    main()
