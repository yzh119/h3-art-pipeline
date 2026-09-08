#!/usr/bin/env python3
"""Build the CSKELE rig/hand study in Blender, without changing the shipped poses.

blender -b --python skeleton_study.py -- --model skeleton.glb --out study

The input is the inspected Meshy v4 asset. Landmarks and segmentation are specific
to this mesh; this is deliberately not an automatic rigger for arbitrary models.
Four independent poses are stored in world coordinates, with IK wrist/ankle
targets and elbow/knee poles. The resulting .blend retains editable controls.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_sprites as render


def material(name, color, roughness=0.65, metallic=0):
    result = bpy.data.materials.new(name)
    result.diffuse_color = (*color, 1)
    result.use_nodes = True
    shader = result.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Metallic'].default_value = metallic
    return result


def make_rig(landmarks):
    data = bpy.data.armatures.new('SkeletonStudy')
    arm = bpy.data.objects.new('SkeletonStudy', data)
    bpy.context.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for name, spec in landmarks.items():
        bone = data.edit_bones.new(name)
        bone.head, bone.tail = spec['head'], spec['tail']
        if spec.get('parent'):
            bone.parent = data.edit_bones[spec['parent']]
        bone.align_roll(Vector((0, -1, 0)))
    bpy.ops.object.mode_set(mode='OBJECT')
    arm.show_in_front = True
    data.display_type = 'STICK'
    return arm


def mesh_from_faces(source, keep, name):
    indices = sorted({index for p in source.data.polygons if keep(p)
                      for index in p.vertices})
    remap = {old: new for new, old in enumerate(indices)}
    polygons = [p for p in source.data.polygons if keep(p)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([source.matrix_world @ source.data.vertices[i].co for i in indices],
                    [], [[remap[i] for i in p.vertices] for p in polygons])
    for mat in source.data.materials:
        mesh.materials.append(mat)
    uv = mesh.uv_layers.new() if source.data.uv_layers.active else None
    for new, old in zip(mesh.polygons, polygons):
        new.material_index = old.material_index
        new.use_smooth = old.use_smooth
        if uv:
            for a, b in zip(new.loop_indices, old.loop_indices):
                uv.data[a].uv = source.data.uv_layers.active.data[b].uv
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def rebuild_weights(source, arm):
    """Keep complete torso/skull components and replace the fused limb geometry.

    Meshy joins some long triangles across anatomical joints. Reweighting those
    triangles produces spikes even with correct IK endpoints. Retained components
    are rigid; the new limb shafts and hands are built separately below.
    """
    points = [source.matrix_world @ v.co for v in source.data.vertices]
    owners = {}
    retained = {}
    for component in render.connected_components(source.data):
        lo = Vector(tuple(min(points[i][a] for i in component) for a in range(3)))
        hi = Vector(tuple(max(points[i][a] for i in component) for a in range(3)))
        if lo.x < -.195 or hi.x > .195 or lo.z < .84:
            continue
        if lo.z > 1.43 and max(abs(lo.x), abs(hi.x)) < .115:
            owner = 'Head'
        elif hi.z < 1.11:
            owner = 'Hips'
        else:
            owner = 'Chest'
        for i in component:
            owners[i] = owner
        retained[owner] = retained.get(owner, 0) + len(component)

    body = mesh_from_faces(source, lambda p: all(i in owners for i in p.vertices), 'Body')
    # mesh_from_faces preserves the sorted source vertex order.
    indices = sorted({i for p in source.data.polygons
                      if all(i in owners for i in p.vertices) for i in p.vertices})
    for owner in ['Head', 'Hips', 'Chest']:
        group = body.vertex_groups.new(name=owner)
        selected = [new for new, old in enumerate(indices) if owners[old] == owner]
        if selected:
            group.add(selected, 1, 'REPLACE')
    body.modifiers.new('SkeletonStudy', 'ARMATURE').object = arm
    return body, {'retained_vertices': retained,
                  'replaced_vertices': len(points) - len(indices)}


class Geometry:
    def __init__(self):
        self.vertices, self.faces = [], []

    def bone(self, start, end, radius=.006, rings=8):
        """Tapered phalanx with wider articular ends; preserves finger gaps."""
        start, end = Vector(start), Vector(end)
        axis = (end - start).normalized()
        u = axis.orthogonal().normalized()
        v = axis.cross(u)
        offset = len(self.vertices)
        for t, scale in [(0, .7), (.12, 1.1), (.35, .72), (.7, .7), (.9, 1.12), (1, .75)]:
            for i in range(rings):
                angle = 2 * math.pi * i / rings
                self.vertices.append(start.lerp(end, t) + radius * scale *
                                     (u * math.cos(angle) + v * math.sin(angle)))
        self.faces.append(tuple(offset + i for i in reversed(range(rings))))
        for row in range(5):
            for i in range(rings):
                j = (i + 1) % rings
                self.faces.append((offset + row*rings+i, offset + row*rings+j,
                                   offset + (row+1)*rings+j, offset + (row+1)*rings+i))
        self.faces.append(tuple(offset + 5*rings+i for i in range(rings)))

    def joint(self, center, radii):
        center = Vector(center)
        offset = len(self.vertices)
        rings, segments = 8, 12
        for row in range(rings + 1):
            latitude = math.pi * row / rings
            for col in range(segments):
                angle = math.tau * col / segments
                self.vertices.append(center + Vector((
                    radii[0] * math.sin(latitude) * math.cos(angle),
                    radii[1] * math.sin(latitude) * math.sin(angle),
                    radii[2] * math.cos(latitude))))
        for row in range(rings):
            for col in range(segments):
                nxt = (col + 1) % segments
                self.faces.append((offset + row*segments+col, offset + (row+1)*segments+col,
                                   offset + (row+1)*segments+nxt, offset + row*segments+nxt))

    def object(self, name, mat, transform=None):
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([transform @ p if transform else p for p in self.vertices],
                        [], self.faces)
        mesh.materials.append(mat)
        for p in mesh.polygons:
            p.use_smooth = True
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(obj)
        return obj


def rigid_geometry(geometry, name, arm, owner, mat):
    obj = geometry.object(name, mat)
    obj.vertex_groups.new(name=owner).add(list(range(len(obj.data.vertices))), 1, 'REPLACE')
    obj.modifiers.new('SkeletonStudy', 'ARMATURE').object = arm
    return obj


def make_limbs(arm, mat):
    result = []
    for side, sign in [('Left', 1), ('Right', -1)]:
        for part, radius in [('Arm', .019), ('ForeArm', .010), ('UpLeg', .025), ('Leg', .018)]:
            owner = side + part
            bone = arm.data.bones[owner]
            a, b = bone.head_local.copy(), bone.tail_local.copy()
            g = Geometry()
            if part in ['ForeArm', 'Leg']:
                offset = Vector((sign * .014, 0, 0))
                g.bone(a + offset, b + offset*.5, radius)
                g.bone(a - offset, b - offset*.5, radius*.7)
            else:
                g.bone(a.lerp(b, .04), a.lerp(b, .97), radius)
            ball = radius * 1.3
            g.joint(a, (ball, ball*.9, ball))
            g.joint(b, (ball*1.2, ball*.85, ball*.8))
            result.append(rigid_geometry(g, owner + 'Geometry', arm, owner, mat))
        foot = arm.data.bones[side + 'Foot'].head_local
        g = Geometry()
        g.joint(foot + Vector((0, .005, -.027)), (.032, .037, .028))
        for i in range(5):
            x = sign * (-.027 + i*.014)
            length = .14 - i*.012
            a = foot + Vector((x*.3, -.008, -.035))
            b = foot + Vector((x, -length*.68, -.045))
            c = foot + Vector((x, -length, -.049))
            g.bone(a, b, .010 if i == 0 else .008)
            g.bone(b, c, .008 if i == 0 else .006)
        result.append(rigid_geometry(g, side + 'FootGeometry', arm, side + 'Foot', mat))
    g = Geometry()
    neck = arm.data.bones['Neck']
    g.bone(neck.head_local, neck.tail_local, .024)
    result.append(rigid_geometry(g, 'NeckGeometry', arm, 'Neck', mat))
    return result


def make_hand(arm, side, closed, mat):
    geometry = Geometry()
    # Four separated metacarpals and three phalanges each, plus a thumb.
    for i, x in enumerate([-.027, -.009, .009, .027]):
        length = [0.90, 1, 1.02, .90][i]
        geometry.bone((x*.28, 0, 0), (x, .060*length, 0), .007)
        if closed:
            path = [(x, .060*length, 0), (x, .094, -.010),
                    (x, .120, .012), (x, .106, .040)]
        else:
            path = [(x, .060*length, 0), (x*1.2, .094*length, .008),
                    (x*1.3, .114*length, .020), (x*1.3, .124*length, .036)]
        for a, b in zip(path, path[1:]):
            geometry.bone(a, b, .006)
    thumb = [(0.012, .005, 0), (.042, .035, .002),
             (.050, .076, .021), (.026, .096, .037)] if closed else [
                 (.012, .005, 0), (.040, .027, .004), (.050, .054, .012), (.043, .070, .027)]
    for a, b in zip(thumb, thumb[1:]):
        geometry.bone(a, b, .0075)
    # +Y points towards the fingers, +Z into the palm. In that frame the
    # anatomical right thumb is on -X. Mirror geometry, including winding;
    # renaming the same mesh Left/Right would produce two left hands.
    if side == 'Right':
        geometry.vertices = [Vector((-p.x, p.y, p.z)) for p in geometry.vertices]
        geometry.faces = [tuple(reversed(face)) for face in geometry.faces]
    name = side + 'Hand'
    result = geometry.object(name + 'Geometry', mat, arm.data.bones[name].matrix_local)
    result.vertex_groups.new(name=name).add(list(range(len(result.data.vertices))), 1, 'REPLACE')
    result.modifiers.new('SkeletonStudy', 'ARMATURE').object = arm
    result['finger_count'] = 5
    return result


def make_weapon(arm, side):
    name = side + 'Hand'
    socket = bpy.data.objects.new('WeaponGrip', None)
    bpy.context.collection.objects.link(socket)
    socket.empty_display_type = 'ARROWS'
    socket.empty_display_size = .08
    constraint = socket.constraints.new('COPY_TRANSFORMS')
    constraint.target, constraint.subtarget = arm, name
    arm['weapon_hand'] = name
    socket['hand'] = name

    leather = material('GripLeather', (.075, .047, .025))
    steel = material('SwordSteel', (.40, .38, .31), .7, .05)
    brass = material('Guard', (.23, .16, .065), .5, .35)
    geom = Geometry()
    geom.bone((-.045, .099, .018), (.055, .099, .018), .011, 12)
    grip = geom.object('SwordGrip', leather)
    grip.parent = socket
    geom = Geometry()
    geom.bone((.064, .025, .018), (.064, .17, .018), .010)
    guard = geom.object('SwordGuard', brass)
    guard.parent = socket
    mesh = bpy.data.meshes.new('Blade')
    # Diamond cross section, pointed blade; separate from hand and body weights.
    verts = []
    for x, width in [(.077, .038), (.61, .028), (.80, .0005)]:
        verts.extend([(x, .099-width, .018), (x, .099, .026),
                      (x, .099+width, .018), (x, .099, .010)])
    faces = [(r*4+i, r*4+(i+1)%4, (r+1)*4+(i+1)%4, (r+1)*4+i)
             for r in range(2) for i in range(4)]
    faces += [(3, 2, 1, 0), (8, 9, 10, 11)]
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(steel)
    blade = bpy.data.objects.new('SwordBlade', mesh)
    bpy.context.collection.objects.link(blade)
    blade.parent = socket
    if side == 'Right':
        for obj in [grip, guard, blade]:
            for vertex in obj.data.vertices:
                vertex.co.x *= -1
            obj.data.flip_normals()
            obj.data.update()
    return socket, [grip, guard, blade]


def empty(name, location):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    obj.empty_display_type = 'SPHERE'
    obj.empty_display_size = .035
    return obj


def make_ik(arm, side, limb):
    upper, lower, end = (('Arm', 'ForeArm', 'Hand') if limb == 'arm'
                         else ('UpLeg', 'Leg', 'Foot'))
    target = empty(side + end + 'Target', arm.data.bones[side + end].head_local)
    root = arm.data.bones[side + upper].head_local
    joint = arm.data.bones[side + lower].head_local
    endpoint = arm.data.bones[side + end].head_local
    axis = (endpoint - root).normalized()
    direction = joint - root - axis * (joint - root).dot(axis)
    pole = empty(side + lower + 'Pole', joint + direction.normalized() * .5)
    constraint = arm.pose.bones[side + lower].constraints.new('IK')
    constraint.target, constraint.pole_target = target, pole
    constraint.chain_count = 2
    constraint.use_stretch = False
    constraint.iterations = 128
    # Calibrate roll once against the known rest elbow/knee. Do not guess that
    # imported left/right bone axes have matching signs.
    best = (float('inf'), 0)
    for step in range(72):
        angle = -math.pi + step * math.tau / 72
        constraint.pole_angle = angle
        bpy.context.view_layer.update()
        error = (arm.pose.bones[side + lower].head - joint).length
        if error < best[0]:
            best = error, angle
    constraint.pole_angle = best[1]
    target.rotation_euler = arm.data.bones[side + end].matrix_local.to_euler()
    rotation = arm.pose.bones[side + end].constraints.new('COPY_ROTATION')
    rotation.target = target
    return {'target': target, 'pole': pole, 'end': side + end, 'joint': side + lower}


def orient_bone(arm, name, rotation):
    bone = arm.pose.bones[name]
    matrix = rotation.to_4x4()
    matrix.translation = bone.head
    bone.matrix = matrix
    bpy.context.view_layer.update()


def apply_study_pose(arm, controls, spec, weapon_hand):
    # These keys are absolute. Reset the entire pose before applying one.
    for b in arm.pose.bones:
        b.matrix_basis = Matrix.Identity(4)
    hips = arm.pose.bones['Hips']
    hips.matrix = Matrix.Translation(Vector(spec['hips'])) @ arm.data.bones['Hips'].matrix_local.to_3x3().to_4x4()
    bpy.context.view_layer.update()
    for name, angle in [('Chest', spec['lean']), ('Neck', spec['neck'])]:
        b = arm.pose.bones[name]
        rotation = Matrix.Rotation(math.radians(angle), 3, 'X')
        rest = arm.data.bones[name].matrix_local.to_3x3()
        orient_bone(arm, name, rotation @ rest)
    for key, control in controls.items():
        control['target'].location = spec[key]['target']
        control['pole'].location = spec[key]['pole']
    bpy.context.view_layer.update()
    # Keep the feet parallel to the floor, independently of the knee solution.
    for side in ['Left', 'Right']:
        name = side + 'Foot'
        controls[side + 'Leg']['target'].rotation_euler = arm.data.bones[name].matrix_local.to_euler()
        name = side + 'Hand'
        forearm = arm.pose.bones[side + 'ForeArm']
        if name == weapon_hand:
            x = Vector(spec['blade_direction']).normalized() * (-1 if side == 'Right' else 1)
            along = (forearm.tail - forearm.head).normalized()
            y = along - x * along.dot(x)
            if y.length < .01:
                raise ValueError('blade and forearm are parallel; specify a usable grip')
            y.normalize()
            z = x.cross(y).normalized()
            controls[side + 'Arm']['target'].rotation_euler = Matrix((x, y, z)).transposed().to_euler()
        else:
            controls[side + 'Arm']['target'].rotation_euler = forearm.matrix.to_euler()
    bpy.context.view_layer.update()


def measurements(arm, controls, socket, weapons):
    rows = {}
    for key, c in controls.items():
        actual = arm.matrix_world @ arm.pose.bones[c['end']].head
        rows[key] = {'target_error': (actual - c['target'].matrix_world.translation).length,
                     'actual': list(actual), 'joint': list(arm.matrix_world @ arm.pose.bones[c['joint']].head)}
    blade = weapons[-1]
    tip = sum((v.co for v in blade.data.vertices[8:12]), Vector()) / 4
    heel = sum((v.co for v in blade.data.vertices[:4]), Vector()) / 4
    rows['blade_length'] = (blade.matrix_world @ tip - blade.matrix_world @ heel).length
    rows['socket_error'] = (socket.matrix_world.translation -
                            arm.matrix_world @ arm.pose.bones[arm['weapon_hand']].head).length
    rows['head'] = list(arm.matrix_world @ arm.pose.bones['Head'].head)
    graph = bpy.context.evaluated_depsgraph_get()
    for side in ['Left', 'Right']:
        obj = bpy.data.objects[side + 'FootGeometry']
        points = render.world_vertices([obj], graph)
        rows[side + 'FootBottom'] = min(p.z for p in points)
    return rows


def hand_details(arm, weapons, directory):
    scene = bpy.context.scene
    camera = scene.camera
    meshes = [o for o in scene.objects if o.type == 'MESH']
    for obj in scene.objects:
        if obj.type == 'LIGHT':
            obj.hide_render = True
    light = bpy.data.objects.new('HandInspectionLight', bpy.data.lights.new('HandInspectionLight', 'AREA'))
    scene.collection.objects.link(light)
    light.data.energy = 4
    light.data.shape = 'DISK'
    light.data.size = .25
    for side in ['Left', 'Right']:
        visible = [bpy.data.objects[side + 'HandGeometry']]
        if side + 'Hand' == arm['weapon_hand']:
            visible += weapons
        for obj in meshes:
            obj.hide_render = obj not in visible
        hand = arm.pose.bones[side + 'Hand'].matrix
        center = hand @ Vector((0, .067, .018))
        camera.location = center + hand.to_3x3() @ Vector((.12, -.12, .28))
        camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
        light.location = center + hand.to_3x3() @ Vector((-.15, -.05, .35))
        light.rotation_euler = (center - light.location).to_track_quat('-Z', 'Y').to_euler()
        camera.data.ortho_scale = .24
        camera.data.shift_x = camera.data.shift_y = 0
        scene.render.resolution_x, scene.render.resolution_y = 700, 600
        render.render_to(str(directory / (side.lower() + '-hand.png')))
    for obj in meshes:
        obj.hide_render = False


def baseline(args):
    """Render the previous implementation using its original camera settings."""
    folder = args.out / 'before'
    folder.mkdir()
    meshes, camera, _ = render.build_scene(str(args.model), (900, 800), 30, -40,
                                          534, 158, args.samples)
    arm = render.find_armature()
    mirror = render.rebind_weapon(meshes, arm) == 'LeftHand'
    render.apply_pose(arm, render.poses.pose_at('HOLDING', 0, 'CSKELE', mirror))
    render.calibrate_camera(camera, (900, 800), 534, 158, str(folder / '_calibration.png'))
    keys = [('holding', 'HOLDING', 0), ('walk_contact', 'MOVING', 0),
            ('windup', 'ATTACK_FRONT', .2), ('strike', 'ATTACK_FRONT', .45)]
    for name, group, t in keys:
        render.apply_pose(arm, render.poses.pose_at(group, t, 'CSKELE', mirror))
        render.render_to(str(folder / (name + '.png')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--profile', type=Path, default=Path(__file__).parent / 'profiles/skeleton-study.json')
    parser.add_argument('--samples', type=int, default=24)
    args = parser.parse_args(render.argv_after_ddash())
    profile = json.loads(args.profile.read_text())
    model_hash = hashlib.sha256(args.model.read_bytes()).hexdigest()
    if model_hash != profile['source_sha256']:
        raise SystemExit('This profile is for the inspected v4 mesh; source SHA-256 does not match.')
    if args.out.exists() and any(args.out.iterdir()):
        raise SystemExit('Use a new output directory for each study revision.')
    args.out.mkdir(parents=True, exist_ok=True)
    code = args.out / 'code'
    code.mkdir()
    scripts = [Path(__file__), Path(render.__file__), Path(render.poses.__file__),
               Path(__file__).parent / 'vcmi_anim.py']
    hashes = {}
    for script in scripts:
        content = script.read_bytes()
        hashes[script.name] = hashlib.sha256(content).hexdigest()
        (code / script.name).write_bytes(content)
    baseline(args)
    meshes, camera, _ = render.build_scene(str(args.model), (900, 800),
        profile['camera']['elevation'], profile['camera']['azimuth'], 534, 158,
        args.samples, 4, .08)
    old_arm = render.find_armature()
    source = max(meshes, key=lambda obj: len(obj.data.vertices))
    arm = make_rig(profile['landmarks'])
    body, repair = rebuild_weights(source, arm)
    for obj in meshes + [old_arm]:
        bpy.data.objects.remove(obj, do_unlink=True)
    bone_mat = material('HandBone', (.54, .48, .35))
    make_limbs(arm, bone_mat)
    held_side = profile['weapon_hand'].removesuffix('Hand')
    for side in ['Left', 'Right']:
        make_hand(arm, side, side == held_side, bone_mat)
    socket, weapons = make_weapon(arm, held_side)
    controls = {side + limb.title(): make_ik(arm, side, limb)
                for side in ['Left', 'Right'] for limb in ['arm', 'leg']}
    bpy.context.view_layer.update()
    apply_study_pose(arm, controls, profile['poses']['holding'], profile['weapon_hand'])
    camera.data.ortho_scale = 8
    camera.location = Vector((0, -.1, .75)) + camera.rotation_euler.to_matrix() @ Vector((0, 0, 10))
    render.calibrate_camera(camera, (900, 800), 534, 158, str(args.out / '_calibration.png'))
    camera_state = {'location': list(camera.location), 'rotation': list(camera.rotation_euler),
                    'ortho_scale': camera.data.ortho_scale, 'shift_x': camera.data.shift_x,
                    'shift_y': camera.data.shift_y}
    report = {}
    for index, (name, spec) in enumerate(profile['poses'].items()):
        apply_study_pose(arm, controls, spec, profile['weapon_hand'])
        report[name] = measurements(arm, controls, socket, weapons)
        render.render_to(str(args.out / (name + '.png')))
        # An independent .blend for each key pose keeps IK controls editable and
        # avoids implying that four diagnostic poses form a finished animation.
        bpy.ops.wm.save_as_mainfile(filepath=str(args.out / (name + '.blend')))
    # Close-ups are rendered after saving so the deliverable opens on the full body.
    apply_study_pose(arm, controls, profile['poses']['holding'], profile['weapon_hand'])
    hand_details(arm, weapons, args.out)
    args.out.joinpath('manifest.json').write_text(json.dumps({
        'source_sha256': model_hash, 'profile': profile, 'repairs': repair,
        'blender': bpy.app.version_string, 'camera': camera_state,
        'samples': args.samples, 'render_size': [900, 800],
        'scripts_sha256': hashes,
        'measurements': report,
    }, indent=2) + '\n')
    print('STUDY', json.dumps(report))


if __name__ == '__main__':
    main()
