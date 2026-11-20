import {NodeIO} from '@gltf-transform/core';
import {ALL_EXTENSIONS} from '@gltf-transform/extensions';
import {dedup,prune,weld,resample,meshopt,textureCompress} from '@gltf-transform/functions';
import {MeshoptEncoder} from 'meshoptimizer';
import sharp from 'sharp';
import fs from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
export async function optimiseAmbient(quality){
 await MeshoptEncoder.ready;
 const io=new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({'meshopt.encoder':MeshoptEncoder});
 const dir=`evorium/static/world3d/assets/${quality}/ambient`;await fs.mkdir(dir,{recursive:true});
 const models={};let bytes=0,triangles=0;
 for(const name of ['cat','dog','fox']){
  const doc=await io.read(`tools/web3d/raw/ambient/${name}.glb`);
  await doc.transform(dedup(),prune(),weld(),resample(),textureCompress({encoder:sharp,targetFormat:'webp',resize:quality==='low'?[128,128]:[256,256]}),meshopt({encoder:MeshoptEncoder,level:'medium'}));
  const clips=doc.getRoot().listAnimations().map(a=>a.getName());
  if(!clips.includes('Idle')||!clips.includes('Walking'))throw Error(`${name} needs Idle and Walking: ${clips}`);
  const file=dir+'/'+name+'.glb';await io.write(file,doc);const size=(await fs.stat(file)).size;
  let count=0;for(const m of doc.getRoot().listMeshes())for(const p of m.listPrimitives())count+=(p.getIndices()?.getCount()||p.getAttribute('POSITION').getCount())/3;
  models[name]={bytes:size,triangles:count,clips};bytes+=size;triangles+=count;
 }
 const limitBytes=(quality==='low'?1.2:2.5)*1e6;
 if(bytes>limitBytes)throw Error('Ambient asset budget exceeded '+quality);
 return {bytes,megabytes:bytes/1e6,limitBytes,triangles,models};
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
 const file='evorium/static/world3d/data/budgets.json',reports=JSON.parse(await fs.readFile(file));
 for(const quality of ['low','high']){
  const r=reports[quality],old=r.ambient||{bytes:0,triangles:0};r.ambient=await optimiseAmbient(quality);
  r.bytes+=r.ambient.bytes-old.bytes;r.megabytes=r.bytes/1e6;r.triangles+=r.ambient.triangles-old.triangles;
  if(r.bytes>(quality==='low'?12:30)*1e6)throw Error('Whole-game budget exceeded '+quality);
  console.log(quality,r.ambient,'whole MB',r.megabytes);
 }
 await fs.writeFile(file,JSON.stringify(reports,null,2)+'\n');
}
