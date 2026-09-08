#!/usr/bin/env python3
"""Look at creature animations -- the originals, your replacements, or both.

Frames live at 450x400 with the creature occupying a small corner of that, so
opening the PNGs directly tells you very little. These views crop to the action,
keep every frame on a *shared* crop so motion stays visible, and can draw the
ground line the engine anchors to.

    sheet    contact sheet of one animation group
    layers   body / shadow / overlay for a single frame
    anim     animated GIF of one group, at the game's own frame rate
    compare  original and replacement side by side, frame for frame
    readability  does a concept image still read at the size the game draws it?

Frames come from either an original .def inside a .lod:

    preview.py sheet --lod "$LOD" --def CSKELE.DEF --group HOLDING

or from a mod you are building:

    preview.py sheet --mod ~/vcmi-mods/hd-creatures --creature CSKELE --group HOLDING

Requires Pillow (`pip install pillow`).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vcmi_anim import (  # noqa: E402
    GROUP_IDS,
    GROUP_NAMES,
    SCALE_DIRS,
    group_label,
    load_json,
    parse_animation,
)

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:
    sys.exit("preview.py needs Pillow: pip install pillow")

BACKDROP = (34, 34, 40, 255)
PAGE = (22, 22, 26, 255)
GRID = (70, 70, 82, 255)
ANCHOR = (220, 90, 90, 255)
CENTRE = (90, 150, 220, 255)
LABEL = (170, 170, 180, 255)


# ---------------------------------------------------------------------------
# Sources: a group of frames, as RGBA images on the full canvas
# ---------------------------------------------------------------------------

def resolve_group(text):
    """'HOLDING', 'holding' or '2' -> group id."""
    key = text.upper()
    if key in GROUP_IDS:
        return GROUP_IDS[key]
    try:
        return int(text)
    except ValueError:
        raise SystemExit("unknown animation group %r" % text)


def frames_from_def(lod, definition, gid, layer="body"):
    """Decode one group straight out of the .def -- no PNGs on disk needed."""
    from def_extract import DefFile, extract, read_lod, split_layers, to_canvas

    blob, entries = read_lod(lod)
    name = definition if definition.upper().endswith(".DEF") else definition + ".DEF"
    parsed = DefFile(extract(blob, entries, name))

    if gid not in parsed.groups:
        raise SystemExit("%s has no group %s (has %s)" % (
            name, group_label(gid), ", ".join(str(g) for g in sorted(parsed.groups))))

    out = []
    for index in range(len(parsed.groups[gid])):
        head, rows = parsed.frame_indices(gid, index)
        canvas = to_canvas(head, rows)
        body, shadow, overlay = split_layers(canvas, parsed.palette)
        pixels = {"body": body, "shadow": shadow, "overlay": overlay}[layer]
        out.append(Image.frombytes(
            "RGBA", (head["fullWidth"], head["fullHeight"]), bytes(pixels)))
    return out


def frames_from_mod(mod_dir, creature, gid, scale=1, layer="body"):
    """Load one group from a mod's animation JSON."""
    content = mod_dir / "content"
    if not content.is_dir():
        content = mod_dir / "Content"
    sprites = content / SCALE_DIRS[scale]
    anim_path = sprites / ("%s.json" % creature.upper())
    if not anim_path.is_file():
        raise SystemExit("no animation JSON at %s" % anim_path)

    groups = parse_animation(load_json(anim_path))
    if gid not in groups or not groups[gid]:
        raise SystemExit("%s has no group %s" % (anim_path.name, group_label(gid)))

    suffix = {"body": "", "shadow": "-shadow", "overlay": "-overlay"}[layer]
    out = []
    for frame in groups[gid]:
        relpath = frame.relpath if not suffix else frame.companion(suffix.lstrip("-"))
        path = sprites / relpath
        if not path.is_file():
            raise SystemExit("missing frame %s" % path)
        out.append(Image.open(path).convert("RGBA"))
    return out


def load_frames(args, layer="body"):
    gid = resolve_group(args.group)
    if args.lod:
        return frames_from_def(args.lod, getattr(args, "definition"), gid, layer), gid
    return frames_from_mod(args.mod, args.creature, gid, args.mod_scale, layer), gid


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------

