"""Export the supplied CC0 pack without modifying its .blend files.
Run: blender -b --python-exit-code 1 -P tools/web3d/build_ambient.py
"""
import bpy, math, json, hashlib
from pathlib import Path
from zipfile import ZipFile
from mathutils import Vector

base = Path(__file__).resolve().parent
archive = Path.home() / 'Downloads/evorium-animals/Animal Pack Vol.2 by @Quaternius.zip'
raw = base / 'raw/animals'
with ZipFile(archive) as z:
    z.extractall(raw)
out = base / 'raw/ambient'
out.mkdir(parents=True, exist_ok=True)
report = {'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'models': {}}
for kind, source, height in [('cat', 'Cat', .40), ('dog', 'Dog', .56), ('fox', 'Wolf', .48)]:
    bpy.ops.wm.open_mainfile(filepath=str(raw / f'Animal Pack Vol.2 by @Quaternius/Blends/{source}.blend'))
    scene = bpy.context.scene
    scene.frame_set(0)
    rig = next(o for o in scene.objects if o.type == 'ARMATURE')
    mesh = next(o for o in scene.objects if o.type == 'MESH')
    # Rest-space world coordinates also account for the wolf mesh's object rotation.
    points = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
    lo, hi = min(v.z for v in points), max(v.z for v in points)
    scale = height / (hi - lo)
    mat = bpy.data.materials.new('Fox orange, white bib, charcoal stockings' if kind == 'fox' else kind+' coat')
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Roughness'].default_value = .95
    colour = mesh.data.color_attributes.new(name='Coat', type='BYTE_COLOR', domain='CORNER')
    for face in mesh.data.polygons:
        p = sum((points[i] for i in face.vertices), Vector()) / len(face.vertices)
        z = (p.z - lo) / (hi - lo)
        if kind == 'fox':
            c = (.64,.16,.025,1)
            if z < .29: c = (.035,.022,.018,1)
            elif p.x > .7 and z < .66: c = (.93,.88,.74,1)
            elif p.x < -4.2: c = (.93,.88,.74,1)
        elif kind == 'cat':
            c = (.055,.065,.075,1) if z > .10 else (.79,.76,.69,1)
        else:
            c = (.27,.15,.065,1) if z > .18 else (.10,.065,.035,1)
        for index in face.loop_indices: colour.data[index].color = c
    vc = mat.node_tree.nodes.new('ShaderNodeVertexColor'); vc.layer_name = 'Coat'
    mat.node_tree.links.new(vc.outputs['Color'], shader.inputs['Base Color'])
    mesh.data.materials.clear();mesh.data.materials.append(mat)
    for p in mesh.data.polygons:p.material_index=0;p.use_smooth=False
    root = bpy.data.objects.new(kind, None);scene.collection.objects.link(root)
    for obj in list(scene.objects):
        if obj != root and obj.parent is None: obj.parent = root
    root.scale = (scale,)*3;root.rotation_euler.z = -math.pi/2
    root.location.z = -lo * scale
    # Export all actions sampled with IK constraints; no retargeting of these animal rigs.
    for t in list(rig.animation_data.nla_tracks):rig.animation_data.nla_tracks.remove(t)
    rig.animation_data.action = bpy.data.actions.get('Idle')
    bpy.ops.export_scene.gltf(filepath=str(out / f'{kind}.glb'),export_format='GLB',
        export_animations=True,export_animation_mode='ACTIONS',export_force_sampling=True,
        export_bake_animation=True,export_anim_single_armature=True,
        export_yup=True,export_cameras=False,export_lights=False)
    report['models'][kind]={'source':source+'.blend','height':height,
        'animations':[a.name for a in bpy.data.actions],'forward':'+Z'}
(out/'inventory.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
