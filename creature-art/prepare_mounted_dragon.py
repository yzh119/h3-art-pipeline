"""Weld positional seams and reduce reviewed non-humanoid bootstraps for rigging."""
import bpy,bmesh,sys,json,hashlib
from pathlib import Path
p=Path(sys.argv[sys.argv.index('--')+1]);out=Path(sys.argv[sys.argv.index('--')+2]);assert not out.exists();out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=str(p));reports=[]
for o in [o for o in bpy.context.scene.objects if o.type=='MESH']:
 bpy.context.view_layer.objects.active=o;o.select_set(True);before=(len(o.data.vertices),len(o.data.polygons))
 bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00003);bm.to_mesh(o.data);bm.free()
 welded=len(o.data.vertices);mod=o.modifiers.new('Animation surface reduction','DECIMATE');mod.ratio=min(1,110000/len(o.data.polygons));bpy.ops.object.modifier_apply(modifier=mod.name)
 for poly in o.data.polygons:poly.use_smooth=True
 reports.append(dict(name=o.name,before=before,weldedVertices=welded,after=[len(o.data.vertices),len(o.data.polygons)]));o.select_set(False)
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(out/'prepared.blend'));(out/'audit.json').write_text(json.dumps({'sourceSHA256':hashlib.sha256(p.read_bytes()).hexdigest(),'objects':reports},indent=2)+'\n')
