#!/usr/bin/env python3
"""Author continuous skeleton motion on the editable study rig in Blender.

Produces editable clips, dense review frames, original-count body frames and
per-frame measurements. It does not install an incomplete animation as a mod.
"""

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skeleton_study as study
import skeleton_geometry as geometry


def smooth(t):
    t = max(0, min(1, t))
    return t*t*(3-2*t)


def mix(a, b, t):
    if isinstance(a, dict):
        return {k: mix(a[k], b[k], t) for k in a}
    if isinstance(a, list):
        return [mix(x, y, t) for x, y in zip(a, b)]
    return a+(b-a)*t


def apply_pose(arm, controls, spec):
    root = bpy.data.objects.get('MotionRoot')
    if root:
        root.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
    for c in controls.values():
        c['target'].rotation_mode = 'XYZ'
    study.apply_study_pose(arm, controls, spec, arm['weapon_hand'])
    for side in ['Left', 'Right']:
        pitch = spec.get('foot_pitch', {}).get(side, 0)
        rotation = Matrix.Rotation(math.radians(pitch), 3, 'X')
        rest = arm.data.bones[side+'Foot'].matrix_local.to_3x3()
        controls[side+'Leg']['target'].rotation_euler = (rotation @ rest).to_euler()
    if 'weapon_quaternion' in spec:
        target = controls[arm['weapon_hand'].replace('Hand', 'Arm')]['target']
        target.rotation_mode = 'QUATERNION'
        target.rotation_quaternion = Quaternion(spec['weapon_quaternion'])
    bpy.context.view_layer.update()
    if root:
        root.rotation_mode = 'XYZ'
        root.rotation_euler.z = math.radians(spec.get('root_yaw', 0))
        bpy.context.view_layer.update()
        if spec.get('floor_support'):
            meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
            bottom = min(p.z for p in study.render.world_vertices(meshes, bpy.context.evaluated_depsgraph_get()))
            root.location.z = max(0, .003-bottom)*spec['floor_support']
            bpy.context.view_layer.update()


