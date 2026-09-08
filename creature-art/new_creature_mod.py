#!/usr/bin/env python3
"""Scaffold a VCMI mod that replaces a creature's battle animation.

Generates mod.json, one animation JSON per scale, and the empty frame directories
your renderer is expected to fill. Frame filenames are fixed up front so the render
side and the engine side agree without a second mapping step.

Usage:
    new_creature_mod.py --mod-dir ~/vcmi-mods/hd-creatures \\
                        --creature CSKELET --canvas 116x104 \\
                        --scales 1,2 --layout layouts/melee.json

The animation name must match the .def it replaces (CSKELET.def -> CSKELET), and
the canvas must be that .def's full frame size. Both come from `def2bmp CSKELET.def`
in the in-game console.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vcmi_anim import (  # noqa: E402
    GROUP_IDS,
    GROUP_NAMES,
    OVERLAY_GROUPS,
    SCALE_DIRS,
    load_json,
)

MOD_JSON = {
    "name": "HD Creatures",
    "description": "Replacement creature artwork",
    "version": "0.1",
    "author": "",
    "contact": "",
    "modType": "Graphical",
}


def parse_canvas(text):
    try:
        width, height = text.lower().split("x")
        return int(width), int(height)
    except ValueError:
        raise argparse.ArgumentTypeError("canvas must look like 116x104") from None


def parse_scales(text):
    scales = []
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        value = int(chunk)
        if value not in SCALE_DIRS:
            raise argparse.ArgumentTypeError("scale must be one of %s" % sorted(SCALE_DIRS))
        scales.append(value)
    if 1 not in scales:
        raise argparse.ArgumentTypeError("scale 1 is mandatory: HD trees are only used when upscaling is on")
    return sorted(set(scales))


def resolve_layout(spec):
    """{group_id: frame_count} from a layout JSON keyed by name or id."""
    layout = {}
    for key, count in spec.items():
        if key.startswith("_"):
            continue  # comment field
        if key in GROUP_IDS:
            gid = GROUP_IDS[key]
        else:
            try:
                gid = int(key)
            except ValueError:
                raise SystemExit("unknown animation group %r in layout" % key)
            if gid not in GROUP_NAMES:
                raise SystemExit("group id %d is not a valid ECreatureAnimType" % gid)
        if not isinstance(count, int) or count < 1:
            raise SystemExit("group %s: frame count must be a positive integer" % key)
        layout[gid] = count
    if not layout:
        raise SystemExit("layout is empty")
    return layout


def layout_from_def(lod_path, creature):
    """Derive {group: frame count} and the canvas straight from the original .def."""
    from def_extract import DefFile, extract, read_lod

    blob, entries = read_lod(lod_path)
    name = creature if creature.upper().endswith(".DEF") else creature + ".DEF"
    definition = DefFile(extract(blob, entries, name))

    layout, skipped, canvases = {}, [], set()
    for gid in sorted(definition.groups):
        head = definition.frame_header(gid, 0)
        canvases.add((head["fullWidth"], head["fullHeight"]))
        if gid not in GROUP_NAMES:
            # e.g. CSKELE has groups 9 and 10, documented as unused duplicates of
            # TURN_L/TURN_R in client/battle/BattleConstants.h
            skipped.append(gid)
            continue
        layout[gid] = len(definition.groups[gid])

    if len(canvases) > 1:
        raise SystemExit("%s: groups disagree on canvas size: %s" % (creature, sorted(canvases)))
    return layout, next(iter(canvases)), skipped


def build_animation(creature, layout, basepath, shadow_mode, generate_overlay):
    sequences = []
    for gid in sorted(layout):
        name = GROUP_NAMES[gid].lower()
        entry = {
            "group": gid,
            "frames": ["%s_%02d.png" % (name, i) for i in range(layout[gid])],
        }
        if shadow_mode:
            entry["generateShadow"] = shadow_mode
        if generate_overlay and gid in OVERLAY_GROUPS:
            entry["generateOverlay"] = 1
        sequences.append(entry)
    return {"basepath": basepath, "sequences": sequences}


def write_json(path, payload, header=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=4)
    if header:
        text = "\n".join("// " + line if line else "//" for line in header) + "\n" + text
    path.write_text(text + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--mod-dir", type=Path, required=True)
    parser.add_argument("--creature", required=True, help="animation name, e.g. CSKELE")
    parser.add_argument(
        "--from-def",
        type=Path,
        metavar="LOD",
        help="read canvas and frame counts from the original .def in this .lod "
             "(e.g. ~/Library/Application Support/vcmi/Data/H3sprite.lod). "
             "Replaces --canvas and --layout.",
    )
    parser.add_argument("--canvas", type=parse_canvas, help="1x frame size, e.g. 450x400")
    parser.add_argument("--scales", type=parse_scales, default=[1, 2])
    parser.add_argument("--layout", type=Path, help="group -> frame count JSON")
    parser.add_argument(
        "--generate-shadow",
        type=int,
        choices=[0, 1, 2],
        default=0,
        help="0 = supply -shadow images yourself (default), 1 = normal, 2 = sheared",
    )
    parser.add_argument(
        "--generate-overlay",
        action="store_true",
        help="let the engine derive the hover outline instead of supplying -overlay images",
    )
    parser.add_argument("--force", action="store_true", help="overwrite existing animation JSON")
    args = parser.parse_args(argv)

    creature = args.creature.upper()

    if args.from_def:
        if args.canvas or args.layout:
            parser.error("--from-def replaces --canvas and --layout")
        layout, (width, height), skipped = layout_from_def(args.from_def, creature)
        print("read %s from %s: canvas %dx%d, %d group(s), %d frame(s)" % (
            creature, args.from_def.name, width, height, len(layout), sum(layout.values())))
        if skipped:
            print("  skipped unused/unknown group(s): %s" % ", ".join(str(g) for g in skipped))
    else:
        if not args.canvas or not args.layout:
            parser.error("pass --from-def, or both --canvas and --layout")
        layout = resolve_layout(load_json(args.layout))
        width, height = args.canvas
    basepath = "creatures/%s/" % creature.lower()

    content = args.mod_dir / "content"
    mod_json = args.mod_dir / "mod.json"
    created = []

    if not mod_json.exists():
        write_json(mod_json, MOD_JSON)
        created.append(mod_json)

    for scale in args.scales:
        sprites = content / SCALE_DIRS[scale]
        anim_path = sprites / ("%s.json" % creature)
        if anim_path.exists() and not args.force:
            print("skip (exists): %s" % anim_path)
        else:
            write_json(
                anim_path,
                build_animation(
                    creature, layout, basepath, args.generate_shadow, args.generate_overlay
                ),
                header=[
                    "%s -- %dx replacement animation" % (creature, scale),
                    "Canvas for every frame: %dx%d px." % (width * scale, height * scale),
                    "Frames must be padded to that size with a fixed ground line;",
                    "the engine crops to the first idle frame and positions by top-left.",
                ],
            )
            created.append(anim_path)
        (sprites / basepath).mkdir(parents=True, exist_ok=True)

    manifest = {
        "creature": creature,
        "canvas1x": {"width": width, "height": height},
        "basepath": basepath,
        "scales": args.scales,
        "groups": [
            {
                "id": gid,
                "name": GROUP_NAMES[gid],
                "frames": layout[gid],
                "files": ["%s_%02d.png" % (GROUP_NAMES[gid].lower(), i) for i in range(layout[gid])],
            }
            for gid in sorted(layout)
        ],
    }
    manifest_path = args.mod_dir / "render" / ("%s.manifest.json" % creature.lower())
    write_json(manifest_path, manifest)
    created.append(manifest_path)

    total = sum(layout.values())
    print("scaffolded %s (%d frames x %d scale(s))" % (creature, total, len(args.scales)))
    for path in created:
        print("  %s" % path)
    print()
    print("render targets, per scale:")
    for scale in args.scales:
        print("  %dx -> %s at %dx%d px" % (
            scale, content / SCALE_DIRS[scale] / basepath, width * scale, height * scale
        ))
    print()
    print("the render manifest at %s lists every expected filename." % manifest_path)
    print("validate with: validate_creature_animation.py %s" % args.mod_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
