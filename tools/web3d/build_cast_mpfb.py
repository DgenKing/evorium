"""Scripted MPFB cast. Run: blender -b --addons bl_ext.blender_org.mpfb -P tools/web3d/build_cast_mpfb.py
Source packs and build products live under ignored raw/. No source kit or website writes.
"""
import argparse,json,math,sys,random
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bl_ext.blender_org.mpfb.services.humanservice import HumanService
from bl_ext.blender_org.mpfb.services.targetservice import TargetService
from bl_ext.blender_org.mpfb.services.locationservice import LocationService

# Explicit artistic settings, not random people: edit these and rebuild.
CAST = {
 'dez':dict(name='Dez Whitworth',gender=1,age=54,weight=.72,muscle=.42,height=1.75,proportions=.48,race=(0,0,1),skin='middleage_caucasian_male',hair='short01',hair_color='#9b9990',beard='grinsegold_beard_sigmund_wip',beard_color='#88857e',outfit='male_casualsuit03',top='#22272a',trousers='#303037'),
 'jess':dict(name='Jess Hartley',gender=0,age=34,weight=.37,muscle=.35,height=1.67,proportions=.5,race=(0,0,1),skin='young_caucasian_female',hair='rehmanpolanski_hair_bun_brown',hair_color='#30221c',outfit='female_casualsuit01',top='#292b30',trousers='#27272d'),
 'tommy':dict(name='Tommy Shaw',gender=1,age=67,weight=.43,muscle=.25,height=1.68,proportions=.45,race=(0,0,1),skin='old_caucasian_male',hair='short01',hair_color='#c9c9bf',balding=True,outfit='male_casualsuit03',cardigan=True,top='#354761',trousers='#4c4e52',stoop=.06),
 'raj':dict(name='Raj Patel',gender=1,age=41,weight=.5,muscle=.4,height=1.73,proportions=.5,race=(.1,.7,.2),skin='middleage_asian_male',skin_tint='#bf946f',hair='culturalibre_hair_02',hair_color='#29292b',beard='grinsegold_beard_sigmund_wip',beard_color='#383436',outfit='male_casualsuit03',top='#888779',trousers='#44474b'),
 'chloe':dict(name='Chloe Barlow',gender=0,age=29,weight=.36,muscle=.32,height=1.68,proportions=.5,race=(0,0,1),skin='young_caucasian_female2',hair='toigo_curled_under_bob',hair_color='#98744d',outfit='female_casualsuit01',top='#668367',trousers='#414c59'),
 'simon':dict(name='Simon Ferris',gender=1,age=46,weight=.4,muscle=.45,height=1.84,proportions=.58,race=(0,0,1),skin='middleage_caucasian_male',hair='culturalibre_hair_05',hair_color='#38302c',outfit='male_elegantsuit01',top='#393e43',trousers='#3d444c'),
 'brenda':dict(name='Brenda Ashworth',gender=0,age=71,weight=.7,muscle=.25,height=1.56,proportions=.42,race=(0,0,1),skin='old_caucasian_female',hair='afro01',hair_color='#b7b5aa',outfit='female_casualsuit01',cardigan=True,top='#a18bab',trousers='#565269'),
 'mo':dict(name='Mohammed "Mo" Iqbal',gender=1,age=38,weight=.6,muscle=.55,height=1.79,proportions=.52,race=(.12,.72,.16),skin='young_asian_male',skin_tint='#c29876',hair='culturalibre_hair_02',hair_color='#24252a',beard='grinsegold_beard_sigmund_wip',beard_color='#292729',outfit='male_casualsuit06',cardigan=True,top='#333d50',trousers='#34363b'),
 'player':dict(name='player',gender=1,age=35,weight=.5,muscle=.45,height=1.76,proportions=.5,race=(0,0,1),skin='young_caucasian_male',hair='short04',hair_color='#483b33',outfit='male_casualsuit06',top='#e9dfc9',trousers='#536c7d'),
}
RAW=Path(__file__).resolve().parent/'raw';DATA=Path(LocationService.get_user_data());OUT=RAW/'cast';OUT.mkdir(exist_ok=True)
args=argparse.ArgumentParser();args.add_argument('--only',choices=list(CAST));a=args.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
used=json.loads((OUT/'licenses.json').read_text()) if a.only and (OUT/'licenses.json').exists() else {};inventory=json.loads((OUT/'inventory.json').read_text()) if a.only and (OUT/'inventory.json').exists() else {}
def asset(kind,name):
 folder=DATA/kind/name
 paths=list(folder.glob('*.proxy' if kind=='proxymeshes' else '*.mhclo'))
 if not paths:raise RuntimeError(f'Missing installed MPFB asset {kind}/{name}')
 path=paths[0];text=path.read_text(errors='replace')
 # Every selected pack was independently checked against its official CC0 asset table.
 pack='bodyparts05' if name.startswith('grinsegold') else 'hair01' if name.startswith(('culturalibre','toigo','rehmanpolanski')) else 'makehuman_system_assets'
 used[kind+'/'+name]={'source':f'https://static.makehumancommunity.org/assets/assetpacks/{pack}.html','license':'CC0-1.0','file':str(path.relative_to(DATA))}
 return path

