"""Bake the ten UAL clips onto MPFB game_engine bones with explicit T/A rest calibration."""
import bpy,json,math
from pathlib import Path
from mathutils import Matrix,Vector
RAW=Path(__file__).resolve().parent/'raw';OUT=RAW/'cast';MAP=json.loads((Path(__file__).resolve().parent/'data/mpfb_to_ual_bones.json').read_text());clips=json.loads((Path(__file__).resolve().parents[2]/'evorium/static/world3d/data/clips.json').read_text())
bpy.ops.wm.open_mainfile(filepath=str(OUT/'dez.blend'));target=bpy.data.objects['EvoriumRig'];bpy.context.scene.render.fps=30
# The reference scene is not rewritten. Remove old actions, then import the original library.
bpy.ops.import_scene.gltf(filepath=str(RAW/'characters/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb'))
source=next(o for o in bpy.data.objects if o.type=='ARMATURE' and o!=target);source.animation_data_create();target.animation_data_create()
for track in source.animation_data.nla_tracks:track.mute=True
source_actions={a.name:a for a in bpy.data.actions}
rest_source={b.name:(source.matrix_world@b.matrix_local).to_quaternion() for b in source.data.bones}
rest_target={b.name:(target.matrix_world@b.matrix_local).to_quaternion() for b in target.data.bones}
calibrated={}
for name,sname in MAP.items():
 sb=source.data.bones[sname];tb=target.data.bones[name]
 # Align anatomical bone directions, while preserving target bone roll. This is the
 # explicit T-pose calibration; names alone do not correct MPFB's A-pose bind mesh.
 if name not in ('Root','pelvis'):
  tv=(target.matrix_world.to_3x3()@(tb.tail_local-tb.head_local)).normalized();sv=(source.matrix_world.to_3x3()@(sb.tail_local-sb.head_local)).normalized();align=tv.rotation_difference(sv);calibrated[name]=align@rest_target[name]
 else:calibrated[name]=rest_target[name]
log={'mapping':MAP,'source_bones':len(source.data.bones),'target_bones':len(target.data.bones),'clips':{}}
scene=bpy.context.scene
scale=target.dimensions.z/source.dimensions.z if source.dimensions.z else 1
for clip in dict.fromkeys(clips.values()):
 action=source_actions[clip];source.animation_data.action=action;source.animation_data.action_slot=action.slots[0]
 result=bpy.data.actions.new('MPFB_'+clip);target.animation_data.action=result
 end=int(round(action.frame_range[1]));scene.frame_start=0;scene.frame_end=end
 for frame in range(end+1):
  scene.frame_set(frame);bpy.context.view_layer.update();desired={}
  for tb in target.data.bones:
   sname=MAP[tb.name];sb=source.pose.bones[sname];global_pose=(source.matrix_world@sb.matrix).to_quaternion()
   desired[tb.name]=global_pose@rest_source[sname].inverted()@calibrated[tb.name]
   parent_rot=desired[tb.parent.name] if tb.parent else target.matrix_world.to_quaternion()
   rest_local=rest_target[tb.parent.name].inverted()@rest_target[tb.name] if tb.parent else target.matrix_world.to_quaternion().inverted()@rest_target[tb.name]
   pb=target.pose.bones[tb.name];pb.rotation_mode='QUATERNION';pb.rotation_quaternion=rest_local.inverted()@parent_rot.inverted()@desired[tb.name];pb.location=(0,0,0)
   if tb.name=='pelvis':
    delta=(source.matrix_world@sb.matrix).translation-(source.matrix_world@source.data.bones[sname].matrix_local).translation
    # Preserve only the pelvis bob/sit displacement, scaled to the reference body.
    pb.location=rest_target[tb.name].inverted()@(delta*scale/target.scale.x)
    pb.keyframe_insert('location',frame=frame)
   pb.keyframe_insert('rotation_quaternion',frame=frame)
 log['clips'][clip]={'frames':end+1,'seconds':end/30};print('RETARGETED',clip,end+1,flush=True)
 # NLA track name is the exported clip name; only the target armature is selected.
 target.animation_data.action=None;track=target.animation_data.nla_tracks.new();track.name=clip;track.strips.new(clip,0,result)
 for tr in target.animation_data.nla_tracks:tr.mute=True
# Export each target NLA track as a named clip.
for tr in target.animation_data.nla_tracks:tr.mute=False
bpy.ops.object.select_all(action='DESELECT');target.select_set(True);bpy.context.view_layer.objects.active=target
scene.frame_start=0;scene.frame_end=max(int(round(a.frame_range[1])) for a in source_actions.values())
bpy.ops.export_scene.gltf(filepath=str(RAW/'animations_mpfb.glb'),export_format='GLB',use_selection=True,use_active_scene=True,export_animations=True,export_animation_mode='NLA_TRACKS',export_force_sampling=True,export_frame_range=False,export_lights=False,export_cameras=False)
(OUT/'retarget_inventory.json').write_text(json.dumps(log,indent=2))