class Motion:
    def __init__(self, profile, contact_height, direction, stride):
        self.profile = profile
        self.contact_height = contact_height
        self.direction = Vector(direction)
        self.stride = stride
        self.rotations = {}

    def contact(self, side, phase):
        return (phase + (0 if side == 'Right' else .5)) % 1 < self.profile['walk']['stance_fraction']

    def pose(self, group, t):
        if group == 'HOLDING':
            result = copy.deepcopy(self.profile['poses']['holding'])
            wave = math.sin(math.tau*t)
            result['hips'][2] += .006*wave
            result['lean'] += 1.4*wave
            result['neck'] -= .6*wave
            result['LeftArm']['target'][2] += .008*wave
            result['RightArm']['target'][2] += .004*wave
        elif group == 'MOVING':
            result = copy.deepcopy(self.profile['poses']['walk_contact'])
            wave = math.sin(math.tau*t)
            result['hips'][0] += .007*wave
            result['hips'][2] -= .014*math.cos(2*math.tau*t)
            result['lean'] += 2*math.sin(2*math.tau*t)
            swing = self.profile['walk']['weapon_arm_swing']
            carry = self.profile['walk']['blade_elevation_degrees']
            result['foot_pitch'] = {}
            duty = self.profile['walk']['stance_fraction']
            for side, sign, offset in [('Right', -1, 0), ('Left', 1, .5)]:
                phase = (t+offset) % 1
                distance = self.stride*(phase-duty/2)
                lift = pitch = 0
                if phase >= duty:
                    u = (phase-duty)/(1-duty)
                    a = self.stride*duty/2
                    slope = self.stride*(1-duty)
                    # Hermite endpoints have the same backwards velocity as the
                    # stance phase. No instantaneous foot-velocity reversal.
                    distance = ((2*u**3-3*u*u+1)*a + (u**3-2*u*u+u)*slope
                                + (-2*u**3+3*u*u)*(-a) + (u**3-u*u)*slope)
                    lift = self.profile['walk']['lift']*math.sin(math.pi*u)**2
                    pitch = 12*math.sin(math.pi*u)**2
                point = Vector((sign*self.profile['walk']['foot_spread'], 0, self.contact_height[side]))
                point -= self.direction*distance
                point.z += lift
                result[side+'Leg']['target'] = list(point)
                result['foot_pitch'][side] = pitch
                # Couple each arm to its own foot in opposition: forward foot,
                # backward wrist. The old cosine put the right pair forward together.
                arm_wave=max(-1, min(1, distance/(self.stride*duty/2)))
                if side == 'Right':
                    angle=math.radians(carry['back']+(carry['front']-carry['back'])*(arm_wave+1)/2)
                    result['blade_direction']=[0,-math.cos(angle),math.sin(angle)]
                    result['RightArm']['target'][1] -= swing['wrist_forward']*arm_wave
                    result['RightArm']['target'][2] += swing['wrist_lift']*arm_wave
                    result['RightArm']['pole'][1] -= swing['elbow_forward']*arm_wave
                else:
                    result['LeftArm']['target'][1] -= .045*arm_wave
        elif group in ['ATTACK_FRONT', 'ATTACK_UP', 'ATTACK_DOWN']:
            keys = self.profile['clips'][group]['keys']
            before, after = keys[0], keys[-1]
            for a, b in zip(keys, keys[1:]):
                if a[0] <= t <= b[0]:
                    before, after = a, b
                    break
            blend = smooth((t-before[0])/(after[0]-before[0]))
            result = mix(self.profile['poses'][before[1]], self.profile['poses'][after[1]], blend)
            if self.rotations:
                result['weapon_quaternion'] = list(self.rotations[before[1]].slerp(self.rotations[after[1]], blend))
            # Rear foot supports the whole attack. The front foot steps into the
            # lunge and returns in a separate lifted phase, instead of sliding.
            idle = self.profile['poses']['holding']['RightLeg']['target']
            strike = self.profile['poses'][self.profile['clips'][group].get('strike_pose', 'strike')]['RightLeg']['target']
            lift = 0
            if t < .12:
                foot = list(idle)
            elif t < 3/7:
                u = (t-.12)/(3/7-.12)
                foot = mix(idle, strike, smooth(u))
                lift = .26*math.sin(math.pi*u)**2
            elif t < .70:
                foot = list(strike)
            elif t < .95:
                u = (t-.70)/.25
                foot = mix(strike, idle, smooth(u))
                lift = .12*math.sin(math.pi*u)**2
            else:
                foot = list(idle)
            foot[2] = self.contact_height['Right']+lift
            result['RightLeg']['target'] = foot
            result['LeftLeg']['target'] = list(self.profile['poses']['holding']['LeftLeg']['target'])
            result['foot_pitch'] = {'Right': 12*lift/.26}
        elif group in ['MOVE_START', 'MOVE_END']:
            start, end = self.pose('HOLDING', 0), self.pose('MOVING', 0)
            if group == 'MOVE_END':
                start, end = end, start
            start.pop('foot_pitch', None)
            end.pop('foot_pitch', None)
            result = mix(start, end, smooth(t))
            for side, offset in [('Right', 0), ('Left', .5)]:
                u = max(0, min(1, (t-offset)*2))
                foot = mix(start[side+'Leg']['target'], end[side+'Leg']['target'], smooth(u))
                foot[2] = self.contact_height[side]+.075*math.sin(math.pi*u)**2
                result[side+'Leg']['target'] = foot
        elif group in ['TURN_L', 'TURN_R']:
            u = t if group == 'TURN_L' else 1-t
            result = self.pose('HOLDING', 0)
            result['root_yaw'] = -75*smooth(u)
        elif group in ['MOUSEON', 'HITTED', 'DEFENCE', 'DEATH']:
            keys = self.profile['clips'][group]['keys']
            a, b = keys[0], keys[-1]
            for before, after in zip(keys, keys[1:]):
                if before[0] <= t <= after[0]:
                    a, b = before, after
                    break
            u = smooth((t-a[0])/(b[0]-a[0]))
            result = mix(self.profile['poses'][a[1]], self.profile['poses'][b[1]], u)
            if self.rotations:
                result['weapon_quaternion'] = list(self.rotations[a[1]].slerp(self.rotations[b[1]], u))
            for side in ['Left', 'Right']:
                result[side+'Leg']['target'][2] = self.contact_height[side]
            if group == 'DEATH':
                result['floor_support'] = smooth(t/.17)
        else:
            raise ValueError(group)
        if group != 'MOVING':
            for side in ['Left', 'Right']:
                if group == 'HOLDING' or (group.startswith('ATTACK_') and side == 'Left'):
                    result[side+'Leg']['target'][2] = self.contact_height[side]
        return result

    def calibrate_grip(self, arm, controls):
        # Slerp key orientations across the attack. Re-deriving a hand basis from
        # a nearly parallel blade and forearm at every frame can flip the wrist.
        names = {name for clip in self.profile['clips'].values() for _, name in clip.get('keys', [])}
        for name in sorted(names):
            spec = copy.deepcopy(self.profile['poses'][name])
            apply_pose(arm, controls, spec)
            self.rotations[name] = controls['RightArm']['target'].matrix_world.to_quaternion()


