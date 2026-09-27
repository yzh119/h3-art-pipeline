"""Helpers for editing Blender vertex weights without stale RNA references."""
import math


def replace_vertex_weights(obj, vertex_index, weights, *, normalize=True):
    """Replace every group membership of one vertex using name -> weight values.

    Copy numeric group indices before removing memberships: VertexGroupElement
    references from list(vertex.groups) become stale as the collection changes.
    An empty mapping clears the vertex. Validation happens before mutation.
    """
    vertex = obj.data.vertices[vertex_index]
    values = {name: float(value) for name, value in weights.items()}
    if any(not name or not isinstance(name, str) for name in values):
        raise ValueError("Weight group names must be nonempty strings")
    if any(not math.isfinite(value) or value < 0 for value in values.values()):
        raise ValueError("Weights must be finite and nonnegative")
    values = {name: value for name, value in values.items() if value > 0}
    total = math.fsum(values.values())
    if normalize and total:
        values = {name: value / total for name, value in values.items()}
    elif any(value > 1 for value in values.values()):
        raise ValueError("Unnormalized Blender weights must not exceed one")
    indices = [membership.group for membership in vertex.groups]
    for index in indices:
        obj.vertex_groups[index].remove([vertex_index])
    for name, value in values.items():
        group = obj.vertex_groups.get(name)
        if group is None:
            group = obj.vertex_groups.new(name=name)
        group.add([vertex_index], value, 'REPLACE')
