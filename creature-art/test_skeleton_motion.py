"""Reopen baked clips and check actual evaluated motion, including subframes.

blender -b --python-exit-code 1 --python test_skeleton_motion.py -- OUTPUT
"""

import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skeleton_study as study
from test_skeleton_study import controls_for


def main():
    directory = Path(sys.argv[sys.argv.index('--')+1])
    manifest = json.loads((directory/'manifest.json').read_text())
    errors, lengths, bottoms, drifts, replay = [], [], [], [], []
    walk_blade_elevations = []
    walk_wrists, walk_elbows, walk_shoulders = [], [], []
    arm_leg = {side: [] for side in ['Right', 'Left']}
    endpoints = {}
    corpse_bottoms = []
    strike_heights = {}
    checked = 0
    for group, clip in manifest['clips'].items():
        bpy.ops.wm.open_mainfile(filepath=str(directory/(group.lower()+'.blend')))
        scene = bpy.context.scene
        arm = bpy.data.objects['SkeletonStudy']
        controls = controls_for(arm)
        socket = bpy.data.objects['WeaponGrip']
        weapons = [bpy.data.objects[n] for n in ['SwordGrip', 'SwordGuard', 'SwordBlade']]
        planted = {}
        states = []
        for half_frame in range(2*(clip['closure_frame']-1)+1):
            frame = 1+half_frame/2
            scene.frame_set(math.floor(frame), subframe=frame % 1)
            row = study.measurements(arm, controls, socket, weapons)
            checked += 1
            lengths.append(row['blade_length'])
            assert row['socket_error'] < 1e-6
            errors.extend(row[c]['target_error'] for c in controls)
            bottoms.extend(row[s+'FootBottom'] for s in ['Left', 'Right'])
            states.append({n: arm.matrix_world @ b.matrix for n, b in arm.pose.bones.items()})
            if group == 'DEATH':
                meshes = [o for o in scene.objects if o.type == 'MESH']
                points = study.render.world_vertices(meshes, bpy.context.evaluated_depsgraph_get())
                corpse_bottoms.append(min(p.z for p in points))
            if half_frame % 2 == 0:
                original = clip['frames'][half_frame//2]
                replay.extend((Vector(row[c]['actual'])-Vector(original[c]['actual'])).length for c in controls)
            if group == 'MOVING':
                direction=Vector(manifest['direction'])
                for side in arm_leg:
                    shoulder_pos=arm.matrix_world @ arm.pose.bones[side+'Arm'].head
                    hip_pos=arm.matrix_world @ arm.pose.bones[side+'UpLeg'].head
                    arm_leg[side].append(((Vector(row[side+'Arm']['actual'])-shoulder_pos).dot(direction), (Vector(row[side+'Leg']['actual'])-hip_pos).dot(direction)))
                shoulder = arm.matrix_world @ arm.pose.bones['RightArm'].head
                elbow = Vector(row['RightArm']['joint'])
                wrist = Vector(row['RightArm']['actual'])
                walk_wrists.append(wrist.y-shoulder.y)
                walk_elbows.append(elbow.y-shoulder.y)
                upper = elbow-shoulder
                walk_shoulders.append(math.degrees(math.atan2(-upper.y, -upper.z)))
                blade = weapons[-1]
                tip = sum((v.co for v in blade.data.vertices[8:12]), Vector())/4
                heel = sum((v.co for v in blade.data.vertices[:4]), Vector())/4
                axis = (blade.matrix_world @ tip-blade.matrix_world @ heel).normalized()
                walk_blade_elevations.append(math.degrees(math.asin(max(-1, min(1, axis.z)))))
                t = (frame-1)/(clip['closure_frame']-1)
                travel = Vector(manifest['direction'])*manifest['stride']*t
                for side, offset in [('Right', 0), ('Left', .5)]:
                    phase = (t+offset) % 1
                    # Exclude the half-frame which straddles stance/swing: it is
                    # linearly interpolated between baked 30 fps controls.
                    if phase < manifest['profile']['walk']['stance_fraction']-1/24:
                        key = (side, math.floor(t+offset))
                        world = Vector(row[side+'Leg']['actual'])+travel
                        planted.setdefault(key, world)
                        drifts.append((world-planted[key]).length)
        endpoints[group] = (states[0], states[-1])
        if group.startswith('ATTACK_'):
            frame = 1+3/7*(clip['closure_frame']-1)
            scene.frame_set(math.floor(frame), subframe=frame % 1)
            blade = weapons[-1]
            tip = sum((v.co for v in blade.data.vertices[8:12]), Vector())/4
            strike_heights[group] = (blade.matrix_world @ tip).z
        if group == 'DEATH':
            assert max(p.z for p in points) < .55, 'death must finish on the floor'
        if manifest['profile']['clips'][group]['loop']:
            assert matrix_error(*endpoints[group]) < 2e-4, ('loop seam', group)
        for obj in scene.objects:
            if obj.type == 'MESH' and obj.vertex_groups and obj.name != 'Body':
                assert 'rest_position' in obj.data.attributes, obj.name
        for image in bpy.data.images:
            if image.type == 'IMAGE' and image.source == 'FILE' and image.users:
                assert image.packed_file
    for a, ai, b, bi in [('ATTACK_FRONT', 0, 'HOLDING', 0),
                          ('ATTACK_FRONT', 1, 'HOLDING', 0),
                          ('MOVE_START', 0, 'HOLDING', 0),
                          ('MOVE_START', 1, 'MOVING', 0),
                          ('MOVE_END', 0, 'MOVING', 0),
                          ('MOVE_END', 1, 'HOLDING', 0)]:
        assert matrix_error(endpoints[a][ai], endpoints[b][bi]) < 2e-4, ('transition', a, b)
    for group in ['MOUSEON', 'HITTED', 'DEFENCE', 'ATTACK_UP', 'ATTACK_DOWN']:
        if group in endpoints:
            for end in endpoints[group]:
                assert matrix_error(end, endpoints['HOLDING'][0]) < 2e-4, ('return to holding', group)
    if 'TURN_L' in endpoints:
        assert matrix_error(endpoints['TURN_L'][0], endpoints['HOLDING'][0]) < 2e-4
        assert matrix_error(endpoints['TURN_R'][1], endpoints['HOLDING'][0]) < 2e-4
        assert matrix_error(endpoints['TURN_L'][1], endpoints['TURN_R'][0]) < 2e-4
        assert matrix_error(*endpoints['TURN_L']) > .5, 'turn must rotate the body'
        assert matrix_error(endpoints['DEATH'][0], endpoints['HOLDING'][0]) < 2e-4
        assert min(corpse_bottoms) > -.002, ('corpse penetrates floor', min(corpse_bottoms))
        assert strike_heights['ATTACK_UP'] > strike_heights['ATTACK_FRONT']+.25
        assert strike_heights['ATTACK_DOWN'] < strike_heights['ATTACK_FRONT']-.25
    assert max(errors) < 2e-4, ('IK', max(errors))
    assert max(replay) < 2e-4, ('saved animation differs from authored motion', max(replay))
    assert min(bottoms) > -2e-4, ('ground penetration', min(bottoms))
    assert max(lengths)-min(lengths) < 1e-5
    assert max(drifts) < 2e-4, ('planted foot drift', max(drifts))
    assert min(walk_blade_elevations)<10 and max(walk_blade_elevations)>55, ('blade levels behind and rises in front',walk_blade_elevations)
    forward=[e for (w,f),e in zip(arm_leg['Right'],walk_blade_elevations) if w>sum(x for x,y in arm_leg['Right'])/len(arm_leg['Right'])]
    backward=[e for (w,f),e in zip(arm_leg['Right'],walk_blade_elevations) if w<sum(x for x,y in arm_leg['Right'])/len(arm_leg['Right'])]
    assert sum(forward)/len(forward)>sum(backward)/len(backward)+20
    correlations={}
    for side,pairs in arm_leg.items():
        mx=sum(a for a,b in pairs)/len(pairs); my=sum(b for a,b in pairs)/len(pairs)
        correlations[side]=sum((a-mx)*(b-my) for a,b in pairs)/math.sqrt(sum((a-mx)**2 for a,b in pairs)*sum((b-my)**2 for a,b in pairs))
        assert correlations[side]<-.8, ('same-side arm and leg must move in opposition',side,correlations[side])
    wrist_swing = max(walk_wrists)-min(walk_wrists)
    elbow_swing = max(walk_elbows)-min(walk_elbows)
    shoulder_swing = max(walk_shoulders)-min(walk_shoulders)
    assert wrist_swing > .30, ('weapon wrist must swing forward and back', wrist_swing)
    assert elbow_swing > .12, ('weapon elbow must participate in the swing', elbow_swing)
    assert shoulder_swing > 25, ('upper arm must rotate at the shoulder', shoulder_swing)
    report = {'evaluated_samples': checked, 'max_ik_error': max(errors),
              'max_replay_error': max(replay), 'min_sole_z': min(bottoms),
              'blade_length_range': max(lengths)-min(lengths), 'max_stance_drift': max(drifts),
              'walk_blade_elevation_degrees': [min(walk_blade_elevations), max(walk_blade_elevations)],
              'strike_tip_heights': strike_heights,
              'arm_leg_correlation': correlations,
              'walk_wrist_swing': wrist_swing, 'walk_elbow_swing': elbow_swing,
              'walk_shoulder_swing_degrees': shoulder_swing,
              'min_corpse_z': min(corpse_bottoms) if corpse_bottoms else None}
    (directory/'checks.json').write_text(json.dumps(report, indent=2)+'\n')
    print('PASS: saved clips and subframes, loop/transition endpoints, IK, ground, grip, planted feet, textures')
    print(json.dumps(report, indent=2))


def matrix_error(a, b):
    return max(abs(a[n][i][j]-b[n][i][j]) for n in a for i in range(4) for j in range(4))


if __name__ == '__main__':
    main()
