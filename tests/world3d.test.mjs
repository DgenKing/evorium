import assert from 'node:assert/strict';import fs from 'node:fs';import {pathfind,pathfindFast,slotPosition,transformRoutes,buildCityRouteGraph} from '../evorium/static/world3d/js/graph.js';import {selectAnimation} from '../evorium/static/world3d/js/anim.js';import {detectQuality,Watchdog} from '../evorium/static/world3d/js/quality.js';import {lookupCast,createCastCache} from '../evorium/static/world3d/js/cast.js';
const data=n=>JSON.parse(fs.readFileSync(new URL('../evorium/static/world3d/data/'+n+'.json',import.meta.url)));
const graph=data('routes'),waypoints=data('waypoints');const small={nodes:{a:[0,0,0],b:[1,0,0],c:[2,0,0],d:[1,0,2]},edges:[['a','b'],['b','c'],['a','d'],['d','c']]};assert.deepEqual(pathfind(small,'a','c'),['a','b','c']);assert.deepEqual(pathfind(small,'a','missing'),[]);
assert.deepEqual(pathfindFast(small,'a','c'),pathfind(small,'a','c'));assert.deepEqual(pathfindFast(small,'a','missing'),[]);const cityRouteData={routes:{nodes:{a:[1,0,0]},edges:[]},waypoints:{p:{position:[1,2,0],yaw:0}}};transformRoutes(cityRouteData,[10,20],90);assert.ok(Math.abs(cityRouteData.routes.nodes.a[0]-10)<1e-8&&Math.abs(cityRouteData.routes.nodes.a[2]-19)<1e-8);assert.ok(Math.abs(cityRouteData.waypoints.p.position[0]-10)<1e-8&&Math.abs(cityRouteData.waypoints.p.position[2]-19)<1e-8&&Math.abs(cityRouteData.waypoints.p.yaw-Math.PI/2)<1e-8);const cityGraph=buildCityRouteGraph({vertices:[[0,0,0],[1,0,0],[1,0,1],[0,0,1],[2,0,0],[2,0,1]],polygons:[[0,1,2,3],[1,4,5,2]],portals:[],graph:{nodes:{n0:[.5,0,.5],n1:[1.5,0,.5]},edges:[['n0','n1']] }},{A:{position:[.1,0,.5],yaw:0},B:{position:[1.9,0,.5],yaw:0}},{nodes:{STREET_LEFT:[0,0,0],STREET_RIGHT:[2,0,1],UPSTAIRS:[0,0,1]},edges:[]});assert.deepEqual(pathfindFast(cityGraph,'A','B'),['A','n0','n1','B']);
const splitCity=buildCityRouteGraph({graph:{nodes:{west:[-24,0,0],east:[24,0,0]},edges:[]}},{},{nodes:{STREET_LEFT:[-1,0,0],STREET_RIGHT:[1,0,0]},edges:[]});assert.ok(pathfindFast(splitCity,'west','east').length,'Henry Street bridges the generated road cutout');
for(const end of ['STREET_LEFT','STREET_RIGHT'])for(const waypoint of [...Object.keys(waypoints),'UPSTAIRS'])assert.ok(pathfind(graph,end,waypoint).length,`${end} cannot reach ${waypoint}`);
for(const [values,expected] of [[{},'idle'],[{speed:1.6},'walk'],[{speed:4},'run'],[{grounded:false,verticalSpeed:2},'jump_start'],[{grounded:false,verticalSpeed:-1},'fall'],[{wasGrounded:false},'land'],[{sitting:true},'sit'],[{talking:true},'talk']])assert.equal(selectAnimation(values),expected);
assert.equal(detectQuality({touch:true}),'low');assert.equal(detectQuality({width:390}),'low');assert.equal(detectQuality({maxTextureSize:16384,pixelRatio:2}),'high');assert.equal(detectQuality({maxTextureSize:8192}),'medium');
assert.deepEqual(slotPosition({position:[1,2,3],yaw:0},2),[2.4,2,3]);assert.ok(Math.abs(slotPosition({position:[0,0,0],yaw:Math.PI/2},1)[2]+.7)<1e-8);
const cast=data('cast');assert.equal(Object.keys(cast).length,11);assert.equal(lookupCast(cast,'Jess Hartley').body,'female');assert.equal(lookupCast(cast,'unknown'),cast.player);
const watchdog=new Watchdog();let preset='high';for(let i=0;i<110;i++)preset=watchdog.update(.1,preset);assert.equal(preset,'low');assert.equal(watchdog.drops,2);
console.log('Web3D: graph, all waypoint routes, animation, quality, watchdog, slots and cast passed.');

