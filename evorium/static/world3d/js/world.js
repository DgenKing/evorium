import * as THREE from 'three';
import {WeatherFX} from './weather.js';import {Night} from './night.js';
import {Octree} from 'three/addons/math/Octree.js';
export class World{
 constructor(scene,assets,preset){
 this.scene=scene;this.preset=preset;this.weather=new WeatherFX(scene,preset===undefined?'low':preset.shadows?'high':'low');this.daylight=.7;this.target=.7;this.open={pub:true,shop:true};this.night=new Night(scene);
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
 this.shuttleLighting=new THREE.Group();scene.add(this.shuttleLighting);this.night.addShuttleLamps(this.shuttleLighting,preset.shadows?preset.lights:0);
 const bulbs=new THREE.InstancedMesh(new THREE.SphereGeometry(.045,6,4),new THREE.MeshBasicMaterial(),18);const transform=new THREE.Object3D();
 for(let i=0;i<18;i++){transform.position.set(-8.5+i*.45,2.9+Math.sin(i*.4)*.12,.25);transform.updateMatrix();bulbs.setMatrixAt(i,transform.matrix);bulbs.setColorAt(i,new THREE.Color(i%2?0xffd46a:0x9dca8c));}this.festive.add(bulbs);
 this.ray=new THREE.Ray();this.blockers={pub:new THREE.Box3(new THREE.Vector3(-5.3,0,-.3),new THREE.Vector3(-4,2.8,.25)),shop:new THREE.Box3(new THREE.Vector3(5.2,0,-.3),new THREE.Vector3(6.6,2.8,.3))};
 this.wetMaterials=new Map();set.traverse(o=>{if(o.isMesh&&/road|pavement|sidewalk|ground/i.test(o.name)&&o.material.roughness!==undefined)this.wetMaterials.set(o.material,o.material.roughness);});
 this.materials=new Set();set.traverse(o=>{if(o.isMesh)this.materials.add(o.material);});this.glowing=[];set.traverse(o=>{if(o.isMesh&&/glass|lamp/i.test(o.name)){o.material=o.material.clone();this.glowing.push(o);}});
 }
 addCity(assets,manifest){
 const shuttle=manifest.shuttle_street||{},position=shuttle.position||[0,0],yaw=THREE.MathUtils.degToRad(shuttle.rotation_degrees||0);
 this.cityTransform={x:position[0],z:position[1],yaw};
 this.festive.position.set(position[0],0,position[1]);this.festive.rotation.y=yaw;
 this.shuttleLighting.position.set(position[0],0,position[1]);this.shuttleLighting.rotation.y=yaw;
 for(const light of this.lights)light.position.applyAxisAngle(new THREE.Vector3(0,1,0),yaw).add(this.festive.position);
 this.set.position.set(position[0],0,position[1]);this.set.rotation.y=yaw;
 this.debug.position.copy(this.set.position);this.debug.rotation.y=yaw;this.set.updateMatrixWorld(true);this.debug.updateMatrixWorld(true);
 if(assets.city?.scene){
  this.city=assets.city.scene;this.cityWindows=[];
  const cache=new Map();
  this.city.traverse(o=>{
   if(!o.isMesh)return;
   o.castShadow=true;o.receiveShadow=true;
   const bay=o.isInstancedMesh&&/window/.test(o.name);
   const materialFor=material=>{
    const key=material.uuid+(bay?'bay':'');
    if(cache.has(key))return cache.get(key);
    const clone=material.clone();
    if(/glass/i.test(material.name||'')){
     clone.emissive?.setHex(0xffb568);
     this.cityWindows.push(clone);
    }
    if(bay&&clone.map){
     // The model UVs use a nominal 3.1 × 3.2 m bay. Scale them with each bay
     // so the world texture repeat remains constant as floors and plots vary.
     clone.onBeforeCompile=shader=>{
      shader.vertexShader=shader.vertexShader.replace('#include <uv_vertex>',`#include <uv_vertex>
       #ifdef USE_INSTANCING
       vec2 bayScale=vec2(length(instanceMatrix[0].xyz)/3.1,length(instanceMatrix[1].xyz)/3.2);
       #ifdef USE_MAP
        vMapUv *= bayScale;
       #endif
       #ifdef USE_NORMALMAP
        vNormalMapUv *= bayScale;
       #endif
       #ifdef USE_ROUGHNESSMAP
        vRoughnessMapUv *= bayScale;
       #endif
       #endif`);
     };
     clone.customProgramCacheKey=()=>'city-bay-uv';
    }
    cache.set(key,clone);
    return clone;
   };
   o.material=Array.isArray(o.material)?o.material.map(materialFor):materialFor(o.material);
  });
  this.scene.add(this.city);
 }
 if(assets.cityCollision?.scene){this.cityCollision=assets.cityCollision.scene;this.cityCollision.updateMatrixWorld(true);}const collisionRoot=new THREE.Group();collisionRoot.add(this.debug.clone(true));if(this.cityCollision)collisionRoot.add(this.cityCollision);collisionRoot.updateMatrixWorld(true);this.octree=new Octree().fromGraphNode(collisionRoot);
 if(assets.cityProps?.scene){this.cityProps=assets.cityProps.scene;const heads=new Set();this.cityProps.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;for(const m of [o.material].flat())if(/lamp_head/i.test(m.name||''))heads.add(m);}});this.scene.add(this.cityProps);this.night.addLamps(manifest.lamps,[...heads]);}
 this.bounds=manifest.bounds||null;
 const attribution=Array.isArray(manifest.attribution)?manifest.attribution.join(' · '):String(manifest.attribution||'© OpenStreetMap contributors · Contains public sector information licensed under the Open Government Licence v3.0.');
 const badge=document.createElement('div');badge.id='city-attribution';badge.textContent=attribution;document.body.append(badge);this.cityAttribution=badge;
 }
 updateSnapshot(s){this.festive.visible=!!s.calendar?.decorations;this.weather.set(s.weather);for(const [material,roughness] of this.wetMaterials)material.roughness=this.weather.style.wet?.35:roughness;this.target=s.daylight;this.open={pub:s.pub_open,shop:s.shop_open};}
 update(dt){this.daylight=THREE.MathUtils.damp(this.daylight,this.target,.3,dt);const d=this.daylight,w=this.weather.style;this.weather.update(dt);
 // Night is moonlit, not black: a cool ambient floor and the 'sun' turns into soft blue moonlight.
 const night=THREE.MathUtils.clamp((.45-d)/.3,0,1);this.hemi.intensity=.3+d*(w.dark?.9:1.3)+night*.3;this.hemi.color.setHex(0xbccfdf).lerp(new THREE.Color(0x7f95c6),night);this.sun.intensity=.1+d*(w.dark?.75:1.8)+night*(w.dark?.1:.35);this.sun.color.setHex(0xffefda).lerp(new THREE.Color(0x9fb3e2),night);
 this.night.update(dt,d,w,this.camera,this.preset.shadows?this.preset.lights:0);
 this.scene.fog.near=w.fog?8:25;this.scene.fog.far=w.fog?38:this.cityTransform&&!this.preset.shadows?42:100;const sky=new THREE.Color(0x1a2a42).lerp(new THREE.Color(0xaab7c2),d);if(w.dark)sky.lerp(new THREE.Color(0x6b7680),.35);this.scene.background.copy(sky);this.scene.fog.color.copy(sky);this.lights.forEach((l,i)=>{l.intensity=this.open[l.userData.place]&&(i<this.preset.lights)?12:0;});for(const material of this.materials)material.lightMapIntensity=.15+d*.5;for(const o of this.glowing){const place=/Pub|Billet/i.test(o.name)?'pub':'shop';o.material.emissive?.setHex(this.open[place]?0xffb568:0);o.material.emissiveIntensity=(1-d)*.9;}for(const material of this.cityWindows||[])material.emissiveIntensity=(1-d)*.35;}
 ground(x,z){const hit=this.octree.rayIntersect(new THREE.Ray(new THREE.Vector3(x,3,z),new THREE.Vector3(0,-1,0)));return hit?.position.y??0;}
 place(p){let x=p.x,z=p.z;if(this.cityTransform){const t=this.cityTransform,dx=x-t.x,dz=z-t.z,c=Math.cos(t.yaw),s=Math.sin(t.yaw);x=dx*c-dz*s;z=dx*s+dz*c;}if(z<-.3&&z>-10&&x>-9.1&&x<.1)return 'pub';if(z<-.3&&z>-10&&x>.3&&x<8.3)return 'shop';return 'street';}
 cameraDistance(origin,direction,max){const hit=this.octree.rayIntersect(new THREE.Ray(origin,direction));return hit?Math.min(max,Math.max(.15,hit.distance-.18)):max;}
}
