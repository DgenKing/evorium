import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';import fs from 'node:fs';import {pathfind,pathfindFast,slotPosition,transformRoutes,buildCityRouteGraph} from '../evorium/static/world3d/js/graph.js';import {selectAnimation} from '../evorium/static/world3d/js/anim.js';import {detectQuality,Watchdog} from '../evorium/static/world3d/js/quality.js';import {lookupCast,createCastCache} from '../evorium/static/world3d/js/cast.js';
const data=n=>JSON.parse(fs.readFileSync(new URL('../evorium/static/world3d/data/'+n+'.json',import.meta.url)));
const graph=data('routes'),waypoints=data('waypoints');const small={nodes:{a:[0,0,0],b:[1,0,0],c:[2,0,0],d:[1,0,2]},edges:[['a','b'],['b','c'],['a','d'],['d','c']]};assert.deepEqual(pathfind(small,'a','c'),['a','b','c']);assert.deepEqual(pathfind(small,'a','missing'),[]);
assert.deepEqual(pathfindFast(small,'a','c'),pathfind(small,'a','c'));assert.deepEqual(pathfindFast(small,'a','missing'),[]);const cityRouteData={routes:{nodes:{a:[1,0,0]},edges:[]},waypoints:{p:{position:[1,2,0],yaw:0}}};transformRoutes(cityRouteData,[10,20],90);assert.ok(Math.abs(cityRouteData.routes.nodes.a[0]-10)<1e-8&&Math.abs(cityRouteData.routes.nodes.a[2]-19)<1e-8);assert.ok(Math.abs(cityRouteData.waypoints.p.position[0]-10)<1e-8&&Math.abs(cityRouteData.waypoints.p.position[2]-19)<1e-8&&Math.abs(cityRouteData.waypoints.p.yaw-Math.PI/2)<1e-8);const cityGraph=buildCityRouteGraph({vertices:[[0,0,0],[1,0,0],[1,0,1],[0,0,1],[2,0,0],[2,0,1]],polygons:[[0,1,2,3],[1,4,5,2]],portals:[],graph:{nodes:{n0:[.5,0,.5],n1:[1.5,0,.5]},edges:[['n0','n1']] }},{A:{position:[.1,0,.5],yaw:0},B:{position:[1.9,0,.5],yaw:0}},{nodes:{STREET_LEFT:[0,0,0],STREET_RIGHT:[2,0,1],UPSTAIRS:[0,0,1]},edges:[]});assert.deepEqual(pathfindFast(cityGraph,'A','B'),['A','n0','n1','B']);
const splitCity=buildCityRouteGraph({graph:{nodes:{west:[-24,0,0],east:[24,0,0]},edges:[]}},{},{nodes:{STREET_LEFT:[-1,0,0],STREET_RIGHT:[1,0,0]},edges:[]});assert.ok(pathfindFast(splitCity,'west','east').length,'Henry Street bridges the generated road cutout');
for(const end of ['STREET_LEFT','STREET_RIGHT'])for(const waypoint of [...Object.keys(waypoints),'UPSTAIRS'])assert.ok(pathfind(graph,end,waypoint).length,`${end} cannot reach ${waypoint}`);
for(const [values,expected] of [[{},'idle'],[{speed:1.6},'walk'],[{speed:4},'run'],[{grounded:false,verticalSpeed:2},'jump_start'],[{grounded:false,verticalSpeed:-1},'fall'],[{wasGrounded:false},'land'],[{sitting:true},'sit'],[{talking:true},'talk']])assert.equal(selectAnimation(values),expected);
assert.equal(detectQuality({touch:true}),'low');assert.equal(detectQuality({width:390}),'low');assert.equal(detectQuality({maxTextureSize:16384,pixelRatio:2}),'high');assert.equal(detectQuality({maxTextureSize:8192}),'medium');
assert.deepEqual(slotPosition({position:[1,2,3],yaw:0},2),[2.4,2,3]);assert.ok(Math.abs(slotPosition({position:[0,0,0],yaw:Math.PI/2},1)[2]+.7)<1e-8);
const cast=data('cast');
const seedPath=fileURLToPath(new URL('../evorium/seed.py',import.meta.url));
const people=JSON.parse(execFileSync('python3',['-c',
 'import runpy, json, sys; print(json.dumps([row[0] for row in runpy.run_path(sys.argv[1])["CHARACTERS"]]))',
 seedPath],{cwd:new URL('..',import.meta.url),encoding:'utf8'}));
