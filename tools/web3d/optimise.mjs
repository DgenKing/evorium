import {NodeIO} from '@gltf-transform/core';
import {ALL_EXTENSIONS} from '@gltf-transform/extensions';
import {dedup,prune,weld,resample,meshopt,textureCompress,join,flatten,simplify} from '@gltf-transform/functions';
import {MeshoptEncoder,MeshoptSimplifier} from 'meshoptimizer';
import sharp from 'sharp';
import fs from 'node:fs/promises';
await MeshoptEncoder.ready;await MeshoptSimplifier.ready;
const io=new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({'meshopt.encoder':MeshoptEncoder});
const reports={};
for(const quality of ['high','low']){
 let bytes=0,triangles=0,gpu=0;
 for(const file of ['shuttle_street','collision','characters','animations']){
 const input=file==='shuttle_street'?'shuttle_street_lit':file;
 const d=await io.read(`tools/web3d/raw/${input}.glb`);
 if(file==='shuttle_street')await d.transform(flatten(),join({keepNamed:false}));
 await d.transform(dedup(),prune(),weld());
 if(quality==='low' && ['shuttle_street','characters'].includes(file))await d.transform(simplify({simplifier:MeshoptSimplifier,ratio:file==='characters'?.35:.35,error:file==='characters'?.01:.001}));
 if(file==='shuttle_street'){
 // Split the baked atlas mesh into independently named interior/glass/sign groups.
 for(const node of [...d.getRoot().listNodes()]){
 const original=node.getMesh();if(!original)continue;const groups=new Map(),matrix=node.getWorldMatrix();
 for(const primitive of original.listPrimitives()){
 const position=primitive.getAttribute('POSITION'),indices=primitive.getIndices().getArray(),sets=new Map();
 for(let k=0;k<indices.length;k+=3){let x=0,y=0,z=0;for(let j=0;j<3;j++){const v=position.getElement(indices[k+j],[]);x+=(matrix[0]*v[0]+matrix[4]*v[1]+matrix[8]*v[2]+matrix[12])/3;y+=(matrix[1]*v[0]+matrix[5]*v[1]+matrix[9]*v[2]+matrix[13])/3;z+=(matrix[2]*v[0]+matrix[6]*v[1]+matrix[10]*v[2]+matrix[14])/3;}
 const mat=primitive.getMaterial()?.getName()||'';let group=/Letter|Plaque/.test(mat)?'Signs':/Glass/.test(mat)?(x<0?'Pub windows glass':'Shop windows glass'):y<3.2&&z<-.25&&z>-10?(x<.1?'Pub interior':'Shop interior'):'Street and backdrop';
 if(!sets.has(group))sets.set(group,[]);sets.get(group).push(indices[k],indices[k+1],indices[k+2]);}
 for(const [name,list] of sets){if(!groups.has(name))groups.set(name,d.createMesh(name));const copy=primitive.clone();copy.setIndices(d.createAccessor().setType('SCALAR').setArray(new Uint32Array(list)).setBuffer(d.getRoot().listBuffers()[0]));groups.get(name).addPrimitive(copy);}
 }
 node.setMesh(null);for(const [name,mesh] of groups)node.addChild(d.createNode(name).setMesh(mesh));original.dispose();
 }
 await d.transform(prune());
 }
 await d.transform(resample(),textureCompress({encoder:sharp,targetFormat:'webp',resize:[quality==='low'?(file==='characters'?512:1024):2048,quality==='low'?(file==='characters'?512:1024):2048]}),meshopt({encoder:MeshoptEncoder,level:'medium'}));
 const output=`evorium/static/world3d/assets/${quality}/${file}.glb`;await io.write(output,d);bytes+=(await fs.stat(output)).size;
 let t=0;for(const m of d.getRoot().listMeshes())for(const p of m.listPrimitives())t+=(p.getIndices()?.getCount()||p.getAttribute('POSITION').getCount())/3;
 if(file!=='collision'&&file!=='animations')triangles+=t;
 for(const tex of d.getRoot().listTextures()){const sz=tex.getSize();if(sz)gpu+=sz[0]*sz[1]*4*4/3;}
 console.log(quality,file,'triangles',t);
 }
 const lightmap=`evorium/static/world3d/assets/${quality}/lightmap.webp`;await sharp(`tools/web3d/raw/lightmaps/day-${quality}.png`).webp({quality:85}).toFile(lightmap);bytes+=(await fs.stat(lightmap)).size;gpu+=(quality==='low'?1024:2048)**2*4*4/3;
 reports[quality]={bytes,megabytes:bytes/1e6,triangles,estimatedTextureMB:gpu/1e6};
 if(bytes>(quality==='low'?12:30)*1e6||triangles>(quality==='low'?150000:400000))throw Error('Budget exceeded '+JSON.stringify(reports[quality]));
}
await fs.writeFile('evorium/static/world3d/data/budgets.json',JSON.stringify(reports,null,2));
for(const file of ['waypoints','routes'])await fs.copyFile(`tools/web3d/raw/${file}.json`,`evorium/static/world3d/data/${file}.json`);
console.log(reports);
