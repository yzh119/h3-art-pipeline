#!/usr/bin/env python3
"""Transfer a related humanoid's rig to a detailed replacement mesh locally.

Fits height/ground, simplifies with UVs retained, and interpolates nearby donor
weights. This is a starting point requiring pose inspection, not automatic approval.
"""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy
from mathutils import Vector,Matrix,kdtree
sys.path.insert(0,str(Path(__file__).resolve().parent))
import render_sprites as render


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',type=Path,required=True);p.add_argument('--donor',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--faces',type=int,default=160000)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.out.exists():raise ValueError('Use a new output directory')
    args.out.mkdir(parents=True);render.reset_scene()
    old=max(render.import_model(str(args.donor)),key=lambda o:len(o.data.vertices));arm=render.find_armature()
    oldcoords=[old.matrix_world@v.co for v in old.data.vertices];tree=kdtree.KDTree(len(oldcoords))
    for i,v in enumerate(oldcoords):tree.insert(v,i)
    tree.balance();oldnames=[g.name for g in old.vertex_groups];weights=[[(g.group,g.weight) for g in v.groups] for v in old.data.vertices]
    imported=set(bpy.context.scene.objects);render.import_model(str(args.model));new=max([o for o in bpy.context.scene.objects if o not in imported and o.type=='MESH'],key=lambda o:len(o.data.vertices))
    before=len(new.data.polygons)
    bpy.ops.object.select_all(action='DESELECT');new.select_set(True);bpy.context.view_layer.objects.active=new
    if before>args.faces:
        mod=new.modifiers.new('Local UV-preserving simplification','DECIMATE');mod.ratio=args.faces/before;mod.use_collapse_triangulate=True;bpy.ops.object.modifier_apply(modifier=mod.name)
    coords=[new.matrix_world@v.co for v in new.data.vertices]
    def bounds(cs):return Vector([min(v[i] for v in cs) for i in range(3)]),Vector([max(v[i] for v in cs) for i in range(3)])
    lo,hi=bounds(coords);oldlo,oldhi=bounds(oldcoords);scale=(oldhi.z-oldlo.z)/(hi.z-lo.z)
    center=Vector(((lo.x+hi.x)/2,(lo.y+hi.y)/2,lo.z));target=Vector(((oldlo.x+oldhi.x)/2,(oldlo.y+oldhi.y)/2,oldlo.z))
    new.matrix_world=Matrix.Translation(target)@Matrix.Scale(scale,4)@Matrix.Translation(-center)@new.matrix_world
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    for name in oldnames:new.vertex_groups.new(name=name)
    distances=[]
    for v in new.data.vertices:
        neighbors=tree.find_n(v.co,3);distances.append(neighbors[0][2]);mix={};total=sum(1/max(d,1e-5)**2 for _,_,d in neighbors)
        for _,i,d in neighbors:
            factor=(1/max(d,1e-5)**2)/total
            for group,w in weights[i]:mix[group]=mix.get(group,0)+w*factor
        norm=sum(mix.values())
        if norm<=0:raise ValueError('Unweighted donor region')
        for g,w in mix.items():
            if w>1e-6:new.vertex_groups[g].add([v.index],w/norm,'REPLACE')
    new.modifiers.new('Transferred skin','ARMATURE').object=arm
    for o in list(imported):
        if o.type=='MESH':bpy.data.objects.remove(o,do_unlink=True)
    for o in bpy.context.scene.objects:o.animation_data_clear()
    bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(args.out/'transferred.blend'))
    bpy.ops.export_scene.gltf(filepath=str(args.out/'rigged.glb'),export_format='GLB',export_animations=False)
    distances.sort();report={'modelSHA256':hashlib.sha256(args.model.read_bytes()).hexdigest(),'donorSHA256':hashlib.sha256(args.donor.read_bytes()).hexdigest(),'facesBefore':before,'facesAfter':len(new.data.polygons),'vertices':len(new.data.vertices),'scale':scale,'nearestDistanceP95':distances[int(.95*len(distances))],'nearestDistanceMax':max(distances),'stage':'transferred weights; requires pose inspection'}
    (args.out/'audit.json').write_text(json.dumps(report,indent=2)+'\n');(args.out/'transfer_rig.py').write_bytes(Path(__file__).read_bytes())

if __name__=='__main__':main()
