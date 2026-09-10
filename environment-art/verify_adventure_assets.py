#!/usr/bin/env python3
"""Verify a sparse adventure-map HD override against its extraction audit.

Checks every recorded sequence at every declared scale without touching game
assets: JSON sequence metadata, body/shadow/overlay frame presence, and canvas
sizes. Registered repaint passes are allowed because only geometry matters.
"""
import argparse
import json
from pathlib import Path

from PIL import Image


def fail(errors, message):
    errors.append(message)


def expected_sequences(record, scale):
    return {str(group): count for group, count in record["groups"][str(scale)].items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mod", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args()

    audit = json.loads(args.audit.read_text())
    scales = [int(value) for value in audit["scales"]]
    records = audit["records"]
    errors = []
    frame_count = 0

    for record in records:
        stem = record["resource"]
        reference_sizes = {}
        for scale in scales:
            root = args.mod / "content" / f"sprites{scale}x"
            metadata_file = root / f"{stem}.json"
            if not metadata_file.is_file():
                fail(errors, f"missing metadata: {metadata_file}")
                continue
            metadata = json.loads(metadata_file.read_text())
            actual = {
                str(sequence.get("group")): len(sequence.get("frames", []))
                for sequence in metadata.get("sequences", [])
            }
            expected = expected_sequences(record, scale)
            if actual != expected:
                fail(errors, f"sequence mismatch at {scale}x for {stem}: {actual} != {expected}")

            folder = root / "adventure-hd" / stem
            for group, count in expected.items():
                for frame in range(count):
                    base = f"{group}_{frame}"
                    for suffix in ("", "-shadow", "-overlay"):
                        image_file = folder / f"{base}{suffix}.png"
                        if not image_file.is_file():
                            fail(errors, f"missing frame: {image_file}")
                            continue
                        with Image.open(image_file) as image:
                            size = image.size
                        key = (group, frame, suffix)
                        if scale == scales[0]:
                            reference_sizes[key] = size
                        else:
                            reference = reference_sizes.get(key)
                            expected_size = (reference[0] * scale // scales[0], reference[1] * scale // scales[0])
                            if size != expected_size:
                                fail(errors, f"canvas mismatch: {image_file}: {size} != {expected_size}")
                    frame_count += 1

    result = {
        "resources": len(records),
        "scales": scales,
        "frames": frame_count,
        "layers": frame_count * 3,
        "errors": len(errors),
    }
    print(json.dumps(result, indent=2))
    if errors:
        for error in errors[:30]:
            print(error)
        if len(errors) > 30:
            print(f"... {len(errors) - 30} more errors")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
