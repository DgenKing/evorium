"""Bake Cycles indirect light to a shared secondary UV atlas; AO fallback on failure.
Run: blender -b -P tools/web3d/bake_lighting.py
Never opens or saves the source kit.
"""
import bpy
from pathlib import Path
raw=Path('tools/web3d/raw');out=raw/'lightmaps';out.mkdir(exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(raw/'shuttle_street.glb'))
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name in bpy.context.view_layer.objects]
bpy.ops.object.select_all(action='DESELECT')
for o in meshes:o.select_set(True)
bpy.context.view_layer.objects.active=meshes[0];bpy.ops.object.join();obj=bpy.context.object
uv=obj.data.uv_layers.new(name='LightmapUV');obj.data.uv_layers.active=uv
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(island_margin=.02);bpy.ops.object.mode_set(mode='OBJECT')
image=bpy.data.images.new('StreetIndirect',width=2048,height=2048,alpha=False)
for mat in obj.data.materials:
 if not mat:continue
 mat.use_nodes=True;node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=image;mat.node_tree.nodes.active=node
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=128;scene.cycles.use_denoising=True
scene.world=bpy.data.worlds.new('Overcast');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.6,.68,.8,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.6
for name,pos,color,power in [('Pub',(-5,4,2.5),(1,.65,.35),200),('Shop',(4,4,2.5),(.7,.85,1),160)]:
 light=bpy.data.lights.new(name,'AREA');light.energy=power;light.color=color;light.shape='DISK';light.size=3;o=bpy.data.objects.new(name,light);scene.collection.objects.link(o);o.location=pos
bpy.context.view_layer.objects.active=obj
scene.render.bake.use_pass_direct=False;scene.render.bake.use_pass_indirect=True;scene.render.bake.use_pass_color=False
try:
 bpy.ops.object.bake(type='DIFFUSE');kind='indirect'
except Exception as exc:
 print('Indirect bake failed, AO fallback:',exc);bpy.ops.object.bake(type='AO');kind='ao'
image.filepath_raw=str(out/'day-high.png');image.file_format='PNG';image.save()
image.scale(1024,1024);image.filepath_raw=str(out/'day-low.png');image.save()
# glTF exports both UV sets; bake UV is used by runtime lightMap channel 1.
bpy.ops.export_scene.gltf(filepath=str(raw/'shuttle_street_lit.glb'),export_format='GLB',use_selection=True,use_active_scene=True,export_lights=False,export_animations=False)
(out/'result.txt').write_text(f'{kind}; Cycles CPU, 128 samples; 2048 high / 1024 low; night uses runtime tint.\n')
