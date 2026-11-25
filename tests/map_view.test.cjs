/* Optional frontend checks: node --test tests/map_view.test.cjs. No packages. */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const PUB = 'The Crooked Billet, Ancoats, Manchester';
const SHOP = "Patel's News, Ancoats";

function mapHarness(agents) {
  const elements = new Map();
  const painted=[];
  const drawing={clearRect(){},save(){},restore(){},transform(){},setTransform(){},fillRect(){},beginPath(){},moveTo(){},lineTo(){},closePath(){},fill(){},stroke(){},arc(){},fillText(value){painted.push(String(value));},measureText:()=>({width:24}),drawImage(){}};
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      hidden: false, innerHTML: '', style: {}, dataset: {},
      addEventListener() {}, setAttribute() {}, focus() {},
      getContext: () => drawing, querySelectorAll: () => [],clientWidth:960,clientHeight:600,
      getBoundingClientRect: () => ({width:960,height:600,left:0,top:0})
    });
    return elements.get(id);
  }
  const context = vm.createContext({
    $:element, latestAgents:agents, latestUsage:{speed:1,places:[
      {key:'pub',name:PUB,label:'The Crooked Billet'},
      {key:'shop',name:SHOP,label:"Patel's News"},
      {key:'street',name:'Henry Street, Ancoats',label:'Henry Street'}
    ]},latestConv:null,latestPlayer:null,
    esc:String, portraits:{}, performance:{now:()=>0},
    document:{visibilityState:'visible',addEventListener() {}},
    localStorage:{getItem:()=>null,setItem() {}}, history:{replaceState() {}},
    location:{hash:'',pathname:'/',search:''},
    window:{addEventListener() {}}, requestAnimationFrame:()=>1,cancelAnimationFrame() {}
  });
  // Inspect the closure in the test VM without exposing implementation state in the app.
  const source=readFileSync('evorium/static/map.js','utf8').replace(
    'window.evoriumMap={update,places:PLACES,getZoom:()=>zoom,zoomAt,wholeArea,',
    'window.evoriumMap={update,people,targetFor,advance,walkSpeed,labelName,getSpeakers:()=>speakers,places:PLACES,getZoom:()=>zoom,zoomAt,wholeArea,'
  );
  vm.runInContext(source,context);
  return {context,map:context.window.evoriumMap,painted};
}
const agent=(id,name,location=PUB,activity='in for a drink')=>({id,name,location,activity});
function update(h,agents) { h.context.latestAgents=agents;h.map.update(); }
function finish(map,person) {
  for(let n=0;n<1000&&person.route.length;n++) map.advance(person,.1,0);
  assert.equal(person.route.length,0);
}

test('known places accept unknown activities; away and upstairs remain off map',()=>{
  const {map}=mapHarness([]);
  assert.equal(map.targetFor(agent(1,'Unknown',PUB,'new activity')),'pub');
  assert.equal(map.targetFor(agent(1,'Unknown',SHOP,'new activity')),'shop');
  assert.equal(map.targetFor(agent(1,'Dez','Flat above The Crooked Billet')),null);
  assert.equal(map.targetFor(agent(1,'Mo','Manchester','driving')),null);
  assert.equal(map.targetFor(agent(1,'Tommy','Ancoats','walking to the shops')),'street');
  assert.equal(map.targetFor(agent(1,'Unknown','Ancoats','about')),null);
});

test('first load snaps to unique spots, polls retain reservations',()=>{
  const agents=Array.from({length:8},(_,i)=>agent(i+1,'Person '+i));
  const h=mapHarness(agents),people=[...h.map.people.values()];
  assert.equal(new Set(people.map(p=>p.spot.key)).size,8);
  assert.ok(people.every(p=>p.route.length===0&&p.x===p.spot.x&&p.y===p.spot.y));
  const keys=people.map(p=>p.spot.key);
  update(h,[...agents].reverse());
  assert.deepEqual(people.map(p=>p.spot.key),keys);
});

test('staff use distinct slots; Tommy and darts have dedicated spots',()=>{
  const h=mapHarness([agent(1,'Dez',PUB,'behind the bar'),agent(2,'Jess',PUB,'working the bar'),agent(3,'Tommy',PUB,'at his usual table'),agent(4,'Mohammed',PUB,'here for darts and company')]);
  const p=id=>h.map.people.get(String(id));
  assert.equal(p(1).spot.key,'staff-0');assert.equal(p(2).spot.key,'staff-1');
  assert.equal(p(3).spot.key,'tommy-0');assert.equal(p(4).spot.key,'darts-0');
});

test('building changes pass through both doors; later changes catch up rather than queue',()=>{
  const h=mapHarness([agent(1,'Raj')]),p=h.map.people.get('1');
  update(h,[agent(1,'Raj',SHOP,'behind the counter')]);
  assert.ok(p.route.some(v=>v.x===100&&v.y===422));
  assert.ok(p.route.some(v=>v.x===880&&v.y===422));
  finish(h.map,p);assert.equal(p.x,p.spot.x);assert.equal(p.y,p.spot.y);
  update(h,[agent(1,'Raj',PUB)]);
  assert.ok(p.route.length>0);
  update(h,[agent(1,'Raj',SHOP,'browsing')]);
  assert.equal(p.route.length,0);assert.equal(p.x,p.spot.x);assert.equal(p.y,p.spot.y);
});

