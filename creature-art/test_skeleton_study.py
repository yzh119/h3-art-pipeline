"""Blender integration checks for an already-rendered skeleton study.

blender -b --python test_skeleton_study.py -- /path/to/study
"""

import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skeleton_study as study


def controls_for(arm):
    controls = {}
    for side in ['Left', 'Right']:
        for limb, end, joint in [('Arm', 'Hand', 'ForeArm'), ('Leg', 'Foot', 'Leg')]:
            controls[side + limb] = {
                'target': bpy.data.objects[side + end + 'Target'],
                'pole': bpy.data.objects[side + joint + 'Pole'],
                'end': side + end, 'joint': side + joint,
            }
    return controls


def main():
    directory = Path(sys.argv[sys.argv.index('--') + 1])
    manifest = json.loads((directory / 'manifest.json').read_text())
    lengths, errors = [], []
    for name, spec in manifest['profile']['poses'].items():
        bpy.ops.wm.open_mainfile(filepath=str(directory / (name + '.blend')))
        arm = bpy.data.objects['SkeletonStudy']
        assert arm['weapon_hand'] == manifest['profile']['weapon_hand']
        socket = bpy.data.objects['WeaponGrip']
        weapons = [bpy.data.objects[n] for n in ['SwordGrip', 'SwordGuard', 'SwordBlade']]
        controls = controls_for(arm)
        for obj in bpy.context.scene.objects:
            if obj.type != 'MESH':
                continue
            if obj in weapons:
                assert not obj.vertex_groups, 'weapon must not have skin weights'
                assert obj.parent == socket
            else:
                for vertex in obj.data.vertices:
                    assert abs(sum(g.weight for g in vertex.groups) - 1) < 1e-6
        report = study.measurements(arm, controls, socket, weapons)
        lengths.append(report['blade_length'])
        for key in controls:
            error = report[key]['target_error']
            errors.append(error)
            assert error < 1e-4, (name, key, error)
        assert report['socket_error'] < 1e-6
        for side in ['Left', 'Right']:
            assert report[side + 'FootBottom'] > 0, 'foot penetrates ground'

        # Moving an editable wrist control must move the hand and weapon together.
        target = controls['RightArm']['target']
        target.location.x += .02
        bpy.context.view_layer.update()
        assert (arm.pose.bones['RightHand'].head - target.location).length < 2e-4
        assert (socket.matrix_world.translation - target.location).length < 2e-4
        assert abs(study.measurements(arm, controls, socket, weapons)['blade_length'] - lengths[-1]) < 1e-5

        # A pose must not inherit the previous pose's transforms or target state.
        for other in reversed(list(manifest['profile']['poses'].values())):
            study.apply_study_pose(arm, controls, other, arm['weapon_hand'])
        study.apply_study_pose(arm, controls, spec, arm['weapon_hand'])
        repeated = study.measurements(arm, controls, socket, weapons)
        for key in controls:
            assert (Vector(repeated[key]['joint']) - Vector(report[key]['joint'])).length < 1e-3
        for image in bpy.data.images:
            if image.type == 'IMAGE' and image.source == 'FILE' and image.users:
                assert image.packed_file, 'blend must retain its source textures'
    assert max(lengths) - min(lengths) < 1e-5
    print('PASS: four saved rigs, IK targets, editable controls, rigid weapon, weights, pose reset, packed textures')
    print('Maximum IK error: %.8f; blade length range: %.8f' % (max(errors), max(lengths) - min(lengths)))


if __name__ == '__main__':
    main()
