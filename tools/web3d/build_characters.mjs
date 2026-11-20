import {NodeIO,Document} from '@gltf-transform/core';
import {mergeDocuments,prune,dedup,resample,unpartition} from '@gltf-transform/functions';
import fs from 'node:fs/promises';
import path from 'node:path';
const raw='tools/web3d/raw',base=raw+'/characters/Universal Base Characters[Standard]/Base Characters/Godot - UE';
const io=new NodeIO();const output=new Document();let log=[];let boneSets=[];
for(const [sex,file] of [['male','Superhero_Male_FullBody.gltf'],['female','Superhero_Female_FullBody.gltf']]){
 const json=JSON.parse(await fs.readFile(path.join(base,file),'utf8'));
 for(const img of json.images||[]){try{await fs.access(path.join(base,img.uri));}catch{const fixed=img.uri.replace('_png.png','.png');await fs.copyFile(path.join(base,fixed),path.join(base,img.uri));log.push('Repaired missing texture alias: '+img.uri);}}
 const d=await io.read(path.join(base,file));
 const bones=d.getRoot().listSkins()[0].listJoints().map(n=>n.getName());boneSets.push(bones);
 log.push(sex+' bones: '+bones.join(', '),'meshes: '+d.getRoot().listMeshes().map(m=>m.getName()),'materials: '+d.getRoot().listMaterials().map(m=>m.getName()));
 for(const s of d.getRoot().listScenes()) {const group=d.createNode(sex);for(const n of s.listChildren())group.addChild(n);s.addChild(group);s.setName(sex);}
 mergeDocuments(output,d);
}
const library=await io.read(raw+'/characters/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb');
const clips={idle:'Idle_Loop',walk:'Walk_Loop',run:'Jog_Fwd_Loop',jump_start:'Jump_Start',fall:'Jump_Loop',land:'Jump_Land',sit:'Sitting_Idle_Loop',sit_down:'Sitting_Enter',stand_up:'Sitting_Exit',talk:'Idle_Talking_Loop'};
for(const a of library.getRoot().listAnimations()){
 const duration=Math.max(...a.listSamplers().map(s=>s.getInput().getMax([])[0]));log.push(a.getName()+' '+duration.toFixed(3)+'s');
 if(!Object.values(clips).includes(a.getName()))a.dispose();
}
const animBones=new Set(library.getRoot().listNodes().map(n=>n.getName()));
for(let i=0;i<boneSets.length;i++){
 const missing=boneSets[i].filter(n=>!animBones.has(n));log.push('Rig '+i+' missing library bones: '+JSON.stringify(missing));
 if(missing.length)throw Error('Rig mismatch: '+missing);
}
for(const n of library.getRoot().listNodes()){n.setMesh(null);n.setSkin(null);}
log.push('Standard pack contains Superhero bodies, used as CC0 stand-ins. No wave or turn clips in Standard library.');
await output.transform(dedup(),prune(),unpartition());await library.transform(resample(),prune());
await io.write(raw+'/characters.glb',output);await io.write(raw+'/animations.glb',library);
await fs.writeFile(raw+'/characters_inventory.txt',log.join('\n'));await fs.writeFile('evorium/static/world3d/data/clips.json',JSON.stringify(clips,null,2));
console.log(log.slice(-3).join('\n'));
