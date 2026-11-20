// Pure policy helpers stay importable by Node; Three.js is loaded only by createAmbient.
import {pathfind,nearest} from './graph.js';
export const intervals={pigeons:[60,180],rubbish:[120,240],cat:[300,600],dog:[600,900],fox:[600,1200]};
export function schedule(kind,now,random=Math.random){const [a,b]=intervals[kind];return now+a+(b-a)*random();}
export function allowed(kind,daylight){return kind==='fox'?daylight<.3:['dog','pigeons'].includes(kind)?daylight>=.3:true;}
export function limits(quality){return {pigeons:quality==='low'?2:quality==='medium'?4:5,events:quality==='low'?1:quality==='medium'?2:5};}
export function separation(position,obstacles,radius=.9){
 let x=0,z=0;for(const p of obstacles){const dx=position[0]-p[0],dz=position[2]-p[2],d=Math.hypot(dx,dz);if(d<radius){const strength=(radius-d)/radius;x+=(d?dx/d:1)*strength;z+=(d?dz/d:0)*strength;}}
 return [x,z];
}
export function streetGraph(graph){const nodes=Object.fromEntries(Object.entries(graph.nodes).filter(([,p])=>p[2]>=.45&&p[2]<=2.75&&p[0]>=-12&&p[0]<=11));return {nodes,edges:graph.edges.filter(([a,b])=>nodes[a]&&nodes[b])};}
export function facing(from,to){return Math.atan2(to[0]-from[0],to[2]-from[2]);}
export function visibleStep(dt,hidden){return hidden?0:Math.min(.05,Math.max(0,dt));}
export async function createAmbient({scene,world,graph,quality,player,actors,enabled=true,testType=null,debris='packet'}){
 const T=await import('three');
 const {GLTFLoader}=await import('three/addons/loaders/GLTFLoader.js');
 const {MeshoptDecoder}=await import('three/addons/libs/meshopt_decoder.module.js');
 const loader=new GLTFLoader().setMeshoptDecoder(MeshoptDecoder),cache=new Map(),events=[];
 const group=new T.Group();group.name='Cosmetic street life';scene.add(group);
 const street=streetGraph(graph),clock={time:0},due=Object.fromEntries(Object.keys(intervals).map(k=>[k,k==='pigeons'?3+Math.random()*7:schedule(k,0)]));
 let active=enabled,loading=new Set(),serial=0,scatterCount=0,failed=[];
 let interacted=false,audio=null;const gesture=()=>{interacted=true;};addEventListener('pointerdown',gesture,{once:true});addEventListener('keydown',gesture,{once:true});
 function rattle(e,gust){if(testType||!interacted||e.debris!=='can'||gust<.4||e.age<(e.nextRattle||0))return;e.nextRattle=e.age+.12;try{audio??=new (window.AudioContext||window.webkitAudioContext)();if(audio.state==='suspended')void audio.resume().catch(()=>{});const source=audio.createBufferSource(),buffer=audio.createBuffer(1,Math.ceil(audio.sampleRate*.035),audio.sampleRate),samples=buffer.getChannelData(0);for(let i=0;i<samples.length;i++)samples[i]=(rng()*2-1);source.buffer=buffer;const gain=audio.createGain(),filter=audio.createBiquadFilter();filter.type='bandpass';filter.frequency.value=1800+rng()*700;filter.Q.value=3;gain.gain.setValueAtTime(.025,audio.currentTime);gain.gain.exponentialRampToValueAtTime(.0001,audio.currentTime+.035);source.connect(filter).connect(gain).connect(audio.destination);source.start();}catch{/* Audio is optional when the browser has no audio device. */}}
 const rng=testType?()=>.45:Math.random;
 const random=(a,b)=>a+(b-a)*rng();
 const obstacles=()=>[player.position.toArray(),...[...actors.people.values()].filter(a=>a.root.visible).map(a=>a.root.position.toArray())];
 function clearAt(x,z,r=.16){const y=world.ground(x,z);if(y>.3||y<-.2)return false;return !world.octree.sphereIntersect(new T.Sphere(new T.Vector3(x,y+r+.025,z),r));}
 function safeSegment(a,b,r=.16){const n=Math.max(1,Math.ceil(Math.hypot(a[0]-b[0],a[2]-b[2])/.12));for(let i=0;i<=n;i++){const t=i/n;if(!clearAt(a[0]+(b[0]-a[0])*t,a[2]+(b[2]-a[2])*t,r))return false;}return true;}
 // The base graph is capsule-verified; discard nodes/edges touching kerbs or props for animals too.
 for(const [id,p] of Object.entries(street.nodes))if(!clearAt(p[0],p[2],.18))delete street.nodes[id];
 street.edges=street.edges.filter(([a,b])=>street.nodes[a]&&street.nodes[b]&&safeSegment(street.nodes[a],street.nodes[b],.18));
 if(!Object.keys(street.nodes).length)throw Error('No safe ambient street nodes');
 function onGround(predicate){const nodes=Object.fromEntries(Object.entries(street.nodes).filter(([,p])=>predicate(world.ground(p[0],p[2]))));return {nodes,edges:street.edges.filter(([a,b])=>nodes[a]&&nodes[b])};}
 const pavement=onGround(y=>y>=-.03),gutter=onGround(y=>y<-.03);
 function snapped(p,network=pavement){return network.nodes[nearest(network,p)].slice();}
 function routeBetween(a,b,network=pavement){return pathfind(network,nearest(network,a),nearest(network,b)).map(id=>network.nodes[id].slice());}
 function place(root,p){root.position.set(p[0],world.ground(p[0],p[2]),p[2]);}
 function remove(e){group.remove(e.root);if(e.procedural)e.root.traverse(o=>{o.dispose?.();o.geometry?.dispose();if(o.material){for(const m of Array.isArray(o.material)?o.material:[o.material])m.dispose();}});e.mixer?.stopAllAction();if(e.mixer)e.mixer.uncacheRoot(e.body);const i=events.indexOf(e);if(i>=0)events.splice(i,1);}
 function material(color){return new T.MeshStandardMaterial({color,roughness:.9});}
 function mesh(g,m,parent){const o=new T.Mesh(g,m);o.castShadow=quality!=='low';o.receiveShadow=true;parent.add(o);return o;}
 async function model(kind){if(!cache.has(kind))cache.set(kind,loader.loadAsync(`/static/world3d/assets/${quality==='low'?'low':'high'}/ambient/${kind}.glb`).catch(e=>{cache.delete(kind);throw e;}));return cache.get(kind);}
 function makeBirds(){
  const root=new T.Group(),count=testType?limits(quality).pigeons:Math.floor(random(2,limits(quality).pigeons+1));
  const geometries=[new T.SphereGeometry(1,quality==='low'?6:8,4),new T.SphereGeometry(1,6,4),new T.BoxGeometry(1,1,1),new T.BoxGeometry(1,1,1),new T.ConeGeometry(1,1,4),new T.BoxGeometry(1,1,1)];
  const mats=[material(0x717987),material(0x46585b),material(0x596373),material(0x596373),material(0xd4a564),material(0x9e6256)];
  const parts=geometries.map((g,i)=>{const o=new T.InstancedMesh(g,mats[i],i===5?count*2:count);o.castShadow=quality!=='low';o.frustumCulled=false;root.add(o);return o;});
  // Eyes share one instanced draw; legs/feet share one draw.
  const eyes=new T.InstancedMesh(new T.SphereGeometry(.012,4,3),material(0x151719),count*2);root.add(eyes);eyes.frustumCulled=false;
  const birds=Array.from({length:count},(_,i)=>{const p=testType?[-2.75+(i%3)*.32,0,1.1+Math.floor(i/3)*.40]:snapped([-2.5+(i%3)*.6,0,1.1+Math.floor(i/3)*.55]);return {p,yaw:.8+i*1.7,phase:i*1.9,next:random(1,3),walk:0};});
  const e={kind:'pigeons',root,parts,eyes,birds,procedural:true,age:0,flight:0,scattered:false};group.add(root);events.push(e);paintBirds(e);return e;
 }
 const dummy=new T.Object3D();
 function instance(part,index,x,y,z,sx,sy,sz,rx=0,ry=0,rz=0){dummy.position.set(x,y,z);dummy.scale.set(sx,sy,sz);dummy.rotation.set(rx,ry,rz);dummy.updateMatrix();part.setMatrixAt(index,dummy.matrix);}
 function paintBirds(e){for(const [i,b] of e.birds.entries()){
  const lift=e.scattered?.08+e.flight*1.7:0,y=world.ground(b.p[0],b.p[2])+lift,peck=e.scattered?0:Math.max(0,Math.sin(e.age*3+b.phase));
  const yaw=b.yaw,s=Math.sin(yaw),c=Math.cos(yaw),forward=(v)=>[b.p[0]+s*v,b.p[2]+c*v];
  instance(e.parts[0],i,b.p[0],y+.16,b.p[2],.10,.115,.18,0,yaw);
  const h=forward(.10+peck*.08);instance(e.parts[1],i,h[0],y+(.30-peck*.17),h[1],.07,.075,.07,0,yaw);
  for(let side=0;side<2;side++){const sign=side?1:-1,flap=e.scattered?Math.sin(e.age*28)*1.05:.12;
   instance(e.parts[2+side],i,b.p[0]+c*.12*sign,y+.18,b.p[2]-s*.12*sign,e.scattered?.25:.035,.025,.17,0,yaw,sign*flap);
   const eye=forward(.12+peck*.08);instance(e.eyes,i*2+side,eye[0]+c*.055*sign,y+(.32-peck*.17),eye[1]-s*.055*sign,1,1,1);
  }
  const beak=forward(.19+peck*.06);instance(e.parts[4],i,beak[0],y+(.29-peck*.19),beak[1],.025,.065,.025,Math.PI/2,yaw);
  for(const side of [-1,1])instance(e.parts[5],i*2+(side>0?1:0),b.p[0]+c*.045*side,y+.025,b.p[2]-s*.045*side,.025,.05,.08,0,yaw);
 }
 for(const o of [...e.parts,e.eyes])o.instanceMatrix.needsUpdate=true;
 }
 function makeRubbish(){
  const kind=testType?debris:['packet','paper','can'][Math.floor(rng()*3)],root=new T.Group();
  if(kind==='can'){
   const can=mesh(new T.CylinderGeometry(.036,.036,.12,quality==='low'?6:10),material(0x8b3430),root);can.rotation.x=Math.PI/2;
   for(const z of [-.061,.061]){const lid=mesh(new T.CircleGeometry(.035,8),material(0xb6babb),root);lid.rotation.y=z>0?0:Math.PI;lid.position.z=z;}
  }else if(kind==='paper'){
   for(const side of [-1,1]){const page=mesh(new T.BoxGeometry(.14,.003,.34),material(0xd8d4c4),root);page.position.x=side*.068;page.rotation.z=side*.13;
    const lines=new T.InstancedMesh(new T.BoxGeometry(.105,.002,.005),material(0x586066),7);page.add(lines);const transform=new T.Object3D();for(let i=0;i<7;i++){transform.position.set(0,.003,-.12+i*.038);transform.updateMatrix();lines.setMatrixAt(i,transform.matrix);}lines.instanceMatrix.needsUpdate=true;}
  }else{
   const g=new T.BoxGeometry(.13,.025,.19,2,1,3),p=g.attributes.position;for(let i=0;i<p.count;i++)p.setY(i,p.getY(i)+Math.sin(p.getX(i)*80+p.getZ(i)*75)*.012);g.computeVertexNormals();mesh(g,material(0xc1a21e),root);
   const stripe=mesh(new T.BoxGeometry(.134,.029,.055),material(0xa33421),root);stripe.position.z=.01;
  }
  const wind=rng()<.5?1:-1,track=kind==='can'?gutter:pavement,p=snapped(testType?[-2.5,0,kind==='can'?2.75:1.1]:[wind>0?-11.8:10.8,0,kind==='can'?2.75:1.1],track);
  const end=snapped([wind>0?10.8:-11.8,0,kind==='can'?2.75:1.1],track);
  const shelter=snapped(kind==='can'?[8.1,0,2.75]:[5.92,0,.55],track),first=routeBetween(p,shelter,track),second=routeBetween(shelter,end,track);
  if(!first.length||!second.length)throw Error('No safe rubbish route');
  const e={kind:'rubbish',debris:kind,root,p,wind,route:testType?routeBetween(p,end,track):[...first,...second.slice(1)],shelterIndex:first.length-1,index:1,age:0,settle:0,settled:false,procedural:true,roll:0};place(root,p);root.position.y+=kind==='can'?.038:kind==='paper'?.012:.03;group.add(root);events.push(e);return e;
 }
 async function makeAnimal(kind){
  const gltf=await model(kind);if(!active||(!allowed(kind,world.target)&&!testType))return;
  // Only one of each kind exists at once, so cached skeletons can be reused safely.
  const root=new T.Group(),body=gltf.scene;root.add(body);const mixer=new T.AnimationMixer(body),actions={};
  for(const clip of gltf.animations)actions[clip.name]=mixer.clipAction(clip);actions.Idle.play();
  root.traverse(o=>{if(o.isMesh){o.castShadow=quality!=='low';o.receiveShadow=true;}});
  const wind=rng()<.5?1:-1,lane=kind==='fox'?1.65:1.1;
  const start=snapped(testType?[-2.5,0,lane]:[wind>0?-11.8:10.8,0,lane]);
  // Doorstep, the cast bollards/lamp, or the quiet end of the street. All remain on the street graph.
  const pause=snapped(kind==='cat'?[5.92,0,.55]:kind==='dog'?[7.7,0,1.1]:[-10.5,0,1.65]);
  const first=routeBetween(start,pause),second=routeBetween(pause,[wind>0?10.8:-11.8,0,lane]);
  if(!first.length||!second.length)throw Error('No safe animal route: '+kind);
  const e={kind,root,body,mixer,actions,action:'Idle',route:[...first,...second.slice(1)],pauseIndex:first.length-1,index:1,p:start,age:0,pause:0,paused:false,wind,groundOffset:0};
  place(root,start);root.rotation.y=testType?Math.PI/2:wind*Math.PI/2;group.add(root);events.push(e);groundAnimal(e);return e;
 }
 function action(e,name){if(e.action===name)return;e.actions[e.action]?.fadeOut(.2);e.actions[name]?.reset().fadeIn(.2).play();e.action=name;}
 function groundAnimal(e){
  // Sample the deformed vertices: IK loops have a small vertical bob. Keep the lowest paw on the ground.
  e.body.position.y=0;e.root.updateMatrixWorld(true);let min=Infinity;const v=new T.Vector3();
  e.body.traverse(o=>{if(!o.isMesh)return;if(o.isSkinnedMesh)o.skeleton.update();for(let i=0;i<o.geometry.attributes.position.count;i++){o.getVertexPosition(i,v);v.applyMatrix4(o.matrixWorld);min=Math.min(min,v.y);}});
  e.groundOffset=world.ground(e.p[0],e.p[2])-min;e.body.position.y=e.groundOffset;
 }
 async function spawn(kind){if(!active||loading.has(kind)||events.some(e=>e.kind===kind)||events.length+loading.size>=limits(quality).events)return;
  loading.add(kind);try{const e=kind==='pigeons'?makeBirds():kind==='rubbish'?makeRubbish():await makeAnimal(kind);if(e)e.id=++serial;}catch(error){failed.push(kind+': '+error.message);console.warn('Street life',kind,error);}finally{loading.delete(kind);}
 }
 function move(e,speed,dt,people){
  const target=e.route[e.index];if(!target)return false;
  const dx=target[0]-e.p[0],dz=target[2]-e.p[2],d=Math.hypot(dx,dz);
  if(d<.09){e.index++;return true;}
  const [ax,az]=separation(e.p,people,e.kind==='rubbish'?.65:1.05),step=Math.min(d,speed*dt),next=[e.p[0]+dx/d*step+ax*dt,e.p[1],e.p[2]+dz/d*step+az*dt];
  // Wait when someone occupies the route; never force a passage through their capsule.
  if(people.some(p=>Math.hypot(next[0]-p[0],next[2]-p[2])<.55)||!safeSegment(e.p,next,e.kind==='rubbish'?.065:.18)||next[2]<.45||next[2]>2.75)return true;
  const heading=facing(e.p,next);e.p=next;place(e.root,next);if(e.kind!=='rubbish')e.root.rotation.y+=Math.atan2(Math.sin(heading-e.root.rotation.y),Math.cos(heading-e.root.rotation.y))*Math.min(1,dt*10);return true;
 }
 function update(dt,daylight,hidden=false,force=false){
  dt=visibleStep(dt,hidden);if(!active||!dt)return;
  clock.time+=dt;const people=obstacles();
  for(const e of [...events]){
   if(!allowed(e.kind,daylight)){remove(e);due[e.kind]=schedule(e.kind,clock.time,rng);continue;}
   e.age+=dt;
   if(e.kind==='pigeons'){
    if(!e.scattered&&e.birds.some(b=>people.some(p=>Math.hypot(b.p[0]-p[0],b.p[2]-p[2])<2.5))&&(!testType||force)){
     e.scattered=true;e.flight=0;scatterCount++;due.pigeons=schedule('pigeons',clock.time,rng);
    }
    if(testType&&!force){e.age=.6;paintBirds(e);continue;}
    for(const b of e.birds){if(e.scattered){b.p[0]+=dt*1.2;b.p[2]+=dt*2;b.yaw=.54;}else{
     b.next-=dt;if(b.next<=0){b.yaw+=random(-1.2,1.2);b.walk=random(.5,1.8);b.next=random(2,5);}
     if(b.walk>0){b.walk-=dt;const n=[b.p[0]+Math.sin(b.yaw)*dt*.18,0,b.p[2]+Math.cos(b.yaw)*dt*.18];if(n[2]>.45&&n[2]<2.7&&safeSegment(b.p,n,.09))b.p=n;}
    }}
    if(e.scattered){e.flight+=dt;if(e.flight>3){remove(e);continue;}}paintBirds(e);
   }else if(e.kind==='rubbish'){
    if(testType&&!force)continue;
    if(e.settle>0){e.settle-=dt;continue;}
    // Gusts alternate movement with lulls. A mid-route lull leaves it by a doorway/bollard.
    if(!e.settled&&e.index>e.shelterIndex){e.settle=random(8,25);e.settled=true;continue;}
    const gust=Math.max(0,Math.sin(e.age*.8)+Math.sin(e.age*2.1)*.35+.4);
    if(!move(e,.9*gust,dt,people)||e.age>110){e.fade=(e.fade??1)-dt*.7;e.root.traverse(o=>{if(o.material){o.material.transparent=true;o.material.opacity=Math.max(0,e.fade);}});if(e.fade<=0)remove(e);continue;}
    rattle(e,gust);e.roll+=dt*gust*(e.debris==='can'?14:5);e.root.rotation.set(e.debris==='can'?0:e.debris==='paper'?e.roll*.6:e.roll,e.debris==='can'?0:e.roll*.4,e.debris==='can'?-e.wind*e.roll:Math.cos(e.roll)*.12);e.root.position.y+=e.debris==='can'?.038:e.debris==='paper'?.025+Math.abs(Math.sin(e.roll*.6))*.18:.03+Math.abs(Math.sin(e.roll))*.105;
   }else{
    if(testType&&!force){action(e,'Walking');e.mixer.update(0);e.mixer.setTime(.45);groundAnimal(e);continue;}
    if(e.pause>0){e.pause-=dt;action(e,'Idle');e.root.rotation.y+=Math.sin(e.age*1.7)*dt*.15;const [ax,az]=separation(e.p,people,1.05);const n=[e.p[0]+ax*dt,0,e.p[2]+az*dt];if(n[2]>=.45&&n[2]<=2.75&&safeSegment(e.p,n,.18)){e.p=n;place(e.root,n);}}
    else{
     if(!e.paused&&e.index>e.pauseIndex){e.paused=true;e.pause=e.kind==='cat'?(rng()<.7?random(20,60):0):random(4,10);}
     const old=e.root.position.clone();if(!move(e,e.kind==='dog'?1.25:e.kind==='fox'?.65:.55,dt,people)||e.age>240){remove(e);continue;}
     action(e,e.pause>0||old.distanceTo(e.root.position)<.001?'Idle':'Walking');
    }
    e.mixer.update(dt*(e.kind==='dog'?1.5:e.kind==='fox'?.8:1));groundAnimal(e);
   }
  }
  if(!testType)for(const kind of Object.keys(intervals))if(clock.time>=due[kind]&&allowed(kind,daylight)&&!events.some(e=>e.kind===kind)&&!loading.has(kind)&&events.length+loading.size<limits(quality).events){due[kind]=schedule(kind,clock.time,rng);void spawn(kind);}
 }
 function setEnabled(value){active=value;group.visible=value;if(!value)for(const e of [...events])remove(e);}
 const api={update,setEnabled,setQuality(value){quality=value;while(events.length>limits(quality).events)remove(events.at(-1));const flock=events.find(e=>e.kind==='pigeons');if(flock&&flock.birds.length>limits(quality).pigeons){flock.birds.length=limits(quality).pigeons;for(const p of [...flock.parts,flock.eyes])p.count=p===flock.eyes||p===flock.parts[5]?flock.birds.length*2:flock.birds.length;}},spawn,
  report(){return {enabled:active,time:clock.time,scatterCount,loading:[...loading],loaded:[...cache.keys()],failures:failed,events:events.map(e=>({kind:e.kind,debris:e.debris,position:e.root.position.toArray(),rotation:e.root.rotation.y,action:e.action,groundOffset:e.groundOffset,routeLength:e.route?.length,index:e.index,destination:e.route?.at(-1),pigeons:e.birds?.length,scattered:e.scattered,flight:e.flight}))};},
  inspect(){return events.map(e=>{const box=new T.Box3().setFromObject(e.root,true);return {kind:e.kind,min:box.min.toArray(),max:box.max.toArray(),height:box.max.y-box.min.y,ground:e.p?world.ground(e.p[0],e.p[2]):null};});},
  async testAPCScatter(){const old=events.find(e=>e.kind==='pigeons');if(old)remove(old);await spawn('pigeons');const flock=events.find(e=>e.kind==='pigeons'),actor=[...actors.people.values()].find(a=>a.root.visible);if(!flock||!actor)throw Error('APC scatter fixture missing');const saved=actor.root.position.clone(),savedPlayer=player.position.clone(),p=flock.birds[0].p;player.position.set(10,0,5);actor.root.position.set(p[0]+1,0,p[2]);update(1/60,1,false,true);actor.root.position.copy(saved);player.position.copy(savedPlayer);const scattered=flock.scattered;remove(flock);if(!scattered)throw Error('APC did not scatter pigeons');return {scattered};},
  testPassage(){const e=events[0];if(!e?.p)throw Error('Ambient passage fixture missing');const p=e.p.slice(),saved=player.position.clone();player.position.set(p[0]-1.3,world.ground(p[0]-1.3,p[2]),p[2]);player.velocity.set(0,0,0);const start=player.position.x;for(let i=0;i<180;i++){player.update(1/60,{x:1,y:0},0);update(1/60,world.daylight,false,true);}const travel=player.position.x-start;player.position.copy(saved);player.velocity.set(0,0,0);player.actor.root.position.copy(saved);if(travel<3)throw Error('Ambient object blocked player');return {travel};},
  testScatter(){const flock=events.find(e=>e.kind==='pigeons');if(!flock)throw Error('Pigeon test needs a flock');const save=player.position.clone();const target=flock.birds[0].p.slice();player.position.set(target[0],world.ground(target[0],target[2]),target[2]+3.2);player.velocity.set(0,0,0);let reached=false;for(let i=0;i<180;i++){player.update(1/60,{x:0,y:-1},0);update(1/60,1,false,true);if(flock.scattered)reached=true;}const travel=target[2]+3.2-player.position.z;player.position.copy(save);player.velocity.set(0,0,0);player.actor.root.position.copy(save);if(!reached||travel<3)throw Error('Pigeons failed to scatter or blocked player');return {scattered:reached,travel,scatterCount};},
  testAnimation(){const e=events.find(e=>e.mixer);if(!e)throw Error('Animal required');action(e,'Walking');e.mixer.update(.3);const values=[];for(const time of [.1,.8]){e.mixer.setTime(time);e.root.updateMatrixWorld(true);const sample=[];e.body.traverse(o=>{if(o.isBone)sample.push(...o.quaternion.toArray());});values.push(sample);}const delta=Math.max(...values[0].map((v,i)=>Math.abs(v-values[1][i])));e.mixer.setTime(.45);groundAnimal(e);if(delta<.001)throw Error('Animal walk clip did not move');return {delta,action:e.action};},
  testPause(){const before=JSON.stringify(api.report());update(30,world.daylight,true);return before===JSON.stringify(api.report());}
 };
 if(testType&&active){if(!intervals[testType])throw Error('Unknown ambient test type');await spawn(testType);update(1/60,world.daylight);}
 return api;
}
