import * as THREE from 'three';
import {WeatherFX} from './weather.js';
import {Octree} from 'three/addons/math/Octree.js';
export class World{
 constructor(scene,assets,preset){
 this.scene=scene;this.preset=preset;this.weather=new WeatherFX(scene,preset===undefined?'low':preset.shadows?'high':'low');this.daylight=.7;this.target=.7;this.open={pub:true,shop:true};
 const set=assets.shuttle_street.scene;scene.add(set);this.set=set;
 set.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;o.material.lightMap=assets.lightmap;o.material.lightMapIntensity=.65;}});
 this.octree=new Octree().fromGraphNode(assets.collision.scene);
 this.debug=assets.collision.scene;this.debug.traverse(o=>{if(o.isMesh)o.material=new THREE.MeshBasicMaterial({wireframe:true,color:0xff3355});});this.debug.visible=false;scene.add(this.debug);
 this.hemi=new THREE.HemisphereLight(0xbccfdf,0x827361,2);scene.add(this.hemi);
 this.sun=new THREE.DirectionalLight(0xffefda,2);this.sun.position.set(-15,25,12);this.sun.castShadow=!!preset.shadows;
 Object.assign(this.sun.shadow.camera,{left:-18,right:18,top:18,bottom:-18,near:1,far:65});this.sun.shadow.mapSize.set(preset.shadows||512,preset.shadows||512);this.sun.shadow.bias=-.0004;scene.add(this.sun);
 this.lights=[];for(const [place,p,color] of [['pub',[-5,2.5,-4],0xffbc78],['pub',[-2,2.5,-7],0xffc98e],['shop',[4,2.6,-4],0xe1efff]]){const l=new THREE.PointLight(color,14,10,2);l.position.fromArray(p);l.userData.place=place;scene.add(l);this.lights.push(l);}
 scene.fog=new THREE.Fog(0xaab7c2,25,100);scene.background=new THREE.Color(0xaab7c2);
 this.festive=new THREE.Group();this.festive.visible=false;scene.add(this.festive);
 const bulbs=new THREE.InstancedMesh(new THREE.SphereGeometry(.045,6,4),new THREE.MeshBasicMaterial(),18);const transform=new THREE.Object3D();
 for(let i=0;i<18;i++){transform.position.set(-8.5+i*.45,2.9+Math.sin(i*.4)*.12,.25);transform.updateMatrix();bulbs.setMatrixAt(i,transform.matrix);bulbs.setColorAt(i,new THREE.Color(i%2?0xffd46a:0x9dca8c));}this.festive.add(bulbs);
 this.ray=new THREE.Ray();this.blockers={pub:new THREE.Box3(new THREE.Vector3(-5.3,0,-.3),new THREE.Vector3(-4,2.8,.25)),shop:new THREE.Box3(new THREE.Vector3(5.2,0,-.3),new THREE.Vector3(6.6,2.8,.3))};
 this.wetMaterials=new Map();set.traverse(o=>{if(o.isMesh&&/road|pavement|sidewalk|ground/i.test(o.name)&&o.material.roughness!==undefined)this.wetMaterials.set(o.material,o.material.roughness);});
 this.materials=new Set();set.traverse(o=>{if(o.isMesh)this.materials.add(o.material);});this.glowing=[];set.traverse(o=>{if(o.isMesh&&/glass|lamp/i.test(o.name)){o.material=o.material.clone();this.glowing.push(o);}});
 }
 updateSnapshot(s){this.festive.visible=!!s.calendar?.decorations;this.weather.set(s.weather);for(const [material,roughness] of this.wetMaterials)material.roughness=this.weather.style.wet?.35:roughness;this.target=s.daylight;this.open={pub:s.pub_open,shop:s.shop_open};}
 update(dt){this.daylight=THREE.MathUtils.damp(this.daylight,this.target,.3,dt);const d=this.daylight,w=this.weather.style;this.weather.update(dt);this.hemi.intensity=.3+d*(w.dark?.9:1.3);this.sun.intensity=.1+d*(w.dark?.75:1.8);this.scene.fog.near=w.fog?8:25;this.scene.fog.far=w.fog?38:100;const sky=new THREE.Color(0x172535).lerp(new THREE.Color(0xaab7c2),d);if(w.dark)sky.lerp(new THREE.Color(0x6b7680),.35);this.scene.background.copy(sky);this.scene.fog.color.copy(sky);this.lights.forEach((l,i)=>{l.intensity=this.open[l.userData.place]&&(i<this.preset.lights)?12:0;});for(const material of this.materials)material.lightMapIntensity=.15+d*.5;for(const o of this.glowing){const place=/Pub|Billet/i.test(o.name)?'pub':'shop';o.material.emissive?.setHex(this.open[place]?0xffb568:0);o.material.emissiveIntensity=(1-d)*.4;}}
 ground(x,z){const hit=this.octree.rayIntersect(new THREE.Ray(new THREE.Vector3(x,3,z),new THREE.Vector3(0,-1,0)));return hit?.position.y??0;}
 place(p){if(p.z<-.3&&p.z>-10&&p.x>-9.1&&p.x<.1)return 'pub';if(p.z<-.3&&p.z>-10&&p.x>.3&&p.x<8.3)return 'shop';return 'street';}
 cameraDistance(origin,direction,max){const hit=this.octree.rayIntersect(new THREE.Ray(origin,direction));return hit?Math.min(max,Math.max(.15,hit.distance-.18)):max;}
}