def material(name,path=None,color=None,alpha=False):
 m=bpy.data.materials.new(name);m.use_nodes=True;nodes=m.node_tree.nodes;nodes.clear();out=nodes.new('ShaderNodeOutputMaterial');bs=nodes.new('ShaderNodeBsdfPrincipled');m.node_tree.links.new(bs.outputs['BSDF'],out.inputs['Surface']);bs.inputs['Roughness'].default_value=.85
 if path:
  lines=path.read_text(errors='replace').splitlines();tex=next((line.split(maxsplit=1)[1] for line in lines if line.startswith('diffuseTexture ')),None)
  if tex:
   image_path=(path.parent/tex).resolve()
   if not image_path.is_file():image_path=path.parent/Path(tex).name
   if not image_path.is_file():raise RuntimeError('Missing texture '+str(image_path))
   image=bpy.data.images.load(str(image_path),check_existing=True);node=nodes.new('ShaderNodeTexImage');node.image=image
   if color:
    tint=nodes.new('ShaderNodeMixRGB');tint.blend_type='MULTIPLY';tint.inputs[0].default_value=1;tint.inputs[2].default_value=(*hexcolor(color),1);m.node_tree.links.new(node.outputs['Color'],tint.inputs[1]);m.node_tree.links.new(tint.outputs[0],bs.inputs['Base Color'])
   else:m.node_tree.links.new(node.outputs['Color'],bs.inputs['Base Color'])
   if alpha:m.node_tree.links.new(node.outputs['Alpha'],bs.inputs['Alpha']);m.surface_render_method='DITHERED'
 elif color:bs.inputs['Base Color'].default_value=(*hexcolor(color),1)
 return m

def hexcolor(color):
 # Blender shader constants are linear.
 values=[int(color[i:i+2],16)/255 for i in (1,3,5)]
 return tuple(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in values)

def add(kind,name,h,color=None,alpha=False):
 p=asset(kind,name);obj=HumanService.add_mhclo_asset(str(p),h,asset_type={'proxymeshes':'Proxymeshes','hair':'Hair','eyes':'Eyes','eyebrows':'Eyebrows','eyelashes':'Eyelashes'}.get(kind,'Clothes'),subdiv_levels=0)
 mhmat=list(p.parent.glob('*.mhmat'));
 if not mhmat:
  ref=next((line.split(maxsplit=1)[1] for line in p.read_text().splitlines() if line.startswith('material ')),None)
  if ref:
   mhmat=[(p.parent/ref).resolve()]
   if kind=='eyes':used['eyes/'+mhmat[0].stem]={'source':'https://static.makehumancommunity.org/assets/assetpacks/makehuman_system_assets.html','license':'CC0-1.0','file':str(mhmat[0].relative_to(DATA))}
 obj.data.materials.clear();obj.data.materials.append(material(name,mhmat[0] if mhmat else None,color,alpha));return obj

def delete_faces(obj,predicate):
 bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.delete(bm,geom=[f for f in bm.faces if predicate(f)],context='FACES');bm.to_mesh(obj.data);bm.free()

