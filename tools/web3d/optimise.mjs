import {optimiseAmbient} from './optimise_ambient.mjs';
import {NodeIO} from '@gltf-transform/core';
import {ALL_EXTENSIONS} from '@gltf-transform/extensions';
import {dedup,prune,weld,resample,meshopt,textureCompress,join,flatten,simplify} from '@gltf-transform/functions';
import {MeshoptEncoder,MeshoptSimplifier} from 'meshoptimizer';
import sharp from 'sharp';
import fs from 'node:fs/promises';
await MeshoptEncoder.ready;await MeshoptSimplifier.ready;
const io=new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({'meshopt.encoder':MeshoptEncoder});
const reports={};
const cast=JSON.parse(await fs.readFile('tools/web3d/raw/cast/inventory.json','utf8'));
const onlyCast=process.argv.includes('--cast-only');

async function optimiseCharacter(id, quality) {
 const document=await io.read(`tools/web3d/raw/cast/${id}.glb`);
 const low=quality==='low';
 await document.transform(dedup(),prune(),weld(),
  simplify({simplifier:MeshoptSimplifier,ratio:low?.30:.85,error:low?.008:.001}),
  textureCompress({encoder:sharp,targetFormat:'webp',resize:low?[512,512]:[1024,1024]}),
  meshopt({encoder:MeshoptEncoder,level:'medium'}));
 const file=`evorium/static/world3d/assets/${quality}/cast/${id}.glb`;
 await io.write(file,document);
 const {size}=await fs.stat(file);
 let triangles=0, textureBytes=0;
 for(const mesh of document.getRoot().listMeshes())for(const primitive of mesh.listPrimitives())
  triangles+=(primitive.getIndices()?.getCount()||primitive.getAttribute('POSITION').getCount())/3;
 for(const texture of document.getRoot().listTextures()){
  const dimensions=texture.getSize();
  if(dimensions)textureBytes+=dimensions[0]*dimensions[1]*4*4/3;
 }
 const report={bytes:size,megabytes:size/1e6,triangles,estimatedTextureMB:textureBytes/1e6};
 if(size>(low?.7:1.6)*1e6||triangles>(low?12000:25000))
  throw Error('Cast budget exceeded '+id+' '+quality+' '+JSON.stringify(report));
 return report;
}

const budgetsFile='evorium/static/world3d/data/budgets.json';
if(onlyCast){
 const existing=JSON.parse(await fs.readFile(budgetsFile,'utf8'));
 for(const quality of ['high','low']){
  const tier=existing[quality];
  for(const id of Object.keys(cast)){
   const previous=tier.cast[id];
   const next=await optimiseCharacter(id,quality);
   tier.cast[id]=next;
   tier.bytes+=next.bytes-(previous?.bytes??0);
   tier.triangles+=next.triangles-(previous?.triangles??0);
   tier.estimatedTextureMB+=next.estimatedTextureMB-(previous?.estimatedTextureMB??0);
   console.log(quality,id,next.bytes,next.triangles);
  }
  tier.megabytes=tier.bytes/1e6;
  if(tier.bytes>(quality==='low'?12:30)*1e6)throw Error('Budget exceeded '+quality);
 }
 await fs.writeFile(budgetsFile,JSON.stringify(existing,null,2));
 process.exit(0);
}