def union_bbox(frames, pad=6):
    """One crop box covering every frame, so motion between frames stays visible."""
    boxes = [f.getchannel("A").getbbox() for f in frames]
    boxes = [b for b in boxes if b]
    if not boxes:
        raise SystemExit("every frame is fully transparent")
    left = max(0, min(b[0] for b in boxes) - pad)
    top = max(0, min(b[1] for b in boxes) - pad)
    right = min(frames[0].width, max(b[2] for b in boxes) + pad)
    bottom = min(frames[0].height, max(b[3] for b in boxes) + pad)
    return (left, top, right, bottom)


def flatten(image, background=BACKDROP):
    plate = Image.new("RGBA", image.size, background)
    plate.alpha_composite(image)
    return plate


def draw_anchor(image, crop, ground, centre):
    """Ground line and horizontal centre, in crop-local coordinates."""
    pen = ImageDraw.Draw(image)
    if ground is not None:
        y = ground - crop[1]
        if 0 <= y < image.height:
            pen.line([(0, y), (image.width, y)], fill=ANCHOR, width=1)
    if centre is not None:
        x = centre - crop[0]
        if 0 <= x < image.width:
            pen.line([(x, 0), (x, image.height)], fill=CENTRE, width=1)


def tile(frames, crop, scale, columns, anchor=None, labels=None):
    """Lay frames out in a grid, all sharing one crop."""
    cells = []
    for index, frame in enumerate(frames):
        cell = flatten(frame.crop(crop))
        if anchor:
            draw_anchor(cell, crop, *anchor)
        cell = cell.resize((cell.width * scale, cell.height * scale), Image.NEAREST)
        if labels:
            pen = ImageDraw.Draw(cell)
            pen.text((4, 4), labels[index], fill=LABEL)
        cells.append(cell)

    columns = min(columns, len(cells))
    rows = (len(cells) + columns - 1) // columns
    cw, ch = cells[0].size
    gap = 4
    sheet = Image.new(
        "RGBA",
        (columns * cw + (columns + 1) * gap, rows * ch + (rows + 1) * gap),
        PAGE,
    )
    for index, cell in enumerate(cells):
        col, row = index % columns, index // columns
        sheet.alpha_composite(cell, (gap + col * (cw + gap), gap + row * (ch + gap)))
    return sheet


def anchor_from_frames(frames):
    """Ground line and centre implied by the frames themselves."""
    boxes = [f.getchannel("A").getbbox() for f in frames]
    boxes = [b for b in boxes if b]
    ground = max(b[3] for b in boxes)
    centre = sum((b[0] + b[2]) / 2 for b in boxes) / len(boxes)
    return int(ground), int(centre)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_sheet(args):
    frames, gid = load_frames(args, args.layer)
    crop = union_bbox(frames)
    anchor = anchor_from_frames(frames) if args.anchor else None
    labels = ["%02d" % i for i in range(len(frames))] if args.numbers else None
    sheet = tile(frames, crop, args.scale, args.columns, anchor, labels)
    sheet.save(args.out)
    print("%s: %d frame(s), crop %dx%d -> %s (%dx%d)" % (
        group_label(gid), len(frames), crop[2] - crop[0], crop[3] - crop[1],
        args.out, sheet.width, sheet.height))
    if anchor:
        print("  ground line y=%d (red), body centre x=%d (blue)" % anchor)
    return 0


def cmd_layers(args):
    tiles, crop = [], None
    for layer in ("body", "shadow", "overlay"):
        frames, gid = load_frames(args, layer)
        if args.frame >= len(frames):
            raise SystemExit("frame %d out of range (group has %d)" % (args.frame, len(frames)))
        if crop is None:
            crop = union_bbox(frames)
        tiles.append(frames[args.frame])
    sheet = tile(tiles, crop, args.scale, 3, None, ["body", "shadow", "overlay"])
    sheet.save(args.out)
    print("%s frame %d layers -> %s" % (group_label(gid), args.frame, args.out))
    return 0