def controls_for(arm):
    return {side+limb.title(): study.make_ik(arm, side, limb)
            for side in ['Left', 'Right'] for limb in ['arm', 'leg']}


def key_pose(arm, controls, frame, previous):
    root = bpy.data.objects['MotionRoot']
    root.keyframe_insert('location', frame=frame)
    root.keyframe_insert('rotation_euler', frame=frame)
    for bone in arm.pose.bones:
        basis = bone.matrix_basis.copy()
        bone.rotation_mode = 'QUATERNION'
        bone.matrix_basis = basis
        key = 'bone:'+bone.name
        if key in previous and previous[key].dot(bone.rotation_quaternion) < 0:
            bone.rotation_quaternion.negate()
        previous[key] = bone.rotation_quaternion.copy()
        bone.keyframe_insert('location', frame=frame)
        bone.keyframe_insert('rotation_quaternion', frame=frame)
    for name, c in controls.items():
        for kind in ['target', 'pole']:
            obj = c[kind]
            obj.keyframe_insert('location', frame=frame)
            if kind == 'target':
                basis = obj.matrix_basis.copy()
                obj.rotation_mode = 'QUATERNION'
                obj.matrix_basis = basis
                if name in previous and previous[name].dot(obj.rotation_quaternion) < 0:
                    obj.rotation_quaternion.negate()
                previous[name] = obj.rotation_quaternion.copy()
                obj.keyframe_insert('rotation_quaternion', frame=frame)


def linear_keys(action):
    # Python keyframe_insert does not honor the UI's interpolation preference.
    # Enforce this on the actual layered Action before saving or sampling it.
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for point in curve.keyframe_points:
                        point.interpolation = 'LINEAR'


def record(arm, controls, socket, weapons, motion, group, t):
    row = study.measurements(arm, controls, socket, weapons)
    row['phase'] = t
    row['weapon_rotation'] = list(socket.matrix_world.to_quaternion())
    row['contact'] = {}
    if group == 'MOVING':
        travel = motion.direction*motion.stride*t
        for side, offset in [('Right', 0), ('Left', .5)]:
            row['contact'][side] = {
                'planted': motion.contact(side, t), 'step': math.floor(t+offset),
                'world_ankle': list(Vector(row[side+'Leg']['actual'])+travel),
            }
    return row