async function addHenryStreetPlaque(document){
 const svg=Buffer.from('<svg width="384" height="96" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="3" width="378" height="90" rx="5" fill="#243a3e" stroke="#d6c7a0" stroke-width="5"/><text x="192" y="64" text-anchor="middle" font-family="Georgia,serif" font-weight="bold" font-size="46" letter-spacing="1" fill="#f2e7c8">HENRY STREET</text></svg>');
 const image=await sharp(svg).webp({quality:40,effort:6}).toBuffer();
 const root=document.getRoot(),buffer=root.listBuffers()[0];
 const texture=document.createTexture('Henry Street plaque').setImage(image).setMimeType('image/webp');
 const material=document.createMaterial('Henry Street plaque material').setBaseColorTexture(texture).setMetallicFactor(0).setRoughnessFactor(.8).setEmissiveFactor([.24,.20,.13]);
 const mesh=document.createMesh('Henry Street plaque overlay');
 const position=document.createAccessor('POSITION').setType('VEC3').setArray(new Float32Array([-.4,-.09,0,.4,-.09,0,.4,.09,0,-.4,.09,0])).setBuffer(buffer);
 const uv=document.createAccessor('TEXCOORD_0').setType('VEC2').setArray(new Float32Array([0,1,1,1,1,0,0,0])).setBuffer(buffer);
 const indices=document.createAccessor('indices').setType('SCALAR').setArray(new Uint16Array([0,1,2,0,2,3])).setBuffer(buffer);
 mesh.addPrimitive(document.createPrimitive().setAttribute('POSITION',position).setAttribute('TEXCOORD_0',uv).setIndices(indices).setMaterial(material));
 root.listScenes()[0].addChild(document.createNode('Henry Street plaque overlay').setMesh(mesh).setTranslation([-8.62,2.21,.315]));
}

for(const quality of ['high','low']){
 let bytes=0,triangles=0,gpu=0;
 for(const file of ['shuttle_street','collision','characters','animations','animations_ual']){
 const input=file==='shuttle_street'?'shuttle_street_lit':file==='animations'?'animations_mpfb':file==='animations_ual'?'animations':file;
 const d=await io.read(`tools/web3d/raw/${input}.glb`);
 if(file==='animations'){const map=JSON.parse(await fs.readFile('tools/web3d/data/mpfb_to_ual_bones.json','utf8'));for(const a of d.getRoot().listAnimations())for(const c of a.listChannels()){const name=c.getTargetNode()?.getName();if(!map[name]||c.getTargetPath()!=='rotation'&&!(name==='pelvis'&&c.getTargetPath()==='translation'))c.dispose();}}
 if(file==='shuttle_street'){
  await d.transform(flatten(),join({keepNamed:false}));
  await addHenryStreetPlaque(d);
 }
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
 if(!['collision','animations','animations_ual','characters'].includes(file))triangles+=t;
 for(const tex of d.getRoot().listTextures()){const sz=tex.getSize();if(sz)gpu+=sz[0]*sz[1]*4*4/3;}
 console.log(quality,file,'triangles',t);
 }
 const perCharacter={};
 await fs.mkdir(`evorium/static/world3d/assets/${quality}/cast`,{recursive:true});
 for(const id of Object.keys(cast)){
  const report=perCharacter[id]=await optimiseCharacter(id,quality);
  bytes+=report.bytes;
  triangles+=report.triangles;
  gpu+=report.estimatedTextureMB*1e6;
 }
 const lightmap=`evorium/static/world3d/assets/${quality}/lightmap.webp`;await sharp(`tools/web3d/raw/lightmaps/day-${quality}.png`).webp({quality:85}).toFile(lightmap);bytes+=(await fs.stat(lightmap)).size;gpu+=(quality==='low'?1024:2048)**2*4*4/3;
 const ambient=await optimiseAmbient(quality);bytes+=ambient.bytes;triangles+=ambient.triangles;
 reports[quality]={ambient,bytes,megabytes:bytes/1e6,triangles,estimatedTextureMB:gpu/1e6,cast:perCharacter};
 if(bytes>(quality==='low'?12:30)*1e6)throw Error('Budget exceeded '+JSON.stringify(reports[quality]));
}
await fs.writeFile(budgetsFile,JSON.stringify(reports,null,2));
for(const file of ['waypoints','routes'])await fs.copyFile(`tools/web3d/raw/${file}.json`,`evorium/static/world3d/data/${file}.json`);
console.log(reports);