def cmd_anim(args):
    frames, gid = load_frames(args, args.layer)
    crop = union_bbox(frames)
    anchor = anchor_from_frames(frames) if args.anchor else None

    cells = []
    for frame in frames:
        cell = flatten(frame.crop(crop))
        if anchor:
            draw_anchor(cell, crop, *anchor)
        cells.append(cell.resize((cell.width * args.scale, cell.height * args.scale), Image.NEAREST))

    cells[0].save(
        args.out,
        save_all=True,
        append_images=cells[1:],
        duration=int(1000 / args.fps),
        loop=0,
        disposal=2,
    )
    print("%s: %d frame(s) at %d fps -> %s" % (group_label(gid), len(frames), args.fps, args.out))
    print("  watch the feet: if they wander, the anchor is wrong")
    return 0


def cmd_compare(args):
    gid = resolve_group(args.group)
    original = frames_from_def(args.lod, args.definition, gid, args.layer)
    replacement = frames_from_mod(args.mod, args.creature, gid, args.mod_scale, args.layer)

    if len(original) != len(replacement):
        print("note: original has %d frames, replacement has %d -- comparing the first %d"
              % (len(original), len(replacement), min(len(original), len(replacement))))

    # Bring the replacement down to 1x so the two are directly comparable.
    if args.mod_scale != 1:
        replacement = [
            f.resize((f.width // args.mod_scale, f.height // args.mod_scale), Image.LANCZOS)
            for f in replacement
        ]

    count = min(len(original), len(replacement))
    crop = union_bbox(original[:count] + replacement[:count])

    interleaved, labels = [], []
    for index in range(count):
        interleaved += [original[index], replacement[index]]
        labels += ["orig %02d" % index, "new  %02d" % index]

    sheet = tile(interleaved, crop, args.scale_out, 2, None, labels)
    sheet.save(args.out)
    print("%s: %d frame pair(s) -> %s" % (group_label(gid), count, args.out))
    return 0


def key_background(image, tolerance=28):
    """Give an opaque image an alpha channel by keying out its backdrop.

    Concept art from an image API arrives on a backdrop, not as a cutout. Without
    this the "silhouette" is the whole rectangle and every score is meaningless.

    The key is global colour distance, not a flood fill from the border. Negative
    space enclosed by the character -- between the legs, inside a bent arm, under a
    sword held across the body -- is not reachable from the frame edge, and a flood
    fill leaves it filled in. Those gaps are exactly what a silhouette-first design
    lives or dies by, so they have to be cut.

    This requires the backdrop to be a flat colour the subject does not contain;
    gen_concept.py asks for chroma green for that reason. A near-neutral or gradient
    backdrop cannot be keyed this way and should be regenerated rather than fought.
    """
    rgb = image.convert("RGB")
    w, h = rgb.size
    pixels = rgb.load()

    border = ([pixels[x, 0] for x in range(0, w, 4)] +
              [pixels[x, h - 1] for x in range(0, w, 4)] +
              [pixels[0, y] for y in range(0, h, 4)] +
              [pixels[w - 1, y] for y in range(0, h, 4)])
    bg = tuple(sorted(c[i] for c in border)[len(border) // 2] for i in range(3))

    keyed = image.copy()
    out = keyed.load()
    for y in range(h):
        for x in range(w):
            r, g, b, _ = out[x, y]
            if abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) <= tolerance:
                out[x, y] = (r, g, b, 0)
    return keyed, bg


def silhouette(image, threshold=0, despeckle=True):
    """Binary alpha mask, trimmed to content.

    Keying a backdrop leaves a scatter of stray pixels at the frame edges. They are
    invisible, but they stretch the bounding box to the full image, and everything
    downstream scales by that box -- the character ends up a few pixels tall inside a
    huge mask and every score collapses. An opening removes specks before measuring.
    """
    alpha = image.getchannel("A").point(lambda v: 255 if v > threshold else 0)
    if despeckle:
        alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
    box = alpha.getbbox()
    if box is None:
        raise SystemExit("image is fully transparent (or nothing survived despeckling)")
    return alpha.crop(box)


def fit_height(mask, height):
    """Scale a mask so it is `height` px tall, preserving aspect."""
    width = max(1, round(mask.width * height / mask.height))
    return mask.resize((width, height), Image.LANCZOS).point(lambda v: 255 if v > 127 else 0)


def silhouette_iou(a, b):
    """Overlap of two masks after centring them on a shared canvas."""
    w, h = max(a.width, b.width), max(a.height, b.height)
    canvas = []
    for mask in (a, b):
        plate = Image.new("L", (w, h), 0)
        plate.paste(mask, ((w - mask.width) // 2, h - mask.height))
        canvas.append(plate)
    pa, pb = canvas[0].getdata(), canvas[1].getdata()
    inter = sum(1 for x, y in zip(pa, pb) if x and y)
    union = sum(1 for x, y in zip(pa, pb) if x or y)
    return inter / union if union else 0.0


def cmd_readability(args):
    """Does a concept image still read at the size the game actually draws it?"""
    with Image.open(args.image) as raw:
        candidate = raw.convert("RGBA")

    keyed_note = None
    opaque = candidate.getchannel("A").getextrema() == (255, 255)
    if args.background == "key" or (args.background == "auto" and opaque):
        candidate, bg = key_background(candidate, args.bg_tolerance)
        keyed_note = "keyed out background #%02X%02X%02X" % bg
        if candidate.getchannel("A").getextrema()[0] == 255:
            raise SystemExit(
                "background keying removed nothing -- the backdrop is not flat. "
                "Cut the character out first, or raise --bg-tolerance.")
    elif opaque:
        raise SystemExit(
            "image is fully opaque, so its silhouette would be the whole rectangle. "
            "Use --background key, or supply a cutout with alpha.")

    mask = silhouette(candidate)
    box = candidate.getchannel("A").getbbox()
    art = candidate.crop(box)

    scaled = {}
    for factor in (1, 2, 4):
        height = args.height * factor
        width = max(1, round(art.width * height / art.height))
        scaled[factor] = art.resize((width, height), Image.LANCZOS)

    strip = [("%dx" % f, flatten(img)) for f, img in sorted(scaled.items())]
    sil_1x = fit_height(mask, args.height)
    sil_plate = Image.new("RGBA", sil_1x.size, (28, 28, 33, 255))
    sil_plate.paste((235, 235, 240, 255), mask=sil_1x)
    strip.append(("silhouette 1x", sil_plate))

    verdict = []
    if args.against:
        gid = resolve_group(args.against_group)
        originals = frames_from_def(args.lod, args.against, gid, "body")
        original = originals[min(args.against_frame, len(originals) - 1)]
        orig_sil = silhouette(original)
        orig_mask = fit_height(orig_sil, args.height)
        orig_plate = Image.new("RGBA", orig_mask.size, (28, 28, 33, 255))
        orig_plate.paste((235, 235, 240, 255), mask=orig_mask)
        strip.append(("original 1x", orig_plate))

        # Proportion is the pose-independent half of the comparison, and the half
        # that actually has to match: the engine draws both into the same hex.
        cand_aspect = mask.width / mask.height
        orig_aspect = orig_sil.width / orig_sil.height
        drift = (cand_aspect / orig_aspect - 1) * 100
        verdict.append("proportions: candidate %.2f wide-to-tall, original %.2f (%+.0f%%)"
                       % (cand_aspect, orig_aspect, drift))
        if abs(drift) <= 15:
            verdict.append("  within 15% -- it will occupy its hex like the original does")
        else:
            verdict.append("  more than 15%% off; %s than the original at the same height"
                           % ("wider" if drift > 0 else "narrower"))

        # Overlap is pose-dependent, so it is a weak signal at concept stage: a free
        # pose is being compared against one specific animation frame, and facing
        # alone can halve it. Take the better of the two mirrorings and report it as
        # an indication, not a gate. It becomes the real test later, when rendered
        # frames are compared against the original frame they replace.
        best = max(silhouette_iou(sil_1x, orig_mask),
                   silhouette_iou(sil_1x.transpose(Image.FLIP_LEFT_RIGHT), orig_mask))
        verdict.append("silhouette overlap (best of both facings): %.0f%%" % (best * 100))
        verdict.append("  indicative only at concept stage -- pose differences dominate.")
        verdict.append("  Judge the 1x tile by eye; the number is the gate for rendered frames.")

    gap, pad = 14, 26
    height = max(img.height for _, img in strip) + pad + 8
    width = sum(img.width for _, img in strip) + gap * (len(strip) + 1)
    sheet = Image.new("RGBA", (width, height), PAGE)
    pen = ImageDraw.Draw(sheet)
    x = gap
    for label, img in strip:
        sheet.alpha_composite(img, (x, pad + (height - pad - 8 - img.height)))
        pen.text((x, 6), label, fill=LABEL)
        x += img.width + gap
    sheet.save(args.out)

    print("%s -> %s" % (args.image, args.out))
    print("  creature drawn at %d px tall; source art is %dx%d" % (args.height, art.width, art.height))
    if keyed_note:
        print("  " + keyed_note)
    for line in verdict:
        print("  " + line)
    return 0

def add_source(parser, allow_mod=True):
    source = parser.add_argument_group("frame source")
    source.add_argument("--lod", type=Path, help="path to H3sprite.lod")
    source.add_argument("--def", dest="definition", help="def name, e.g. CSKELE.DEF")
    if allow_mod:
        source.add_argument("--mod", type=Path, help="mod directory")
        source.add_argument("--creature", help="animation name, e.g. CSKELE")
        source.add_argument(
            "--mod-scale", type=int, default=1, choices=sorted(SCALE_DIRS),
            help="which Sprites{N}x tree to read from the mod (default 1)")
    parser.add_argument("--group", required=True, help="group name or id, e.g. HOLDING or 2")
    parser.add_argument("--layer", default="body", choices=["body", "shadow", "overlay"])


def check_source(parser, args, allow_mod=True):
    has_def = bool(args.lod and args.definition)
    has_mod = allow_mod and bool(getattr(args, "mod", None) and getattr(args, "creature", None))
    if has_def == has_mod:
        parser.error("give either --lod with --def, or --mod with --creature")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sheet = sub.add_parser("sheet", help="contact sheet of one group")
    add_source(sheet)
    sheet.add_argument("--out", default="sheet.png")
    sheet.add_argument("--scale", type=int, default=2, help="zoom factor for the output")
    sheet.add_argument("--columns", type=int, default=6)
    sheet.add_argument("--anchor", action="store_true", help="draw ground line and centre")
    sheet.add_argument("--numbers", action="store_true", help="label frames")
    sheet.set_defaults(func=cmd_sheet)

    layers = sub.add_parser("layers", help="body / shadow / overlay for one frame")
    add_source(layers)
    layers.add_argument("--frame", type=int, default=0)
    layers.add_argument("--out", default="layers.png")
    layers.add_argument("--scale", type=int, default=4, help="zoom factor for the output")
    layers.set_defaults(func=cmd_layers)

    anim = sub.add_parser("anim", help="animated GIF of one group")
    add_source(anim)
    anim.add_argument("--out", default="anim.gif")
    anim.add_argument("--scale", type=int, default=3, help="zoom factor for the output")
    anim.add_argument("--fps", type=int, default=8)
    anim.add_argument("--anchor", action="store_true")
    anim.set_defaults(func=cmd_anim)

    read = sub.add_parser(
        "readability", help="does a concept image still read at in-game size?")
    read.add_argument("image", help="candidate concept art (PNG with alpha)")
    read.add_argument("--height", type=int, default=79,
                      help="height in px the creature occupies in game (CSKELE idle: 79)")
    read.add_argument("--out", default="readability.png")
    read.add_argument("--lod", type=Path, help="archive, to compare against the original")
    read.add_argument("--against", help="original def to compare against, e.g. CSKELE.DEF")
    read.add_argument("--against-group", default="HOLDING")
    read.add_argument("--against-frame", type=int, default=0)
    read.add_argument("--background", choices=["auto", "key", "alpha"], default="auto",
                      help="auto: key out a flat backdrop when the image has no alpha "
                           "(default); key: always; alpha: trust the alpha channel")
    read.add_argument("--bg-tolerance", type=int, default=28,
                      help="how close to the backdrop colour still counts as background")
    read.set_defaults(func=cmd_readability)

    compare = sub.add_parser("compare", help="original vs replacement, frame for frame")
    add_source(compare)
    compare.add_argument("--out", default="compare.png")
    compare.add_argument("--scale-out", type=int, default=2)
    compare.set_defaults(func=cmd_compare)

    args = parser.parse_args(argv)

    if args.command == "readability":
        if bool(args.against) != bool(args.lod):
            parser.error("--against needs --lod (and vice versa)")
    elif args.command == "compare":
        if not (args.lod and args.definition and args.mod and args.creature):
            parser.error("compare needs --lod, --def, --mod and --creature")
    else:
        check_source(parser, args)

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
