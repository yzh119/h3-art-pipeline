"""Blend linear and volume-preserving armature deformation using a vertex mask.

Run inside Blender. The mesh must end in an unmasked linear Armature modifier;
the named vertex group controls the added volume-preserving result (0..1).
This changes deformation, not bone weights or the rest mesh.
"""


def add_volume_blend(mesh, armature, group_name, *, name="LocalVolumeBlend"):
    if mesh.type != "MESH" or armature.type != "ARMATURE":
        raise ValueError("Expected a mesh and an armature")
    if group_name not in mesh.vertex_groups:
        raise ValueError("The influence vertex group must already exist")
    if not mesh.modifiers:
        raise ValueError("An existing linear Armature modifier is required")
    base = mesh.modifiers[-1]
    if (base.type != "ARMATURE" or base.object != armature
            or base.use_deform_preserve_volume or base.use_multi_modifier
            or base.vertex_group):
        raise ValueError("The last modifier must be an unmasked linear Armature for this rig")
    modifier = mesh.modifiers.new(name, "ARMATURE")
    modifier.object = armature
    modifier.use_vertex_groups = base.use_vertex_groups
    modifier.use_bone_envelopes = base.use_bone_envelopes
    modifier.use_multi_modifier = True
    modifier.use_deform_preserve_volume = True
    modifier.vertex_group = group_name
    return modifier