def build(identifier,c):
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 macro=TargetService.get_default_macro_info_dict();macro.update(gender=c['gender'],age=.5+(c['age']-25)/130,weight=c['weight'],muscle=c['muscle'],height=.5,proportions=c['proportions'],race=dict(zip(('african','asian','caucasian'),c['race'])))
 h=HumanService.create_human(macro_detail_dict=macro);h.name=identifier
 rig=HumanService.add_builtin_rig(h,'game_engine');rig.name='EvoriumRig'
 proxy=add('proxymeshes','male1591' if c['gender'] else 'female1605',h)
 skinpath=next((DATA/'skins'/c['skin']).glob('*.mhmat'));used['skins/'+c['skin']]={'source':'https://static.makehumancommunity.org/assets/assetpacks/makehuman_system_assets.html','license':'CC0-1.0','file':str(skinpath.relative_to(DATA))}
 proxy.data.materials.clear();proxy.data.materials.append(material(identifier+' skin',skinpath,c.get('skin_tint')))
 meshes=[proxy,add('eyes','low-poly',h),add('eyebrows','eyebrow001',h,c['hair_color'],True),add('eyelashes','eyelashes01',h,'#282526',True)]
 hair=add('hair',c['hair'],h,None,True)
 # Hair textures are often black; replace base colour while retaining strand alpha.
 hairmat=hair.data.materials[0];bs=next(n for n in hairmat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
 for link in list(hairmat.node_tree.links):
  if link.to_socket==bs.inputs['Base Color']:hairmat.node_tree.links.remove(link)
 bs.inputs['Base Color'].default_value=(*hexcolor(c['hair_color']),1)
 if c.get('balding'):
  xs=[v.co.x for v in hair.data.vertices];zs=[v.co.z for v in hair.data.vertices];cx=(max(xs)+min(xs))/2;half=(max(xs)-min(xs))/2;high=min(zs)+(max(zs)-min(zs))*.65
  delete_faces(hair,lambda f:abs(f.calc_center_median().x-cx)<half*.7 and f.calc_center_median().z>high)
 if identifier=='brenda':
  # Use the fitted CC0 afro's bounds to build an opaque, low-poly curly perm.
  xs=[v.co.x for v in hair.data.vertices];ys=[v.co.y for v in hair.data.vertices];zs=[v.co.z for v in hair.data.vertices];center=Vector(((min(xs)+max(xs))/2,(min(ys)+max(ys))/2,(min(zs)+max(zs))/2));rx=(max(xs)-min(xs))*.43;ry=(max(ys)-min(ys))*.43;rz=(max(zs)-min(zs))*.4
  bm=bmesh.new();rng=random.Random(71)
  for row in range(6):
   angle=row*.28;count=max(1,int(28*math.sin(angle)))
   for i in range(count):
    theta=i/count*math.tau+row*.35+rng.uniform(-.12,.12);a2=angle+rng.uniform(-.12,.12);point=center+Vector((rx*math.sin(a2)*math.cos(theta),ry*math.sin(a2)*math.sin(theta),rz*.7*math.cos(a2)+rng.uniform(-.012,.012)))
    result=bmesh.ops.create_icosphere(bm,subdivisions=1,radius=rng.uniform(.020,.033));bmesh.ops.scale(bm,verts=result['verts'],vec=(1,rng.uniform(.8,1.2),rng.uniform(.8,1.3)));bmesh.ops.translate(bm,verts=result['verts'],vec=point)
    for face in {f for v in result['verts'] for f in v.link_faces}:face.material_index=rng.randrange(3)
  mesh=bpy.data.meshes.new('Brenda fitted perm');bm.to_mesh(mesh);bm.free();hair.data=mesh
  hair.vertex_groups.clear();group=hair.vertex_groups.new(name='head');group.add(list(range(len(mesh.vertices))),1,'REPLACE');
  for i,color in enumerate(['#8b8b83','#a8a89e','#b9b9af']):hair.data.materials.append(material('Brenda silver curls '+str(i),color=color))
  for face in hair.data.polygons:face.use_smooth=True
 meshes.append(hair)
 if c.get('beard'):
  beard=add('clothes',c['beard'],h,None,True);bm=beard.data.materials[0];bs=next(n for n in bm.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
  for link in list(bm.node_tree.links):
   if link.to_socket==bs.inputs['Base Color']:bm.node_tree.links.remove(link)
  bs.inputs['Base Color'].default_value=(*hexcolor(c['beard_color']),1)
  surface=BVHTree.FromPolygons([v.co for v in proxy.data.vertices],[p.vertices[:] for p in proxy.data.polygons])
  for vertex in beard.data.vertices:
   point,normal,_,_=surface.find_nearest(vertex.co)
   if point is not None:vertex.co=point+(vertex.co-point)*(.08 if identifier=='dez' else .5)+normal*.001
  meshes.append(beard)
 clothes=add('clothes',c['outfit'],h);meshes.append(clothes)
 # Real garment geometry, with per-face material colours; no runtime body/clothing mask.
 clothes.data.materials.clear();clothes.data.materials.append(material(identifier+' top',color=c['top']));clothes.data.materials.append(material(identifier+' trousers',color=c['trousers']))
 zs=[v.co.z for v in proxy.data.vertices];height=max(zs)-min(zs);waist=min(zs)+height*.49
 for f in clothes.data.polygons:f.material_index=0 if f.center.z>waist else 1
 if identifier=='tommy':
  plaid=bpy.data.images.new('Tommy checked shirt',width=256,height=256);pixels=[]
  for y in range(256):
   for x in range(256):
    tone=.32 if x%8<1 or y%8<1 else .66 if (x//4+y//4)%2 else .82;pixels.extend([tone*.9,tone*.94,tone,1])
  plaid.pixels=pixels;mat=clothes.data.materials[0];bs=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=plaid;mat.node_tree.links.new(node.outputs['Color'],bs.inputs['Base Color'])
 if c.get('cardigan'):
  cardigan=add('clothes','male_casualsuit05',h);delete_faces(cardigan,lambda f:f.calc_center_median().z<waist);cardigan.data.materials.clear();cardigan.data.materials.append(material(identifier+' cardigan',color=c['top']));meshes.append(cardigan)
 meshes.append(add('clothes','shoes02',h,'#353234'))
 # Export only fitted game meshes, not helper basemesh. Bake masks before decimation.
 for obj in meshes:
  bpy.context.view_layer.objects.active=obj
  for mod in list(obj.modifiers):
   if mod.type not in ('ARMATURE',):bpy.ops.object.modifier_apply(modifier=mod.name)
  obj.data.update()
 # Normalize overall stature in object transforms; glTF is metres and +Y up.
 feet=min((o.matrix_world@v.co).z for o in meshes for v in o.data.vertices)
 top=max((o.matrix_world@v.co).z for o in meshes for v in o.data.vertices);scale=c['height']/(top-feet)
 rig.scale=(scale,scale,scale);rig.location.z=-feet*scale
 for pb in rig.pose.bones:pb.rotation_mode='QUATERNION'
 bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
 for o in meshes:o.select_set(True)
 bpy.context.view_layer.objects.active=rig
 # Store a canonical build scene for retargeting and diagnostics; never opened in UI.
 bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(identifier+'.blend')))
 bpy.ops.export_scene.gltf(filepath=str(OUT/(identifier+'.glb')),export_format='GLB',use_selection=True,use_active_scene=True,export_animations=False,export_yup=True,export_lights=False,export_cameras=False,export_apply=False)
 inventory[identifier]={'name':c['name'],'height':c['height'],'macro':macro,'bones':{b.name:{'parent':b.parent.name if b.parent else None,'matrix':list(sum((list(row) for row in b.matrix_local),[]))} for b in rig.data.bones},'vertices':sum(len(o.data.vertices) for o in meshes),'assets':list(used)}
 print('CAST_EXPORTED',identifier,inventory[identifier]['vertices'],flush=True)

for identifier,c in CAST.items():
 if not a.only or identifier==a.only:build(identifier,c)
(OUT/'inventory.json').write_text(json.dumps(inventory,indent=2));(OUT/'licenses.json').write_text(json.dumps(used,indent=2))
