#!/usr/bin/env python3
"""Turn a concept image into a 3D mesh with the Meshy API.

Second stage of the pipeline: the concept defines the design, this produces
something that can be rigged and posed. Meshy is used only for this — concepts
may come from a reference-guided image generator; rigging remains a separate stage.

    export MESHY_API_KEY=...
    gen_mesh.py concept/skeleton-front.png --out mesh/skeleton

Writes <out>.glb and <out>.json recording the task id, parameters and credits, so
a result can be traced back to the exact request that produced it.

The image is cropped to its subject before upload. A concept sits in a large
mostly-empty frame, and Meshy reconstructs what it is given — framing the subject
is free and measurably better than sending the padding too.
"""

import argparse
import base64
import hashlib
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

API = "https://api.meshy.ai/openapi/v1/image-to-3d"


def request(url, key, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Authorization": "Bearer %s" % key}
    if data:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=90) as response:
        return json.load(response)


def to_data_uri(path, crop=True):
    """Base64 data URI, cropped to the subject when Pillow is available."""
    raw = Path(path).read_bytes()
    if crop:
        try:
            from PIL import Image
            import io
            with Image.open(path) as img:
                image = img.convert("RGBA")
            box = image.getchannel("A").getbbox()
            if box:
                pad = 12
                box = (max(0, box[0] - pad), max(0, box[1] - pad),
                       min(image.width, box[2] + pad), min(image.height, box[3] + pad))
                buffer = io.BytesIO()
                image.crop(box).save(buffer, format="PNG", optimize=True)
                raw = buffer.getvalue()
        except ImportError:
            pass
    return "data:image/png;base64," + base64.b64encode(raw).decode()


def poll(task_id, key, timeout=1800):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        task = request("%s/%s" % (API, task_id), key)
        status = task.get("status")
        progress = task.get("progress")
        if progress != last:
            print("    %s %s%%" % (status, progress), flush=True)
            last = progress
        if status == "SUCCEEDED":
            return task
        if status in ("FAILED", "CANCELED", "EXPIRED"):
            raise SystemExit("mesh task %s: %s" % (status, json.dumps(task.get("task_error") or {})))
        time.sleep(6)
    raise SystemExit("timed out waiting for the mesh")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("image", help="concept image, ideally a cutout with alpha")
    parser.add_argument("--out", type=Path, required=True, help="output prefix, e.g. mesh/skeleton")
    parser.add_argument("--model", default="latest",
                        help="meshy-5 / meshy-6 / meshy-7 / latest (default)")
    parser.add_argument("--polycount", type=int, default=20000,
                        help="target polygon count after remeshing")
    parser.add_argument("--topology", default="quad", choices=["quad", "triangle"],
                        help="quad deforms better once rigged (default)")
    parser.add_argument("--no-texture", action="store_true")
    parser.add_argument("--no-remesh", action="store_true", help="Keep the detailed triangular reconstruction")
    parser.add_argument("--resume", action="store_true", help="Poll/download the persisted task without submitting")
    parser.add_argument("--no-image-enhancement", action="store_true", help="preserve an already reviewed concept")
    parser.add_argument("--texture-resolution", choices=["2k", "4k", "8k"], default="2k")
    parser.add_argument("--no-crop", action="store_true", help="send the frame as-is")
    parser.add_argument("--format", default="glb", help="which model_urls entry to download")
    args = parser.parse_args(argv)

    key = os.environ.get("MESHY_API_KEY")
    if not key:
        parser.error("MESHY_API_KEY is not set")

    pending = args.out.with_suffix(".pending.json")
    if args.out.with_suffix("." + args.format).exists():
        parser.error("Output model already exists")
    if pending.exists() and not args.resume:
        parser.error("Task already submitted; use --resume")
    if args.resume and not pending.exists():
        parser.error("No pending task to resume")

    payload = {
        "ai_model": args.model,
        "should_remesh": not args.no_remesh,
        "topology": args.topology,
        "target_polycount": args.polycount,
        "should_texture": not args.no_texture,

    }

    if args.no_remesh:
        payload.pop("topology")
        payload.pop("target_polycount")

    if args.model == "meshy-5":
        if args.no_image_enhancement or args.texture_resolution != "2k":
            parser.error("Meshy 5 does not support enhancement control or higher-resolution textures")
    else:
        payload["texture_resolution"] = args.texture_resolution
        payload["image_enhancement"] = not args.no_image_enhancement

    if args.resume:
        record = json.loads(pending.read_text())
        if hashlib.sha256(Path(args.image).read_bytes()).hexdigest() != record["source_sha256"]:
            parser.error("Resume image differs from the submitted source")
        task_id = record["task_id"]
        payload = record["parameters"]
    else:
        payload["image_url"] = to_data_uri(args.image, crop=not args.no_crop)
        print("submitting %s ..." % args.image, flush=True)
        task_id = request(API, key, payload)["result"]
        print("  task %s" % task_id, flush=True)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        pending.write_text(json.dumps({
            "task_id": task_id,
            "source_sha256": hashlib.sha256(Path(args.image).read_bytes()).hexdigest(),
            "parameters": {k: v for k, v in payload.items() if k != "image_url"}
        }, indent=2) + "\n")
    task = poll(task_id, key)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    urls = task.get("model_urls") or {}
    if args.format not in urls:
        raise SystemExit("no %s in model_urls (have: %s)" % (args.format, ", ".join(urls)))
    target = args.out.with_suffix("." + args.format)
    with urllib.request.urlopen(urls[args.format], timeout=300) as response:
        target.write_bytes(response.read())

    meta = {
        "task_id": task_id,
        "source_image": str(args.image),
        "parameters": {k: v for k, v in payload.items() if k != "image_url"},
        "consumed_credits": task.get("consumed_credits"),
        "model_urls": list(urls),
        "texture_urls": task.get("texture_urls"),
    }
    args.out.with_suffix(".json").write_text(json.dumps(meta, indent=2) + "\n")

    print("\n  %s  (%.1f MB)" % (target, target.stat().st_size / 1e6))
    print("  %s credits" % task.get("consumed_credits"))
    print("  parameters and task id recorded in %s" % args.out.with_suffix(".json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
