"""Asset-free Blender regression: --background --python-exit-code 1 --python FILE."""
import math
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blend_armature_volume import add_volume_blend

bpy.ops.wm.read_factory_settings(use_empty=True)
rig_data = bpy.data.armatures.new("TestRig")
rig = bpy.data.objects.new("TestRig", rig_data)
bpy.context.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
rig.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
for name in ("A", "B"):
    bone = rig_data.edit_bones.new(name)
    bone.head = (0, 0, 0)
    bone.tail = (0, 0, 1)
bpy.ops.object.mode_set(mode="OBJECT")
for name, angle in (("A", 70), ("B", -70)):
    rig.pose.bones[name].rotation_mode = "XYZ"
    rig.pose.bones[name].rotation_euler.y = math.radians(angle)
data = bpy.data.meshes.new("TestMesh")
data.from_pydata([(1, 0, .25), (1, 0, .5), (1, 0, .75)], [], [])
mesh = bpy.data.objects.new("TestMesh", data)
bpy.context.collection.objects.link(mesh)
for name in ("A", "B"):
    mesh.vertex_groups.new(name=name).add([0, 1, 2], .5, "REPLACE")
mask = mesh.vertex_groups.new(name="VolumeMask")
weights = (0, .35, 1)
for i, weight in enumerate(weights):
    mask.add([i], weight, "REPLACE")
base = mesh.modifiers.new("Linear", "ARMATURE")
base.object = rig


def positions():
    bpy.context.view_layer.update()
    evaluated = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    result = evaluated.to_mesh()
    coords = [vertex.co.copy() for vertex in result.vertices]
    evaluated.to_mesh_clear()
    return coords


linear = positions()
base.use_deform_preserve_volume = True
volume = positions()
assert max((a - b).length for a, b in zip(linear, volume)) > .1
base.use_deform_preserve_volume = False
add_volume_blend(mesh, rig, "VolumeMask")
mixed = positions()
for a, b, actual, weight in zip(linear, volume, mixed, weights):
    assert (a.lerp(b, weight) - actual).length < 1e-6
before = len(mesh.modifiers)
for name in ("MissingMask", "VolumeMask"):
    try:
        add_volume_blend(mesh, rig, name)
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid mask/stack should be rejected")
assert len(mesh.modifiers) == before
print("PASS: zero/full/partial blend and invalid mask/stack")
