"""Shared helpers for the creature art tooling.

Kept dependency-free on purpose: everything here runs on a stock Python 3.8+.
"""

import json
import re
import struct
from pathlib import Path

# ---------------------------------------------------------------------------
# Animation groups -- mirrors ECreatureAnimType in client/battle/BattleConstants.h
# ---------------------------------------------------------------------------

GROUP_NAMES = {
    0: "MOVING",
    1: "MOUSEON",
    2: "HOLDING",
    3: "HITTED",
    4: "DEFENCE",
    5: "DEATH",
    6: "DEATH_RANGED",
    7: "TURN_L",
    8: "TURN_R",
    11: "ATTACK_UP",
    12: "ATTACK_FRONT",
    13: "ATTACK_DOWN",
    14: "SHOOT_UP",
    15: "SHOOT_FRONT",
    16: "SHOOT_DOWN",
    17: "SPECIAL_UP",
    18: "SPECIAL_FRONT",
    19: "SPECIAL_DOWN",
    20: "MOVE_START",
    21: "MOVE_END",
    22: "DEAD",
    23: "DEAD_RANGED",
    24: "RESURRECTION",
    25: "FROZEN",
    30: "CAST_UP",
    31: "CAST_FRONT",
    32: "CAST_DOWN",
    40: "GROUP_ATTACK_UP",
    41: "GROUP_ATTACK_FRONT",
    42: "GROUP_ATTACK_DOWN",
    50: "TELEPORT_START",
    51: "TELEPORT_END",
}

GROUP_IDS = {name: gid for gid, name in GROUP_NAMES.items()}

# Groups the engine uses without any fallback path.
REQUIRED_GROUPS = [0, 2, 5, 11, 12, 13]

# Absence is survivable but visibly wrong in game.
RECOMMENDED_GROUPS = [1, 3, 4, 7, 8]

# Required only for creatures with a ranged attack.
SHOOTER_GROUPS = [14, 15, 16]

# Synthesised by CreatureAnimation if not supplied.
DERIVED_GROUPS = [22, 23, 24, 25]

# Groups that carry the mouse-hover highlight, and therefore need an overlay layer.
OVERLAY_GROUPS = [1, 2]

# Idle loops: the creature should not translate across these frames.
IDLE_GROUPS = [1, 2]

SCALE_DIRS = {1: "Sprites", 2: "Sprites2x", 3: "Sprites3x", 4: "Sprites4x"}


def group_label(gid):
    name = GROUP_NAMES.get(gid)
    return "%d (%s)" % (gid, name) if name else "%d (unknown)" % gid


# ---------------------------------------------------------------------------
# VCMI-flavoured JSON: allows // and /* */ comments and trailing commas
# ---------------------------------------------------------------------------

_TOKENS = re.compile(
    r'"(?:\\.|[^"\\])*"'      # string literal (so comment markers inside strings survive)
    r"|//[^\n]*"              # line comment
    r"|/\*.*?\*/",            # block comment
    re.S,
)


def _strip_comments(text):
    def repl(m):
        tok = m.group(0)
        if tok.startswith('"'):
            return tok
        # Preserve newlines so reported line numbers stay meaningful.
        return "".join(c for c in tok if c == "\n")

    return _TOKENS.sub(repl, text)


_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


def load_json(path):
    """Parse a VCMI JSON file. Raises ValueError with the file name on failure."""
    raw = Path(path).read_text(encoding="utf-8-sig")
    cleaned = _TRAILING_COMMA.sub(r"\1", _strip_comments(raw))
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError("%s: %s" % (path, exc)) from None


# ---------------------------------------------------------------------------
# PNG inspection without Pillow
# ---------------------------------------------------------------------------

_PNG_SIG = b"\x89PNG\r\n\x1a\n"

COLOR_TYPES = {
    0: "grayscale",
    2: "rgb",
    3: "indexed",
    4: "grayscale+alpha",
    6: "rgba",
}


class PngInfo:
    __slots__ = ("width", "height", "bit_depth", "color_type", "interlaced")

    def __init__(self, width, height, bit_depth, color_type, interlaced):
        self.width = width
        self.height = height
        self.bit_depth = bit_depth
        self.color_type = color_type
        self.interlaced = interlaced

    @property
    def has_alpha(self):
        return self.color_type in (4, 6)

    @property
    def color_name(self):
        return COLOR_TYPES.get(self.color_type, "type%d" % self.color_type)

    @property
    def size(self):
        return (self.width, self.height)


def read_png_info(path):
    """Read IHDR only. Returns PngInfo, or raises ValueError if not a usable PNG."""
    with open(path, "rb") as handle:
        header = handle.read(8)
        if header != _PNG_SIG:
            raise ValueError("not a PNG file")
        length_type = handle.read(8)
        if len(length_type) != 8 or length_type[4:] != b"IHDR":
            raise ValueError("malformed PNG: missing IHDR")
        ihdr = handle.read(struct.unpack(">I", length_type[:4])[0])
        if len(ihdr) < 13:
            raise ValueError("malformed PNG: truncated IHDR")
    width, height, bit_depth, color_type = struct.unpack(">IIBB", ihdr[:10])
    return PngInfo(width, height, bit_depth, color_type, ihdr[12] != 0)


# ---------------------------------------------------------------------------
# Animation JSON model
# ---------------------------------------------------------------------------

class Frame:
    """One frame reference resolved out of an animation JSON."""

    __slots__ = ("group", "index", "relpath", "generate_shadow", "generate_overlay")

    def __init__(self, group, index, relpath, generate_shadow, generate_overlay):
        self.group = group
        self.index = index
        self.relpath = relpath
        self.generate_shadow = generate_shadow
        self.generate_overlay = generate_overlay

    def companion(self, suffix):
        """`foo/bar.png` + `shadow` -> `foo/bar-shadow.png`."""
        base, dot, ext = self.relpath.rpartition(".")
        if not dot:
            return "%s-%s" % (self.relpath, suffix)
        return "%s-%s.%s" % (base, suffix, ext)

    def __repr__(self):
        return "Frame(%s[%d]=%s)" % (group_label(self.group), self.index, self.relpath)


def parse_animation(config):
    """Flatten an animation JSON into {group_id: [Frame, ...]}.

    Mirrors RenderHandler::initFromJson: `sequences` replaces a group wholesale,
    `images` patches individual frames.
    """
    basepath = config.get("basepath", "") or ""
    groups = {}

    for seq in config.get("sequences", []):
        gid = int(seq.get("group", 0))
        shadow = seq.get("generateShadow")
        overlay = seq.get("generateOverlay")
        frames = []
        for index, name in enumerate(seq.get("frames", [])):
            frames.append(Frame(gid, index, basepath + name, shadow, overlay))
        groups[gid] = frames

    for image in config.get("images", []):
        gid = int(image.get("group", 0))
        index = int(image.get("frame", 0))
        frames = groups.setdefault(gid, [])
        while len(frames) <= index:
            frames.append(None)
        name = image.get("file")
        frames[index] = Frame(
            gid,
            index,
            basepath + name if name else None,
            image.get("generateShadow"),
            image.get("generateOverlay"),
        )

    return groups


# ---------------------------------------------------------------------------
# Minimal PNG writer (RGBA, 8-bit, non-interlaced)
# ---------------------------------------------------------------------------

def write_png(path, width, height, rgba):
    """Write `rgba` (width*height*4 bytes, row-major) as an RGBA PNG."""
    import zlib

    def chunk(kind, payload):
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    stride = width * 4
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter type: none
        raw += rgba[y * stride:(y + 1) * stride]

    Path(path).write_bytes(
        _PNG_SIG
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )
