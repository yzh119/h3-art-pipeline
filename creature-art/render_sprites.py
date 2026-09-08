#!/usr/bin/env python3
"""Render a rigged model back into Heroes III sprite frames. Runs inside Blender.

    blender -b --python render_sprites.py -- \\
        --model rigged/skeleton.glb --out frames/holding \\
        --canvas 450x400 --ground 267 --height 79 --elevation 30

The engine gives no way to nudge a sprite afterwards: the frame's own canvas and
the position of the creature inside it are the only anchor there is. So the camera
is solved rather than eyeballed — the model's vertices are projected into camera
space and the orthographic scale and shift are computed so the creature lands at
exactly `height` pixels tall with its feet on `ground`.

Three passes per frame, matching what the engine expects back:

    <name>_NN.png           the creature
    <name>_NN-shadow.png    its ground shadow, on a catcher plane
    <name>_NN-overlay.png   flat white silhouette for the hover highlight

Frames come from the model's own animation, sampled evenly across its length.
"""

import argparse
import math
import os
import sys

import bpy
from mathutils import Euler, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import poses  # noqa: E402
from vcmi_anim import GROUP_IDS  # noqa: E402


def poses_group_id(name):
    return GROUP_IDS[name]


def argv_after_ddash():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_model(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".glb" or ext == ".gltf":
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    else:
        raise SystemExit("unsupported model format: %s" % ext)
    return [o for o in bpy.context.scene.objects if o.type == "MESH"]


def world_vertices(meshes, depsgraph):
    """Every vertex in world space, after modifiers and the current pose."""
    points = []
    for obj in meshes:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        matrix = evaluated.matrix_world
        points.extend([matrix @ v.co for v in mesh.vertices])
        evaluated.to_mesh_clear()
    return points


def measure_alpha_bbox(path, threshold=0.004):
    """(left, top, right, bottom) of solidly opaque pixels, read back in Blender.

    Threshold is low on purpose: this has to agree with what everything downstream
    measures, and PIL's getbbox counts any non-zero alpha. Raising it to measure
    only solid coverage made calibration self-consistent and still left the render
    a pixel off, because the two were measuring different extents.
    """
    image = bpy.data.images.load(path)
    try:
        width, height = image.size
        pixels = list(image.pixels)          # RGBA floats, bottom-up
        left, top, right, bottom = width, height, -1, -1
        for y in range(height):
            row = y * width * 4
            for x in range(width):
                if pixels[row + x * 4 + 3] > threshold:
                    flipped = height - 1 - y   # to top-down pixel coordinates
                    if x < left: left = x
                    if x > right: right = x
                    if flipped < top: top = flipped
                    if flipped > bottom: bottom = flipped
        return None if right < 0 else (left, top, right + 1, bottom + 1)
    finally:
        bpy.data.images.remove(image)


def calibrate_camera(camera, canvas, ground, height_px, probe_path, rounds=8):
    """Render, measure, correct, until the creature lands on the anchor.

    An analytic solve looked exact and rendered 51 px where it predicted 79. The
    projection and the render disagreed for reasons that did not survive scrutiny,
    so this measures the render instead -- ground truth, one cheap extra frame, and
    it self-corrects for whatever a future model does.

    Scale and position are corrected in separate phases. Fixing both at once makes
    them fight: rescaling moves the feet, so a position correction computed against
    the old scale overshoots.
    """
    width_px, canvas_h = canvas
    larger = float(max(width_px, canvas_h))
    box = None

    for attempt in range(rounds):
        render_to(probe_path)
        box = measure_alpha_bbox(probe_path)
        if box is None:
            raise SystemExit("nothing rendered -- the camera is not pointing at the model")
        got_h = box[3] - box[1]
        got_feet = box[3]
        got_cx = (box[0] + box[2]) / 2.0

        off_h = got_h - height_px
        off_y = ground - got_feet
        off_x = got_cx - width_px / 2.0
        print("CALIBRATE %d: height %d (%+d), feet %d (%+d), centre %.1f (%+.1f)"
              % (attempt, got_h, off_h, got_feet, -off_y, got_cx, off_x))

        if abs(off_h) <= 1 and abs(off_y) <= 1 and abs(off_x) <= 1:
            return box

        if abs(off_h) > 1:
            # ortho_scale is inversely proportional to rendered size. Nothing else
            # this round -- the position correction is computed after the scale is
            # settled.
            camera.data.ortho_scale *= got_h / float(height_px)
            continue

        # Shift is a fraction of the larger render dimension. Sign established by
        # measurement: increasing shift_y moves the rendered content down.
        camera.data.shift_y += off_y / larger
        camera.data.shift_x += off_x / larger

    print("CALIBRATE gave up after %d rounds" % rounds)
    return box


def build_scene(model, canvas, elevation, azimuth, ground, height_px, samples,
                key_energy=9.0, ambient=0.04):
    reset_scene()
    meshes = import_model(model)
    sanitise_materials(meshes)
    scene = bpy.context.scene

    scene.render.resolution_x, scene.render.resolution_y = canvas
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    # Blender defaults to the AgX view transform, which is built for photographic
    # footage: it rolls off highlights and desaturates hard. Against the original's
    # luminance range of 169 and peak saturation of 1.00, our renders were coming
    # out at 61 and 0.24. Standard passes the render through untouched, which is
    # what a sprite wants.
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"

    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True

    camera_data = bpy.data.cameras.new("cam")
    camera_data.type = "ORTHO"
    camera = bpy.data.objects.new("cam", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera

    # Elevation above the horizon, azimuth around the model. Blender's camera
    # looks down -Z, so an X rotation of 90 degrees puts it level with the ground.
    camera.rotation_euler = (math.radians(90 - elevation), 0.0, math.radians(azimuth))
    distance = 100.0
    direction = Vector((
        math.sin(math.radians(azimuth)) * math.cos(math.radians(elevation)),
        -math.cos(math.radians(azimuth)) * math.cos(math.radians(elevation)),
        math.sin(math.radians(elevation)),
    ))
    camera.location = direction * distance

    # matrix_world is stale until the view layer catches up with the location and
    # rotation just assigned; solving against the stale matrix silently projects
    # into world space instead of camera space.
    bpy.context.view_layer.update()
    # A starting guess; calibration converges from anything that frames the model.
    camera.data.ortho_scale = 4.0

    # Flat, even key light: the render stage supplies its own shadow pass, so the
    # beauty pass should not bake one in.
    # The original has a hard value structure -- lit bone against near-black
    # recesses. A soft even key washes that out at 79 pixels, where three or four
    # value masses are all that survives. So: a strong key, a weak fill for shape,
    # and very little ambient.
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", type="SUN"))
    sun.data.energy = key_energy
    sun.data.angle = math.radians(8)
    sun.rotation_euler = (math.radians(38), 0.0, math.radians(azimuth - 55))
    scene.collection.objects.link(sun)

    fill = bpy.data.objects.new("fill", bpy.data.lights.new("fill", type="SUN"))
    fill.data.energy = key_energy * 0.10
    fill.rotation_euler = (math.radians(70), 0.0, math.radians(azimuth + 120))
    scene.collection.objects.link(fill)

    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[1].default_value = ambient
    scene.world = world

    return meshes, camera, sun


def find_armature():
    for obj in bpy.context.scene.objects:
        if obj.type == "ARMATURE":
            return obj
    return None


def apply_yaw(armature, degrees, rest):
    """Rotate the whole model about the world vertical.

    Turning a creature is not a bone rotation: the hips' own axes are not the
    world's, so yawing them tips it over rather than turning it.
    """
    armature.rotation_mode = "XYZ"
    armature.rotation_euler = (rest[0], rest[1], rest[2] + math.radians(degrees))


def apply_pose(armature, pose):
    """Set every bone's local rotation from a {bone: (x, y, z) degrees} dict."""
    for bone in armature.pose.bones:
        bone.rotation_mode = "XYZ"
        degrees = pose.get(bone.name)
        bone.rotation_euler = Euler(
            tuple(math.radians(v) for v in degrees) if degrees else (0.0, 0.0, 0.0), "XYZ")
    bpy.context.view_layer.update()


def render_to(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def frames_from_original(lod_path, def_name, group_id):
    """How many frames the creature's own .def uses for this group.

    poses.py carries the skeleton's frame counts, and inheriting them for every
    creature silently changes the animation: the zombie's death is nine frames in
    the original and was being rendered as six. The engine allows a different
    count -- the JSON replaces a group wholesale -- but it should be a decision,
    not a leftover.
    """
    from def_extract import DefFile, extract, read_lod

    blob, entries = read_lod(lod_path)
    name = def_name if def_name.upper().endswith(".DEF") else def_name + ".DEF"
    parsed = DefFile(extract(blob, entries, name))
    return len(parsed.groups.get(group_id, []))

def sanitise_materials(meshes):
    """Undo what the glTF import leaves on a Meshy material.

    Meshy's export wires the base colour texture into Emission as well, at full
    strength, and sets Metallic to 1. The result glows: turn every light off and
    the model still renders at mid-grey, because it is lighting itself. Measured
    against the original that showed up as a luminance floor of 112 where the
    original reaches 24, and killing the fill and the ambient changed nothing.

    Metallic 1 also removes the diffuse response, so what shading survives comes
    from a specular lobe rather than form.
    """
    seen, fixed = set(), 0
    for obj in meshes:
        for material in obj.data.materials:
            if material is None or material.name in seen or not material.use_nodes:
                continue
            seen.add(material.name)
            for node in material.node_tree.nodes:
                if node.type != "BSDF_PRINCIPLED":
                    continue
                for link in list(material.node_tree.links):
                    if link.to_node is node and link.to_socket.name.startswith("Emission"):
                        material.node_tree.links.remove(link)
                if "Emission Strength" in node.inputs:
                    node.inputs["Emission Strength"].default_value = 0.0
                if "Metallic" in node.inputs and not node.inputs["Metallic"].is_linked:
                    node.inputs["Metallic"].default_value = 0.0
                if "Roughness" in node.inputs and not node.inputs["Roughness"].is_linked:
                    node.inputs["Roughness"].default_value = 0.65
                fixed += 1
    if fixed:
        print("MATERIALS un-emissive: %d" % fixed)
    return fixed

def connected_components(mesh):
    """Union-find over edges. A skeleton mesh is hundreds of separate bones."""
    parent = list(range(len(mesh.vertices)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for edge in mesh.edges:
        a, b = find(edge.vertices[0]), find(edge.vertices[1])
        if a != b:
            parent[a] = b

    groups = {}
    for index in range(len(mesh.vertices)):
        groups.setdefault(find(index), []).append(index)
    return list(groups.values())


def bone_hops(armature):
    """Hop distance between every pair of bones, over the parent/child graph."""
    import collections
    adjacent = collections.defaultdict(set)
    for bone in armature.pose.bones:
        if bone.parent:
            adjacent[bone.name].add(bone.parent.name)
            adjacent[bone.parent.name].add(bone.name)

    distance = {}
    for source in adjacent:
        seen, queue = {source: 0}, [source]
        while queue:
            node = queue.pop(0)
            for peer in adjacent[node]:
                if peer not in seen:
                    seen[peer] = seen[node] + 1
                    queue.append(peer)
        distance[source] = seen
    return distance


def rebind_weapon(meshes, armature, min_hops=5):
    """Bind held props to the hand bone.

    Meshy's auto-rig weights the whole model in one pass, with no notion of what
    is body and what is held. The skeleton's sword came out split between
    LeftHand (35%) and LeftFoot (43%): the grip follows the fist, the tip follows
    the toes, and the blade stretches between them like a walking stick.

    Finding it geometrically does not work. An earlier version took the component
    the hand grips that reaches furthest, and picked the humerus -- the arm bones
    are longer than the visible part of the blade and start closer to the joint.
    Distance-to-nearest-bone does not work either; ribs bow further from the spine
    than the blade does from the leg.

    The weights themselves are the signal. Every real body part is influenced by
    bones that are neighbours in the skeleton -- a femur by hip and knee, one hop
    apart, a rib by two spine joints, three. Only rigid geometry held across the
    body picks up two bones from different limb chains. On the skeleton the split
    is exactly ten hops for all five sword components and at most three for the
    other 173.
    """
    hops = bone_hops(armature)
    moved, held = 0, None
    for obj in meshes:
        names = {g.index: g.name for g in obj.vertex_groups}
        targets = {}
        for component in connected_components(obj.data):
            if len(component) < 40:
                continue
            weight = {}
            for index in component:
                for entry in obj.data.vertices[index].groups:
                    name = names[entry.group]
                    weight[name] = weight.get(name, 0.0) + entry.weight
            ranked = sorted(weight, key=weight.get, reverse=True)[:2]
            if len(ranked) < 2 or hops.get(ranked[0], {}).get(ranked[1], 0) < min_hops:
                continue
            hand = next((n for n in ranked if "hand" in n.lower()), None)
            if hand is None:
                print("REBIND skipped %d vertices spanning %s -- no hand among them"
                      % (len(component), " and ".join(ranked)))
                continue
            targets.setdefault(hand, []).extend(component)

        for hand, indices in sorted(targets.items()):
            group = obj.vertex_groups.get(hand) or obj.vertex_groups.new(name=hand)
            others = [g for g in obj.vertex_groups if g.name != hand]
            for index in indices:
                for other in others:
                    try:
                        other.remove([index])
                    except RuntimeError:
                        pass
                group.add([index], 1.0, "REPLACE")
            moved += len(indices)
            held = hand
            print("REBIND %d vertices onto %s" % (len(indices), hand))

    if not moved:
        print("REBIND found nothing to move -- the prop is already bound to one bone")
    return held


def clamp_alpha(path, threshold=0.06):
    """Zero out near-transparent pixels.

    The shadow catcher leaves a faint scatter across the whole frame -- sampling
    noise the denoiser turns into a few thousandths of alpha. Invisible, but it
    stretches the layer's bounding box to the full canvas, and everything
    downstream measures bounding boxes.
    """
    image = bpy.data.images.load(path)
    try:
        pixels = [0.0] * (len(image.pixels))
        image.pixels.foreach_get(pixels)
        for index in range(3, len(pixels), 4):
            if pixels[index] < threshold:
                pixels[index] = 0.0
        image.pixels.foreach_set(pixels)
        image.filepath_raw = path
        image.file_format = "PNG"
        image.save()
    finally:
        bpy.data.images.remove(image)

def make_shadow_catcher(meshes, camera):
    """A ground plane that catches the shadow and renders nothing else.

    Cycles' shadow catcher writes the shadow into alpha on a transparent film, so
    the pass comes out as exactly the layer the engine wants: black where the
    creature occludes the light, transparent everywhere else.
    """
    lowest = min((obj.matrix_world @ v.co).z
                 for obj in meshes for v in obj.data.vertices)
    bpy.ops.mesh.primitive_plane_add(size=200.0, location=(0.0, 0.0, lowest))
    plane = bpy.context.object
    plane.is_shadow_catcher = True
    return plane


def set_overlay_materials(meshes):
    """Flat white emission on everything: the hover-highlight silhouette.

    Returns what to restore, so the beauty pass can be rendered afterwards.
    """
    white = bpy.data.materials.new("overlay_white")
    white.use_nodes = True
    tree = white.node_tree
    tree.nodes.clear()
    emission = tree.nodes.new("ShaderNodeEmission")
    emission.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
    emission.inputs[1].default_value = 1.0
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    tree.links.new(emission.outputs[0], output.inputs[0])

    saved = []
    for obj in meshes:
        saved.append((obj, list(obj.data.materials)))
        obj.data.materials.clear()
        obj.data.materials.append(white)
    return saved


def restore_materials(saved):
    for obj, materials in saved:
        obj.data.materials.clear()
        for material in materials:
            obj.data.materials.append(material)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--out", required=True, help="output directory")
    parser.add_argument("--name", default="", help="frame name prefix (default: the group)")
    parser.add_argument("--group", choices=sorted(poses.GROUPS),
                        help="which Heroes III animation group to render")
    parser.add_argument("--canvas", default="450x400")
    parser.add_argument("--ground", type=int, default=267)
    parser.add_argument("--height", type=int, default=79, help="creature height in pixels")
    parser.add_argument("--elevation", type=float, default=30.0)
    # Heroes III's creatures are three-quarter views facing right, not head-on
    # portraits. Rendering at 0 put the camera in front of the creature, which
    # foreshortened every attack -- the sword swung towards the lens and barely
    # moved on screen. Negative azimuth turns the model to face right.
    parser.add_argument("--azimuth", type=float, default=-40.0)
    parser.add_argument("--frames", type=int, default=0,
                        help="override the group's frame count")
    parser.add_argument("--samples", type=int, default=48)
    parser.add_argument("--creature", help="which per-creature pose profile to use "
                                           "(defaults to --def)")
    parser.add_argument("--lod", help="archive to read the original frame counts from")
    parser.add_argument("--def", dest="definition", help="the creature's def, e.g. CZOMBI.DEF")
    parser.add_argument("--rebind-weapon", action="store_true",
                        help="move weapon geometry onto the hand bone before posing")
    parser.add_argument("--key-energy", type=float, default=9.0)
    parser.add_argument("--ambient", type=float, default=0.04)
    parser.add_argument("--body-only", action="store_true",
                        help="skip the shadow and overlay passes")
    parser.add_argument("--scale", type=int, default=1, help="render at N times 1x")
    args = parser.parse_args(argv_after_ddash())

    width, height = (int(v) for v in args.canvas.lower().split("x"))
    canvas = (width * args.scale, height * args.scale)
    ground = args.ground * args.scale
    creature_px = args.height * args.scale

    meshes, camera, _ = build_scene(
        args.model, canvas, args.elevation, args.azimuth, ground, creature_px, args.samples,
        args.key_energy, args.ambient)

    os.makedirs(args.out, exist_ok=True)
    scene = bpy.context.scene

    armature = find_armature()
    mirror = False
    if armature is not None and args.rebind_weapon:
        # Which hand holds the weapon decides which arm the attacks swing. The
        # skeleton is left-handed; the groups are written right-handed.
        mirror = rebind_weapon(meshes, armature) == "LeftHand"
        if mirror:
            print("REBIND mirroring the pose for a left-handed creature")

    # Calibrate on the idle, not on the group being rendered.
    #
    # The rig arrives in an A-pose and the combat stance is hunched, so calibrating
    # before posing put the creature 2 px too tall and 2 px too low. But
    # calibrating on each group's own first frame is wrong in a subtler way: it
    # forces every group to start at exactly --height, which erases the height
    # differences between groups. The original walks at 71-76 px and guards at
    # 82-109 against an 80 px idle -- it crouches to move and reaches up to parry,
    # and rescaling each group to 79 flattens both.
    rest_yaw = tuple(armature.rotation_euler) if armature is not None else (0.0, 0.0, 0.0)
    if armature is not None:
        apply_pose(armature, poses.pose_at(
            "HOLDING", 0.0, args.creature or args.definition, mirror))

    # Calibrate at the sample count the frames will use. A cheaper probe renders a
    # narrower antialiased edge than the final frames, so the bbox comes out a
    # pixel small and every frame lands a pixel low. One extra frame out of
    # sixty-eight is a better trade than a systematic offset.
    calibrate_camera(camera, canvas, ground, creature_px,
                     os.path.join(args.out, "_calibration.png"))

    if args.group:
        if armature is None:
            raise SystemExit("--group needs a rigged model; no armature found")
        spec = poses.GROUPS[args.group]
        count = args.frames
        if not count and args.lod and args.definition:
            count = frames_from_original(args.lod, args.definition, poses_group_id(args.group))
            if count:
                print("FRAMES %s: %d from the original" % (args.group, count))
        count = count or spec["frames"]
        name = args.name or args.group.lower()
        lights = [o for o in scene.objects if o.type == "LIGHT"]
        for index in range(count):
            # A loop samples [0, 1) so the last frame does not repeat the first;
            # a one-shot samples [0, 1] so it reaches its final pose.
            t = index / float(count) if spec.get("loop") else (
                index / float(count - 1) if count > 1 else 0.0)
            apply_pose(armature, poses.pose_at(args.group, t, args.creature or args.definition, mirror))
            apply_yaw(armature, poses.yaw_at(args.group, t), rest_yaw)
            stem = os.path.join(args.out, "%s_%02d" % (name, index))
            render_to(stem + ".png")

            if not args.body_only:
                # Shadow: the catcher plane only, creature hidden from camera.
                plane = make_shadow_catcher(meshes, camera)
                for obj in meshes:
                    obj.visible_camera = False
                render_to(stem + "-shadow.png")
                clamp_alpha(stem + "-shadow.png")
                for obj in meshes:
                    obj.visible_camera = True
                bpy.data.objects.remove(plane, do_unlink=True)

                # Overlay: flat white, no lighting, no shadow.
                saved = set_overlay_materials(meshes)
                for light in lights:
                    light.hide_render = True
                render_to(stem + "-overlay.png")
                for light in lights:
                    light.hide_render = False
                restore_materials(saved)
    else:
        count = 1
        render_to(os.path.join(args.out, "%s_00.png" % (args.name or "frame")))

    probe = os.path.join(args.out, "_calibration.png")
    if os.path.exists(probe):
        os.remove(probe)

    print("RENDERED %d frame(s) at %dx%d, ground %d, creature %d px"
          % (count, canvas[0], canvas[1], ground, creature_px))


if __name__ == "__main__":
    main()
