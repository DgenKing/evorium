// Chrome DevTools Protocol, Node built-ins only. Always targets fake server 8011.
import {spawn} from 'node:child_process';import fs from 'node:fs/promises';
const base='http://127.0.0.1:8011';const smoke=await(await fetch(base+'/smoke/status')).json();if(!smoke.fake_models)throw Error('Fake smoke server required');
const cityMode=process.argv.includes('--city'),night=process.argv.includes('--night'),grey=process.argv.includes('--grey');
const cityWalk=process.argv.includes('--city-walk');
const output=cityMode?'tools/city/build/screenshots':'tools/web3d/raw/screens';await fs.mkdir(output,{recursive:true});
if(cityMode)await fetch(base+'/smoke/at',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({at:night?'2026-11-24 23:00:00':'2026-11-24 12:00:00'})});
const overviewCameras=new Map();
let lines=[];
if(cityMode){
  const roads=JSON.parse(await fs.readFile('tools/city/build/layers/roads.geojson','utf-8')).features;
  const length=points=>points.slice(1).reduce((sum,p,i)=>sum+Math.hypot(p[0]-points[i][0],p[1]-points[i][1]),0);
  lines=['Blossom Street','Henry Street','Hood Street','Jersey Street','Murray Street'].map(name=>{
   const candidates=roads.filter(f=>f.properties.name===name).flatMap(({geometry:g})=>g.type==='LineString'?[g.coordinates]:g.type==='MultiLineString'?g.coordinates:[]);
   const line=candidates.sort((a,b)=>length(b)-length(a))[0];
   return {name,points:line.map(([x,z])=>[Math.max(-198.9,Math.min(198.9,x)),Math.max(-148.9,Math.min(148.9,z))])};
  });
  for(const {name,points} of lines){
   const [a,b]=points.slice(1).map((point,i)=>[points[i],point]).sort((u,v)=>length(v)-length(u))[0];
   const eye=[a[0]*.7+b[0]*.3,2.6,a[1]*.7+b[1]*.3],target=[b[0],1.5,b[1]];
   overviewCameras.set(name.split(' ')[0].toLowerCase(),[eye,target]);
  }
}
const chrome=spawn('/usr/bin/google-chrome',['--headless=new','--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--remote-debugging-port=9333','--user-data-dir=/tmp/evorium-chrome','--no-first-run','--disable-dev-shm-usage','about:blank'],{stdio:'ignore'});
const pause=ms=>new Promise(r=>setTimeout(r,ms));
try{
 let page;for(let i=0;i<100;i++){try{page=(await(await fetch('http://127.0.0.1:9333/json')).json()).find(p=>p.type==='page');if(page)break;}catch{}await pause(200);}
 if(!page)throw Error('Chrome CDP unavailable');
 const socket=new WebSocket(page.webSocketDebuggerUrl);await new Promise(r=>socket.addEventListener('open',r,{once:true}));let id=0;const pending=new Map();socket.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);pending.delete(m.id);if(m.error)p.reject(Error(JSON.stringify(m.error)));else p.resolve(m.result);}};
 function cdp(method,params={}){return new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});socket.send(JSON.stringify({id:n,method,params}));});}
 async function evaluate(expression){const r=await cdp('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.text+JSON.stringify(r.exceptionDetails.exception));return r.result.value;}
 await cdp('Page.enable');await cdp('Network.enable');await cdp('Network.setCacheDisabled',{cacheDisabled:true});await cdp('Runtime.enable');let all=[],budgetFailures=[];
 const oneView=process.argv.includes('--movement-only')||process.argv.includes('--poses');
 const devices=oneView?[['desktop',1280,720]]:[['desktop',1280,720],['phone',390,844]];
 const tier=process.argv.find(arg=>arg.startsWith('--tier='))?.slice(7);
 const qualities=tier?[tier]:oneView?['low']:['low','high'];
 for(const [device,width,height] of devices)for(const quality of qualities)for(const cam of (process.argv.includes('--cast')?['lineup',...['dez','jess','tommy','raj','chloe','simon','brenda','mo','player'].map(id=>'head&character='+id)]:process.argv.includes('--poses')?['dez','tommy','brenda'].flatMap(id=>['idle','walk','run','jump_start','sit','talk'].map(pose=>'body&character='+id+'&pose='+pose)):process.argv.find(a=>a.startsWith('--cam='))?[process.argv.find(a=>a.startsWith('--cam=')).slice('--cam='.length).split(',')].flat():process.argv.includes('--movement-only')?['pub']:['street','pub','shop','cast','player'])){
 await cdp('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:device==='phone'});await cdp('Emulation.setTouchEmulationEnabled',{enabled:device==='phone'});
 await cdp('Page.navigate',{url:`${base}/world3d?test=1&quality=${quality}&cam=${cam}${cityMode?'&city=1':''}`});
 let ready=false;for(let i=0;i<240;i++){await pause(250);if(await evaluate('window.__evoriumReady===true && !!window.__evoriumTest')){ready=true;break;}const errors=await evaluate('window.__evoriumReport?.errors');if(errors?.length)throw Error(JSON.stringify(errors));}
 if(!ready)throw Error('Page never became ready');
 if(overviewCameras.has(cam)){
  const [eye,target]=overviewCameras.get(cam);
  await evaluate(`{const camera=window.__evoriumTest.camera;camera.position.fromArray(${JSON.stringify(eye)});camera.lookAt(...${JSON.stringify(target)});}`);
  await pause(1200);
 }
 const report=await evaluate('window.__evoriumReport');if(cityMode&&!report.loadedAssets.includes('city'))throw Error('City mode did not load city assets');if(Math.hypot(...report.player.position.map((v,i)=>v-report.player.actorPosition[i]))>.01)throw Error('Avatar and capsule positions differ');if(cam.startsWith('lineup')||cam.startsWith('head')||cam.startsWith('body'))report.poseMetrics=await evaluate('window.__evoriumTest.measureCast()');const actual=report.characters.map(c=>c.id).sort();if(JSON.stringify(actual)!==JSON.stringify(report.expectedCharacters.sort()))throw Error('Spawned characters differ from scene');if(report.errors.length)throw Error(report.errors.join('\n'));if(cityMode&&!await evaluate("document.querySelector('#city-attribution')?.textContent.includes('© OpenStreetMap contributors')"))throw Error('Missing city attribution');if(report.visibleTriangles>(quality==='low'?150000:400000))budgetFailures.push([device,quality,cam,report.visibleTriangles]);
 if(cityWalk&&all.length===0){
  const walks=await evaluate('window.__evoriumTest.cityWalk('+JSON.stringify(lines)+')');
  const unreachable=await evaluate('window.__evoriumTest.cityRoutes()');
  await fs.writeFile(output+'/walks.json',JSON.stringify({walks,unreachable},null,2));
  console.log('CITY WALKS',JSON.stringify({walks,unreachable}));
  if(walks.some(walk=>walk.failure)||unreachable.length)throw Error('City walking or route check failed');
 }
 if(grey){await evaluate("if(window.__evoriumTest.world.cityProps)window.__evoriumTest.world.cityProps.visible=false;window.__evoriumTest.world.city.traverse(o=>{if(o.isMesh){const mats=Array.isArray(o.material)?o.material:[o.material];for(const m of mats){m.map=null;m.color?.setHex(0x858585);m.emissive?.setHex(0x000000);m.roughness=1;m.needsUpdate=true;}}})");await pause(250);}if(report.modelFallbacks?.length)throw Error('Unexpected model fallback '+JSON.stringify(report.modelFallbacks));if(cam==='lineup'&&report.lineup.length!==9)throw Error('Incomplete cast lineup');const stem=`${cityMode?(grey?'grey-':night?'night-':'day-'):''}${device}-${quality}-${cam.replaceAll('&','-').replaceAll('=','-')}`;const shot=await cdp('Page.captureScreenshot',{format:'png'});await fs.writeFile(output+'/'+stem+'.png',Buffer.from(shot.data,'base64'));await fs.writeFile(output+'/'+stem+'.json',JSON.stringify(report,null,2));console.log(stem,report.drawCalls,report.triangles,'visible',report.visibleTriangles,report.fps.toFixed(1));all.push({stem,...report});
 }
 if(!process.argv.includes('--screens-only')&&!process.argv.includes('--cast')&&!process.argv.includes('--poses')){
 const physics=await evaluate('window.__evoriumTest.physics()');await fs.writeFile(output+'/physics.json',JSON.stringify(physics,null,2));console.log('PHYSICS',JSON.stringify(physics));
 const movement=await evaluate('window.__evoriumTest.movement()');await fs.writeFile(output+'/movement.json',JSON.stringify(movement,null,2));console.log('MOVEMENT',JSON.stringify(movement.results));
 if(!await evaluate('window.__evoriumTest.calendar(true)')||await evaluate('window.__evoriumTest.calendar(false)'))throw Error('Festive decoration toggle failed');
 console.log('CALENDAR festive lights toggle passed');
 for(const condition of ['rain','snow','fog','unknown']){
 const result=await evaluate(`window.__evoriumTest.weather({condition:'${condition}',raining:${condition==='rain'}})`);
 if((condition==='rain'||condition==='snow')&&!result.particles)throw Error('Missing weather particles '+condition);
 if(condition==='fog'&&!result.style.fog)throw Error('Missing weather fog');
 if(condition==='unknown'&&result.particles)throw Error('Unknown weather should have no particles');
 const shot=await cdp('Page.captureScreenshot',{format:'png'});await fs.writeFile(output+'/weather-'+condition+'.png',Buffer.from(shot.data,'base64'));
 }const highRain=await evaluate("window.__evoriumTest.weather({condition:'rain',raining:true},'high')");const lowRain=await evaluate("window.__evoriumTest.weather({condition:'rain',raining:true},'low')");if(lowRain.particles>=highRain.particles)throw Error('Weather quality downgrade failed');await evaluate("window.__evoriumTest.weather({condition:'unknown'})");console.log('WEATHER rain, snow, fog, unknown and quality downgrade rendered without errors');
 const chat=await evaluate('window.__evoriumTest.chat()');await fs.writeFile(output+'/chat.json',JSON.stringify(chat,null,2));console.log('CHAT',chat.text);
 await fetch(base+'/smoke/at',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({at:'2026-11-19 18:59:00'})});const beforeFast=await evaluate('window.__evoriumTest.refresh()');
 await fetch(base+'/speed',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({speed:60})});await pause(6000);const fast=await evaluate('window.__evoriumTest.refresh()');if(fast.speed!==60||fast.sim_at===beforeFast.sim_at||JSON.stringify(fast.characters)===JSON.stringify(beforeFast.characters))throw Error('60x routine changes not reflected');await fs.writeFile(output+'/speed60.json',JSON.stringify(fast,null,2));await fetch(base+'/speed',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({speed:0})});
 }
 const reportFile=output+'/'+(cityMode?(grey?'grey-':night?'night-':'day-'):'')+'reports.json';
 if(tier){
  const previous=JSON.parse(await fs.readFile(reportFile,'utf-8').catch(()=> '[]'));
  all=[...previous.filter(row=>row.quality!==tier),...all];
 }
 await fs.writeFile(reportFile,JSON.stringify(all,null,2));socket.close();if(budgetFailures.length)throw Error('In-view triangle budget exceeded: '+JSON.stringify(budgetFailures));
}finally{chrome.kill();}
