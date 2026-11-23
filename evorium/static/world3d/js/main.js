import * as THREE from 'three';
import {CSS2DRenderer} from 'three/addons/renderers/CSS2DRenderer.js';
import {loadAssets,loadData} from './assets.js';
import {presets,detectQuality,Watchdog} from './quality.js';
import {World} from './world.js';import {Input} from './input.js';import {FollowCamera} from './camera.js';import {Player} from './player.js';import {Actors} from './npcs.js';import {Network,request} from './net.js';import {UI,$} from './ui.js';import {pathfind,nearest,distance} from './graph.js';
const params=new URLSearchParams(location.search),test=params.get('test')==='1';
window.__evoriumReady=false;window.__evoriumReport={errors:[]};
addEventListener('error',e=>window.__evoriumReport.errors.push(e.message||String(e.error||'Browser resource error')));addEventListener('unhandledrejection',e=>window.__evoriumReport.errors.push(String(e.reason)));
function stored(key,fallback){try{return localStorage.getItem('evorium3d.'+key)||fallback;}catch{return fallback;}}
function save(key,value){try{localStorage.setItem('evorium3d.'+key,value);}catch{}}
async function boot(){
 if(matchMedia('(pointer:coarse)').matches)$('controls').textContent='Left thumb move · Right drag look · Pinch zoom';
 const canvas=$('world'),scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(55,innerWidth/innerHeight,.08,150);
 const selected=params.get('quality')||stored('quality','auto');let preset=presets[selected]?selected:detectQuality({touch:matchMedia('(pointer:coarse)').matches,width:innerWidth});
 const renderer=new THREE.WebGLRenderer({canvas,antialias:preset==='high',powerPreference:'high-performance'});renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1;
 if(selected==='auto')preset=detectQuality({touch:matchMedia('(pointer:coarse)').matches,width:innerWidth,maxTextureSize:renderer.capabilities.maxTextureSize,pixelRatio:devicePixelRatio});
 function applyPreset(){const p=presets[preset];renderer.setPixelRatio(Math.min(devicePixelRatio,p.pixelRatio));renderer.shadowMap.enabled=!!p.shadows;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.setSize(innerWidth,innerHeight);}
 applyPreset();const labels=new CSS2DRenderer({element:$('labels')});labels.setSize(innerWidth,innerHeight);
 const data=await loadData(),assets=await loadAssets(presets[preset].assets,p=>{$('progress').value=p;},data.cast);
 const world=new World(scene,assets,presets[preset]),actors=new Actors(scene,assets,data,world),player=new Player(await actors.create('player'),world),follow=new FollowCamera(camera,world);actors.player=player;
 const input=new Input(canvas,async(action,event)=>{if(action==='KeyE'&&!input.blocked)await ui.chat(actors.nearestTalk(player));if(action==='KeyN'){actors.tags=!actors.tags;$('tags').checked=actors.tags;save('tags',actors.tags);}if(action==='KeyC')world.debug.visible=!world.debug.visible;if(action==='F1')$('debug').hidden=!$('debug').hidden;if(action==='Escape'){await ui.closeChat();$('settings').hidden=true;input.blocked=false;}$('card').hidden=action==='Escape'||$('card').hidden;if(action==='pick'&&!input.blocked){const ray=new THREE.Raycaster();ray.setFromCamera(new THREE.Vector2(event.clientX/innerWidth*2-1,1-event.clientY/innerHeight*2),camera);const candidates=[...actors.people.values()];for(const hit of ray.intersectObjects(candidates.map(a=>a.body),true)){const a=candidates.find(a=>{let n=hit.object;while(n){if(n===a.root)return true;n=n.parent;}return false;});if(a){ui.card(a.person);break;}}}});
 const ui=new UI(input,actors);actors.onSelect=p=>ui.card(p);actors.tags=stored('tags','true')!=='false';follow.invert=stored('invert','false')==='true';follow.sensitivity=Number(stored('sensitivity','1'));
 $('tags').checked=actors.tags;$('invert').checked=follow.invert;$('sensitivity').value=follow.sensitivity;$('quality').value=preset;
 $('settings-button').onclick=()=>{$('settings').hidden=!$('settings').hidden;input.blocked=!$('settings').hidden;input.reset();};$('close-settings').onclick=()=>{$('settings').hidden=true;input.blocked=false;};
 $('tags').onchange=e=>{actors.tags=e.target.checked;save('tags',actors.tags);};$('invert').onchange=e=>{follow.invert=e.target.checked;save('invert',follow.invert);};$('sensitivity').oninput=e=>{follow.sensitivity=Number(e.target.value);save('sensitivity',follow.sensitivity);};$('quality').onchange=e=>{save('quality',e.target.value);const url=new URL(location);url.searchParams.set('quality',e.target.value);location.assign(url);};
 let ambient=null;const ambientType=test&&params.get('ambient')!=='off'?params.get('ambient'):null;
 $('street-life').checked=stored('street-life','true')!=='false'&&params.get('ambient')!=='off';if(ambientType)$('street-life').checked=true;$('street-life').onchange=e=>{save('street-life',e.target.checked);ambient?.setEnabled(e.target.checked&&params.get('ambient')!=='off');};
 let snapshot=await request('/world/scene');world.updateSnapshot(snapshot);if(ambientType||params.get('cam')==='ambient'){world.target=(ambientType||params.get('focus'))==='fox'?.12:1;snapshot.daylight=world.target;}if(test)world.daylight=snapshot.daylight;await actors.sync(snapshot,test);const net=new Network(async s=>{snapshot=s;world.updateSnapshot(s);await actors.sync(s,false);await ui.pollPlayer();},text=>ui.banner(text));if(!test)net.poll();
 let joined=snapshot.player?.place||'',doorBusy=false;
 async function doors(){const target=player.place;if(target===joined||doorBusy)return;doorBusy=true;try{await request('/player/enter',{place:target});joined=target;}catch(e){ui.toast(e.message);player.position.set(target==='pub'?-4.62:5.92,.06,.9);player.velocity.set(0,0,0);}finally{doorBusy=false;}}
 const studio=test&&['lineup','head','body'].includes(params.get('cam')),pose=data.clips[params.get('pose')]?params.get('pose'):'idle';let lineup=[];
 if(studio){
 world.set.visible=false;world.daylight=1;world.target=1;world.scene.fog.near=45;world.sun.position.set(-5,10,8);
 const floor=new THREE.Mesh(new THREE.PlaneGeometry(40,40),new THREE.MeshStandardMaterial({color:0x9da6a7,roughness:1}));floor.rotation.x=-Math.PI/2;floor.receiveShadow=true;scene.add(floor);
 for(const [index,[name,config]] of Object.entries(data.cast).entries()){
 let actor=name==='player'?player.actor:[...actors.people.values()].find(a=>a.person.name===name);if(!actor)actor=await actors.create(name);
 actor.root.position.set((index-4)*1.65,0,2);actor.root.rotation.y=0;
 if(!actor.label)actors.label(actor,{first:name==='player'?'Rob':name.startsWith('Mohammed')?'Mo':name.split(' ')[0],name});
 actor.label.visible=true;actor.bubble.hidden=true;actor.expires=0;lineup.push({name,model:config.model,actor});if(name==='player')player.position.copy(actor.root.position);
 }
 if(['head','body'].includes(params.get('cam'))){const selected=params.get('character')||'dez';for(const entry of lineup)entry.actor.root.visible=entry.model===`cast/${selected}.glb`;}
 }
 // Test cameras keep world state deterministic and use the public smoke snapshot.
 const cameras={street:[[-1,4.3,15],[-.5,1,-1]],pub:[[-4.5,2.2,-1.3],[-4.3,1.1,-6]],shop:[[6.4,2.2,-3.2],[2.5,1.2,-5.5]],cast:[[-6,2.3,-1],[-4,1.2,-5]],player:[[-4.62,2.5,5],[-4.62,1,0]]};
 if(test){if(studio){if(['head','body'].includes(params.get('cam'))){const entry=lineup.find(e=>e.actor.root.visible);if(!entry)throw Error('Unknown cast close-up');const head=entry.actor.root.position.clone().add(new THREE.Vector3(0,entry.actor.height*(params.get('cam')==='head'?.87:.5),0));camera.position.copy(head).add(new THREE.Vector3(0,.05,params.get('cam')==='head'?1.2:3.1));camera.lookAt(head);}else{const distance=innerWidth/innerHeight<1?34:12;camera.position.set(0,2.4,distance);camera.lookAt(0,1,2);}}else{const c=cameras[params.get('cam')]||cameras.street;camera.position.fromArray(c[0]);camera.lookAt(new THREE.Vector3().fromArray(c[1]));}}else {await request('/player/enter',{place:player.place});joined=player.place;await ui.initial();}
 if(ambientType||params.get('cam')==='ambient'){const z=(ambientType||params.get('focus'))==='fox'||params.get('debris')==='can'?1.65:1.1;const distance=innerWidth/innerHeight<1?3.8:3.2;camera.position.set(-.7,1.25,z+distance);camera.lookAt(-2.5,.30,z);player.position.set(-3.4,world.ground(-3.4,2.2),2.2);player.actor.root.position.copy(player.position);}
 let visibleTriangles=0,visibleDrawCalls=0;
 let last=performance.now(),fps=0,elapsed=0,frames=0;const watchdog=new Watchdog();
 function report(){return {ambient:ambient?.report(),errors:window.__evoriumReport.errors,loadedAssets:Object.keys(assets).filter(k=>typeof assets[k]!=='function'),loadedCharacters:assets.loadedCharacters(),modelFallbacks:assets.modelFallbacks,quality:preset,drawCalls:renderer.info.render.calls,triangles:renderer.info.render.triangles,visibleTriangles,visibleDrawCalls,textures:renderer.info.memory.textures,geometries:renderer.info.memory.geometries,fps,characters:[...actors.people.values()].map(a=>({id:a.person.id,name:a.person.name,waypoint:a.person.waypoint,position:a.root.position.toArray()})),expectedCharacters:snapshot.characters.filter(p=>p.visible).map(p=>p.id),lineup:lineup.map(e=>({name:e.name,model:e.model,height:e.actor.height,fallback:e.actor.fallback})),pose,collisionOK:!!world.octree,player:{position:player.position.toArray(),actorPosition:player.actor.root.position.toArray(),place:player.place},sim_at:snapshot.sim_at,speed:snapshot.speed};}
 function frame(now){requestAnimationFrame(frame);const wallDt=(now-last)/1000,dt=Math.min(wallDt,.05);last=now;elapsed+=wallDt;frames++;if(elapsed>1){fps=frames/elapsed;elapsed=0;frames=0;}
 if(document.hidden)return;
 const controls=input.sample();if(!test){player.update(dt,controls,follow.yaw);follow.update(dt,player.position,controls);doors();}else if(!studio)player.actor.animate('idle',dt);
 world.update(test?1/60:dt);if(!studio)actors.update(test?1/60:dt,camera);else for(const entry of lineup){entry.actor.animate(pose,1/60);entry.actor.mixer.setTime(Number(params.get('frame')||.5));entry.actor.ground(pose);entry.actor.label.visible=entry.actor.root.visible;}if(test){if(!studio){player.actor.mixer.setTime(.5);player.actor.ground();}player.actor.root.position.copy(player.position);if(!studio)for(const a of actors.people.values()){a.mixer.setTime(.5);a.ground();}}ambient?.update(dt,snapshot.daylight,document.hidden);visibleTriangles=0;visibleDrawCalls=0;scene.traverse(o=>{if(o.isMesh&&!o.userData.counted){o.userData.counted=true;o.onBeforeRender=(_renderer,_scene,_camera,geometry,_material,group)=>{visibleDrawCalls++;visibleTriangles+=(group?.count??geometry.index?.count??geometry.attributes.position.count)/3;};}});renderer.render(scene,camera);labels.render(scene,camera);
 const nearby=actors.nearestTalk(player);$('talk').hidden=!nearby||input.blocked;$('talk-hint').hidden=!nearby||input.blocked;if(nearby)$('talk-hint').textContent='Press E to talk to '+nearby.person.first;
 if(!test){const next=watchdog.update(dt,preset);if(next!==preset){preset=next;ambient?.setQuality(preset);world.preset=presets[preset];world.sun.castShadow=!!presets[preset].shadows;applyPreset();ui.toast('Quality adjusted for smoother walking.');}}
 if(!$('debug').hidden)$('debug').textContent=JSON.stringify({...report(),lastPoll:net.lastPoll},null,2);
 window.__evoriumReport=report();
 }
 requestAnimationFrame(frame);addEventListener('resize',()=>{camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight);labels.setSize(innerWidth,innerHeight);});
 $('loading').hidden=true;await new Promise(r=>setTimeout(r,1500));await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));window.__evoriumReady=true;
 // Start after the first view and visible cast. Each animal GLB loads only when its event is due.
 window.__evoriumAmbientReady=false;
 if(!studio&&params.get('ambient')!=='off'){try{const {createAmbient}=await import('./ambient.js');ambient=await createAmbient({scene,world,graph:data.routes,quality:preset,player,actors,enabled:$('street-life').checked,testType:ambientType,debris:params.get('debris')||'packet'});ambient.setEnabled($('street-life').checked);}catch(e){console.warn('Street life unavailable',e);window.__evoriumReport.errors.push('Street life: '+e.message);}}
 window.__evoriumAmbientReady=true;
 if(test){
 window.__evoriumTest={ambient,renderer,camera,scene,measureCast(){return lineup.map(({name,actor})=>{let minY=Infinity,maxY=-Infinity;actor.root.updateMatrixWorld(true);actor.body.traverse(o=>{if(!o.isMesh)return;if(o.isSkinnedMesh)o.skeleton.update();const p=new THREE.Vector3();for(let i=0;i<o.geometry.attributes.position.count;i++){o.getVertexPosition(i,p);p.applyMatrix4(o.matrixWorld);minY=Math.min(minY,p.y-actor.root.position.y);maxY=Math.max(maxY,p.y-actor.root.position.y);}});return{name,minY,maxY,height:actor.height};});},physics(){
 const saved=player.position.clone(),open={...world.open};let maximum=0;
 player.position.set(1.08,.1,1.2);player.velocity.set(0,0,0);for(let i=0;i<30;i++)player.update(1/60,{x:0,y:0},0);
 const floor=player.position.y;player.update(1/60,{x:0,y:0,jump:true},0);for(let i=0;i<90;i++){player.update(1/60,{x:0,y:0},0);maximum=Math.max(maximum,player.position.y-floor);}if(maximum<.7||!player.grounded)throw Error('Jump/landing check failed');
 player.position.set(-8,.06,-3);player.velocity.set(0,0,0);for(let i=0;i<120;i++)player.update(1/60,{x:-1,y:0},0);const wallX=player.position.x;if(wallX<-8.8)throw Error('Player crossed masonry');
 const cameraDistance=world.cameraDistance(new THREE.Vector3(-8,1.5,-3),new THREE.Vector3(-1,0,0),3.5);if(cameraDistance>1.2)throw Error('Camera crossed wall');
 world.open.pub=false;player.position.set(-4.62,.06,.9);player.velocity.set(0,0,0);for(let i=0;i<100;i++)player.update(1/60,{x:0,y:-1},0);if(player.position.z<.25)throw Error('Closed door crossed');
 const closedDoorZ=player.position.z;world.open=open;player.position.copy(saved);player.velocity.set(0,0,0);return{jumpHeight:maximum,wallX,cameraDistance,closedDoorZ};
 },refresh:async()=>{snapshot=await request('/world/scene');world.updateSnapshot(snapshot);await actors.sync(snapshot,true);return report();},
 async movement(){
 const status=await request('/smoke/status');if(!status.fake_models)throw Error('Movement test requires verified offline smoke server');
 const events=[],results=[];player.position.set(-4.62,.06,1.5);player.place='street';joined='';await request('/player/leave',{});
 for(const destination of ['PUB_BAR','STREET_LINK','NEWS_TILL','STREET_LINK']){
 const route=pathfind(data.routes,nearest(data.routes,player.position.toArray()),destination);if(!route.length)throw Error('No route to '+destination);
 for(const node of route){const target=new THREE.Vector3().fromArray(data.routes.nodes[node]);let steps=0;
 while(Math.hypot(player.position.x-target.x,player.position.z-target.z)>.12&&steps++<900){const delta=target.clone().sub(player.position);player.update(1/60,{x:delta.x/Math.max(.1,Math.hypot(delta.x,delta.z)),y:delta.z/Math.max(.1,Math.hypot(delta.x,delta.z)),run:false,jump:false},0);const before=joined;await doors();if(joined!==before)events.push(joined||'leave');}
 if(steps>=900)throw Error('Player stuck on '+node+' '+player.position.toArray());
 }
 const remaining=distance(player.position.toArray(),data.routes.nodes[destination]);player.setCollider();const collision=world.octree.capsuleIntersect(player.collider);if(remaining>2||collision&&collision.depth>.025)throw Error('Movement failed '+destination);
 results.push({destination,distance:remaining,collisionDepth:collision?.depth||0});
 }
 const npc=actors.nearestTalk(player);return{results,events,report:report()};
 },async chat(){const status=await request('/smoke/status');if(!status.fake_models)throw Error('Fake server required');const a=[...actors.people.values()].find(a=>a.person.place==='pub');await request('/player/enter',{place:'pub'});await ui.chat(a);$('message').value='Hello from the offline browser test';await ui.send();const text=$('chat-log').textContent;if(!text.includes('FAKE REPLY')||text.includes('rationale'))throw Error('Chat check failed');await ui.closeChat();await request('/player/leave',{});return{text};},world,player,actors};
 }
}
boot().catch(error=>{window.__evoriumReport.errors.push(error.stack||error.message);$('load-status').textContent='Could not open the street: '+error.message;});