test('upstairs departure and arrival use the internal stair door, including shop visits',()=>{
  const h=mapHarness([agent(1,'Dez',PUB,'behind the bar')]),p=h.map.people.get('1');
  update(h,[agent(1,'Dez','Flat above The Crooked Billet','off duty upstairs')]);
  assert.equal(p.route.at(-1).x,74);assert.equal(p.route.at(-1).y,151);
  finish(h.map,p);assert.equal(p.visible,false);
  update(h,[agent(1,'Dez',SHOP,'buying supplies')]);
  assert.equal(p.x,74);assert.equal(p.y,151);
  assert.ok(p.route.some(v=>v.x===100&&v.y===422));
  finish(h.map,p);assert.equal(p.visible,true);
  update(h,[agent(1,'Dez','Flat above The Crooked Billet','asleep')]);
  assert.ok(p.route.some(v=>v.x===880&&v.y===422));
  assert.equal(p.route.at(-1).x,74);
});

test('ordinary arrivals and departures use the street, speed caps, idle stays local',()=>{
  const h=mapHarness([agent(1,'Jess','Home','asleep')]),p=h.map.people.get('1');
  assert.equal(p.visible,false);
  update(h,[agent(1,'Jess',PUB,'working the bar')]);
  assert.ok(p.x<0||p.x>960);finish(h.map,p);
  h.map.advance(p,0,20);
  assert.ok(p.route.every(v=>Math.abs(v.x-p.spot.x)<=7&&v.y===p.spot.y));
  finish(h.map,p);
  h.context.latestUsage={speed:10000};h.map.update();assert.ok(h.map.walkSpeed()<=310);
  update(h,[agent(1,'Jess','Home','asleep')]);
  assert.ok(p.route.at(-1).x<0||p.route.at(-1).x>960);
  finish(h.map,p);assert.equal(p.visible,false);
});

test('only running conversations mark speakers; player has a separate unoccupied spot',()=>{
  const h=mapHarness([agent(1,'Dez'),agent(2,'Chloe')]);
  h.context.latestPlayer={id:9,name:'Sam',place:'pub'};
  h.context.latestConv={status:'running',location:PUB,messages:[{speaker_id:1},{speaker_id:2}]};
  h.map.update();
  assert.deepEqual([...h.map.getSpeakers()],['1','2']);
  assert.equal(new Set([...h.map.people.values()].map(p=>p.spot.key)).size,3);
  assert.equal(h.map.people.get('player-9').agent.isPlayer,true);
  h.context.latestConv.status='completed';h.map.update();assert.equal(h.map.getSpeakers().size,0);
});


test('map shows the local player and other named players independently, including the street',()=>{
  const h=mapHarness([agent(1,'Dez')]);
  h.context.latestPlayer={id:20,name:'Rob',place:'street',other_players:[{id:21,name:'Thomas',place:'pub'}]};
  h.map.update();
  const self=h.map.people.get('player-20'),friend=h.map.people.get('player-21');
  assert.ok(self.visible&&friend.visible);
  assert.equal(self.target,'street');assert.equal(friend.target,'pub');
  assert.equal(h.map.labelName(self.agent),'You');assert.equal(h.map.labelName(friend.agent),'Thomas');
  h.context.latestPlayer.other_players=[];h.map.update();
  assert.equal(h.map.people.has('player-21'),false);assert.equal(h.map.people.has('player-20'),true);
});

const cityData={bounds:[[-200,-150],[200,150]],henry:{position:[4.9,5.48],rotation_degrees:41.8,size:[35.1,23.4]},
  buildings:[{id:'way/99',type:'commercial',shape:[[30,20],[40,20],[40,30],[30,30]]}],roads:[],open_spaces:[],trees:[]};

test('zoom stays in range and Whole area resets the view',()=>{
  const h=mapHarness([]);h.map.setCityData(cityData);
  assert.equal(h.map.getZoom(),1);h.map.zoomAt(6);assert.equal(h.map.getZoom(),6);
  h.map.zoomAt(99);assert.equal(h.map.getZoom(),8.5);h.map.zoomAt(.01);assert.equal(h.map.getZoom(),1);
  h.map.zoomAt(6);h.map.wholeArea();assert.equal(h.map.getZoom(),1);
});

test('a new OSM place in the single places list is labelled on the map',()=>{
  const h=mapHarness([]);h.map.setCityData(cityData);
  h.map.places.push({key:'arcade',name:'Back-street Arcade',osmId:'way/99',locations:['Back-street Arcade, Ancoats'],occupants:'arcade'});
  assert.equal(h.map.targetFor(agent(99,'Peggy','Back-street Arcade, Ancoats')),'place:arcade');
  h.context.latestAgents=[agent(99,'Peggy','Back-street Arcade, Ancoats')];h.map.update();
  assert.ok(h.map.people.get('99').visible);
  h.map.render();
  assert.ok(h.painted.includes('Back-street Arcade'));assert.ok(h.painted.includes('Peggy'));
});

test('short greetings render only while current and at the speaker’s place',()=>{
  const h=mapHarness([agent(1,'Dez')]);h.map.setCityData(cityData);
  const now=Date.now()/1000;
  h.context.latestUsage.greetings=[
    {id:1,place:'pub',text:'Morning!',start:now-1},
    {id:1,place:'shop',text:'Wrong venue',start:now-1},
    {id:1,place:'pub',text:'Too old',start:now-10},
    {id:1,place:'pub',text:'Too early',start:now+10}
  ];
  h.map.update();h.map.render();
  assert.ok(h.painted.includes('Morning!'));
  for(const hidden of ['Wrong venue','Too old','Too early'])assert.ok(!h.painted.includes(hidden));
});