for(const [name,config] of Object.entries(cast)){assert.ok(config.height>1.4&&config.height<2);if(config.fallback){assert.equal(config.model,null);continue;}assert.match(config.model,/^cast\/[a-z]+\.glb$/);for(const quality of ['low','high'])assert.ok(fs.existsSync(new URL('../evorium/static/world3d/assets/'+quality+'/'+config.model,import.meta.url)),name);}
const clips=data('clips');assert.equal(new Set(Object.values(clips)).size,10);assert.equal(clips.walk,'Walk_Loop');assert.equal(clips.sit,'Sitting_Idle_Loop');
let loaded=[],fallbacks=[];const cache=createCastCache(cast,async model=>{loaded.push(model);if(model.includes('jess'))throw Error('test missing model');return{model};},async()=>({gltf:{fallback:true},animations:{}}),item=>fallbacks.push(item));
assert.equal(loaded.length,0);const rob=await cache.get('player');assert.equal(rob.fallback,false);await cache.get('unknown');assert.equal(loaded.length,1);const jess=await cache.get('Jess Hartley');assert.equal(jess.fallback,true);assert.equal(fallbacks.length,1);await cache.get('Jess Hartley');assert.equal(fallbacks.length,1);assert.equal(loaded.length,2);
// Stand-ins until they get their own models: nobody uses the bare mannequin.
assert.equal(cast['Norman Pilling'].model,'cast/tommy.glb');assert.equal(cast['Maxine Stott'].model,'cast/brenda.glb');
assert.ok(Object.values(cast).every(config=>!config.fallback),'no planned mannequin fallbacks');
console.log('MPFB cast: all models, dimensions, ten clips, lazy caching and fallback passed.');

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
const nearbyHuman={person:{kind:'player',visible:true,place:'pub'},root:{position:{distanceTo:()=>.2}}};
const nearbyAPC={person:{kind:'npc',visible:true,place:'pub'},root:{position:{distanceTo:()=>1}}};
const selection={people:new Map([[21,nearbyHuman],[1,nearbyAPC]])};
assert.equal(Actors.prototype.nearestTalk.call(selection,{place:'pub',position:{}}),nearbyAPC);
nearbyAPC.route=[[2,0,2]];
assert.equal(Actors.prototype.nearestTalk.call(selection,{place:'pub',position:{}}),undefined);
selection.people.delete(1);
assert.equal(Actors.prototype.nearestTalk.call(selection,{place:'pub',position:{}}),undefined);
const requestedModels=[];
const actors=new Actors({}, {}, {routes:{nodes:{STREET_LEFT:[0,0,0],STREET_WAIT:[1,0,0]}},waypoints:{STREET_WAIT:{position:[1,0,0],yaw:0}}}, {ground:()=>0,place:()=> 'street'});
actors.create=async name=>{requestedModels.push(name);return{root:{position:{fromArray(){}}},tag:{}};};
actors.label=()=>{};
await actors.sync({speed:1,characters:[{id:21,name:'Thomas',first:'Thomas',kind:'player',visible:true,place:'street',waypoint:'STREET_WAIT',slot:0}]},true);
assert.equal(requestedModels[0],'player');assert.equal(actors.people.get(21).tag.textContent,'Thomas');
console.log('Accounts: other humans use the player body and cannot receive an E-talk prompt.');

// Incoming APC chat is shown as ordinary dialogue and never replaces an open panel.
const uiSource=fs.readFileSync(new URL('../evorium/static/world3d/js/ui.js',import.meta.url),'utf8').replace(/^import .*;$/gm,'').replaceAll('export ','');
const elements=new Map();const element=id=>{if(!elements.has(id))elements.set(id,{hidden:true,textContent:'',style:{},replaceChildren(){},focus(){}});return elements.get(id);};
let incoming={police:{notice:'PCSO Grace Adeyemi wants a word',outcomes:[]},conversation:{agent_b_id:16,messages:[{speaker_name:'Grace Adeyemi',text:'Can we have a word?',rationale:'PRIVATE'}]}};
const UIClass=runInNewContext(uiSource+'\nUI;', {document:{getElementById:element},window:{},request:async()=>incoming,Date,setTimeout,clearTimeout});
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
