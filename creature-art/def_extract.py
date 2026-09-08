#!/usr/bin/env python3
"""Read Heroes III .def animations out of a .lod archive.

Two things this gives the art pipeline:

  info    the numbers every later step needs -- canvas size, animation groups,
          frame counts, and where the creature's ground line sits inside the
          canvas (derived from per-frame margins)

  export  reference frames as PNG, already split into the three layers the
          engine wants back: body, shadow and overlay. H3 encodes those in
          reserved palette indices 0-7; this undoes that encoding, so the
          renders you produce later have something exact to match against.

Usage:
    def_extract.py info   H3sprite.lod CSKELE.DEF
    def_extract.py export H3sprite.lod CSKELE.DEF --out ref/cskele

Format references: lib/filesystem/CArchiveLoader.cpp (LOD), client/render/CDefFile.cpp
(DEF), clientsdl2/render/ScalableImage.cpp:31-51 (the special palette).
"""

import argparse
import json
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vcmi_anim import GROUP_NAMES, group_label, write_png  # noqa: E402

# clientsdl2/render/ScalableImage.cpp:42 -- what palette indices 0-7 really mean.
# (r, g, b, a) after translation; anything >= 8 is ordinary colour.
SPECIAL_PALETTE = [
    (0, 0, 0, 0),    # 0 transparency
    (0, 0, 0, 64),   # 1 shadow border
    (0, 0, 0, 64),   # 2 shadow border (fog of war)
    (0, 0, 0, 128),  # 3 shadow body (fog of war)
    (0, 0, 0, 128),  # 4 shadow body
    (0, 0, 0, 0),    # 5 selection / owner flag
    (0, 0, 0, 128),  # 6 shadow body below selection
    (0, 0, 0, 64),   # 7 shadow border below selection
]

SHADOW_INDICES = {1: 64, 2: 64, 3: 128, 4: 128, 6: 128, 7: 64}
OVERLAY_INDICES = {5}


# ---------------------------------------------------------------------------
# LOD archive
# ---------------------------------------------------------------------------

def read_lod(path):
    """{upper-case name: bytes}. Mirrors CArchiveLoader::initLODArchive."""
    blob = Path(path).read_bytes()
    total = struct.unpack_from("<I", blob, 8)[0]
    entries = {}
    pos = 0x5C
    for _ in range(total):
        raw_name = blob[pos:pos + 16]
        pos += 16
        offset, full_size, _unused, packed_size = struct.unpack_from("<IIII", blob, pos)
        pos += 16
        name = raw_name.split(b"\0")[0].decode("latin-1").upper()
        entries[name] = (offset, full_size, packed_size)
    return blob, entries


def extract(blob, entries, name):
    key = name.upper()
    if key not in entries:
        raise SystemExit("%s not found in archive" % name)
    offset, full_size, packed_size = entries[key]
    if packed_size:
        return zlib.decompress(blob[offset:offset + packed_size])
    return blob[offset:offset + full_size]


# ---------------------------------------------------------------------------
# DEF animation
# ---------------------------------------------------------------------------

