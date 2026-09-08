#!/usr/bin/env python3
"""Detect large mesh tears in reopened humanoid scenes, beyond IK checks."""
import argparse,hashlib,json,math,sys
from pathlib import Path
import bpy
import numpy as np


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scenes',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--mesh',default='VampireSkin')
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.out.exists():raise ValueError('Output already exists')
    reports=[]
    for path in sorted(args.scenes.glob('*.blend')):
        bpy.ops.wm.open_mainfile(filepath=str(path));scene=bpy.context.scene;obj=bpy.data.objects.get(args.mesh)
        if obj is None:continue
        mesh=obj.data;rest=np.empty(len(mesh.vertices)*3);mesh.vertices.foreach_get('co',rest);rest=rest.reshape(-1,3)
        edges=np.empty(len(mesh.edges)*2,dtype=np.int32);mesh.edges.foreach_get('vertices',edges);edges=edges.reshape(-1,2)
        lengths=np.linalg.norm(rest[edges[:,0]]-rest[edges[:,1]],axis=1);valid=lengths>1e-5
        for phase in [0,.5,1]:
            frame=scene.frame_start+(scene.frame_end-scene.frame_start)*phase;scene.frame_set(math.floor(frame),subframe=frame%1)
            evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());posed=evaluated.to_mesh()
            if len(posed.vertices)!=len(mesh.vertices):raise ValueError('Topology-changing modifier needs a different check')
            coords=np.empty(len(posed.vertices)*3);posed.vertices.foreach_get('co',coords);coords=coords.reshape(-1,3)
            after=np.linalg.norm(coords[edges[:,0]]-coords[edges[:,1]],axis=1);evaluated.to_mesh_clear()
            ratio=after[valid]/lengths[valid];growth=after[valid]-lengths[valid]
            if not np.isfinite(ratio).all():raise ValueError('Nonfinite deformation')
            reports.append({'scene':path.name,'sourceSHA256':hashlib.sha256(path.read_bytes()).hexdigest(),'frame':frame,'maximumEdgeRatio':float(ratio.max()),'edgeRatioP99':float(np.quantile(ratio,.99)),'largeStretchedEdges':int(((ratio>8)&(growth>.08)).sum())})
    if not reports:raise ValueError('No humanoid scenes checked')
    report={'samples':reports,'largeStretchedEdges':sum(r['largeStretchedEdges'] for r in reports),'thresholds':{'minimumEdgeRatio':8,'minimumAbsoluteGrowth':.08},'scope':'Three poses per scene; detects large tears, not all aesthetic or cloth defects'}
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'samples':len(reports),'largeStretchedEdges':report['largeStretchedEdges']}))
    if report['largeStretchedEdges']:raise ValueError('Large mesh tears detected')

if __name__=='__main__':main()
