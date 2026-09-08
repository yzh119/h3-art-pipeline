"""Refined rigid limb surfaces for the skeleton's animation pass."""

import math

import bpy
from mathutils import Vector

import skeleton_study as study


def shaft(geometry, a, b, radius, bow=(0, 0, 0)):
    a, b, bow = Vector(a), Vector(b), Vector(bow)
    axis = (b - a).normalized()
    u = axis.orthogonal().normalized()
    v = axis.cross(u)
    offset = len(geometry.vertices)
    rings, sides = 13, 16
    for row in range(rings):
        t = row / (rings - 1)
        # Rounded ends and a slight asymmetric shaft taper, without the six-ring
        # angular knuckles used by the first pose study.
        width = .70 + .34 * math.exp(-((t-.12)/.16)**2) + .40 * math.exp(-((t-.90)/.14)**2)
        center = a.lerp(b, t) + bow * math.sin(math.pi*t)
        for col in range(sides):
            angle = math.tau*col/sides
            geometry.vertices.append(center + radius*width*(
                u*math.cos(angle) + v*math.sin(angle)*.82))
    geometry.faces.append(tuple(offset+i for i in reversed(range(sides))))
    for row in range(rings-1):
        for col in range(sides):
            nxt = (col+1) % sides
            geometry.faces.append((offset+row*sides+col, offset+row*sides+nxt,
                                   offset+(row+1)*sides+nxt, offset+(row+1)*sides+col))
    geometry.faces.append(tuple(offset+(rings-1)*sides+i for i in range(sides)))


def bone_material():
    mat = study.material('LimbBone', (.48, .45, .36), .78)
    tree = mat.node_tree
    shader = tree.nodes.get('Principled BSDF')
    coord = tree.nodes.new('ShaderNodeAttribute')
    coord.attribute_name = 'rest_position'
    noise = tree.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 42
    noise.inputs['Detail'].default_value = 2
    tree.links.new(coord.outputs['Vector'], noise.inputs['Vector'])
    ramp = tree.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (.32, .30, .24, 1)
    ramp.color_ramp.elements[1].color = (.55, .52, .42, 1)
    tree.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    tree.links.new(ramp.outputs['Color'], shader.inputs['Base Color'])
    bump = tree.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = .12
    bump.inputs['Distance'].default_value = .003
    tree.links.new(noise.outputs['Fac'], bump.inputs['Height'])
    tree.links.new(bump.outputs['Normal'], shader.inputs['Normal'])
    return mat


def refine(arm):
    material = bone_material()
    for side, sign in [('Left', 1), ('Right', -1)]:
        for part in ['Arm', 'ForeArm', 'UpLeg', 'Leg']:
            name = side + part
            old = bpy.data.objects.get(name + 'Geometry')
            if old:
                bpy.data.objects.remove(old, do_unlink=True)
            bone = arm.data.bones[name]
            a, b = bone.head_local, bone.tail_local
            g = study.Geometry()
            if part == 'UpLeg':
                start = a.lerp(b, .10) + Vector((sign*.018, 0, 0))
                g.joint(a, (.032, .030, .033))
                shaft(g, a, start, .026)
                shaft(g, start, a.lerp(b, .96), .027, (sign*.006, -.012, 0))
                for offset in [-.015, .015]:
                    g.joint(b+Vector((offset, 0, .006)), (.023, .024, .025))
                g.joint(b+Vector((0, -.023, .010)), (.023, .012, .023))
            elif part == 'Arm':
                g.joint(a, (.025, .027, .028))
                shaft(g, a.lerp(b, .05), a.lerp(b, .96), .021, (0, -.006, 0))
                for offset in [-.010, .010]:
                    g.joint(b+Vector((offset, 0, 0)), (.016, .018, .016))
            else:
                leg = part == 'Leg'
                offset = Vector((sign*(.017 if leg else .012), 0, 0))
                radius = .020 if leg else .013
                shaft(g, a+offset, b+offset*.55, radius, (0, -.006, 0))
                shaft(g, a-offset, b-offset*.55, radius*.64, (sign*.004, .004, 0))
                for endpoint in [a, b]:
                    g.joint(endpoint, (radius*1.2, radius, radius*.8))
            study.rigid_geometry(g, name+'Geometry', arm, name, material)

    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH' or obj.name == 'Body' or not obj.vertex_groups:
            continue
        obj.data.materials.clear()
        obj.data.materials.append(material)
        # A fixed mesh attribute anchors noise to the undeformed surface, so it
        # cannot crawl over a limb when the armature moves through world space.
        attribute = obj.data.attributes.new('rest_position', 'FLOAT_VECTOR', 'POINT')
        attribute.data.foreach_set('vector', [n for vertex in obj.data.vertices for n in vertex.co])