class DefFile:
    """Parsed .def: palette, group -> frame offsets. Mirrors CDefFile."""

    def __init__(self, data):
        self.data = data
        pos = 4                      # type
        pos += 8                     # width, height -- unused, as in CDefFile
        total_blocks = struct.unpack_from("<I", data, pos)[0]
        pos += 4

        self.palette = [tuple(data[pos + i * 3: pos + i * 3 + 3]) for i in range(256)]
        pos += 768

        self.groups = {}             # gid -> [offset]
        self.names = {}              # gid -> [frame name]
        for _ in range(total_blocks):
            gid = struct.unpack_from("<I", data, pos)[0]
            pos += 4
            count = struct.unpack_from("<I", data, pos)[0]
            pos += 12                # count field + 8 unknown bytes

            names = []
            for _ in range(count):
                names.append(data[pos:pos + 13].split(b"\0")[0].decode("latin-1"))
                pos += 13
            self.names[gid] = names

            offsets = list(struct.unpack_from("<%dI" % count, data, pos))
            pos += 4 * count
            self.groups[gid] = offsets

    def frame_header(self, gid, index):
        """SSpriteDef -- client/render/CDefFile.h:28."""
        off = self.groups[gid][index]
        (size, fmt, full_w, full_h, w, h, left, top) = struct.unpack_from("<IIIIIIii", self.data, off)
        return {
            "size": size, "format": fmt,
            "fullWidth": full_w, "fullHeight": full_h,
            "width": w, "height": h,
            "leftMargin": left, "topMargin": top,
        }

    def frame_indices(self, gid, index):
        """Decode one frame to a width*height list of palette indices."""
        head = self.frame_header(gid, index)
        base = self.groups[gid][index] + 32
        data = self.data
        w, h, fmt = head["width"], head["height"], head["format"]

        # CDefFile.cpp:105 -- SGTWMTA/SGTWMTB oddity
        if fmt == 1 and w > head["fullWidth"] and h > head["fullHeight"]:
            head["leftMargin"] = head["topMargin"] = 0
            w = head["width"] = head["fullWidth"]
            h = head["height"] = head["fullHeight"]
            base -= 16

        rows = []
        if fmt == 0:
            pos = base
            for _ in range(h):
                rows.append(list(data[pos:pos + w]))
                pos += w

        elif fmt == 1:
            line_offsets = struct.unpack_from("<%dI" % h, data, base)
            for i in range(h):
                pos = base + line_offsets[i]
                row = []
                while len(row) < w:
                    seg_type = data[pos]
                    length = data[pos + 1] + 1
                    pos += 2
                    if seg_type == 0xFF:
                        row.extend(data[pos:pos + length])
                        pos += length
                    else:
                        row.extend([seg_type] * length)
                rows.append(row[:w])

        elif fmt in (2, 3):
            # Format 2 stores one starting offset and then runs contiguously;
            # format 3 stores a fresh offset per row. CDefFile.cpp:170-215.
            pos = base + struct.unpack_from("<H", data, base)[0]
            for i in range(h):
                if fmt == 3:
                    pos = base + struct.unpack_from("<H", data, base + i * 2 * (w // 32))[0]
                row = []
                while len(row) < w:
                    segment = data[pos]
                    pos += 1
                    code, length = segment >> 5, (segment & 31) + 1
                    if code == 7:
                        row.extend(data[pos:pos + length])
                        pos += length
                    else:
                        row.extend([code] * length)
                rows.append(row[:w])
        else:
            raise SystemExit("unsupported def format %d" % fmt)

        return head, rows


def to_canvas(head, rows):
    """Place the decoded block into the full canvas, padded with index 0."""
    full_w, full_h = head["fullWidth"], head["fullHeight"]
    left, top = head["leftMargin"], head["topMargin"]
    canvas = [[0] * full_w for _ in range(full_h)]
    for y, row in enumerate(rows):
        ty = top + y
        if not 0 <= ty < full_h:
            continue
        for x, value in enumerate(row):
            tx = left + x
            if 0 <= tx < full_w:
                canvas[ty][tx] = value
    return canvas


def split_layers(canvas, palette):
    """(body, shadow, overlay) as flat RGBA bytearrays."""
    body, shadow, overlay = bytearray(), bytearray(), bytearray()
    for row in canvas:
        for value in row:
            if value >= 8:
                body += bytes(palette[value]) + b"\xff"
                shadow += b"\0\0\0\0"
                overlay += b"\0\0\0\0"
            else:
                body += b"\0\0\0\0"
                alpha = SHADOW_INDICES.get(value, 0)
                shadow += bytes((0, 0, 0, alpha))
                overlay += b"\xff\xff\xff\xff" if value in OVERLAY_INDICES else b"\0\0\0\0"
    return body, shadow, overlay


def content_bbox(canvas):
    """Bounding box of body pixels (index >= 8): (left, top, right, bottom)."""
    left = top = 1 << 30
    right = bottom = -1
    for y, row in enumerate(canvas):
        for x, value in enumerate(row):
            if value >= 8:
                left, right = min(left, x), max(right, x)
                top, bottom = min(top, y), max(bottom, y)
    return None if right < 0 else (left, top, right + 1, bottom + 1)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_info(args):
    blob, entries = read_lod(args.lod)
    definition = DefFile(extract(blob, entries, args.definition))

    canvases = {}
    print("%s" % args.definition.upper())
    print()
    print("%-26s %6s  %s" % ("group", "frames", "canvas"))
    print("-" * 52)
    total = 0
    for gid in sorted(definition.groups):
        frames = definition.groups[gid]
        head = definition.frame_header(gid, 0)
        size = (head["fullWidth"], head["fullHeight"])
        canvases.setdefault(size, []).append(gid)
        total += len(frames)
        print("%-26s %6d  %dx%d" % (group_label(gid), len(frames), *size))
    print("-" * 52)
    print("%-26s %6d" % ("total", total))
    print()

    if len(canvases) > 1:
        print("WARNING: groups disagree on canvas size: %s" % dict(canvases))
    else:
        print("canvas: %dx%d (all groups agree)" % next(iter(canvases)))

    if args.anchor:
        print()
        print("ground line and horizontal centre of the body pixels, per group:")
        print("%-26s %8s %8s %8s" % ("group", "bottom", "centre", "spread"))
        print("-" * 54)
        for gid in sorted(definition.groups):
            bottoms, centres = [], []
            for i in range(len(definition.groups[gid])):
                head, rows = definition.frame_indices(gid, i)
                box = content_bbox(to_canvas(head, rows))
                if box:
                    bottoms.append(box[3])
                    centres.append((box[0] + box[2]) / 2)
            if bottoms:
                print("%-26s %8.1f %8.1f %8.1f" % (
                    group_label(gid),
                    sum(bottoms) / len(bottoms),
                    sum(centres) / len(centres),
                    max(bottoms) - min(bottoms),
                ))
    return 0


def cmd_export(args):
    blob, entries = read_lod(args.lod)
    definition = DefFile(extract(blob, entries, args.definition))
    out = Path(args.out)

    layout = {"groups": [], "canvas": None}
    written = 0
    for gid in sorted(definition.groups):
        if args.groups and gid not in args.groups:
            continue
        name = (GROUP_NAMES.get(gid) or ("group%d" % gid)).lower()
        entry = {"id": gid, "name": GROUP_NAMES.get(gid, str(gid)), "frames": []}
        for i in range(len(definition.groups[gid])):
            head, rows = definition.frame_indices(gid, i)
            canvas = to_canvas(head, rows)
            w, h = head["fullWidth"], head["fullHeight"]
            layout["canvas"] = [w, h]

            body, shadow, overlay = split_layers(canvas, definition.palette)
            stem = "%s_%02d" % (name, i)
            (out / "body").mkdir(parents=True, exist_ok=True)
            write_png(out / "body" / ("%s.png" % stem), w, h, body)
            written += 1
            if not args.body_only:
                for label, pixels in (("shadow", shadow), ("overlay", overlay)):
                    (out / label).mkdir(parents=True, exist_ok=True)
                    write_png(out / label / ("%s.png" % stem), w, h, pixels)
                    written += 1

            box = content_bbox(canvas)
            entry["frames"].append({"file": "%s.png" % stem, "bbox": box})
        layout["groups"].append(entry)

    (out / "layout.json").write_text(json.dumps(layout, indent=2) + "\n")
    print("wrote %d png(s) to %s" % (written, out))
    print("canvas %dx%d; layout written to %s" % (*layout["canvas"], out / "layout.json"))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    info = sub.add_parser("info", help="print groups, frame counts and canvas")
    info.add_argument("lod", type=Path)
    info.add_argument("definition")
    info.add_argument("--anchor", action="store_true", help="also report per-group ground line")
    info.set_defaults(func=cmd_info)

    export = sub.add_parser("export", help="export reference frames as layered PNG")
    export.add_argument("lod", type=Path)
    export.add_argument("definition")
    export.add_argument("--out", required=True)
    export.add_argument("--groups", type=lambda s: {int(x) for x in s.split(",")}, default=None)
    export.add_argument("--body-only", action="store_true")
    export.set_defaults(func=cmd_export)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
