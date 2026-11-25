import {createCastCache} from './cast.js';
import {TextureLoader} from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {MeshoptDecoder} from 'three/addons/libs/meshopt_decoder.module.js';
const loader=new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
export async function loadAssets(quality,progress,cast,cityEnabled=false){const result={};let count=0;await Promise.all(['shuttle_street','collision','animations'].map(async name=>{result[name]=await loader.loadAsync(`/static/world3d/assets/${quality}/${name}.glb`);progress(++count/3);}));if(cityEnabled){const [city,cityCollision]=await Promise.all(['city','city-collision'].map(name=>loader.loadAsync(`/static/world3d/assets/${quality}/${name}.glb`)));result.city=city;result.cityCollision=cityCollision;result.cityProps=await loader.loadAsync(`/static/world3d/assets/${quality}/city-props.glb`).catch(()=>null);}result.lightmap=await new TextureLoader().loadAsync(`/static/world3d/assets/${quality}/lightmap.webp`);result.lightmap.channel=1;result.lightmap.flipY=false;result.modelErrors=[];const cache=createCastCache(cast,key=>loader.loadAsync(`/static/world3d/assets/${quality}/${key}`),item=>{result.modelErrors.push(item);console.error('Character model unavailable',item);});result.getCharacter=name=>cache.get(name);result.loadedCharacters=()=>cache.loaded();return result;}
export async function loadData(cityEnabled=false){const names=['waypoints','routes','clips','cast','budgets',...(cityEnabled?['city','arcade']:[])];return Object.fromEntries(await Promise.all(names.map(async n=>{const r=await fetch(`/static/world3d/data/${n}.json`);if(!r.ok)throw Error('Missing data: '+n);return[n,await r.json()];})));}

export async function loadGameCatalogue(){
 const response=await fetch('/static/games/games.json');
 if(!response.ok)throw Error('Arcade game catalogue unavailable');
 return response.json();
}
