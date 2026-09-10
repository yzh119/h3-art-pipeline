#!/usr/bin/env python3
"""Report which adventure-map resources differ from a preserved HD baseline.

The structural verifier proves that every native frame is present. This tool
separately reports body layers whose pixels were deliberately repainted or
replaced, so baseline extraction is never mistaken for authored HD work.
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops


def differs(left, right):
    with Image.open(left) as left_image, Image.open(right) as right_image:
        if left_image.size != right_image.size:
            return True
        return ImageChops.difference(left_image.convert("RGBA"), right_image.convert("RGBA")).getbbox() is not None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mod", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True, help="Extraction audit defining the resource set")
    parser.add_argument("--scale", type=int, default=4)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    records = json.loads(args.audit.read_text())["records"]
    root = args.mod / "content" / f"sprites{args.scale}x" / "adventure-hd"
    baseline = args.baseline / "content" / f"sprites{args.scale}x" / "adventure-hd"
    changed, unchanged, missing = [], [], []
    for record in records:
        stem = record["resource"]
        current = root / stem / "0_0.png"
        source = baseline / stem / "0_0.png"
        if not current.is_file() or not source.is_file():
            missing.append(stem)
        elif differs(current, source):
            changed.append(stem)
        else:
            unchanged.append(stem)

    result = {
        "scale": args.scale,
        "resources": len(records),
        "customizedBodies": changed,
        "baselineBodies": unchanged,
        "missingComparison": missing,
        "counts": {"customized": len(changed), "baseline": len(unchanged), "missing": len(missing)},
    }
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n")
    print(rendered)
    if missing:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
