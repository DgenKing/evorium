import {TextureLoader} from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {MeshoptDecoder} from 'three/addons/libs/meshopt_decoder.module.js';
const loader=new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
export async function loadAssets(quality,progress){const result={};let count=0;await Promise.all(['shuttle_street','collision','characters','animations'].map(async name=>{result[name]=await loader.loadAsync(`/static/world3d/assets/${quality}/${name}.glb`);progress(++count/4);}));result.lightmap=await new TextureLoader().loadAsync(`/static/world3d/assets/${quality}/lightmap.webp`);result.lightmap.channel=1;result.lightmap.flipY=false;return result;}
export async function loadData(){const names=['waypoints','routes','clips','cast','budgets'];return Object.fromEntries(await Promise.all(names.map(async n=>{const r=await fetch(`/static/world3d/data/${n}.json`);if(!r.ok)throw Error('Missing data: '+n);return[n,await r.json()];})));}
