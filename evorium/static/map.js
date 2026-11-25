/* Read-only neighbourhood map: one city-data fetch at startup, then cached rendering. */
(() => {
  'use strict';
  const WIDTH = 960, HEIGHT = 600;
  const WALK_SPEED = 68, MAX_WALK_SPEED = 310, SPRITE_SCALE = 1.35;
  const COLOURS = {
    ground:'#777363', pavement:'#b4ac96', road:'#575957', wall:'#674c3e',
    pubFloor:'#b29b78', shopFloor:'#b5b29c', wood:'#73513b', trim:'#d5b881',
    ink:'#f4e9cf', shadow:'#302e29', foliage:'#626d4e'
  };
  const DOORS = {pub:{x:100,y:422}, shop:{x:880,y:422}};
  const STREET_Y = 467;
  // One registry drives the map labels, occupants and zoom targets. Add a row here
  // to place a future OSM building on the overview and expose its occupants.
  const PLACES = [];
  // Placement within the existing Henry Street artwork is in kit-local metres.
  const HENRY_ANCHORS = {pub:[-8,0],shop:[10,0],street:[0,-7]};
  const CITY_DATA_URL='/static/world3d/data/map2d.json';
  let cityMap=null, zoom=1, panX=0, panY=0, mapCenter=null, pointers=new Map(), drag=null, tapTime=0;
  const zoomRange={min:1,max:8.5};
  if(typeof fetch==='function') fetch(CITY_DATA_URL).then(r=>r.ok?r.json():null).then(data=>{cityMap=data;render();}).catch(()=>{});
  const STAIRS = {x:74,y:151};
  const points = (prefix, room, coords) => coords.map(([x,y],i)=>({key:`${prefix}-${i}`,room,x,y}));
  const BEHIND_BAR = points('staff','pub',[[170,179],[290,179],[365,179]]);
  const TOMMY_TABLE = points('tommy','pub',[[446,285],[482,285]]);
  const DARTS = points('darts','pub',[[470,206],[432,206]]);
  const PUB_SEATS = points('seat','pub',[[139,270],[223,270],[289,270],[373,270],[139,357],[223,357],[289,357],[373,357]]);
  const BAR_STOOLS = points('stool','pub',[[163,235],[272,235],[382,235]]);
  const TILL = points('till','shop',[[867,181],[818,181]]);
  const SHOP_CUSTOMER = points('customer','shop',[[867,247],[766,275],[766,330],[719,365],[819,365],[867,335],[719,325],[766,220],[867,285]]);
  const STREET_SPOTS = points('street','street',[[180,467],[350,467],[520,467],[690,467],[830,467],[100,500],[300,500],[600,500],[800,500]]);
  const SPRITES = {
    Dez:{hair:'#9b9990',top:'#303e40',trousers:'#323239',skin:'#c99b79',stocky:true},
    Jess:{hair:'#49362d',top:'#34373d',trousers:'#343039',skin:'#d1a184',ponytail:true},
    Tommy:{hair:'#c9c9bf',top:'#354761',trousers:'#4c4e52',skin:'#d2aa8c',bald:true,checks:true},
    Raj:{hair:'#26282a',top:'#c7c8ad',trousers:'#55585e',skin:'#af7e58',beard:true},
    Chloe:{hair:'#98744d',top:'#668367',trousers:'#414c59',skin:'#dbb79a',long:true},
    Simon:{hair:'#38302c',top:'#7c7f80',trousers:'#515960',skin:'#cfad90',tie:true},
    Brenda:{hair:'#b7b5aa',top:'#a18bab',trousers:'#565269',skin:'#d1a78f',curly:true,short:true},
    Mohammed:{hair:'#24252a',top:'#333d50',trousers:'#34363b',skin:'#ab7753',beard:true},
    Player:{hair:'#483b33',top:'#e9dfc9',trousers:'#536c7d',skin:'#c79d7a'},
    Default:{hair:'#615346',top:'#a87553',trousers:'#49545b',skin:'#bf9675'}
  };
  const canvas = $('map-canvas'), ctx = canvas.getContext('2d');
  const popup = $('map-popup');
  const people = new Map();
  const spriteFrames = new Map();
  let activeTab = 'dashboard', frameId = null, lastFrame = null, selectedId = null;
  let usage = {}, conversation = null, player = null, initialised = false;
  let speakers = new Set();

  function firstName(agent) { return agent.isPlayer ? (agent.isSelf?'You':agent.name) : agent.name.split(/\s+/)[0]; }
  function spriteDefinition(agent) { return SPRITES[agent.isPlayer?'Player':firstName(agent)] || SPRITES.Default; }
  function labelName(agent) { return firstName(agent)==='Mohammed' ? 'Mo' : firstName(agent); }
  function randomFor(id) {
    let seed = [...String(id)].reduce((n,c)=>(n*31+c.charCodeAt(0))>>>0, 173);
    return () => { seed=(Math.imul(seed,1664525)+1013904223)>>>0; return seed/4294967296; };
  }
  function selectTab(name, focus=false, remember=true) {
    activeTab = name==='map' ? 'map' : 'dashboard';
    for (const view of ['dashboard','map']) {
      const chosen = activeTab===view;
      $(`${view}-view`).hidden=!chosen;
      $(`${view}-tab`).setAttribute('aria-selected',String(chosen));
      $(`${view}-tab`).tabIndex=chosen?0:-1;
    }
    if (remember) {
      try { localStorage.setItem('evorium-view',activeTab); } catch (_) { /* private browsing */ }
      try { history.replaceState(null,'',location.pathname+location.search+(activeTab==='map'?'#map':'')); } catch (_) { /* embedded page */ }
    }
    if (focus) $(`${activeTab}-tab`).focus();
    if (activeTab!=='map') closePopup(false);
    resizeCanvas();
    syncAnimation();
  }
  for (const name of ['dashboard','map']) {
    $(`${name}-tab`).addEventListener('click',()=>selectTab(name));
    $(`${name}-tab`).addEventListener('keydown',event=>{
      if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
      event.preventDefault();
      selectTab(event.key==='Home'?'dashboard':event.key==='End'?'map':activeTab==='map'?'dashboard':'map',true);
    });
  }
  window.addEventListener('hashchange',()=>selectTab(location.hash==='#map'?'map':'dashboard',false,false));
  document.addEventListener('visibilitychange',syncAnimation);
  window.addEventListener('resize',resizeCanvas);

  function resizeCanvas() {
    if (activeTab!=='map') return;
    const bounds=canvas.getBoundingClientRect(), ratio=window.devicePixelRatio || 1;
    canvas.width=Math.max(1,Math.round(bounds.width*ratio));
    canvas.height=Math.max(1,Math.round(bounds.height*ratio));
    ctx.setTransform(canvas.width/WIDTH,0,0,canvas.height/HEIGHT,0,0);
    ctx.imageSmoothingEnabled=false;
    render();
  }
  function rect(x,y,w,h,colour) { ctx.fillStyle=colour;ctx.fillRect(x,y,w,h); }
  function text(value,x,y,size=13,colour=COLOURS.ink,align='left') {
    ctx.fillStyle=colour;ctx.font=`${size}px system-ui, sans-serif`;ctx.textAlign=align;ctx.fillText(value,x,y);
  }
  function building(x,width,floor) {
    rect(x+6,128,width,306,'#39382e');
    rect(x,116,width,306,COLOURS.wall);
    rect(x+9,146,width-18,266,floor);
    rect(x+9,146,width-18,7,'#0002');
  }
  function table(x,y,usual=false) {
    rect(x-33,y-20,66,40,COLOURS.wood);
    rect(x-30,y-17,60,3,'#a27d55');
    for (const dx of [-42,34]) rect(x+dx,y-6,8,17,'#655644');
    rect(x-8,y-8,6,7,'#d4bf91');rect(x+14,y+3,5,5,'#c6bda3');
    if (usual) text("Tommy's table",x,y+40,10,'#574b39','center');
  }
  function drawDoor(room,open) {
    const door=DOORS[room];
    rect(door.x-19,412,38,12,open?'#cbb58e':'#463e36');
    if (open) rect(door.x-21,404,5,28,COLOURS.wood);
    else { rect(door.x-16,415,32,3,'#766550');rect(door.x+9,415,3,3,'#d4b66d'); }
  }
  function drawScene() {
    const shopOpen=!!usage.places?.find(p=>p.key==='shop')?.open;
    rect(0,0,WIDTH,HEIGHT,COLOURS.ground);
    rect(0,433,WIDTH,77,COLOURS.pavement);
    for (let x=0;x<WIDTH;x+=48) rect(x,435,1,72,'#938d7d');
    rect(0,510,WIDTH,90,COLOURS.road);
    rect(0,506,WIDTH,4,'#d7cdb1');
    for (let x=12;x<WIDTH;x+=100) rect(x,554,45,3,'#c0bba2');
    text('← Great Ancoats Street',24,492,12,'#5b5548');
    text('Blossom Street →',936,492,12,'#5b5548','right');
    building(40,480,COLOURS.pubFloor);
    building(540,110,'#786c59');
    building(670,250,COLOURS.shopFloor);
    for(let y=161;y<408;y+=20) rect(50,y,460,1,'#78634522');
    rect(120,193,282,22,COLOURS.wood);
    rect(116,190,290,6,'#c3985c');
    text('BAR',258,207,10,'#e0c6a0','center');
    for (let x=140;x<400;x+=31) { rect(x,151,9,15,'#53604c');rect(x+1,148,7,4,'#baa677'); }
    for (const seat of BAR_STOOLS) rect(seat.x-7,seat.y-2,14,9,'#67503f');
    table(181,267);table(331,267);table(181,354);table(331,354);table(464,278,true);
    rect(62,148,24,24,'#65533d');
    for (let y=152;y<171;y+=5) rect(65,y,18,2,'#cbb58c');
    text('↑ Flat',65,190,10,'#62513d');
    ctx.beginPath();ctx.arc(470,159,12,0,Math.PI*2);ctx.fillStyle='#333d36';ctx.fill();
    ctx.beginPath();ctx.arc(470,159,7,0,Math.PI*2);ctx.fillStyle='#aa6b4e';ctx.fill();
    rect(469,158,3,3,'#ead8a2');text('Darts',470,184,10,'#62513d','center');
    rect(548,150,94,260,'#514c40');
    for(let y=157;y<407;y+=24) { rect(550,y,90,18,'#88785b');rect(557,y+5,3,3,'#544b3e'); }
    text('EMPTY UNIT',595,238,12,'#d1c5ac','center');
    text('Northgate Estates',595,260,9,'#d1c5ac','center');
    rect(804,196,94,20,COLOURS.wood);rect(851,189,19,9,'#4b5049');
    text('TILL',843,210,9,'#e3cfac','center');
    for (const x of [706,797]) {
      rect(x,242,29,88,'#6f674e');
      for (let y=247;y<328;y+=16) for (let i=0;i<3;i++) rect(x+3+i*8,y,6,11,['#a27f5c','#d4c297','#74856c'][i]);
    }
    text('The Crooked Billet',280,137,17,COLOURS.ink,'center');
    text("Patel's News",795,137,17,COLOURS.ink,'center');
    if(usage.calendar?.decorations){for(let i=0;i<16;i++){rect(56+i*28,135+(i%2)*4,4,4,i%2?'#eec95d':'#b9d79b');}}
    drawDoor('pub',!!usage.pub_open);drawDoor('shop',shopOpen);
    if (!usage.pub_open) { rect(49,146,462,266,'#171a2388');text('CLOSED',282,401,12,'#d3c8b4','center'); }
    if (!shopOpen) { rect(679,146,232,266,'#171a2377');text('CLOSED',793,401,12,'#d3c8b4','center'); }
    const ledger=usage.ledger||{}, values=ledger.stats||{};
    for(const [key,x,w] of [['pub',49,462],['shop',679,232]]){
      const closed=key==='pub'?values['pub.closed']:values['shop.open']===0;
      if(closed){
        rect(x,146,w,266,'#575b5b');
        for(let y=150;y<411;y+=12)rect(x,y,w,2,'#333838');
        text('SHUTTERED',x+w/2,288,15,'#e2d8c6','center');
      }
      if((ledger.notices||[]).some(n=>n.place===key)){
        rect(x+8,369,42,34,'#e6d7af');text('NOTICE',x+29,389,8,'#3f382c','center');
      }
    }
    for (const x of [29,935]) { rect(x,374,15,43,'#62523e');rect(x-7,362,29,23,COLOURS.foliage); }
  }
  function nightTint() {
    const match=String(usage.sim_time||'').match(/,\s*(\d{1,2}):(\d{2})/);
    const hour=match?+match[1]+(+match[2]/60):12;
    if(hour>=19 || hour<7) rect(0,102,WIDTH,498,'#15223b88');
    else if(hour>=17) rect(0,102,WIDTH,498,`rgba(101,61,47,${0.12+(hour-17)*0.09})`);
    if((hour>=17 || hour<7) && usage.pub_open) {
      for(const x of [220,350]) { rect(x,414,45,8,'#e4b566');rect(x-8,424,61,14,'#e4b56633'); }
    }
  }
  function drawWeather(time){
    const w=usage.weather||{},snow=w.condition==='snow';if(!w.raining&&!snow)return;
    ctx.save();ctx.strokeStyle='#b8d3e266';ctx.fillStyle='#eef5ffbb';
    for(let i=0;i<(snow?45:70);i++){const x=(i*137+time*.012)%WIDTH,y=440+(i*53+time*(snow?.009:.065))%150;
      if(snow){ctx.fillRect(x,y,2,2);}else{ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x-2,y+7);ctx.stroke();}}
    ctx.restore();
  }
  function drawHud() {
    rect(16,14,WIDTH-32,78,'#252824ec');
    text(usage.sim_time||'Waiting for the simulation…',32,39,16);
    text(`${usage.speed??'—'}× · ${usage.weather?.label||'Weather unavailable'} · Pub ${usage.pub_open?'open':'closed'}`,32,66,13,'#c0b69f');
    text(`In the pub: ${(usage.present||[]).join(', ')||'nobody'}`,WIDTH-32,66,13,'#c0b69f','right');
  }
  function drawSprite(context,person,time=0,scale=SPRITE_SCALE) {
    const d=spriteDefinition(person.agent), moving=person.route?.length>0;
    const step=moving?[0,2,0,-2][Math.floor(time*8+person.phase)%4]:0;
    const gesture=!moving&&person.idleUntil>time;
    const bob=gesture?Math.round(Math.sin(time*7+person.phase)):0;
    const cacheKey=`${person.agent.isPlayer?'Player':firstName(person.agent)}:${step}:${gesture}`;
    let sprite=spriteFrames.get(cacheKey);
    if(!sprite) {
      sprite=document.createElement('canvas');sprite.width=24;sprite.height=36;
      const pixels=sprite.getContext('2d');pixels.translate(12,32);
      const block=(x,y,w,h,c)=>{pixels.fillStyle=c;pixels.fillRect(x,y,w,h);};
      const height=d.short?2:0;
      block(-7,-1,14,3,'#23282144');
      if(person.agent.isPlayer) { pixels.strokeStyle='#fff2d5';pixels.lineWidth=1;pixels.strokeRect(-9.5,-27.5,19,31); }
      block(-5,-8,4,7+step,d.trousers);block(1,-8,4,7-step,d.trousers);
      block(-6,-1+step,5,2,'#292b2c');block(1,-1-step,5,2,'#292b2c');
      block(d.stocky?-7:-6,-17+height,d.stocky?14:12,10-height,d.top);
      block(-8,-16+height,2,8,d.top);block(6,-16+height,2,8,d.top);
      block(-8,-9,2,3,d.skin);
      block(6,gesture?-15:-9,3,3,d.skin);
      block(-5,-25+height,10,9,d.skin);
      block(-5,-26+height,10,3,d.hair);
      if(d.bald) block(-3,-26,6,3,d.skin);
      if(d.long) { block(-6,-24,2,10,d.hair);block(4,-24,2,10,d.hair); }
      if(d.ponytail) block(-8,-24,3,5,d.hair);
      if(d.curly) { block(-6,-25+height,12,3,d.hair);block(-5,-28+height,3,3,d.hair);block(0,-28+height,4,3,d.hair); }
      block(3,-21+height,1,1,'#252625');
      if(d.beard) block(-4,-19+height,8,3,d.hair);
      if(d.tie) { block(-1,-17,2,9,'#4c3844');block(-3,-17,2,3,'#d4d4c7'); }
      if(d.checks) { block(-3,-16,6,8,'#b4a187');block(-1,-16,1,8,'#656b6a');block(-3,-13,6,1,'#656b6a'); }
      spriteFrames.set(cacheKey,sprite);
    }
    context.save();context.translate(Math.round(person.x),Math.round(person.y+bob));
    context.scale(scale*(person.facing||1),scale);context.imageSmoothingEnabled=false;
    context.drawImage(sprite,-12,-32);context.restore();
  }
  function render(time=0) {
    ctx.clearRect(0,0,WIDTH,HEIGHT);
    if(cityMap?.bounds) { drawArea();drawPeople(time); }
    if(zoom>2 && cityMap?.henry) drawCutaway(time);
  }
  function drawCutaway(time=0) {
    const z=cityMap.henry, angle=(Number(z.rotation_degrees)||0)*Math.PI/180;
    const cutX=z.size[0]/WIDTH, cutZ=z.size[1]/HEIGHT, factor=areaScale()*zoom;
    const a=factor*Math.cos(angle)*cutX,b=factor*Math.sin(angle)*cutX;
    const c=-factor*Math.sin(angle)*cutZ,d=factor*Math.cos(angle)*cutZ;
    const center=worldScreen(...z.position);
    const opacity=Math.max(0,Math.min(1,(zoom-2.2)/4.4));
    ctx.save();ctx.globalAlpha=opacity;ctx.transform(a,b,c,d,center.x-a*WIDTH/2-c*HEIGHT/2,center.y-b*WIDTH/2-d*HEIGHT/2);
    drawScene();nightTint();
    for (const person of [...people.values()].filter(p=>p.visible&&!p.target?.startsWith('place:')).sort((a,b)=>a.y-b.y)) {
      drawSprite(ctx,person,time);
      const label=labelName(person.agent);
      ctx.font='12px system-ui, sans-serif';
      const labelWidth=ctx.measureText(label).width+12;
      rect(person.x-labelWidth/2,person.y+6,labelWidth,17,'#262722d9');
      text(label,person.x,person.y+19,12,'#f4e9cf','center');
      if(speakers.has(String(person.agent.id))) drawBubble(person);
    }
    drawWeather(time);drawHud();ctx.restore();
  }
  function henryTarget(){return cityMap?.henry?.position||[0,0];}
  function areaScale(){
    const b=cityMap.bounds, width=b[1][0]-b[0][0],height=b[1][1]-b[0][1];
    return Math.min((WIDTH-70)/width,(HEIGHT-70)/height);
  }
  function worldScreen(x,z){
    const b=cityMap.bounds,cx=mapCenter?.[0]??(b[0][0]+b[1][0])/2,cz=mapCenter?.[1]??(b[0][1]+b[1][1])/2,s=areaScale()*zoom;
    return {x:WIDTH/2+panX+(x-cx)*s,y:HEIGHT/2+panY-(z-cz)*s};
  }
  function drawArea(){
    const b=cityMap.bounds;mapCenter ||= [(b[0][0]+b[1][0])/2,(b[0][1]+b[1][1])/2];
    rect(0,0,WIDTH,HEIGHT,'#4a483d');ctx.save();
    const pathShape=shape=>{ctx.beginPath();shape.forEach((p,i)=>{const q=worldScreen(p[0],p[1]);if(i)ctx.lineTo(q.x,q.y);else ctx.moveTo(q.x,q.y);});ctx.closePath();};
    for(const space of cityMap.open_spaces||[]){pathShape(space.shape);ctx.fillStyle=space.name==='Cutting Room Square'?'#746f58':'#625f4d';ctx.fill();}
    for(const road of cityMap.roads||[]){
      const pts=road.line.map(p=>worldScreen(p[0],p[1]));if(pts.length<2)continue;
      const scale=areaScale()*zoom;ctx.beginPath();pts.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));
      const foot=['footway','path','steps','cycleway','pedestrian'].includes(road.type);ctx.lineCap='round';
      if(!foot){ctx.strokeStyle='#aaa28e';ctx.lineWidth=Math.max(1,scale*(road.width+3.2));ctx.stroke();}
      ctx.strokeStyle=foot?'#aaa28e':'#686760';ctx.lineWidth=Math.max(1,scale*road.width);ctx.stroke();
    }
    for(const building of cityMap.buildings||[]){pathShape(building.shape);ctx.fillStyle=building.type==='commercial'?'#88715c':'#847361';ctx.fill();ctx.strokeStyle='#c4b596';ctx.lineWidth=Math.max(.6,areaScale()*zoom*.16);ctx.stroke();}
    if(cityMap.henry?.shape?.length){pathShape(cityMap.henry.shape);ctx.strokeStyle='#e6bd73';ctx.lineWidth=Math.max(1,areaScale()*zoom*.35);ctx.stroke();}
    for(const [x,z] of cityMap.trees||[]){const p=worldScreen(x,z),r=Math.max(2,areaScale()*zoom*.65);ctx.beginPath();ctx.arc(p.x,p.y,r,0,Math.PI*2);ctx.fillStyle='#536148';ctx.fill();}
    const hour=Number(String(usage.sim_time||'').match(/,\s*(\d{1,2}):/)?.[1]||12);
    if(hour>=19||hour<7)rect(0,0,WIDTH,HEIGHT,'#15223b55');
    const streetNames=new Map();for(const road of cityMap.roads||[])if(['Henry Street','Blossom Street','Hood Street','Jersey Street','Murray Street'].includes(road.name)&&road.line.length>1){const old=streetNames.get(road.name);if(!old||road.line.length>old.length)streetNames.set(road.name,road.line);}
    ctx.font='11px system-ui,sans-serif';ctx.textAlign='center';ctx.fillStyle='#f0dfba';
    for(const [name,line] of streetNames){const loc=line[Math.floor(line.length/2)],p=worldScreen(...loc);ctx.fillText(name,p.x,p.y-5);}
    for(const [index,place] of PLACES.entries()){const p=placeScreen(place);ctx.beginPath();ctx.arc(p.x,p.y,5,0,Math.PI*2);ctx.fillStyle='#e6bd73';ctx.fill();ctx.strokeStyle='#29251d';ctx.lineWidth=1.5;ctx.stroke();ctx.font='11px system-ui,sans-serif';ctx.textAlign='left';ctx.fillStyle='#fff0cf';ctx.fillText(place.name,p.x+8,p.y+(index===0?-8:index===1?16:4));}
    ctx.restore();
  }
  function placeScreen(place){
    return worldScreen(...placeWorld(place));
  }
  function placeWorld(place){
    if(place.position) return place.position;
    let x,z;
    if(place.osmId){const building=cityMap.buildings.find(b=>String(b.id)===String(place.osmId));if(building){x=building.shape.reduce((n,p)=>n+p[0],0)/building.shape.length;z=building.shape.reduce((n,p)=>n+p[1],0)/building.shape.length;}}
    if(x===undefined){const h=cityMap.henry,pos=h.position,angle=(Number(h.rotation_degrees)||0)*Math.PI/180,l=place.local||[0,0];x=pos[0]+l[0]*Math.cos(angle)+l[1]*Math.sin(angle);z=pos[1]-l[0]*Math.sin(angle)+l[1]*Math.cos(angle);}
    return [x,z];
  }
  function drawPeople(time){
    const fade=Math.max(0,Math.min(1,(zoom-2.2)/4.4));
    for(const person of people.values())if(person.visible){
      const p=personScreen(person);
      ctx.save();ctx.globalAlpha=person.target?.startsWith('place:')?1:1-fade;ctx.beginPath();ctx.arc(p.x,p.y,person.agent.isPlayer?5:4,0,Math.PI*2);ctx.fillStyle=person.agent.isPlayer?'#85d7ff':'#f5dc9c';ctx.fill();ctx.strokeStyle='#25231e';ctx.lineWidth=1.5;ctx.stroke();
      if(zoom<4) {ctx.font='10px system-ui,sans-serif';ctx.textAlign='left';ctx.fillStyle='#fff0cf';ctx.fillText(labelName(person.agent),p.x+6,p.y-5);}
      ctx.restore();
    }
  }
  function personScreen(person){
    if(!cityMap?.henry)return {x:WIDTH/2,y:HEIGHT/2};
    if(person.target?.startsWith('place:')){
      const place=PLACES.find(p=>`place:${p.key}`===person.target);if(place){const anchor=placeWorld(place),n=[...String(person.agent.id)].reduce((v,c)=>v+c.charCodeAt(0),0),angle=n*2.399,r=.6+(n%5)*.22;return worldScreen(anchor[0]+Math.cos(angle)*r,anchor[1]+Math.sin(angle)*r);}
    }
    const angle=(Number(cityMap.henry.rotation_degrees)||0)*Math.PI/180,h=henryTarget();
    const lx=(person.x-WIDTH/2)*cityMap.henry.size[0]/WIDTH,lz=(HEIGHT/2-person.y)*cityMap.henry.size[1]/HEIGHT;
    return worldScreen(h[0]+lx*Math.cos(angle)+lz*Math.sin(angle),h[1]-lx*Math.sin(angle)+lz*Math.cos(angle));
  }
  function zoomAt(next,x=WIDTH/2,y=HEIGHT/2){
    if(!cityMap?.bounds)return;const old=zoom,worldX=(x-WIDTH/2-panX)/(areaScale()*old)+(mapCenter[0]),worldZ=mapCenter[1]-(y-HEIGHT/2-panY)/(areaScale()*old);
    zoom=Math.max(zoomRange.min,Math.min(zoomRange.max,next));const s=areaScale()*zoom;panX=x-WIDTH/2-(worldX-mapCenter[0])*s;panY=y-HEIGHT/2+(worldZ-mapCenter[1])*s;render();
  }
  function wholeArea(){if(cityMap?.bounds)mapCenter=[(cityMap.bounds[0][0]+cityMap.bounds[1][0])/2,(cityMap.bounds[0][1]+cityMap.bounds[1][1])/2];zoom=1;panX=panY=0;render();}
  function drawBubble(person) {
    const x=person.x+9,y=person.y-55;
    rect(x,y,23,15,'#f4e9cf');rect(x+2,y+15,4,4,'#f4e9cf');
    for(let i=0;i<3;i++) rect(x+4+i*6,y+6,2,2,'#5d594e');
  }
  function syncAnimation() {
    const visible=activeTab==='map' && document.visibilityState!=='hidden';
    if(!visible) { if(frameId!==null) cancelAnimationFrame(frameId);frameId=null;lastFrame=null;return; }
    if(frameId===null) frameId=requestAnimationFrame(animate);
  }
  function animate(timestamp) {
    const time=timestamp/1000, delta=lastFrame===null?0:Math.min(time-lastFrame,0.1);
    lastFrame=time;
    for(const person of people.values()) advance(person,delta,time);
    render(time);positionPopup();
    frameId=requestAnimationFrame(animate);
  }

  // Movement and card functions below share the same stable person records.
  function targetFor(agent) {
    const place=PLACES.find(row=>row.locations.includes(agent.location));
    if(place?.key==='pub') {
      if(['behind the bar','working the bar','covering Jess behind the bar'].includes(agent.activity)) return 'staff';
      if(agent.activity==='at his usual table') return 'tommy';
      if(agent.activity==='here for darts and company') return 'darts';
      return 'pub';
    }
    if(place?.key==='shop') return agent.activity==='behind the counter'?'till':'shop';
    if(place?.key==='street' || (agent.location==='Ancoats' && agent.activity==='walking to the shops')) return 'street';
    if(place)return `place:${place.key}`;
    return null;
  }
  function poolFor(target,agent) {
    if(target?.startsWith('place:'))return Array.from({length:12},(_,i)=>({key:`${target}-${i}`,room:'street',x:480+(i%4-1.5)*12,y:285+Math.floor(i/4)*14}));
    if(target==='staff') return firstName(agent)==='Jess'?[BEHIND_BAR[1],BEHIND_BAR[0],BEHIND_BAR[2]]:BEHIND_BAR;
    return {tommy:TOMMY_TABLE,darts:DARTS,pub:[...PUB_SEATS,...BAR_STOOLS],till:TILL,shop:SHOP_CUSTOMER,street:STREET_SPOTS}[target]||[];
  }
  function allocate(target,agent) {
    const used=new Set([...people.values()].map(p=>p.spot?.key));
    return poolFor(target,agent).find(spot=>!used.has(spot.key))||null;
  }
  function roomAt(person) {
    if(person.y<425 && person.x>=40 && person.x<=520) return 'pub';
    if(person.y<425 && person.x>=670 && person.x<=920) return 'shop';
    return 'street';
  }
  function insidePath(room,point,entering) {
    // The staff strip has an opening to the left of the counter.
    const path=room==='pub' && point.y<192
      ? [{x:100,y:390},{x:90,y:390},{x:90,y:179},{x:point.x,y:179},point]
      : [{x:DOORS[room].x,y:390},{x:point.x,y:390},point];
    return entering?path:path.slice(0,-1).reverse();
  }
  function routeTo(person,spot) {
    const path=[];
    const upstairs=person.agent.location==='Flat above The Crooked Billet';
    const fromUpstairs=person.previousLocation==='Flat above The Crooked Billet';
    const destination=upstairs?'pub':spot?.room||'street';
    const destinationSpot=upstairs?STAIRS:spot;
    if(!person.visible) {
      const entry=fromUpstairs?STAIRS:{x:spot?.x<WIDTH/2?-25:WIDTH+25,y:STREET_Y};
      person.x=entry.x;person.y=entry.y;person.visible=true;
    }
    const actualSource=roomAt(person);
    if(actualSource===destination && destinationSpot) {
      if(destination==='street') return [destinationSpot];
      return [...insidePath(destination,person,false),...insidePath(destination,destinationSpot,true)];
    }
    if(actualSource!=='street') path.push(...insidePath(actualSource,person,false),DOORS[actualSource],{x:DOORS[actualSource].x,y:STREET_Y});
    if(destination!=='street') path.push({x:DOORS[destination].x,y:STREET_Y},DOORS[destination],...insidePath(destination,destinationSpot,true));
    else if(spot) path.push(spot);
    else path.push({x:person.x<WIDTH/2?-30:WIDTH+30,y:STREET_Y});
    return path.map(p=>({x:p.x,y:p.y}));
  }
  function settle(person,spot) {
    person.route=[];person.visible=!!spot;
    if(spot) { person.x=spot.x;person.y=spot.y; }
  }
  function changeTarget(person,target,spot,firstLoad) {
    const behind=person.travelling;
    person.target=target;person.spot=spot;person.idleUntil=0;person.returning=false;
    if(firstLoad || behind) { settle(person,spot);person.travelling=false;return; }
    if(!spot&&!person.visible) return;
    person.route=routeTo(person,spot);person.travelling=true;
  }
  function walkSpeed() { return Math.min(MAX_WALK_SPEED,WALK_SPEED*(1+Math.log10(Math.max(1,Number(usage.speed)||1)))); }
  function advance(person,delta,time) {
    if(!person.visible) return;
    let distance=walkSpeed()*delta;
    while(person.route.length && distance>0) {
      const next=person.route[0],dx=next.x-person.x,dy=next.y-person.y,length=Math.hypot(dx,dy);
      if(dx) person.facing=dx<0?-1:1;
      if(length<=distance) { person.x=next.x;person.y=next.y;person.route.shift();distance-=length; }
      else { person.x+=dx/length*distance;person.y+=dy/length*distance;distance=0; }
    }
    if(person.route.length) return;
    person.travelling=false;
    if(!person.spot) { person.visible=false;return; }
    if(time<person.nextIdle) return;
    person.nextIdle=time+4+person.random()*8;
    person.idleUntil=time+1.3+person.random();
    if(speakers.has(String(person.agent.id))) return;
    if(person.target==='street') {
      const x=person.x<WIDTH/2?820:150;
      person.route=[{x,y:person.spot.y}];
    } else if(['staff','shop'].includes(person.target)) {
      const offset=(person.random()-.5)*14;
      person.route=[{x:person.spot.x+offset,y:person.spot.y},person.spot];
    }
  }
  function update() {
    if(latestAgents===null) return;
    usage=latestUsage||{};conversation=latestConv;player=latestPlayer;
    for(const place of usage.places||[]){
      if(PLACES.some(row=>row.key===place.key)) continue;
      PLACES.push({key:place.key,name:place.label||place.name,locations:[place.name],local:HENRY_ANCHORS[place.key],...place.map});
    }
    const agents=[...latestAgents];
    for(const human of [...(player?.other_players||[]),...(player?.place?[{...player,isSelf:true}]:[])]) {
      if(!PLACES.some(p=>p.key===human.place)) continue;
      agents.push({...human,id:`player-${human.id}`,isPlayer:true,location:PLACES.find(p=>p.key===human.place).locations[0],activity:'visiting'});
    }
    const ids=new Set(agents.map(a=>String(a.id)));
    for(const [id] of people) if(!ids.has(id)) people.delete(id);
    // Release changed reservations first; unchanged assignments never reshuffle.
    for(const agent of agents) {
      const person=people.get(String(agent.id));
      if(person && person.target!==targetFor(agent)) person.spot=null;
    }
    for(const agent of agents) {
      const id=String(agent.id),target=targetFor(agent);
      let person=people.get(id);
      if(!person) {
        const random=randomFor(id);
        person={agent,target:undefined,spot:null,x:0,y:STREET_Y,route:[],visible:false,facing:1,random,phase:random()*6,nextIdle:performance.now()/1000+4+random()*8,idleUntil:0,travelling:false};
        people.set(id,person);
      }
      person.previousLocation=person.agent.location;person.agent=agent;
      if(person.target!==target || (target&&!person.spot)) changeTarget(person,target,allocate(target,agent),!initialised);
    }
    initialised=true;
    updateConversation();updateRoster();refreshPopup();
    if(activeTab==='map') render(performance.now()/1000);
  }
  function updateConversation() {
    speakers=new Set();
    // db.py permits running, completed and failed. Only running is live.
    const live=[conversation,player?.conversation].filter(c=>c?.status==='running');
    for(const conv of live) {
      const participants=[];
      for(const message of conv.messages||[]) {
        const humanId=`player-${message.speaker_id}`;
        const id=people.has(humanId)?humanId:String(message.speaker_id);
        const person=people.get(id);
        if(!person?.visible || person.agent.location!==conv.location) continue;
        speakers.add(id);if(!participants.includes(person)) participants.push(person);
      }
      for(const person of participants) {
        const other=participants.find(p=>p!==person);
        if(other) person.facing=other.x<person.x?-1:1;
      }
    }
  }
  function updateRoster() {
    const shown=[...people.values()].filter(p=>p.visible&&!p.agent.isPlayer);
    const markup=shown.map(p=>`<button type="button" data-map-agent="${esc(p.agent.id)}" aria-pressed="${String(selectedId===String(p.agent.id))}">${esc(p.agent.name)}</button>`).join('');
    if($('map-roster').innerHTML!==markup) $('map-roster').innerHTML=markup;
  }
  function closePopup(focus=false) {
    selectedId=null;popup.hidden=true;updateRoster();
    if(focus) canvas.focus({preventScroll:true});
  }
  function positionPopup() {
    if(popup.hidden || window.innerWidth<=600) return;
    const person=people.get(selectedId);if(!person) return;
    const width=canvas.clientWidth,height=canvas.clientHeight;
    const point=personScreen(person),x=point.x/WIDTH*width,y=point.y/HEIGHT*height;
    popup.style.left=`${Math.max(8,Math.min(width-popup.offsetWidth-8,x+22))}px`;
    popup.style.top=`${Math.max(8,Math.min(height-popup.offsetHeight-8,y-50))}px`;
  }
  function refreshPopup() {
    if(selectedId===null) return;
    const person=people.get(selectedId);
    if(!person?.visible) { closePopup();return; }
    const a=person.agent,fc=a.fact_counts||{},portrait=portraits[a.name];
    const relationships=(a.relationships||[]).map(r=>{
      const meter=(key,label)=>{
        const value=Math.max(0,Math.min(100,Number(r[`${key}_value`])||0));
        return `<label title="${esc(r[key])}">${label}<meter min="0" max="100" value="${value}" aria-label="${esc(label+' towards '+r.name+': '+r[key])}"></meter><span>${value}</span></label>`;
      };
      return `<div class="relationship"><span title="${esc(r.reason||'')}">${esc(r.name)}</span>${meter('trust','Trust')}${meter('warmth','Warmth')}</div>`;
    }).join('')||'<div>No relationships yet.</div>';
    const plans=(a.plans||[]).filter(p=>p.status!=='cancelled').slice(0,3).map(p=>`<div>${esc((p.start_at||'').slice(11))} · ${esc(p.action)} ${esc(p.place||'')} [${esc(p.status)}]</div>`).join('');
    const promises=(a.promises||[]).filter(p=>!p.status||p.status==='open').slice(0,3).map(p=>`<div>${esc(p.content)}${p.to_name?' · '+esc(p.to_name):''}</div>`).join('');
    const focusKey=popup.contains(document.activeElement)?document.activeElement.dataset.popupAction:null;
    const scroll=popup.scrollTop;
    popup.innerHTML=`<button class="popup-close" type="button" data-popup-action="close" aria-label="Close character card">×</button>
      <div class="popup-heading">${portrait?`<img class="popup-photo" src="/static/portraits/${esc(portrait)}.png" alt="${esc(a.name)}">`:'<canvas class="popup-photo" width="96" height="96" aria-label="Character sprite"></canvas>'}
      <div><h2>${esc(a.name)}</h2><div class="sub">${esc(a.age??'')} · ${esc(a.occupation||'')}</div><span class="mood">${esc(a.mood||'')}</span></div></div>
      <div class="row"><b>Now</b>${esc(a.activity||'—')} · ${esc((a.location||'').split(',')[0])}</div>
      ${a.today_action?`<div class="row"><b>Today:</b> ${esc(a.today_action)}</div>`:''}
      <div class="row"><b>Goal</b>${esc(a.current_goal||'—')}</div>
      <div class="row"><b>Knowledge</b>${esc(fc.seed||0)} known · ${esc(fc.told||0)} told · ${esc(fc.claim||0)} rumour</div>
      <div class="mem"><b>Relationships</b>${relationships}</div>
      <div class="mem"><b>Today's plans</b>${plans||'<div>Following their routine.</div>'}</div>
      <div class="mem"><b>Open promises</b>${promises||'<div>No open promises.</div>'}</div>
      <button class="full-card" type="button" data-popup-action="full">Full card →</button>`;
    const miniature=popup.querySelector('canvas');
    if(miniature) {
      const context=miniature.getContext('2d');context.imageSmoothingEnabled=false;
      drawSprite(context,{...person,x:48,y:86,route:[],idleUntil:0},0,3);
    }
    const photo=popup.querySelector('img');
    if(photo) photo.onerror=()=>{ const fallback=document.createElement('canvas');fallback.width=96;fallback.height=96;fallback.className='popup-photo';photo.replaceWith(fallback);drawSprite(fallback.getContext('2d'),{...person,x:48,y:86,route:[],idleUntil:0},0,3); };
    if(focusKey) popup.querySelector(`[data-popup-action="${focusKey}"]`)?.focus({preventScroll:true});
    popup.scrollTop=scroll;positionPopup();
  }
  function openPopup(id) {
    if(!people.get(String(id))?.visible) return;
    selectedId=String(id);popup.hidden=false;refreshPopup();updateRoster();
    popup.querySelector('button').focus({preventScroll:true});
    if(window.innerWidth<=600) popup.scrollIntoView({block:'nearest',behavior:'smooth'});
  }
  function hitPerson(event) {
    const bounds=canvas.getBoundingClientRect();
    const x=(event.clientX-bounds.left)*WIDTH/bounds.width,y=(event.clientY-bounds.top)*HEIGHT/bounds.height;
    const radius=Math.max(8,18*WIDTH/bounds.width);
    return [...people.values()].filter(p=>p.visible&&!p.agent.isPlayer)
      .filter(p=>{const q=personScreen(p);return Math.hypot(q.x-x,q.y-y)<radius;})
      .sort((a,b)=>{const aa=personScreen(a),bb=personScreen(b);return Math.hypot(aa.x-x,aa.y-y)-Math.hypot(bb.x-x,bb.y-y);})[0];
  }
  canvas.addEventListener('pointerdown',event=>{
    canvas.setPointerCapture?.(event.pointerId);pointers.set(event.pointerId,{x:event.clientX,y:event.clientY});
    if(pointers.size===1)drag={id:event.pointerId,x:event.clientX,y:event.clientY,px:panX,py:panY};
    else if(pointers.size===2){const pts=[...pointers.values()];drag={pinch:Math.hypot(pts[0].x-pts[1].x,pts[0].y-pts[1].y),zoom};}
  });
  canvas.addEventListener('pointermove',event=>{
    canvas.style.cursor=hitPerson(event)?'pointer':'grab';if(!pointers.has(event.pointerId))return;
    pointers.set(event.pointerId,{x:event.clientX,y:event.clientY});
    if(pointers.size===1&&drag?.id===event.pointerId){const b=canvas.getBoundingClientRect();panX=drag.px+(event.clientX-drag.x)*WIDTH/b.width;panY=drag.py+(event.clientY-drag.y)*HEIGHT/b.height;render();}
    else if(pointers.size===2&&drag?.pinch){const pts=[...pointers.values()],distance=Math.hypot(pts[0].x-pts[1].x,pts[0].y-pts[1].y);zoom=Math.max(zoomRange.min,Math.min(zoomRange.max,drag.zoom*distance/drag.pinch));render();}
  });
  canvas.addEventListener('pointerup',event=>{pointers.delete(event.pointerId);if(!pointers.size)drag=null;});
  canvas.addEventListener('pointercancel',event=>{pointers.delete(event.pointerId);drag=null;});
  canvas.addEventListener('wheel',event=>{event.preventDefault();const b=canvas.getBoundingClientRect();zoomAt(zoom*Math.exp(-event.deltaY*.0015),(event.clientX-b.left)*WIDTH/b.width,(event.clientY-b.top)*HEIGHT/b.height);},{passive:false});
  canvas.addEventListener('dblclick',event=>{const b=canvas.getBoundingClientRect();zoomAt(zoom*1.8,(event.clientX-b.left)*WIDTH/b.width,(event.clientY-b.top)*HEIGHT/b.height);});
  canvas.addEventListener('pointerup',event=>{const now=performance.now();if(event.pointerType==='touch'&&now-tapTime<360){const b=canvas.getBoundingClientRect();zoomAt(zoom*1.8,(event.clientX-b.left)*WIDTH/b.width,(event.clientY-b.top)*HEIGHT/b.height);tapTime=0;}else tapTime=now;});
  canvas.addEventListener('click',event=>{const person=hitPerson(event);if(person) openPopup(person.agent.id);else {
    closePopup();
    if(!cityMap?.bounds)return;
    const b=canvas.getBoundingClientRect(),x=(event.clientX-b.left)*WIDTH/b.width,y=(event.clientY-b.top)*HEIGHT/b.height;
    const place=PLACES.find(row=>{const p=placeScreen(row);return Math.hypot(p.x-x,p.y-y)<10;});
    if(place && zoom<5){const position=placeWorld(place);wholeArea();mapCenter=position;zoomAt(6);}
  }});
  $('map-zoom-in').addEventListener('click',()=>zoomAt(zoom*1.5));
  $('map-zoom-out').addEventListener('click',()=>zoomAt(zoom/1.5));
  $('map-whole-area').addEventListener('click',wholeArea);
  $('map-roster').addEventListener('click',event=>{const button=event.target.closest('[data-map-agent]');if(button) openPopup(button.dataset.mapAgent);});
  popup.addEventListener('click',event=>{
    const action=event.target.closest('[data-popup-action]')?.dataset.popupAction;
    if(action==='close') closePopup(true);
    if(action==='full') {
      const id=selectedId;selectTab('dashboard');
      const card=[...$('agents').querySelectorAll('[data-agent-id]')].find(c=>c.dataset.agentId===id);
      if(card) { card.open=true;card.scrollIntoView({behavior:'smooth',block:'start'});card.querySelector('summary').focus({preventScroll:true}); }
    }
  });
  document.addEventListener('pointerdown',event=>{if(!popup.hidden&&!popup.contains(event.target)&&!canvas.contains(event.target)&&!$('map-roster').contains(event.target)) closePopup();});
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!popup.hidden) closePopup(true);});

  window.evoriumMap={update,places:PLACES,getZoom:()=>zoom,zoomAt,wholeArea,
    setCityData:data=>{cityMap=data;mapCenter=data?.bounds?[(data.bounds[0][0]+data.bounds[1][0])/2,(data.bounds[0][1]+data.bounds[1][1])/2]:null;},render};
  let remembered='dashboard';
  try { remembered=localStorage.getItem('evorium-view')||remembered; } catch (_) { /* storage unavailable */ }
  selectTab(location.hash==='#map'?'map':location.hash==='#dashboard'?'dashboard':remembered,false,false);
  update();
})();
