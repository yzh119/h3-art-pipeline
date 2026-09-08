#!/usr/bin/env python3
"""Render a reviewed bootstrap scene, optionally studying a spectral material.

Creates a separate editable scene. No rig, animation or mod installation implied.
"""
import argparse,json,math,sys
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
import render_portrait

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--spectral',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
 if a.out.exists():raise ValueError('Use a fresh output directory')
 a.out.mkdir(parents=True);bpy.ops.wm.open_mainfile(filepath=str(a.source));scene=bpy.context.scene
 scene.camera.rotation_euler=(math.radians(78),0,math.radians(315));scene.objects['sun'].data.energy=5;scene.objects['fill'].data.energy=1.5
 changed=[]
 if a.spectral:
  for mat in bpy.data.materials:
   if not mat.use_nodes:continue
   tree=mat.node_tree
   for node in list(tree.nodes):
    if node.type!='BSDF_PRINCIPLED':continue
    color=node.inputs['Base Color'];incoming=list(color.links)
    gray=tree.nodes.new('ShaderNodeRGBToBW')
    if incoming:tree.links.new(incoming[0].from_socket,gray.inputs[0])
    else:gray.inputs[0].default_value=color.default_value
    ramp=tree.nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=(.28,.32,.37,1);ramp.color_ramp.elements[1].color=(.90,.95,1,1)
    tree.links.new(gray.outputs[0],ramp.inputs[0]);tree.links.new(ramp.outputs['Color'],color)
    tree.links.new(ramp.outputs['Color'],node.inputs['Emission Color']);node.inputs['Emission Strength'].default_value=.16
    node.inputs['Metallic'].default_value=.12;node.inputs['Roughness'].default_value=.45;changed.append(mat.name)
 scene_path=a.out/'study.blend';bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(scene_path))
 (a.out/'study.json').write_text(json.dumps({'stage':'static bootstrap material study; unrigged, not installed','source':str(a.source),'spectral':a.spectral,'modifiedMaterials':changed,'geometryChanged':False,'wingTransparency':'not yet implemented'},indent=2)+'\n')
 sys.argv=['blender','--','--source',str(scene_path),'--out',str(a.out/'portrait.png')];render_portrait.main()
if __name__=='__main__':main()
