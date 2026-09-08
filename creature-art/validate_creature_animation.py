#!/usr/bin/env python3
"""Validate replacement creature battle animations in a VCMI mod.

Checks the layout rules the engine assumes but never reports:

  * every frame of a creature shares one canvas size
  * scale variants agree on frame counts, filenames and canvas ratio
  * required animation groups are present
  * PNGs are non-indexed, so shadow/overlay/player-colour variants work
  * mouse-hover overlays exist for the idle groups
  * (with Pillow) the creature does not drift inside its canvas across a group

See README.md for why each of these matters and where the engine enforces it.

Usage:
    validate_creature_animation.py MOD_DIR [--shooter CSKELET,CARCHER] [--json]

Exits 1 if any error was reported.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vcmi_anim import (  # noqa: E402
    DERIVED_GROUPS,
    GROUP_NAMES,
    IDLE_GROUPS,
    OVERLAY_GROUPS,
    RECOMMENDED_GROUPS,
    REQUIRED_GROUPS,
    SCALE_DIRS,
    SHOOTER_GROUPS,
    group_label,
    load_json,
    parse_animation,
    read_png_info,
)

try:
    from PIL import Image
except ImportError:
    Image = None

# How far the alpha bounding box may wander within an idle loop, in 1x pixels,
# before it reads as bobbing rather than breathing. Calibrated against the original
# H3 art, where the idle groups hold their ground line at exactly 0.0 drift.
IDLE_DRIFT_LIMIT = 2


class Report:
    def __init__(self):
        self.entries = []

    def add(self, severity, creature, message):
        self.entries.append({"severity": severity, "creature": creature, "message": message})

    def error(self, creature, message):
        self.add("error", creature, message)

    def warn(self, creature, message):
        self.add("warning", creature, message)

    def info(self, creature, message):
        self.add("info", creature, message)

    @property
    def errors(self):
        return [e for e in self.entries if e["severity"] == "error"]

    @property
    def warnings(self):
        return [e for e in self.entries if e["severity"] == "warning"]


def find_content_root(mod_dir):
    """VCMI mods use `content/` or `Content/` interchangeably."""
    for name in ("content", "Content"):
        candidate = mod_dir / name
        if candidate.is_dir():
            return candidate
    return mod_dir


def scale_dir(content_root, scale):
    """Locate the Sprites/Sprites2x/... directory, tolerating case differences."""
    wanted = SCALE_DIRS[scale].lower()
    for child in content_root.iterdir():
        if child.is_dir() and child.name.lower() == wanted:
            return child
    return None


def resolve_file(root, relpath):
    """Resource lookup in VCMI is case-insensitive; mirror that, but report drift."""
    direct = root / relpath
    if direct.is_file():
        return direct, True
    parts = Path(relpath).parts
    current = root
    for part in parts:
        if not current.is_dir():
            return None, False
        match = next((c for c in current.iterdir() if c.name.lower() == part.lower()), None)
        if match is None:
            return None, False
        current = match
    return (current, False) if current.is_file() else (None, False)


def discover(content_root):
    """{creature_name: {scale: (json_path, sprites_root)}} keyed case-insensitively."""
    found = {}
    for scale in sorted(SCALE_DIRS):
        sprites = scale_dir(content_root, scale)
        if sprites is None:
            continue
        for json_path in sorted(sprites.rglob("*.json")):
            name = json_path.stem.upper()
            found.setdefault(name, {})[scale] = (json_path, sprites)
    return found


def alpha_bbox(path):
    """(left, top, right, bottom) of non-transparent pixels, or None."""
    with Image.open(path) as img:
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        return img.getchannel("A").getbbox()


def check_scale(report, creature, scale, json_path, sprites_root, is_shooter, base_canvas):
    """Validate one scale variant. Returns (groups, canvas, frame_names) or None."""
    try:
        config = load_json(json_path)
    except ValueError as exc:
        report.error(creature, "%dx: %s" % (scale, exc))
        return None

    groups = parse_animation(config)
    if not groups:
        report.error(creature, "%dx: %s declares no frames" % (scale, json_path.name))
        return None

    # -- group coverage --------------------------------------------------
    present = {gid for gid, frames in groups.items() if frames}
    for gid in REQUIRED_GROUPS:
        if gid not in present:
            report.error(creature, "%dx: missing required group %s" % (scale, group_label(gid)))
    for gid in RECOMMENDED_GROUPS:
        if gid not in present:
            report.warn(creature, "%dx: missing group %s" % (scale, group_label(gid)))
    if is_shooter:
        for gid in SHOOTER_GROUPS:
            if gid not in present:
                report.error(
                    creature,
                    "%dx: shooter is missing %s" % (scale, group_label(gid)),
                )
    for gid in sorted(present):
        if gid not in GROUP_NAMES:
            report.error(creature, "%dx: group id %d is not a valid ECreatureAnimType" % (scale, gid))
        if gid in DERIVED_GROUPS:
            report.info(
                creature,
                "%dx: group %s is supplied but the engine can derive it" % (scale, group_label(gid)),
            )

    # -- per-frame inspection --------------------------------------------
    canvases = {}
    frame_names = {}
    for gid in sorted(groups):
        frames = groups[gid]
        frame_names[gid] = []
        for frame in frames:
            if frame is None or frame.relpath is None:
                report.error(creature, "%dx: %s has a hole in its frame list" % (scale, group_label(gid)))
                continue
            frame_names[gid].append(frame.relpath)

            path, exact = resolve_file(sprites_root, frame.relpath)
            if path is None:
                report.error(creature, "%dx: missing file %s" % (scale, frame.relpath))
                continue
            if not exact:
                report.warn(
                    creature,
                    "%dx: %s resolves only case-insensitively (breaks on case-sensitive "
                    "filesystems when packed)" % (scale, frame.relpath),
                )

            try:
                info = read_png_info(path)
            except (ValueError, OSError) as exc:
                report.error(creature, "%dx: %s: %s" % (scale, frame.relpath, exc))
                continue

            canvases.setdefault(info.size, []).append(frame.relpath)

            if info.color_type == 3:
                report.error(
                    creature,
                    "%dx: %s is an indexed PNG; shadow/overlay/player-colour variants "
                    "require rgb or rgba" % (scale, frame.relpath),
                )
            elif not info.has_alpha:
                report.warn(
                    creature,
                    "%dx: %s has no alpha channel (%s)" % (scale, frame.relpath, info.color_name),
                )
            if info.interlaced:
                report.warn(creature, "%dx: %s is interlaced" % (scale, frame.relpath))

        # -- overlay / shadow layers -------------------------------------
        if gid in OVERLAY_GROUPS:
            check_companion(report, creature, scale, sprites_root, frames, "overlay", "error")
        check_companion(report, creature, scale, sprites_root, frames, "shadow", "warning")

    if not canvases:
        return None

    if len(canvases) > 1:
        biggest = max(canvases, key=lambda size: len(canvases[size]))
        detail = ", ".join(
            "%dx%d (%d frames, e.g. %s)" % (w, h, len(files), files[0])
            for (w, h), files in sorted(canvases.items(), key=lambda kv: -len(kv[1]))
        )
        report.error(
            creature,
            "%dx: frames use %d different canvas sizes -- every frame must share one "
            "canvas or the engine crops to the idle frame. %s" % (scale, len(canvases), detail),
        )
        canvas = biggest
    else:
        canvas = next(iter(canvases))

    if base_canvas is not None:
        expected = (base_canvas[0] * scale, base_canvas[1] * scale)
        if canvas != expected:
            report.error(
                creature,
                "%dx: canvas is %dx%d but 1x implies %dx%d" % (scale, canvas[0], canvas[1], *expected),
            )

    if Image is not None:
        check_drift(report, creature, scale, sprites_root, groups)

    return groups, canvas, frame_names


def check_companion(report, creature, scale, sprites_root, frames, suffix, severity):
    """Every frame in the group needs the companion layer, or the generate* flag."""
    attr = "generate_%s" % suffix
    flagged = [f for f in frames if f is not None and getattr(f, attr)]
    if len(flagged) == len(frames) and frames:
        return  # engine generates it

    missing = []
    for frame in frames:
        if frame is None or frame.relpath is None or getattr(frame, attr):
            continue
        path, _ = resolve_file(sprites_root, frame.companion(suffix))
        if path is None:
            missing.append(frame.relpath)

    if not missing:
        return

    gid = frames[0].group if frames and frames[0] else -1
    message = "%dx: group %s has no %s layer for %d/%d frames (no `generate%s` flag and " \
              "no `-%s` companion images, e.g. %s)" % (
                  scale, group_label(gid), suffix, len(missing), len(frames),
                  suffix.capitalize(), suffix, missing[0],
              )
    if severity == "error":
        report.error(creature, message + " -- overlays are required for the hover highlight")
    else:
        report.warn(creature, message)


def check_drift(report, creature, scale, sprites_root, groups):
    """Report how far the creature moves inside its canvas across each group."""
    for gid in sorted(groups):
        boxes = []
        for frame in groups[gid]:
            if frame is None or frame.relpath is None:
                continue
            path, _ = resolve_file(sprites_root, frame.relpath)
            if path is None:
                continue
            try:
                box = alpha_bbox(path)
            except OSError:
                continue
            if box is None:
                report.warn(creature, "%dx: %s is fully transparent" % (scale, frame.relpath))
                continue
            boxes.append(box)

        if len(boxes) < 2:
            continue

        bottoms = [b[3] for b in boxes]
        centres = [(b[0] + b[2]) / 2.0 for b in boxes]
        ground_drift = (max(bottoms) - min(bottoms)) / float(scale)
        centre_drift = (max(centres) - min(centres)) / float(scale)

        if gid in IDLE_GROUPS:
            # An idle loop must stay planted. Judge that by the ground line only: the
            # bounding-box centre moves for legitimate reasons -- CSKELE's MOUSEON raises
            # its sword from horizontal to vertical, dragging the centre 9px while the
            # feet never move a pixel.
            if ground_drift > IDLE_DRIFT_LIMIT:
                report.warn(
                    creature,
                    "%dx: group %s idle loop drifts inside the canvas -- ground line moves "
                    "%.1fpx (1x-equivalent, limit %dpx); the creature will appear to slide"
                    % (scale, group_label(gid), ground_drift, IDLE_DRIFT_LIMIT),
                )
            elif centre_drift > IDLE_DRIFT_LIMIT:
                report.info(
                    creature,
                    "%dx: group %s idle loop is planted (ground line %.1fpx) but its outline "
                    "shifts %.1fpx -- normal for a raised weapon, wrong if the body sways"
                    % (scale, group_label(gid), ground_drift, centre_drift),
                )
        else:
            # Action groups legitimately move -- a lunge shifts the ground line, and a
            # weapon swing drags the bounding-box centre far outside the body. Measured
            # against the original H3 art, an absolute threshold here only produces noise
            # (CSKELE's ATTACK_FRONT alone drifts 50px of centre). Report the numbers and
            # let the reviewer compare them against the original rather than a guess.
            report.info(
                creature,
                "%dx: group %s moves inside the canvas -- ground line %.1fpx, centre %.1fpx "
                "(1x-equivalent); compare against the original before assuming this is wrong"
                % (scale, group_label(gid), ground_drift, centre_drift),
            )


def check_against_original(report, creature, groups, lod_path, def_name):
    """Compare group coverage and frame counts against the .def being replaced.

    The cross-scale checks only prove the replacement agrees with itself. The
    original is sitting on disk, and the first zombie shipped with twelve of
    thirteen groups at the wrong frame count -- inherited from the skeleton -- with
    every other check passing.

    A different count is legal: a JSON sequence replaces a group wholesale. So this
    reports rather than fails, but it reports loudly enough to be a decision.
    """
    try:
        from def_extract import DefFile, extract, read_lod
    except ImportError:
        return
    try:
        blob, entries = read_lod(lod_path)
        name = def_name if def_name.upper().endswith(".DEF") else def_name + ".DEF"
        original = DefFile(extract(blob, entries, name))
    except SystemExit as exc:
        report.warn(creature, "could not read the original: %s" % exc)
        return

    for gid in sorted(groups):
        mine = len(groups[gid])
        theirs = len(original.groups.get(gid, []))
        if theirs == 0:
            report.info(creature, "group %s is not in the original" % group_label(gid))
        elif mine != theirs:
            report.warn(
                creature,
                "group %s has %d frames, the original has %d -- legal, but check it "
                "is deliberate" % (group_label(gid), mine, theirs))

    missing = [g for g in original.groups if g in GROUP_NAMES and g not in groups]
    if missing:
        report.info(
            creature,
            "the original also has %s; those fall back to the .def"
            % ", ".join(group_label(g) for g in sorted(missing)))

def validate_creature(report, creature, variants, is_shooter, lod=None):
    scales = sorted(variants)
    if 1 not in scales:
        report.error(
            creature,
            "no 1x animation; HD trees are only consulted when an upscaling filter is active",
        )

    results = {}
    base_canvas = None
    for scale in scales:
        json_path, sprites_root = variants[scale]
        outcome = check_scale(
            report, creature, scale, json_path, sprites_root, is_shooter, base_canvas
        )
        if outcome is None:
            continue
        groups, canvas, frame_names = outcome
        results[scale] = (groups, canvas, frame_names)
        if scale == 1:
            base_canvas = canvas
            if lod:
                check_against_original(report, creature, groups, lod, creature)

    # -- cross-scale agreement -------------------------------------------
    if 1 in results:
        base_groups, _, base_names = results[1]
        base_counts = {gid: len(frames) for gid, frames in base_groups.items() if frames}
        for scale in scales:
            if scale == 1 or scale not in results:
                continue
            groups, _, names = results[scale]
            counts = {gid: len(frames) for gid, frames in groups.items() if frames}

            for gid in sorted(set(base_counts) | set(counts)):
                if gid not in counts:
                    report.error(
                        creature,
                        "%dx: group %s exists at 1x but not here" % (scale, group_label(gid)),
                    )
                elif gid not in base_counts:
                    report.error(
                        creature,
                        "%dx: group %s exists here but not at 1x" % (scale, group_label(gid)),
                    )
                elif counts[gid] != base_counts[gid]:
                    report.error(
                        creature,
                        "%dx: group %s has %d frames, 1x has %d"
                        % (scale, group_label(gid), counts[gid], base_counts[gid]),
                    )
                elif names.get(gid) != base_names.get(gid):
                    report.warn(
                        creature,
                        "%dx: group %s uses different filenames than 1x; scale variants "
                        "should share basepath and frame names" % (scale, group_label(gid)),
                    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mod_dir", type=Path, help="mod directory (the one holding mod.json)")
    parser.add_argument(
        "--shooter",
        default="",
        help="comma-separated animation names that need the SHOOT_* groups",
    )
    parser.add_argument("--lod", help="archive of the originals, to compare group coverage "
                                      "and frame counts against the .def being replaced")
    parser.add_argument("--json", action="store_true", help="emit findings as JSON")
    parser.add_argument("--quiet", action="store_true", help="suppress info-level findings")
    args = parser.parse_args(argv)

    if not args.mod_dir.is_dir():
        parser.error("%s is not a directory" % args.mod_dir)

    shooters = {name.strip().upper() for name in args.shooter.split(",") if name.strip()}

    report = Report()
    content_root = find_content_root(args.mod_dir)
    creatures = discover(content_root)

    if not creatures:
        print("no animation JSON found under %s" % content_root, file=sys.stderr)
        return 1

    for creature in sorted(creatures):
        validate_creature(report, creature, creatures[creature], creature in shooters, args.lod)

    entries = report.entries
    if args.quiet:
        entries = [e for e in entries if e["severity"] != "info"]

    if args.json:
        json.dump({"findings": entries}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        order = {"error": 0, "warning": 1, "info": 2}
        icon = {"error": "ERROR  ", "warning": "warning", "info": "note   "}
        for entry in sorted(entries, key=lambda e: (order[e["severity"]], e["creature"])):
            print("%s %-10s %s" % (icon[entry["severity"]], entry["creature"], entry["message"]))
        print(
            "\n%d creature(s): %d error(s), %d warning(s)"
            % (len(creatures), len(report.errors), len(report.warnings))
        )
        if Image is None:
            print("note: install Pillow to enable anchor-drift analysis")

    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