assert.deepEqual(Object.keys(cast).sort(),['player',...people].sort());
assert.equal(lookupCast(cast,'Jess Hartley').body,'female');
assert.throws(()=>lookupCast(cast,'unknown'),/Missing cast model/);
const watchdog=new Watchdog();let preset='high';for(let i=0;i<110;i++)preset=watchdog.update(.1,preset);assert.equal(preset,'low');assert.equal(watchdog.drops,2);
console.log('Web3D: graph, all waypoint routes, animation, quality, watchdog, slots and cast passed.');

const models=new Set();
const budgets=data('budgets');
function readModel(quality, model){
 const catalog=new URL(`../evorium/static/world3d/assets/${quality}/${model}`,import.meta.url);
 const file=fs.readFileSync(catalog);
 assert.equal(file.toString('ascii',0,4),'glTF',model);
 const length=file.readUInt32LE(12);
 return {size:file.length,json:JSON.parse(file.toString('utf8',20,20+length))};
}
function jointNames({skins,nodes}){
 return [...new Set(skins.flatMap(skin=>skin.joints.map(index=>nodes[index].name)))].sort();
}
const playerJoints=jointNames(readModel('high',cast.player.model).json);
for(const [name,config] of Object.entries(cast)){
 assert.ok(config.height>1.4&&config.height<2,name);
 assert.ok(config.scale>0 && config.labelOffset>0 && /^#[0-9a-f]{6}$/i.test(config.tint),name);
 assert.ok(!config.fallback,name);
 if(name!=='player')assert.notEqual(config.model,cast.player.model,name);
 assert.match(config.model,/^cast\/[a-z]+\.glb$/);
 assert.ok(!models.has(config.model),`${name} reuses a cast model`);
 models.add(config.model);
 for(const quality of ['low','high']){
  const {size,json}=readModel(quality,config.model);
  const id=config.model.slice('cast/'.length,-'.glb'.length);
  assert.equal(size,budgets[quality].cast[id].bytes,name);
  assert.deepEqual(jointNames(json),playerJoints,name);
  assert.ok(json.meshes.length>=5,`${name} is missing fitted meshes`);
  if(name==='Norman Pilling')assert.ok(json.nodes.some(node=>node.name==='Norman night tie'));
 }
}
const clips=data('clips');assert.equal(new Set(Object.values(clips)).size,10);assert.equal(clips.walk,'Walk_Loop');assert.equal(clips.sit,'Sitting_Idle_Loop');
const loaded=[],modelErrors=[];
const cache=createCastCache(cast,async model=>{
 loaded.push(model);
 if(model===cast['Jess Hartley'].model)throw Error('test missing model');
 return {model};
},error=>modelErrors.push(error));
assert.deepEqual(loaded,[]);
assert.equal((await cache.get('player')).model,cast.player.model);
await assert.rejects(cache.get('unknown'),/Missing cast model/);
assert.deepEqual(loaded,[cast.player.model]);
const jess=cache.get('Jess Hartley');
await assert.rejects(jess,/test missing model/);
assert.equal(cache.get('Jess Hartley'),jess);
for(const name of ['Norman Pilling','Maxine Stott'])assert.equal((await cache.get(name)).model,cast[name].model);
assert.deepEqual(loaded,[cast.player.model,cast['Jess Hartley'].model,cast['Norman Pilling'].model,cast['Maxine Stott'].model]);
assert.deepEqual(modelErrors.map(error=>error.name),['unknown','Jess Hartley']);
console.log('MPFB cast: dedicated models, game-engine joints, ten clips and lazy loading passed.');

const {schedule,allowed,limits,separation,streetGraph,visibleStep,intervals,facing}=await import('../evorium/static/world3d/js/ambient.js');
for(const [kind,[min,max]] of Object.entries(intervals)){assert.equal(schedule(kind,20,()=>0),20+min);assert.equal(schedule(kind,20,()=>1),20+max);assert.equal(schedule(kind,20,()=>.5),20+(min+max)/2);}
for(const kind of ['dog','pigeons']){assert.equal(allowed(kind,.299),false);assert.equal(allowed(kind,.3),true);}
assert.equal(allowed('fox',.299),true);assert.equal(allowed('fox',.3),false);assert.equal(allowed('fox',1),false);
for(const kind of ['cat','rubbish'])for(const d of [0,.3,1])assert.equal(allowed(kind,d),true);
assert.deepEqual(limits('low'),{pigeons:2,events:1});assert.equal(limits('medium').pigeons,4);assert.equal(limits('high').pigeons,5);
assert.deepEqual(separation([0,0,0],[[3,0,0]]),[0,0]);assert.ok(separation([0,0,0],[[.3,0,0]])[0]<0);assert.ok(separation([0,0,0],[[0,0,0]]).every(Number.isFinite));
assert.equal(visibleStep(20,true),0);assert.equal(visibleStep(20,false),.05);assert.equal(visibleStep(-1,false),0);
const street=streetGraph(graph);for(const p of Object.values(street.nodes))assert.ok(p[2]>=.45&&p[2]<=2.75);for(const [a,b] of street.edges)assert.ok(street.nodes[a]&&street.nodes[b]);assert.ok(pathfind(street,'STREET_LEFT','STREET_RIGHT').length);
for(const quality of ['low','high']){const budget=data('budgets')[quality];assert.ok(budget.ambient.bytes<=budget.ambient.limitBytes);assert.ok(budget.bytes<=(quality==='low'?12:30)*1e6);for(const kind of ['cat','dog','fox']){assert.deepEqual(budget.ambient.models[kind].clips.sort(),['Idle','Walking']);assert.ok(fs.existsSync(new URL(`../evorium/static/world3d/assets/${quality}/ambient/${kind}.glb`,import.meta.url)));}}
console.log('Street life: scheduling bounds, day/night boundary, quality caps, separation, hidden pause, street graph and asset budgets passed.');

assert.equal(facing([0,0,0],[1,0,0]),Math.PI/2);assert.equal(facing([0,0,0],[0,0,1]),0);assert.equal(facing([0,0,0],[-1,0,0]),-Math.PI/2);
function directoryBytes(dir){return fs.readdirSync(dir,{withFileTypes:true}).filter(entry=>!/^city(?:-collision|-props)?\.glb$/.test(entry.name)).reduce((sum,entry)=>sum+(entry.isDirectory()?directoryBytes(dir+'/'+entry.name):fs.statSync(dir+'/'+entry.name).size),0);}
for(const quality of ['low','high']){const dir=new URL('../evorium/static/world3d/assets/'+quality,import.meta.url).pathname;assert.equal(directoryBytes(dir),data('budgets')[quality].bytes);assert.equal(directoryBytes(dir+'/ambient'),data('budgets')[quality].ambient.bytes);}
console.log('Street life: movement heading and independent on-disk budget accounting passed.');


// Exercise actor selection/sync without a renderer; importing Three.js is unnecessary here.
const {runInNewContext}=await import('node:vm');
const actorSource=fs.readFileSync(new URL('../evorium/static/world3d/js/npcs.js',import.meta.url),'utf8').replace(/^import .*;$/gm,'').replace('export class Actors','class Actors');
const Actors=runInNewContext(actorSource+'\nActors;', {slotPosition,pathfind,pathfindFast});
const nearbyHuman={person:{kind:'player',account:'thomas',name:'Thomas',visible:true,place:'pub'},root:{position:{distanceTo:()=>.2}}};
const nearbyAPC={person:{kind:'npc',visible:true,place:'pub'},root:{position:{distanceTo:()=>1}}};
const selection={people:new Map([[21,nearbyHuman],[1,nearbyAPC]])};
assert.equal(Actors.prototype.nearestTalk.call(selection,{place:'pub',position:{}}),nearbyHuman);
nearbyHuman.route=[[2,0,2]];
assert.equal(Actors.prototype.nearestTalk.call(selection,{place:'pub',position:{}}),nearbyAPC);
nearbyHuman.route=[];
const requestedModels=[];
const actors=new Actors({}, {}, {routes:{nodes:{STREET_LEFT:[0,0,0],STREET_WAIT:[1,0,0]}},waypoints:{STREET_WAIT:{position:[1,0,0],yaw:0}}}, {ground:()=>0,place:()=> 'street'});
actors.create=async name=>{requestedModels.push(name);return{root:{position:{fromArray(){}}},tag:{}};};
actors.label=()=>{};
await actors.sync({speed:1,characters:[{id:21,name:'Thomas',first:'Thomas',kind:'player',visible:true,place:'street',waypoint:'STREET_WAIT',slot:0}]},true);
assert.equal(requestedModels[0],'player');assert.equal(actors.people.get(21).tag.textContent,'Thomas');
console.log('Accounts: other humans share the player body and are selectable nearby.');

// Incoming APC chat is shown as ordinary dialogue and never replaces an open panel.
const uiSource=fs.readFileSync(new URL('../evorium/static/world3d/js/ui.js',import.meta.url),'utf8').replace(/^import .*;$/gm,'').replaceAll('export ','');
const elements=new Map();const element=id=>{if(!elements.has(id))elements.set(id,{hidden:true,textContent:'',style:{},replaceChildren(){},focus(){}});return elements.get(id);};
let incoming={police:{notice:'PCSO Grace Adeyemi wants a word',outcomes:[]},conversation:{agent_b_id:16,messages:[{speaker_name:'Grace Adeyemi',text:'Can we have a word?',rationale:'PRIVATE'}]}};
const {messageLine}=await import('../evorium/static/world3d/js/player-chat.js');
const UIClass=runInNewContext(uiSource+'\nUI;', {document:{getElementById:element},window:{},request:async()=>incoming,PlayerChat:class {},messageLine,Date,setTimeout,clearTimeout});
const graceActor={person:{id:16,first:'Grace'}};const ui=new UIClass({reset(){},blocked:false},{people:new Map([[16,graceActor]])});
const displayed=[];ui.line=(name,text)=>displayed.push([name,text]);await ui.pollPlayer();
assert.equal(ui.target,graceActor);assert.equal(element('chat').hidden,false);assert.equal(ui.input.blocked,true);
assert.equal(displayed[0][1],'Can we have a word?');assert.ok(!JSON.stringify(displayed).includes('PRIVATE'));
const otherTarget={person:{id:1,first:'Dez'}};ui.target=otherTarget;ui.polledAt=0;await ui.pollPlayer();assert.equal(ui.target,otherTarget);
incoming={police:{notice:'',outcomes:['formal warning']},conversation:null};ui.polledAt=0;await ui.pollPlayer();assert.match(element('police-notice').textContent,/formal warning/);
console.log('Police follow-ups: incoming chat, private rationale, existing-panel isolation and outcome notice passed.');

const weatherSource=fs.readFileSync(new URL('../evorium/static/world3d/js/weather.js',import.meta.url),'utf8').replace(/^import .*;$/gm,'').replaceAll('export ','');
const weatherStyle=runInNewContext(weatherSource+'\nweatherStyle;');
const WeatherClass=runInNewContext(weatherSource+'\nWeatherFX;');
const weatherSwitch={quality:'high',reading:{condition:'rain',raining:true},set(r){this.style=weatherStyle(r,this.quality);}};WeatherClass.prototype.setQuality.call(weatherSwitch,'low');assert.equal(weatherSwitch.style.count,60);
assert.equal(weatherStyle({condition:'unknown'}).count,0);
assert.ok(weatherStyle({condition:'rain',raining:true},'low').count<weatherStyle({condition:'rain',raining:true},'high').count);
assert.equal(weatherStyle({condition:'snow'}).snow,true);assert.equal(weatherStyle({condition:'fog'}).fog,true);
assert.equal(weatherStyle({condition:'rain',raining:true}).dark,true);
console.log('Weather: bounded quality particle counts, unknown fallback, snow, fog and wet lighting passed.');

// E and the touch Talk button share the target dispatch. Human messages use literal text nodes.
const mainSource=fs.readFileSync(new URL('../evorium/static/world3d/js/main.js',import.meta.url),'utf8');
const inputSource=fs.readFileSync(new URL('../evorium/static/world3d/js/input.js',import.meta.url),'utf8');
assert.match(mainSource,/action==='KeyE'.*ui\.talk\(actors\.nearestTalk\(player\)\)/);
assert.match(inputSource,/#talk'\)\.onclick=\(\)=>onAction\('KeyE'\)/);
const dispatch=[];
const target=Actors.prototype.nearestTalk.call(selection,{place:'pub',position:{}});
UIClass.prototype.talk.call({direct:{open:(...args)=>dispatch.push(['player',...args])},
 chat:()=>dispatch.push(['APC'])},target);
assert.deepEqual(dispatch,[['player','thomas','Thomas']]);
function elementForText(tag){
 return {tag,children:[],textContent:'',append(...children){this.children.push(...children);},
   set innerHTML(_){throw Error('Do not parse human chat as HTML');}};
}
const payload='<img src=x onerror=alert(1)>';
const line=messageLine({createElement:elementForText},'<Thomas>',payload);
assert.deepEqual(line.children.map(node=>[node.tag,node.textContent]),[['strong','<Thomas>: '],['span',payload]]);
console.log('Player chat: E dispatches to private chat and renders text literally.');
