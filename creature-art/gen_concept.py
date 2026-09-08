#!/usr/bin/env python3
"""Generate creature concept art with the Black Forest Labs FLUX API.

The concept step feeds the mesh step, so what matters is not a pretty picture but
a clean, evenly lit character on a plain background that image-to-3D can read.
Baked shadows, rim light and motion blur all fight the render stage later.

    export BFL_API_KEY=...
    gen_concept.py --prompt-file docs/prompt-cskele.txt --out concept/cskele

Writes <out>-front.png and <out>-side.png plus a .json recording the exact prompt,
seed and cost of each, so a result can be reproduced or bisected later.

Cost is reported per call; flux-2-pro is 3 credits (~$0.03) at 1MP.
"""

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

API = "https://api.bfl.ai/v1"
DEFAULT_MODEL = "flux-2-pro"

# Appended to every view so the output stays usable by image-to-3D.
# The backdrop matters as much as the character. Image models default to a subtle
# gradient or an implied floor, and a gradient cannot be keyed out cleanly -- it
# leaves a haze across the whole frame that swallows the silhouette. Demand a single
# flat colour, and one that the subject cannot contain.
MESH_SAFE = (
    "Isolated on a solid uniform chroma green background, one single flat colour "
    "filling the entire frame, absolutely no gradient, no vignette, no floor, "
    "no horizon, no cast shadow, no contact shadow. "
    "Flat even studio lighting, no rim light, no motion blur, no depth of field. "
    "Full body in frame, no cropping, single character, no text."
)

VIEWS = {
    "front": "three-quarter front view",
    "side": "side view, same pose and proportions",
    # The A-pose seen from the side, for multi-image reconstruction. Single-image
    # reconstruction fills the negative space between paired bones -- tibia and
    # fibula merge into one smooth tube -- and more polygons do not bring it back.
    "aposeside": (
        "exact side view of a neutral A-pose, facing to the right, "
        "arms held down and away from the body with clear space between arm and "
        "torso, legs straight and slightly apart, any weapon held down and out at "
        "about forty-five degrees clear of the legs, body upright and not hunched"
    ),
    # A rigging-friendly neutral pose. Auto-riggers estimate a skeleton from the
    # silhouette, and fail when limbs sit against the torso -- which is exactly what
    # the proportion hint asks for. So the mesh is built from this view instead, and
    # the compact in-game proportions come from the animation, not from the concept.
    #
    # The weapon has to be held clear of the body too. Tucked against the leg it
    # reconstructs as a thin sliver that vanishes from the side -- and in the
    # original the sword is most of what makes the silhouette readable.
    #
    # But "clear of the body" alone bought a sword nearly as long as the figure,
    # held at arm's length like a fishing rod, and the mesh inherits whatever the
    # concept draws. Hence the explicit proportion and the bent elbow.
    "apose": (
        "standing straight in a neutral A-pose, facing directly forward, "
        "arms held down and out away from the body at about forty-five degrees "
        "with clear space between each arm and the torso, "
        "legs straight and shoulder-width apart with clear space between them, "
        "any weapon held down and out to the side at about forty-five degrees, "
        "clear of the torso and legs and fully visible against the background, "
        "the weapon in correct proportion to the figure and no longer than half "
        "its height, elbow bent so the hand stays near the hip, "
        "body upright and not hunched, symmetrical"
    ),
}

# Views whose whole point is a spread pose; the proportion hint would fight them.
POSE_VIEWS = {"apose", "aposeside"}