def build(args, rig_profile):
    meshes, camera, _ = study.render.build_scene(str(args.model), (900, 800),
        rig_profile['camera']['elevation'], rig_profile['camera']['azimuth'], 534, 158,
        args.samples, 4, .08)
    old_arm = study.render.find_armature()
    source = max(meshes, key=lambda obj: len(obj.data.vertices))
    arm = study.make_rig(rig_profile['landmarks'])
    _, repair = study.rebuild_weights(source, arm)
    for obj in meshes+[old_arm]:
        bpy.data.objects.remove(obj, do_unlink=True)
    mat = study.material('HandBone', (.54, .48, .35))
    study.make_limbs(arm, mat)
    held = rig_profile['weapon_hand'].removesuffix('Hand')
    for side in ['Left', 'Right']:
        study.make_hand(arm, side, side == held, mat)
    socket, weapons = study.make_weapon(arm, held)
    geometry.refine(arm)
    controls = controls_for(arm)
    contact = {side: arm.data.bones[side+'Foot'].head_local.z -
               min(v.co.z for v in bpy.data.objects[side+'FootGeometry'].data.vertices)
               for side in ['Left', 'Right']}
    root = bpy.data.objects.new('MotionRoot', None)
    bpy.context.scene.collection.objects.link(root)
    for obj in list(bpy.context.scene.objects):
        if obj != root and obj.type not in ['CAMERA', 'LIGHT'] and obj.parent is None:
            obj.parent = root
    return arm, controls, socket, weapons, camera, repair, contact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--profile', type=Path, default=Path(__file__).parent/'profiles/skeleton-motion.json')
    parser.add_argument('--samples', type=int, default=24)
    parser.add_argument('--no-render', action='store_true')
    args = parser.parse_args(study.render.argv_after_ddash())
    profile = json.loads(args.profile.read_text())
    rig_profile = json.loads((args.profile.parent/profile['rig_profile']).read_text())
    if hashlib.sha256(args.model.read_bytes()).hexdigest() != rig_profile['source_sha256']:
        raise SystemExit('source SHA-256 does not match the inspected skeleton')
    if args.out.exists() and any(args.out.iterdir()):
        raise SystemExit('Use an empty output directory')
    args.out.mkdir(parents=True, exist_ok=True)
    code = args.out/'code'
    code.mkdir()
    scripts = [Path(__file__), Path(study.__file__), Path(geometry.__file__),
               Path(study.render.__file__), Path(study.render.poses.__file__), Path(__file__).parent/'vcmi_anim.py']
    hashes = {}
    for p in scripts:
        content = p.read_bytes()
        (code/p.name).write_bytes(content)
        hashes[p.name] = hashlib.sha256(content).hexdigest()
    arm, controls, socket, weapons, camera, repair, contact = build(args, rig_profile)
    scene = bpy.context.scene
    scene.render.fps = profile['fps']
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
    direction = camera.rotation_euler.to_matrix().col[0].copy()
    direction.z = 0
    direction.normalize()
    motion = Motion(profile, contact, direction, 1)
    apply_pose(arm, controls, motion.pose('HOLDING', 0))
    camera.data.ortho_scale = 8
    camera.location = Vector((0, -.1, .75))+camera.rotation_euler.to_matrix()@Vector((0, 0, 10))
    study.render.calibrate_camera(camera, (900, 800), 534, 158, str(args.out/'_calibration.png'))
    motion.stride = profile['walk']['hex_width']*profile['walk']['tiles_per_cycle']*camera.data.ortho_scale/450
    motion.calibrate_grip(arm, controls)
    report = {}
    objects = [arm, bpy.data.objects['MotionRoot']]+[c[k] for c in controls.values() for k in ['target', 'pole']]
    for group, clip in profile['clips'].items():
        for obj in objects:
            obj.animation_data_clear()
        count = round(clip['seconds']*profile['fps'])
        previous = {}
        rows = []
        for i in range(count+1):
            scene.frame_set(i+1)
            apply_pose(arm, controls, motion.pose(group, i/count))
            key_pose(arm, controls, i+1, previous)
            bpy.context.view_layer.update()
            rows.append(record(arm, controls, socket, weapons, motion, group, i/count))
        scene.frame_start = 1
        scene.frame_end = count if clip['loop'] else count+1
        scene['clip'] = group
        scene['loop'] = clip['loop']
        scene['closure_frame'] = count+1
        scene['travel_per_cycle'] = motion.stride if group == 'MOVING' else 0
        scene['travel_direction'] = list(direction)
        for obj in objects:
            obj.animation_data.action.name = group+'/'+obj.name
            linear_keys(obj.animation_data.action)
        scene.frame_set(1)
        bpy.ops.wm.save_as_mainfile(filepath=str(args.out/(group.lower()+'.blend')))
        report[group] = {'frames': rows, 'closure_frame': count+1}
        if args.no_render:
            continue
        directory = args.out/'review'/group.lower()
        directory.mkdir(parents=True)
        for i in range(scene.frame_end):
            scene.frame_set(i+1)
            study.render.render_to(str(directory/('%03d.png' % i)))
        for scale in [1, 2]:
            scene.render.resolution_x, scene.render.resolution_y = 450*scale, 400*scale
            directory = args.out/('sprites%dx' % scale)
            directory.mkdir(exist_ok=True)
            for i in range(clip['sprite_frames']):
                t = i/(clip['sprite_frames'] if clip['loop'] else clip['sprite_frames']-1)
                frame = 1+t*count
                scene.frame_set(math.floor(frame), subframe=frame % 1)
                study.render.render_to(str(directory/('%s_%02d.png' % (group.lower(), i))))
        scene.render.resolution_x, scene.render.resolution_y = 900, 800
    manifest = {'source_sha256': rig_profile['source_sha256'], 'rig_profile': rig_profile,
        'profile': profile, 'scripts_sha256': hashes, 'repairs': repair,
        'contact_height': contact, 'stride': motion.stride, 'direction': list(direction),
        'camera': {'ortho_scale': camera.data.ortho_scale, 'rotation': list(camera.rotation_euler),
                   'location': list(camera.location), 'shift_x': camera.data.shift_x, 'shift_y': camera.data.shift_y},
        'blender': bpy.app.version_string, 'samples': args.samples, 'clips': report}
    (args.out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print('MOTION: saved %d clips, stride %.6f' % (len(report), motion.stride))


if __name__ == '__main__':
    main()
