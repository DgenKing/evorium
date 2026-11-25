import * as THREE from 'three';
import {clone} from 'three/addons/utils/SkeletonUtils.js';
import {CSS2DObject} from 'three/addons/renderers/CSS2DRenderer.js';
import {lookupCast} from './cast.js';
import {nearest,pathfind,pathfindFast,slotPosition,distance} from './graph.js';
export class Actors{
 constructor(scene,assets,data,world){this.scene=scene;this.assets=assets;this.data=data;this.world=world;this.people=new Map();this.departures=new Map();this.tags=true;this.findPath=data.city?pathfindFast:pathfind;}
 async create(name){
 const gltf=await this.assets.getCharacter(name),config=lookupCast(this.data.cast,name);
 const body=clone(gltf.scene),root=new THREE.Group();root.add(body);this.scene.add(root);
 const bounds=new THREE.Box3().setFromObject(body);body.position.y-=bounds.min.y;
 body.traverse(o=>{if(o.isMesh){o.castShadow=true;o.frustumCulled=false;}});
 const mixer=new THREE.AnimationMixer(body),actions={};
 const hip=body.getObjectByName('pelvis'),reference=this.assets.animations.scene.getObjectByName('pelvis');
 for(const [key,name] of Object.entries(this.data.clips)){
  const animation=this.assets.animations.animations.find(clip=>clip.name===name);
  if(!animation)continue;
  const clip=animation.clone();
  const translation=clip.tracks.find(track=>track.name==='pelvis.position');
  if(hip&&reference&&translation)for(let i=0;i<translation.values.length;i+=3){
   translation.values[i]+=hip.position.x-reference.position.x;
   translation.values[i+1]+=hip.position.y-reference.position.y;
   translation.values[i+2]+=hip.position.z-reference.position.z;
  }
  actions[key]=mixer.clipAction(clip);
 }
 // Track only sole/foot vertices, not the full mesh, to keep planted clips on the floor.
 const bindY=body.position.y,soles=[];root.updateMatrixWorld(true);body.traverse(o=>{if(!o.isSkinnedMesh)return;const indices=[],v=new THREE.Vector3();for(let i=0;i<o.geometry.attributes.position.count;i++){v.fromBufferAttribute(o.geometry.attributes.position,i).applyMatrix4(o.matrixWorld);if(v.y<config.height*.16)indices.push(i);}if(indices.length)soles.push({mesh:o,indices});});
 let active;const actor={root,body,mixer,actions,bindY,ground(state=this.state){body.position.y=bindY;if(!['idle','talk','walk','run','sit','sit_down','stand_up','land'].includes(state))return;root.updateMatrixWorld(true);for(const skeleton of new Set(soles.map(s=>s.mesh.skeleton)))skeleton.update();let lowest=Infinity;const v=new THREE.Vector3();for(const {mesh,indices} of soles)for(const index of indices){mesh.getVertexPosition(index,v);v.applyMatrix4(mesh.matrixWorld);lowest=Math.min(lowest,v.y-root.position.y);}if(Number.isFinite(lowest)&&Math.abs(lowest)<.25)body.position.y=bindY-lowest;},height:config.height,animate(state,dt){this.state=state;const next=actions[state]||actions.idle;if(next!==active){active?.fadeOut(.2);next?.reset().fadeIn(.2).play();active=next;}mixer.update(dt);this.ground(state);}};
 if(config.nightTie){
  actor.nightTie=body.getObjectByName('Norman_night_tie');
  if(actor.nightTie)actor.nightTie.visible=false;
 }
 return actor;
 }
 label(actor,person){const wrap=document.createElement('div');wrap.className='actor-label';const bubble=document.createElement('div');bubble.className='bubble';bubble.hidden=true;const tag=document.createElement('button');tag.className='name-tag';tag.textContent=person.first;tag.onclick=()=>this.onSelect?.(actor.person||person);const activity=document.createElement('div');activity.className='actor-activity';activity.hidden=true;wrap.append(bubble,tag,activity);const object=new CSS2DObject(wrap);object.position.y=actor.height+configLabelOffset(this.data.cast,person.kind==='player'?'player':person.name);actor.root.add(object);Object.assign(actor,{label:object,tag,bubble,activity,expires:0});}
 say(actor,text){actor.bubble.textContent=text.slice(0,220);actor.bubble.hidden=false;actor.expires=performance.now()+6000;}
 async sync(snapshot,test=false){
 this.snapshot=snapshot;
 const ids=new Set(snapshot.characters.map(p=>p.id));
 for(const p of snapshot.characters){
  let a=this.people.get(p.id);
  const waypoint=this.data.waypoints[p.waypoint];
  const end=p.visible&&waypoint ? p.waypoint :
   this.data.city ? (p.door||'STREET_LEFT') : p.first==='Dez'?'UPSTAIRS':'STREET_LEFT';
  const target=this.data.routes.nodes[end];
  const journey=this.data.city&&p.travel;
  const origin=journey&&this.data.routes.nodes[journey.from];
  if(p.visible&&!waypoint)continue; // Original kit has no city-only destinations.
  if(!target||(!a&&!p.visible&&(!origin||test||this.departures.get(p.id)===journey.id)))continue;
  const arrival=p.visible ? slotPosition(waypoint, this.data.city&&p.waypoint.startsWith('r')?Math.min(p.slot,3):p.slot) : [...target];
  const floor=this.world.place({x:arrival[0],z:arrival[2]});
  arrival[1]=floor==='pub'?0:floor==='shop'?.055:this.world.ground(arrival[0],arrival[2]);
  if(!a){
   const route=origin&&!test?this.findPath(this.data.routes,journey.from,end).map(n=>this.data.routes.nodes[n]):[];
   // Catch up a newly opened page to the same walk other clients are seeing.
   let travelled=(journey?.age||0)*this.walkRate(p);
   while(route.length>1&&travelled>=distance(route[0],route[1])){
    travelled-=distance(route[0],route[1]);route.shift();
   }
   if(!p.visible&&route.length<2)continue;
   try{a=await this.create(p.kind==='player'?'player':p.name);}
   catch{continue;} // Failed model loads are reported by the asset cache.
   this.label(a,p);
   a.root.position.fromArray(route.length>1?route.shift():arrival);
   if(route.length&&travelled>0){
    const next=new THREE.Vector3().fromArray(route[0]);
    const fraction=Math.min(1,travelled/Math.max(.001,next.distanceTo(a.root.position)));
    a.root.position.lerp(next,fraction);
   }
   if(route.length){const {x,z}=a.root.position;a.root.position.y=this.world.ground(x,z);}
   a.route=route.length?[...route,arrival]:[];
   this.people.set(p.id,a);
  }else if(a.end!==end||a.person.slot!==p.slot||a.journey!==journey?.id){
   if(test){a.root.position.fromArray(arrival);a.route=[];}
   else{
    const start=nearest(this.data.routes,a.root.position.toArray());
    const route=this.findPath(this.data.routes,start,end);
    a.route=route.length?[...route.map(n=>this.data.routes.nodes[n]),arrival]:[];
    if(!route.length)a.root.position.fromArray(arrival);
   }
  }
  a.end=end;a.journey=journey?.id;a.person=p;a.tag.textContent=p.first;a.leaving=!p.visible;
  if(a.nightTie)a.nightTie.visible=p.place==='arcade'&&p.activity?.includes('in a tie');
  if(p.line_at&&p.line_at!==a.lineAt){this.say(a,p.line||'');a.lineAt=p.line_at;}
 }
 for(const [id,a] of this.people)if(!ids.has(id)){this.scene.remove(a.root);a.label.element.remove();this.people.delete(id);}
 }
 walkRate(p){
  const pace=['Tommy','Brenda'].includes(p.first)?1.1:['Raj','Dez'].includes(p.first)?1.5:1.4;
  return pace*Math.max(1,Math.min(6,Number(this.snapshot?.speed)||1));
 }
 update(dt,camera){
 const eye=camera.position, now=Date.now()/1000;
 const greetings=new Map((this.snapshot?.greetings||[]).filter(line=>line.start<=now&&now<line.start+6).map(line=>[line.id,line]));
 for(const [id,a] of this.people){const p=a.person;let moving=false;
 if(a.route.length&&!a.chatting){const next=new THREE.Vector3().fromArray(a.route[0]);const floorPlace=this.world.place(next);next.y=floorPlace==='pub'?0:floorPlace==='shop'?.055:this.world.ground(next.x,next.z);const dir=next.clone().sub(a.root.position);const speed=this.walkRate(p);
 if(dir.length()<speed*dt+.08){a.root.position.copy(next);a.route.shift();}else{dir.normalize();a.root.position.addScaledVector(dir,speed*dt);a.root.rotation.y=THREE.MathUtils.damp(a.root.rotation.y,Math.atan2(dir.x,dir.z),8,dt);moving=true;}}
 if(a.leaving&&!a.route.length){this.departures.set(id,a.journey);this.scene.remove(a.root);a.label.element.remove();this.people.delete(id);continue;}
 if(!moving&&p.visible){const other=this.people.get(p.talking_to);const yaw=a.chatting?Math.atan2(this.player.position.x-a.root.position.x,this.player.position.z-a.root.position.z):other?Math.atan2(other.root.position.x-a.root.position.x,other.root.position.z-a.root.position.z):this.data.waypoints[p.waypoint].yaw;a.root.rotation.y=THREE.MathUtils.damp(a.root.rotation.y,yaw,8,dt);}
 const hello=greetings.get(id);
 if(hello&&hello.place===p.place&&!a.chatting&&!p.talking_to&&a.helloAt!==hello.start){
  this.say(a,hello.text);
  a.expires=performance.now()+1000*(hello.start+6-now);
  a.helloAt=hello.start;
 }
 const sitting=['PUB_BOOTH','PUB_WINDOW'].includes(p.waypoint)||
  (p.place==='cafe'&&p.slot<=3);
 const gesturing=p.kind==='npc'&&/buying|browsing|counter|working the bar/.test(p.activity||'')&&(now+id)%11<1.5;
 a.animate(moving?'walk':a.chatting||p.talking_to||(hello&&hello.place===p.place)?'talk':sitting?'sit':gesturing?'talk':'idle',dt);
 a.tag.title=p.activity||'';
 if(performance.now()>a.expires)a.bubble.hidden=true;
 const head=a.root.position.clone().add(new THREE.Vector3(0,a.height+.1,0)),d=eye.distanceTo(head);const ray=this.world.octree.rayIntersect(new THREE.Ray(eye,head.clone().sub(eye).normalize()));a.label.visible=d<12&&(!ray||ray.distance>d-.3);a.tag.hidden=!this.tags;
 const activity=p.activity||'';
 if(a.activity.textContent!==activity)a.activity.textContent=activity;
 a.activity.hidden=!this.tags||!activity||moving||d>=5||!a.bubble.hidden;
 }
 }
 nearestTalk(player){return [...this.people.values()].filter(a=>a.person.kind!=='player'&&a.person.visible&&!a.route?.length&&a.person.place===player.place&&a.root.position.distanceTo(player.position)<2).sort((a,b)=>a.root.position.distanceTo(player.position)-b.root.position.distanceTo(player.position))[0];}
}

function configLabelOffset(cast,name){return lookupCast(cast,name).labelOffset??.22;}
