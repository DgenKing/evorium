"""Read-only Blender kit export. Run with -- --out tools/web3d/raw."""
import bpy, json, math, argparse, sys
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
args=argparse.ArgumentParser();args.add_argument('--out',default='tools/web3d/raw');a=args.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
s=next(s for s in bpy.data.scenes if s.name.startswith('01 Street'));bpy.context.window.scene=s
log=[f'Scene: {s.name}']
collision=[];visible=[]
for c in s.collection.children_recursive:
 log.append(f'COLLECTION {c.name}: {len(c.objects)} hidden={c.hide_viewport} render_hidden={c.hide_render}')
 for o in c.objects:
  log.append(f'  {o.name} {o.type}')
  if o.type=='MESH':
   if 'Collision' in c.name:collision.append(o)
   elif 'Cast' not in c.name and not o.name.startswith('SKM_') and o.find_armature() is None:visible.append(o)
# Make hulls selectable (in memory only).
for c in s.collection.children_recursive:c.hide_viewport=False
for layer in s.view_layers:
 def show(l):
  l.exclude=False;l.hide_viewport=False
  for ch in l.children:show(ch)
 show(layer.layer_collection)
for o in collision:o.hide_set(False);o.hide_viewport=False
# glTF does not export Blender FONT objects directly. Evaluate signage into meshes.
for c in s.collection.children_recursive:
 if 'Cast' in c.name:continue
 for o in list(c.objects):
  if o.type=='FONT':
   o.data.resolution_u=2;o.data.bevel_resolution=0
   evaluated=o.evaluated_get(bpy.context.evaluated_depsgraph_get())
   mesh=bpy.data.meshes.new_from_object(evaluated)
   text=bpy.data.objects.new('SIGN | '+o.name,mesh);s.collection.objects.link(text);text.matrix_world=o.matrix_world.copy();visible.append(text)
verts=[];faces=[]
for o in collision:
 off=len(verts);verts.extend(o.matrix_world@v.co for v in o.data.vertices);faces.extend(tuple(off+i for i in p.vertices) for p in o.data.polygons)
bvh=BVHTree.FromPolygons(verts,faces)
def clear(p,q):
 d=Vector(q)-Vector(p);hit=bvh.ray_cast(Vector(p),d.normalized(),d.length)
 return hit[0] is None
way={}
truth=json.loads((Path(bpy.data.filepath).parent/'unreal/waypoints.json').read_text())
for o in bpy.data.collections['Street | Gameplay waypoints'].objects:
 p=o.matrix_world.translation
 expected=Vector(truth[o.name]['position_m_blender']);delta=(p-expected).length
 if delta>.05:raise RuntimeError(f'Waypoint mismatch {o.name}: {delta}')
 floor=bvh.ray_cast(p+Vector((0,0,2)),Vector((0,0,-1)),5)
 log.append(f'WAYPOINT {o.name}: crosscheck={delta:.5f}m floor={floor[0]}')
 way[o.name]={'position':[p.x,p.z,-p.y],'yaw':math.radians(truth[o.name]['facing_deg_from_minus_y'])}
for name in ('PUB_ENTRY','NEWS_ENTRY'):
 p=Vector(truth[name]['position_m_blender']);p.z=1
 ok=clear(p+Vector((0,-1,0)),p+Vector((0,1,0)))
 log.append(f'DOOR {name}: open={ok}')
 if not ok:raise RuntimeError(f'Door blocked {name}')
# Dense collision-verified walking graph: avoids the bar, stock shelves and seats.
nodes={n:v['position'] for n,v in way.items()}
nodes.update(STREET_LEFT=[-12,.06,1.5],STREET_RIGHT=[11,.06,1.5],PUB_OUT=[-4.62,.06,.85],PUB_IN=[-4.62,.06,-.9],NEWS_OUT=[5.92,.06,.85],NEWS_IN=[5.92,.06,-.9],UPSTAIRS=[-6,.06,-8.9])
for x in range(-23,21):
 for z in range(-18,6):
  px=x*.55;pz=z*.55
  if (px<.2 and px>-8.5 and pz<0) or (px>1 and px<7.7 and pz<0) or pz>=.55:
   nodes[f'g{x}_{z}']=[px,.06,pz]
def bpos(p):return Vector((p[0],-p[2],1.0))
edges=[]
items=list(nodes.items())
for i,(n,p) in enumerate(items):
 for m,q in items[i+1:]:
  d=math.dist(p,q)
  if d>1.3:continue
  # Three parallel waist rays give a 0.7m walking corridor.
  direction=bpos(q)-bpos(p)
  if direction.length<.01:continue
  side=Vector((-direction.y,direction.x,0)).normalized()*.36
  if all(clear(bpos(p)+side*k,bpos(q)+side*k) for k in (-1,0,1)):edges.append([n,m])
log.append(f'GRAPH {len(nodes)} nodes, {len(edges)} edges, all edges verified with 3 waist rays')
(out/'waypoints.json').write_text(json.dumps(way,indent=2));(out/'routes.json').write_text(json.dumps({'nodes':nodes,'edges':edges},separators=(',',':')))
def select(objects):
 bpy.ops.object.select_all(action='DESELECT')
 for o in objects:o.hide_set(False);o.select_set(True)
 bpy.context.view_layer.objects.active=objects[0]
def export(objects,name,materials=True):
 select(objects)
 bpy.ops.export_scene.gltf(filepath=str(out/name),export_format='GLB',use_selection=True,use_active_scene=True,export_apply=True,export_yup=True,export_lights=False,export_cameras=False,export_materials='EXPORT' if materials else 'NONE',export_animations=False)
export(collision,'collision.glb',False)
# Merge by material and location class; preserve signs, glass and interior groups.
select(visible)
for o in list(visible):
 if o.type=='FONT':continue
# glTF-transform joins compatible primitives after export; preserve source names here.
export(list(dict.fromkeys(visible)),'shuttle_street.glb')
(out/'blend_inventory.txt').write_text('\n'.join(log))
print('\n'.join(log[-19:]))
