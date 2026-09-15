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
    14: "TBNCMARK", 15: "TBNCSILO", 16: "TBNCBLAK", 17: "TBNCSPEC",
    21: "TBNCEXT0", 22: "TBNCEXT1", 26: "TBNCHOLY",
    30: "TBNCDW_0", 31: "TBNCDW_1", 32: "TBNCDW_2", 33: "TBNCDW_3",
    34: "TBNCDW_4", 35: "TBNCDW_5", 36: "TBNCDW_6",
    37: "TBNCUP_0", 38: "TBNCUP_1", 39: "TBNCUP_2", 40: "TBNCUP_3",
    41: "TBNCUP_4", 42: "TBNCUP_5", 43: "TBNCUP_6",
}

# Dragon Vault town layers contain a second, separate lower foreground chunk
# used by the town-screen composition. The construction thumbnail depicts only
# the cliff portal, so use that upper component rather than centring both.
CROPS = {
    36: (56, 0, 274, 212),
    43: (56, 0, 274, 212),
}

# Logical town-screen anchors for each source layer. They are converted to the
# 2x TBNCBACK coordinate system when producing a thumbnail scene.
ANCHORS = {
    "TBNCMAGE": (341, 116), "TBNCMAG2": (341, 97), "TBNCMAG3": (341, 78),
    "TBNCMAG4": (340, 62), "TBNCMAG5": (343, 35), "TBNCTVRN": (508, 189),
    "TBNCDOCK": (617, 265), "TBNCCSTL": (138, 66), "TBNCCAS2": (139, 66),
    "TBNCCAS3": (34, 18), "TBNCHALL": (468, 76), "TBNCHAL2": (482, 56),
    "TBNCHAL3": (478, 26), "TBNCHAL4": (481, 26), "TBNCMARK": (347, 215),
    "TBNCSILO": (276, 185), "TBNCBLAK": (382, 252), "TBNCEXT0": (307, 61), "TBNCSPEC": (18, 0),
    "TBNCEXT1": (247, 275), "TBNCHOLY": (410, 88), "TBNCDW_0": (80, 222),
    "TBNCDW_1": (502, 223), "TBNCDW_2": (0, 187), "TBNCDW_3": (607, 212),
    "TBNCDW_4": (206, 207), "TBNCDW_5": (0, 31), "TBNCDW_6": (663, 25),
    "TBNCUP_0": (64, 222), "TBNCUP_1": (498, 224), "TBNCUP_2": (0, 179),
    "TBNCUP_3": (615, 193), "TBNCUP_4": (222, 171), "TBNCUP_5": (0, 30),
    "TBNCUP_6": (662, 23),
}

# Reviewed target regions in the 1800x840 thumbnail master. These preserve the
# native construction-list hierarchy: narrow towers keep vertical room, while
# broad mausoleums retain their horizontal span. Dragon Vault is handled as a
# mountain scene below rather than a freestanding fit.
THUMBNAIL_BOXES = {
    16: (400, 150, 1400, 750),
    30: (240, 60, 1560, 820), 31: (120, 70, 1656, 800),
    32: (510, 0, 1110, 840), 33: (0, 190, 1800, 790),
    34: (480, 50, 1200, 810), 35: (600, 0, 1260, 840),
    37: (120, 35, 1680, 830), 38: (90, 55, 1710, 805),
    39: (420, 0, 1170, 840), 40: (0, 145, 1800, 795),
    41: (480, 20, 1230, 825), 42: (570, 0, 1320, 840),
}


def master_from_layer(source, crop=None, target_box=None):
    """Place one town building layer in the 150:70 thumbnail master frame."""
    source = source.convert("RGBA")
    if crop:
        source = source.crop(crop)
    canvas = Image.new("RGBA", (1800, 840))
    if target_box:
        left, top, right, bottom = target_box
        target_width, target_height = right - left, bottom - top
    else:
        left, top, target_width, target_height = 130, 80, 1540, 760
    scale = min(target_width / source.width, target_height / source.height)
    size = (max(1, round(source.width * scale)), max(1, round(source.height * scale)))
    source = source.resize(size, Image.Resampling.LANCZOS)
    x = left + (target_width - source.width) // 2
    y = top + (target_height - source.height) // 2
    canvas.alpha_composite(source, (x, y))
    return canvas


def town_scene_master(source, background, anchor, crop=None):
    """Crop the HD town scene around the actual building-layer anchor."""
    source = source.convert("RGBA")
    offset_x = offset_y = 0
    if crop:
        offset_x, offset_y = crop[:2]
        source = source.crop(crop)
    x = anchor[0] * 2 + offset_x
    y = anchor[1] * 2 + offset_y
    center_x = x + source.width // 2
    center_y = y + source.height // 2
    left = max(0, min(background.width - 600, center_x - 300))
    top = max(0, min(background.height - 280, center_y - 140))
    canvas = background.convert("RGBA").crop((left, top, left + 600, top + 280))
    canvas.alpha_composite(source, (x - left, y - top))
    return canvas.resize((1800, 840), Image.Resampling.LANCZOS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--town-layers", type=Path, required=True,
                        help=".../content/sprites2x/necropolis")
    parser.add_argument("--fallback", type=Path, required=True,
                        help="existing generated masters; used only for slot 18")
    parser.add_argument("--background", type=Path,
                        help="HD TBNCBACK used for cliff-portal thumbnail scenes")
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
        elif args.background and frame in (36, 43):
            image = town_scene_master(Image.open(source), Image.open(args.background),
                                      ANCHORS[source_name], CROPS.get(frame))
        else:
            image = master_from_layer(Image.open(source), CROPS.get(frame), THUMBNAIL_BOXES.get(frame))
        image.save(args.out / f"hallnecr-{frame:02}.png")
    print(f"derived {len(SOURCES)} town-layer masters; retained 1 native fallback")


if __name__ == "__main__":
    main()
