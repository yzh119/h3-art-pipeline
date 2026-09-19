"""Blender regression: normalizing a skinned mesh must preserve its posed shape.

Run: blender -b --python creature-art/test_bootstrap_normalization.py
"""
import math
import sys
import tempfile
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bootstrap_review import normalize_hierarchy, without_bone_widgets
from render_sprites import world_vertices


def sample(mesh, rig, angle):
    rig.pose.bones['upper'].rotation_mode = 'XYZ'
    rig.pose.bones['upper'].rotation_euler.x = angle
    bpy.context.view_layer.update()
    return world_vertices([mesh], bpy.context.evaluated_depsgraph_get())


for parent_mesh in (False, True):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.object.armature_add(location=(2, 3, 4))
    rig = bpy.context.object
    rig.name = 'TestRig'
    bpy.ops.object.mode_set(mode='EDIT')
    lower = rig.data.edit_bones[0]
    lower.name = 'lower'
    lower.head, lower.tail = (0, 0, 0), (0, 0, 1)
    upper = rig.data.edit_bones.new('upper')
    upper.head, upper.tail, upper.parent = (0, 0, 1), (0, 0, 2), lower
    bpy.ops.object.mode_set(mode='OBJECT')
    data = bpy.data.meshes.new('Strip')
    data.from_pydata([(x, 0, z) for z in (0, .8, 1.2, 2) for x in (-.2, .2)],
                     [], [(i, i + 1, i + 3, i + 2) for i in (0, 2, 4)])
    mesh = bpy.data.objects.new('TestMesh', data)
    bpy.context.scene.collection.objects.link(mesh)
    mesh.location = rig.location
    bpy.context.view_layer.update()
    if parent_mesh:
        world = mesh.matrix_world.copy()
        mesh.parent = rig
        mesh.matrix_world = world
    for name in ('lower', 'upper'):
        mesh.vertex_groups.new(name=name)
    for vertex in data.vertices:
        weight = max(0, min(1, (vertex.co.z - .8) / .4))
        mesh.vertex_groups['lower'].add([vertex.index], 1 - weight, 'REPLACE')
        mesh.vertex_groups['upper'].add([vertex.index], weight, 'REPLACE')
    mesh.modifiers.new('Skin', 'ARMATURE').object = rig
    angles = (0, .6, -1.1)
    before = [sample(mesh, rig, angle) for angle in angles]
    sample(mesh, rig, 0)
    # Importers can create unlinked mesh objects for bone display. Their geometry
    # must not move the physical model's floor or change its normalization scale.
    widget_data = bpy.data.meshes.new('WidgetGeometry')
    widget_data.from_pydata([(0, 0, -100), (1, 0, 100), (0, 1, 0)], [], [(0, 1, 2)])
    widget = bpy.data.objects.new('UnusualControlName', widget_data)
    rig.pose.bones['upper'].custom_shape = widget
    widget_world = widget.matrix_world.copy()
    assert without_bone_widgets([mesh, widget]) == [mesh]
    normalize_hierarchy([mesh, widget], 1.7)
    assert widget.parent is None
    assert widget.matrix_world == widget_world
    # Original rest bounds are x=[1.8,2.2], y=3, z=[4,6].
    expected = [[(v - Vector((2, 3, 4))) * .85 for v in pose] for pose in before]
    for angle, wanted in zip(angles, expected):
        actual = sample(mesh, rig, angle)
        assert max((a - b).length for a, b in zip(actual, wanted)) < 1e-5
    with tempfile.TemporaryDirectory() as directory:
        path = str(Path(directory) / 'normalized.blend')
        bpy.ops.wm.save_as_mainfile(filepath=path)
        bpy.ops.wm.open_mainfile(filepath=path)
        actual = sample(bpy.data.objects['TestMesh'], bpy.data.objects['TestRig'], -.6)
        assert all(math.isfinite(v) for point in actual for v in point)
        actual = sample(bpy.data.objects['TestMesh'], bpy.data.objects['TestRig'], angles[-1])
        assert max((a - b).length for a, b in zip(actual, expected[-1])) < 1e-5
print('PASS: bone widgets excluded; parented/unparented meshes retain three poses after reopening')
