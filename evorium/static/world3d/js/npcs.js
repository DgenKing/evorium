import * as THREE from 'three';
import {clone} from 'three/addons/utils/SkeletonUtils.js';
import {CSS2DObject} from 'three/addons/renderers/CSS2DRenderer.js';
import {lookupCast} from './cast.js';
import {nearest,pathfind,slotPosition,distance} from './graph.js';
export class Actors{
 constructor(scene,assets,data,world){this.scene=scene;this.assets=assets;this.data=data;this.world=world;this.people=new Map();this.tags=true;}
 create(name){
 const config=lookupCast(this.data.cast,name);const source=this.assets.characters.scenes.find(s=>s.name===config.body)||this.assets.characters.scene;
 const body=clone(source),root=new THREE.Group();root.add(body);this.scene.add(root);
 const bounds=new THREE.Box3().setFromObject(body),height=bounds.max.y-bounds.min.y;const factor=1.75/height*config.scale;body.scale.multiplyScalar(factor);body.scale.x*=config.width;body.position.y=-bounds.min.y*factor;
 body.traverse(o=>{if(o.isMesh){o.castShadow=true;o.frustumCulled=false;o.material=o.material.clone();o.material.color.multiply(new THREE.Color(config.tint).lerp(new THREE.Color('white'),.45));}});
 body.traverse(o=>{if(o.isMesh && /Superhero|Sphere/i.test(o.name)){o.geometry.computeBoundingBox();const b=o.geometry.boundingBox;o.material.map=null;o.material.normalMap=null;o.material.color.set('white');o.material.roughness=.9;o.material.onBeforeCompile=shader=>{shader.uniforms.clothColor={value:new THREE.Color(config.tint)};shader.uniforms.skinColor={value:new THREE.Color(config.skin)};shader.uniforms.trousersColor={value:new THREE.Color(config.trousers)};shader.uniforms.clothMin={value:b.min.y};shader.uniforms.clothHeight={value:b.max.y-b.min.y};shader.vertexShader='varying float wardrobeHeight; uniform float clothMin; uniform float clothHeight;\n'+shader.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\nwardrobeHeight=(position.y-clothMin)/clothHeight;');shader.fragmentShader='varying float wardrobeHeight;uniform vec3 clothColor;uniform vec3 skinColor;uniform vec3 trousersColor;\n'+shader.fragmentShader.replace('#include <color_fragment>','#include <color_fragment>\nvec3 garment=wardrobeHeight<0.47?trousersColor:clothColor;diffuseColor.rgb*=wardrobeHeight<0.82?garment:skinColor;');};o.material.customProgramCacheKey=()=>config.tint;}});
 const mixer=new THREE.AnimationMixer(body),actions={};for(const [key,clip] of Object.entries(this.data.clips)){const animation=this.assets.animations.animations.find(a=>a.name===clip);if(animation)actions[key]=mixer.clipAction(animation);}
 let active;const actor={root,body,mixer,actions,animate(state,dt){const next=actions[state]||actions.idle;if(next!==active){active?.fadeOut(.2);next?.reset().fadeIn(.2).play();active=next;}mixer.update(dt);}};
 return actor;
 }
 label(actor,person){const wrap=document.createElement('div');wrap.className='actor-label';const bubble=document.createElement('div');bubble.className='bubble';bubble.hidden=true;const tag=document.createElement('button');tag.className='name-tag';tag.textContent=person.first;tag.onclick=()=>this.onSelect?.(person);wrap.append(bubble,tag);const object=new CSS2DObject(wrap);object.position.y=2;actor.root.add(object);Object.assign(actor,{label:object,tag,bubble,expires:0});}
 say(actor,text){actor.bubble.textContent=text.slice(0,220);actor.bubble.hidden=false;actor.expires=performance.now()+6000;}
 sync(snapshot,test=false){
 this.snapshot=snapshot;const ids=new Set(snapshot.characters.map(p=>p.id));
 for(const p of snapshot.characters){let a=this.people.get(p.id);
 if(!a&&p.visible){a=this.create(p.name);this.label(a,p);a.root.position.fromArray(this.data.routes.nodes.STREET_LEFT);a.person=p;a.route=[];this.people.set(p.id,a);}
 if(!a)continue;
 const changed=!a.person||a.person.waypoint!==p.waypoint||a.person.slot!==p.slot||a.person.visible!==p.visible;a.person=p;
 if(p.line_at&&p.line_at!==a.lineAt){this.say(a,p.line||'');a.lineAt=p.line_at;}
 if(p.visible){const target=slotPosition(this.data.waypoints[p.waypoint],p.slot);if(test||snapshot.speed>10||distance(a.root.position.toArray(),target)>35){a.root.position.fromArray(target);a.route=[];}else if(changed||!a.target){a.route=pathfind(this.data.routes,nearest(this.data.routes,a.root.position.toArray()),p.waypoint).map(n=>this.data.routes.nodes[n]);a.route.push(target);}a.target=target;a.leaving=false;}
 else if(!a.leaving){const end=p.first==='Dez'?'UPSTAIRS':a.root.position.x<0?'STREET_LEFT':'STREET_RIGHT';a.route=pathfind(this.data.routes,nearest(this.data.routes,a.root.position.toArray()),end).map(n=>this.data.routes.nodes[n]);a.leaving=true;}
 }
 for(const [id,a] of this.people)if(!ids.has(id)){this.scene.remove(a.root);a.label.element.remove();this.people.delete(id);}
 }
 update(dt,camera){const eye=camera.position;
 for(const [id,a] of this.people){const p=a.person;let moving=false;
 if(a.route.length&&!a.chatting){const next=new THREE.Vector3().fromArray(a.route[0]);next.y=this.world.ground(next.x,next.z);const dir=next.clone().sub(a.root.position);const speed=['Tommy','Brenda'].includes(p.first)?1.1:['Raj','Dez'].includes(p.first)?1.5:1.4;
 if(dir.length()<speed*dt+.08){a.root.position.copy(next);a.route.shift();}else{dir.normalize();a.root.position.addScaledVector(dir,speed*dt);a.root.rotation.y=THREE.MathUtils.damp(a.root.rotation.y,Math.atan2(dir.x,dir.z),8,dt);moving=true;}}
 if(a.leaving&&!a.route.length){this.scene.remove(a.root);a.label.element.remove();this.people.delete(id);continue;}
 if(!moving&&p.visible){const other=this.people.get(p.talking_to);const yaw=a.chatting?Math.atan2(this.player.position.x-a.root.position.x,this.player.position.z-a.root.position.z):other?Math.atan2(other.root.position.x-a.root.position.x,other.root.position.z-a.root.position.z):this.data.waypoints[p.waypoint].yaw;a.root.rotation.y=THREE.MathUtils.damp(a.root.rotation.y,yaw,8,dt);}
 a.animate(moving?'walk':a.chatting||p.talking_to?'talk':['PUB_BOOTH','PUB_WINDOW'].includes(p.waypoint)?'sit':'idle',dt);
 if(performance.now()>a.expires)a.bubble.hidden=true;
 const head=a.root.position.clone().add(new THREE.Vector3(0,1.9,0)),d=eye.distanceTo(head);const ray=this.world.octree.rayIntersect(new THREE.Ray(eye,head.clone().sub(eye).normalize()));a.label.visible=d<12&&(!ray||ray.distance>d-.3);a.tag.hidden=!this.tags;
 }
 }
 nearestTalk(player){return [...this.people.values()].filter(a=>a.person.visible&&a.person.place===player.place&&a.root.position.distanceTo(player.position)<2).sort((a,b)=>a.root.position.distanceTo(player.position)-b.root.position.distanceTo(player.position))[0];}
}
