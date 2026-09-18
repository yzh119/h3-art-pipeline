"""Build animated cloth collision ellipsoids between joint heads in Blender.

Run with blender --background --python this_file.py -- --help.
Bone tails may be much longer than the anatomical segment in an imported or
reposed rig. Explicit start/end joints avoid using that display length.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy


def sample_segments(scene, rig, segments, frames, max_length):
    """Read world-space joint endpoints, checking every requested frame first."""
    if not math.isfinite(max_length) or max_length <= 0:
        raise ValueError('max_length must be finite and positive')
    for segment in segments:
        if not math.isfinite(segment['radius']) or segment['radius'] <= 0:
            raise ValueError('Each radius must be finite and positive')
        for field in ('start', 'end'):
            if segment[field] not in rig.pose.bones:
                raise ValueError('Missing joint: ' + segment[field])
    previous_frame = scene.frame_current
    samples = []
    try:
        for frame in frames:
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            row = []
            for segment in segments:
                start = rig.matrix_world @ rig.pose.bones[segment['start']].head
                end = rig.matrix_world @ rig.pose.bones[segment['end']].head
                length = (end - start).length
                if not math.isfinite(length) or not 1e-6 < length <= max_length:
                    raise ValueError(f'{segment["start"]} -> {segment["end"]} '
                                     f'has length {length} at frame {frame}')
                row.append((start.copy(), end.copy()))
            samples.append((frame, row))
    finally:
        scene.frame_set(previous_frame)
    return samples


def build_colliders(segments, samples):
    objects = []
    for index, segment in enumerate(segments):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8)
        obj = bpy.context.object
        obj.name = f'JointCollider_{segment["start"]}_{segment["end"]}'
        obj.hide_render = True
        obj.rotation_mode = 'QUATERNION'
        obj.modifiers.new('ClothCollision', 'COLLISION')
        obj.collision.thickness_outer = .006
        radius = segment['radius']
        previous_rotation = None
        for frame, row in samples:
            start, end = row[index]
            direction = end - start
            rotation = direction.to_track_quat('Z', 'Y')
            if previous_rotation is not None and rotation.dot(previous_rotation) < 0:
                rotation.negate()
            obj.location = (start + end) * .5
            obj.rotation_quaternion = rotation
            obj.scale = (radius, radius, direction.length * .5 + radius * .5)
            for prop in ('location', 'rotation_quaternion', 'scale'):
                obj.keyframe_insert(prop, frame=frame)
            previous_rotation = rotation.copy()
        for layer in obj.animation_data.action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        for key in curve.keyframe_points:
                            key.interpolation = 'LINEAR'
        objects.append(obj)
    return objects


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--segments', type=Path, required=True,
                        help='JSON array of {start, end, radius}, in scene world units')
    parser.add_argument('--rig', default='Armature')
    parser.add_argument('--action', help='Use this rig action when sampling')
    parser.add_argument('--frames', nargs=2, type=int, required=True, metavar=('START', 'END'))
    parser.add_argument('--step', type=int, default=1)
    parser.add_argument('--max-length', type=float, required=True,
                        help='Maximum anatomical segment length in scene world units')
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    args = parser.parse_args(argv)
    if args.output.exists() or args.output.resolve() == args.scene.resolve():
        parser.error('Use a new output path; source scenes are never overwritten')
    if args.step < 1 or args.frames[1] < args.frames[0]:
        parser.error('Require positive step and END >= START')
    segments = json.loads(args.segments.read_text())
    if not isinstance(segments, list) or not segments:
        parser.error('Segments must be a nonempty array')
    bpy.ops.wm.open_mainfile(filepath=str(args.scene.resolve()))
    scene = bpy.context.scene
    rig = bpy.data.objects[args.rig]
    if args.action:
        rig.animation_data_create().action = bpy.data.actions[args.action]
    frames = list(range(args.frames[0], args.frames[1] + 1, args.step))
    if frames[-1] != args.frames[1]:
        frames.append(args.frames[1])
    samples = sample_segments(scene, rig, segments, frames, args.max_length)
    objects = build_colliders(segments, samples)
    scene.frame_set(frames[0])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    report = {'objects': [obj.name for obj in objects], 'frames': frames,
              'segments': [{**segment, 'minimumLength': min((row[i][1]-row[i][0]).length for _, row in samples),
                            'maximumLength': max((row[i][1]-row[i][0]).length for _, row in samples)}
                           for i, segment in enumerate(segments)],
              'scope': 'Joint collision proxies only; cloth contact and appearance require separate review.'}
    args.output.with_suffix('.colliders.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
