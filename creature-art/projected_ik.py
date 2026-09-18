"""Choose an IK target's depth while retaining its camera projection.

Transform the camera ray and shoulder into the IK solver's coordinate space
before calling. A ray that misses the reach sphere still requires the caller
to clamp its two-bone solve; this helper never lengthens bones.
"""
from dataclasses import dataclass
import math
from mathutils import Vector


@dataclass
class RayTarget:
    position: Vector
    depth_adjustment: float
    minimum_shoulder_distance: float
    reachable: bool


def choose_depth_on_ray(target, direction, shoulder, maximum_reach):
    """Keep the old depth if possible, otherwise use the nearest feasible depth.

    If the entire ray is out of reach, return its closest point to the shoulder
    with reachable=False. The depth adjustment is measured along the normalized
    input ray, in the same units as the input points.
    """
    target, direction, shoulder = map(Vector, (target, direction, shoulder))
    if any(len(v) != 3 or not all(math.isfinite(x) for x in v)
           for v in (target, direction, shoulder)):
        raise ValueError('Expected finite three-dimensional points and direction')
    if not math.isfinite(maximum_reach) or maximum_reach <= 0:
        raise ValueError('maximum_reach must be finite and positive')
    if direction.length < 1e-12:
        raise ValueError('Camera ray direction must be nonzero')
    direction.normalize()
    centre = (shoulder - target).dot(direction)
    closest = target + direction * centre
    distance = (closest - shoulder).length
    reachable = distance <= maximum_reach
    if reachable:
        half = math.sqrt(max(0, maximum_reach**2 - distance**2))
        depth = max(centre - half, min(centre + half, 0))
    else:
        depth = centre
    return RayTarget(target + direction * depth, depth, distance, reachable)
