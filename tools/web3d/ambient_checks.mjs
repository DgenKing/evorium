// Deterministic street-life captures and interaction checks, fake server 8011 only.
import {spawn} from 'node:child_process';import fs from 'node:fs/promises';
const base='http://127.0.0.1:8011';if(!(await(await fetch(base+'/smoke/status')).json()).fake_models)throw Error('Fake smoke server required');
const out='tools/web3d/raw/screens/ambient';await fs.mkdir(out,{recursive:true});
const chrome=spawn('/usr/bin/google-chrome',['--headless=new','--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--remote-debugging-port=9334','--user-data-dir=/tmp/evorium-ambient-chrome','--no-first-run','--disable-dev-shm-usage','about:blank'],{stdio:'ignore'});
const pause=ms=>new Promise(r=>setTimeout(r,ms));
try{
 let page;for(let i=0;i<100;i++){try{page=(await(await fetch('http://127.0.0.1:9334/json')).json()).find(p=>p.type==='page');if(page)break;}catch{}await pause(200);}
 if(!page)throw Error('Chrome unavailable');const socket=new WebSocket(page.webSocketDebuggerUrl);await new Promise(r=>socket.addEventListener('open',r,{once:true}));
 let serial=0;const pending=new Map();socket.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result);}};
 const cdp=(method,params={})=>new Promise((resolve,reject)=>{const id=++serial;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));});
 async function evaluate(expression){const r=await cdp('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
 await cdp('Page.enable');await cdp('Runtime.enable');await cdp('Network.enable');await cdp('Network.setCacheDisabled',{cacheDisabled:true});
 const single=process.argv.find(a=>a.startsWith('--one='))?.slice(6),reports=[];
 for(const [device,width,height,quality] of [['desktop',1280,720,'high'],['phone',390,844,'low']])for(const type of single?[single]:['off','pigeons','rubbish','rubbish&debris=paper','rubbish&debris=can','cat','dog','fox']){
  await cdp('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:device==='phone'});await cdp('Emulation.setTouchEmulationEnabled',{enabled:device==='phone'});
  await cdp('Page.navigate',{url:`${base}/world3d?test=1&cam=ambient&quality=${quality}&ambient=${type}`});
  let ready=false;for(let i=0;i<300;i++){await pause(200);if(await evaluate('window.__evoriumReady&&window.__evoriumAmbientReady&&!!window.__evoriumTest')){ready=true;break;}const errors=await evaluate('window.__evoriumReport?.errors');if(errors?.length)throw Error(JSON.stringify(errors));}
  if(!ready)throw Error('Ambient page not ready');await pause(1200);
  const r=await evaluate('window.__evoriumReport');if(r.errors.length||r.ambient?.failures.length)throw Error(JSON.stringify(r));
  const kind=type.split('&')[0];if(kind!=='off'&&!r.ambient.events.some(e=>e.kind===kind))throw Error('Missing '+type);
  if(r.ambient?.loaded.length&&['off','pigeons','rubbish'].includes(kind))throw Error('Unexpected animal download');
  if(quality==='low'&&(r.ambient?.events.length>1||r.ambient?.events.some(e=>e.pigeons>2)))throw Error('Low cap exceeded');
  if(['cat','dog','fox'].includes(kind))r.animation=await evaluate('window.__evoriumTest.ambient.testAnimation()');
  r.metrics=await evaluate('window.__evoriumTest.ambient?.inspect()');
  if(['cat','dog','fox'].includes(kind)){const m=r.metrics[0];if(Math.abs(m.min[1]-m.ground)>.015||Math.abs(m.height-({cat:.40,dog:.56,fox:.48}[kind]))>.13)throw Error('Animal scale/grounding failed '+JSON.stringify(m));}
  // Measure a full 30 rendered frames after warm-up; identical framing for off/day cases.
  r.performance=await evaluate(`new Promise(resolve=>{const times=[];let prev=performance.now();function tick(now){times.push(now-prev);prev=now;if(times.length<30)requestAnimationFrame(tick);else resolve({fps:30000/times.reduce((a,b)=>a+b,0),calls:window.__evoriumReport.drawCalls,triangles:window.__evoriumReport.visibleTriangles});}requestAnimationFrame(tick);})`);
  const stem=`${device}-${quality}-${type.replaceAll('&','-').replaceAll('=','-')}`;
  const shot=await cdp('Page.captureScreenshot',{format:'png'});await fs.writeFile(out+'/'+stem+'.png',Buffer.from(shot.data,'base64'));
  if(kind!=='off'){
   if(kind!=='pigeons')r.passage=await evaluate('window.__evoriumTest.ambient.testPassage()');
   r.hiddenPaused=await evaluate('window.__evoriumTest.ambient.testPause()');if(!r.hiddenPaused)throw Error('Hidden tab did not pause');
   r.lifecycle=await evaluate(`(()=>{const a=window.__evoriumTest.ambient;a.update(.05,${kind==='fox'?1:kind==='pigeons'||kind==='dog'?0:1});const result=a.report();return result;})()`);
   if(['fox','dog','pigeons'].includes(kind)&&r.lifecycle.events.length)throw Error('Day/night removal failed');
  }
  if(kind==='pigeons'){
   r.scatter=await evaluate('(async()=>{const a=window.__evoriumTest.ambient;await a.spawn("pigeons");return a.testScatter();})()');
   r.apcScatter=await evaluate('window.__evoriumTest.ambient.testAPCScatter()');
  }
  if(kind==='cat'){
   r.toggle=await evaluate(`(()=>{document.getElementById('street-life').click();return {enabled:window.__evoriumTest.ambient.report().enabled,saved:localStorage.getItem('evorium3d.street-life')};})()`);
   if(r.toggle.enabled||r.toggle.saved!=='false')throw Error('Toggle did not save');
   await evaluate(`localStorage.removeItem('evorium3d.street-life')`);
  }
  reports.push({stem,...r});await fs.writeFile(out+'/'+stem+'.json',JSON.stringify(r,null,2));console.log(stem,JSON.stringify({metrics:r.metrics,perf:r.performance,scatter:r.scatter}));
 }
 await fs.writeFile(out+'/reports.json',JSON.stringify(reports,null,2));socket.close();
}finally{chrome.kill();}