def post(path, payload, key):
    request = urllib.request.Request(
        "%s/%s" % (API, path),
        data=json.dumps(payload).encode(),
        headers={"x-key": key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def poll(url, key, timeout=300):
    deadline = time.time() + timeout
    while time.time() < deadline:
        request = urllib.request.Request(url, headers={"x-key": key})
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.load(response)
        status = body.get("status")
        if status == "Ready":
            return body["result"]["sample"]
        if status in ("Error", "Failed", "Content Moderated", "Request Moderated"):
            raise SystemExit("generation failed: %s" % json.dumps(body)[:400])
        time.sleep(2)
    raise SystemExit("timed out waiting for the image")


def cutout(path, tolerance=90):
    """Key the chroma backdrop to transparency, then despill what remains.

    Order matters. Despilling first would neutralise the green backdrop itself into
    a flat grey close to bone, and there would be nothing left to key against. So:
    key while the backdrop is still unmistakably green, then despill only the subject.

    Despill is the classic one -- wherever green leads the other two channels it is
    pulled back to their maximum. Green bleeds onto anything standing in front of a
    green screen, and that tint would otherwise be baked into the mesh texture.

    Writing a real cutout also means every downstream step gets a true alpha channel
    instead of guessing at a backdrop.
    """
    try:
        from PIL import Image
    except ImportError:
        return "Pillow not installed - left as-is, no cutout"

    with Image.open(path) as raw:
        image = raw.convert("RGBA")
    pixels = image.load()
    w, h = image.size

    border = ([pixels[x, 0][:3] for x in range(0, w, 4)] +
              [pixels[x, h - 1][:3] for x in range(0, w, 4)] +
              [pixels[0, y][:3] for y in range(0, h, 4)] +
              [pixels[w - 1, y][:3] for y in range(0, h, 4)])
    bg = tuple(sorted(c[i] for c in border)[len(border) // 2] for i in range(3))

    keyed = 0
    for y in range(h):
        for x in range(w):
            r, g, b, _ = pixels[x, y]
            if abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) <= tolerance:
                pixels[x, y] = (r, g, b, 0)
                keyed += 1
            else:
                ceiling = max(r, b)
                if g > ceiling:
                    pixels[x, y] = (r, ceiling, b, 255)

    image.save(path)
    subject = w * h - keyed
    if subject < w * h * 0.01:
        return "WARNING: keying removed almost everything - check the backdrop"
    return "cutout: backdrop #%02X%02X%02X removed, subject is %.0f%% of frame" % (
        bg[0], bg[1], bg[2], 100.0 * subject / (w * h))


def generate(prompt, out_path, key, model, width, height, seed):
    payload = {"prompt": prompt, "width": width, "height": height}
    if seed is not None:
        payload["seed"] = seed

    submitted = post(model, payload, key)
    cost = submitted.get("cost")
    url = poll(submitted["polling_url"], key)

    with urllib.request.urlopen(url, timeout=120) as response:
        out_path.write_bytes(response.read())

    note = cutout(out_path)

    return {
        "cutout": note,
        "file": out_path.name,
        "prompt": prompt,
        "model": model,
        "width": width,
        "height": height,
        "seed": seed,
        "cost_credits": cost,
        "request_id": submitted.get("id"),
    }


# Image models spread a character out — planted stance, arms away from the body,
# wings open. Heroes III creatures are compact because they sit on a hex, so every
# prompt states the target proportion explicitly. The phrasing is derived from the
# original's measured width-to-height rather than written per creature.
COMPACTNESS = "Limbs held close to the body. Do not spread or open the pose."


def proportion_hint(aspect):
    """State the target proportion as a ratio, not an adjective.

    Adjectives backfire: "broad and low" for a 0.76 creature made FLUX spread the
    bone dragon's wings and pushed it to 1.15. A number carries the constraint
    without suggesting a pose.
    """
    if aspect is None:
        return COMPACTNESS
    return ("The whole silhouette fits in a box about %.1f times as tall as it is "
            "wide. %s" % (1.0 / aspect, COMPACTNESS))


def load_roster(path):
    import re
    raw = path.read_text()
    raw = re.sub(r",(\s*[}\]])", r"\1", raw)
    return json.loads(raw)


def run_roster(args, key):
    """Generate every creature in a roster into one directory."""
    roster = load_roster(args.roster)
    style = roster.get("_style", "")
    views = [v.strip() for v in args.views.split(",") if v.strip()]
    args.out.mkdir(parents=True, exist_ok=True)

    records, total, failed = [], 0.0, []
    for entry in roster["creatures"]:
        for view in views:
            target = args.out / ("%s-%s.png" % (entry["name"], view))
            if target.exists() and not args.force:
                print("skip (exists): %s" % target.name)
                continue
            # `design` is what the creature is; `pose` is how it stands. The apose
            # view brings its own pose and skips both the creature's pose and the
            # proportion hint, which exist to serve the in-game silhouette.
            if view in POSE_VIEWS:
                parts = (entry.get("design") or entry.get("body"), style)
            else:
                parts = (entry.get("design") or entry.get("body"), entry.get("pose", ""),
                         style, proportion_hint(entry.get("aspect")))
            prompt = " ".join(x for x in tuple(parts) + (VIEWS[view] + ".", MESH_SAFE) if x)
            if args.dry_run:
                print("[%s %s]\n  %s\n" % (entry["name"], view, prompt))
                continue
            print("%-18s %-6s ..." % (entry["name"], view), end=" ", flush=True)
            try:
                record = generate(prompt, target, key, args.model, args.width, args.height, args.seed)
            except SystemExit as exc:
                print("FAILED: %s" % exc)
                failed.append(entry["name"])
                continue
            record["creature"] = entry["name"]
            record["target_aspect"] = entry.get("aspect")
            records.append(record)
            total += record["cost_credits"] or 0
            print("%s credits, %s" % (record["cost_credits"], record["cutout"]))

    if args.dry_run:
        return 0

    (args.out / "roster.json").write_text(json.dumps({"images": records}, indent=2) + "\n")
    print("\n%d image(s), %.0f credits (~$%.2f) -> %s" % (len(records), total, total * 0.01, args.out))
    if failed:
        print("failed: %s" % ", ".join(failed))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--prompt", help="the character description, without view or lighting")
    source.add_argument("--prompt-file", type=Path, help="read the description from a file")
    source.add_argument("--roster", type=Path,
                        help="a roster JSON; generates every creature in it into --out as a directory")
    parser.add_argument("--out", type=Path, required=True, help="output prefix, e.g. concept/cskele")
    parser.add_argument("--views", default="front,side",
                        help="comma-separated subset of: %s" % ", ".join(VIEWS))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1440)
    parser.add_argument("--seed", type=int, help="fixed seed, so the two views match better")
    parser.add_argument("--dry-run", action="store_true", help="print the prompts, call nothing")
    parser.add_argument("--force", action="store_true", help="regenerate images that already exist")
    args = parser.parse_args(argv)

    key = os.environ.get("BFL_API_KEY")
    if not key and not args.dry_run:
        parser.error("BFL_API_KEY is not set")

    if args.roster:
        return run_roster(args, key)

    base = (args.prompt_file.read_text().strip() if args.prompt_file else args.prompt)
    views = [v.strip() for v in args.views.split(",") if v.strip()]
    for view in views:
        if view not in VIEWS:
            parser.error("unknown view %r; known: %s" % (view, ", ".join(VIEWS)))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    records, total = [], 0.0

    for view in views:
        prompt = "%s %s. %s" % (base, VIEWS[view], MESH_SAFE)
        target = args.out.with_name("%s-%s.png" % (args.out.name, view))
        if args.dry_run:
            print("[%s] -> %s\n  %s\n" % (view, target, prompt))
            continue
        print("generating %s ..." % view, flush=True)
        record = generate(prompt, target, key, args.model, args.width, args.height, args.seed)
        records.append(record)
        total += record["cost_credits"] or 0
        print("  %s  (%s credits, %s)" % (target, record["cost_credits"], record["cutout"]))

    if args.dry_run:
        return 0

    meta = args.out.with_name("%s.json" % args.out.name)
    meta.write_text(json.dumps({"base_prompt": base, "images": records}, indent=2) + "\n")
    print("\n%d image(s), %.0f credits (~$%.2f)" % (len(records), total, total * 0.01))
    print("prompts and seeds recorded in %s" % meta)
    print("\nnext: check it reads at in-game size")
    print("  preview.py readability %s-front.png --height 79 \\" % args.out)
    print('      --lod "$LOD" --against CSKELE.DEF --out check.png')
    return 0


if __name__ == "__main__":
    sys.exit(main())
