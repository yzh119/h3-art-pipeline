"""Run in Blender: -b --python-exit-code 1 --python test_skin_weights.py."""
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skin_weights import replace_vertex_weights

bpy.ops.wm.read_factory_settings(use_empty=True)
data = bpy.data.meshes.new('WeightRegression')
data.from_pydata([(0, 0, 0), (1, 0, 0)], [], [])
obj = bpy.data.objects.new('WeightRegression', data)
bpy.context.scene.collection.objects.link(obj)
for name, value in [('chest', .4), ('left', .2), ('right', .3), ('pelvis', .1)]:
    obj.vertex_groups.new(name=name).add([0, 1], value, 'REPLACE')


def read(index):
    return {obj.vertex_groups[w.group].name: w.weight
            for w in data.vertices[index].groups}


untouched = read(1)
replace_vertex_weights(obj, 0, {'chest': .75, 'pelvis': .25})
assert read(0) == {'chest': .75, 'pelvis': .25}, read(0)
assert read(1) == untouched
replace_vertex_weights(obj, 0, {'new_bone': 4, 'chest': 0})
assert read(0) == {'new_bone': 1}
try:
    replace_vertex_weights(obj, 0, {'new_bone': float('nan')})
except ValueError:
    pass
else:
    raise AssertionError('Invalid weight accepted')
assert read(0) == {'new_bone': 1}
replace_vertex_weights(obj, 0, {})
assert read(0) == {} and read(1) == untouched
print('Weight replacement: no stale memberships; neighboring vertex unchanged')
