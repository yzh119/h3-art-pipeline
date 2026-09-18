"""Blender regression: collision length follows adjacent joint heads, not tails."""
import sys
from pathlib import Path
import bpy
from mathutils import Vector
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_joint_colliders import sample_segments, build_colliders

bpy.ops.wm.read_factory_settings(use_empty=True)
data = bpy.data.armatures.new('SyntheticLongTail')
rig = bpy.data.objects.new('Rig', data)
bpy.context.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
rig.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
a = data.edit_bones.new('Upper'); a.head = (0, 0, 1); a.tail = (0, 0, -33)
b = data.edit_bones.new('Lower'); b.head = (0, 0, .66); b.tail = (0, 0, .3)
bpy.ops.object.mode_set(mode='OBJECT')
segments = [{'start': 'Upper', 'end': 'Lower', 'radius': .1}]
samples = sample_segments(bpy.context.scene, rig, segments, [1, 11], .5)
assert abs((samples[0][1][0][1] - samples[0][1][0][0]).length - .34) < 1e-6
objects = build_colliders(segments, samples)
bpy.context.scene.frame_set(1)
assert abs(objects[0].scale.z - .22) < 1e-6
assert (objects[0].location - Vector((0, 0, .83))).length < 1e-6
try:
    sample_segments(bpy.context.scene, rig, segments, [1], .1)
except ValueError:
    pass
else:
    raise AssertionError('Expected implausible segment length to be rejected')
print('PASS: 34-unit bone tail yields .34-unit joint segment; length guard rejects bad bounds')
