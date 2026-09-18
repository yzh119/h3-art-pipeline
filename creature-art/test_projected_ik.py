"""Asset-free Blender regression for projected IK target depth selection."""
import math
from pathlib import Path
import sys
from mathutils import Vector
sys.path.insert(0, str(Path(__file__).resolve().parent))
from projected_ik import choose_depth_on_ray

p = choose_depth_on_ray((1, 0, .2), (0, 0, 1), (0, 0, 0), 2)
assert p.reachable and p.depth_adjustment == 0
p = choose_depth_on_ray((1, 0, 5), (0, 0, 4), (0, 0, 0), 2)
assert p.reachable and abs(p.position.length - 2) < 1e-6
assert abs(p.position.z - math.sqrt(3)) < 1e-6
assert p.position.x == 1 and p.position.y == 0
p = choose_depth_on_ray((3, 0, 5), (0, 0, 1), (0, 0, 0), 2)
assert not p.reachable and (p.position - Vector((3, 0, 0))).length < 1e-6
for direction, reach in [((0, 0, 0), 2), ((0, 0, 1), 0), ((0, 0, 1), float('nan'))]:
    try:
        choose_depth_on_ray((1, 0, 5), direction, (0, 0, 0), reach)
    except ValueError:
        pass
    else:
        raise AssertionError('Invalid input was accepted')
print('PASS: unchanged depth, sphere intersection, unreachable ray, and invalid inputs')
