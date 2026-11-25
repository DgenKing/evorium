import {request} from './net.js';

export function gameMessage(event, active) {
 if(!active || event.source!==active.frame.contentWindow || event.origin!=='null')return null;
 const data=event.data;
 if(!data || typeof data!=='object' || Array.isArray(data))return null;
 if(data.type==='evorium:exit'&&Object.keys(data).length===1)return {exit:true};
 if(data.type!=='evorium:score'||data.slug!==active.game.slug||Object.keys(data).length!==3)return null;
 const spec=active.game.score||{};
 return Number.isSafeInteger(data.score)&&data.score>=(spec.min??0)&&data.score<=(spec.max??2147483647)
  ? {score:data.score}:null;
}

function formatBest(game,value) {
 if(value==null)return 'Your best: —';
 const unit=game.score?.unit||'points';
 const score=['wave','arena'].includes(unit)?unit+' '+value:value.toLocaleString()+' '+unit;
 return 'Your best: '+score;
}

export class ArcadeGames {
 constructor({arcade, player, input, canvas, toast}) {
  Object.assign(this,{arcade,player,input,canvas,toast,bests:{},active:null});
  const $=id=>document.getElementById(id);
  this.dialog=$('arcade-game');this.slot=$('arcade-frame-slot');this.title=$('arcade-game-title');
  this.best=$('arcade-game-best');this.hint=$('arcade-play-hint');
  this.play=$('arcade-play');this.exit=$('arcade-exit');
  this.play.onclick=()=>{if(!input.blocked)this.open(this.nearby());};
  this.exit.onclick=()=>this.close();
  this.dialog.addEventListener('cancel',event=>{event.preventDefault();this.close();});
  addEventListener('message',event=>this.receive(event));
  request('/arcade/scores').then(scores=>{
   this.bests={...scores,...this.bests};this.updateLabels();
  }).catch(()=>{});
 }

 nearby() {
  if(!this.arcade.contains(this.player.position))return null;
  let game=null,best=1.65;
  for(const entry of this.arcade.games.values()) {
   const p=this.player.position,q=entry.position;
   const distance=Math.hypot(p.x-q.x,p.z-q.z);
   if(distance<best){best=distance;game=entry;}
  }
  return game;
 }

 updateLabels() {
  for(const game of this.arcade.games.values())game.drawBest(formatBest(game,this.bests[game.slug]));
  if(this.active)this.best.textContent=formatBest(this.active.game,this.bests[this.active.game.slug]);
 }

 welcome() {
  const games=[...this.arcade.games.values()].sort((a,b)=>a.placement.localeCompare(b.placement)).map(g=>g.title);
  return 'Gun Street Amusements. You can play '+games.join(', ')+
   '. Walk up to a machine or the pool table and press E (tap Play on a phone). Esc leaves a game.';
 }

 updateHint(game) {
  // Say what's playable once each time the player walks in.
  const inside=this.arcade.contains(this.player.position);
  if(inside&&!this.inside&&!this.input.blocked)this.toast(this.welcome());
  this.inside=inside;
  this.hint.hidden=this.play.hidden=!game||this.input.blocked;
  if(!this.hint.hidden){
   const text=game.title+' · E to play · '+formatBest(game,this.bests[game.slug]);
   if(this.hint.textContent!==text)this.hint.textContent=text;
   this.play.setAttribute('aria-label','Play '+game.title);
  }
 }

 open(game) {
  if(!game||this.active||this.input.blocked)return false;
  const frame=document.createElement('iframe');
  frame.setAttribute('sandbox','allow-scripts');
  frame.referrerPolicy='no-referrer';
  if(game.motion)frame.allow='accelerometer *; gyroscope *';
  frame.title=game.title;
  frame.src='/static/games/'+encodeURIComponent(game.slug)+'/index.html';
  const active={frame,game};
  this.active=active;
  this.title.textContent=game.title;
  this.best.textContent=formatBest(game,this.bests[game.slug]);
  this.input.reset();this.input.blocked=true;
  this.player.velocity.set(0,0,0);
  this.updateHint(null);
  frame.addEventListener('load',()=>{if(this.active===active)frame.focus();});
  this.slot.replaceChildren(frame);
  this.dialog.showModal();
  return true;
 }

 close() {
  if(!this.active)return;
  this.active=null;
  this.slot.replaceChildren();
  this.dialog.close();
  this.input.reset();this.input.blocked=false;
  this.canvas.focus({preventScroll:true});
 }

 async receive(event) {
  const active=this.active,message=gameMessage(event,active);
  if(!message)return;
  if(message.exit){this.close();return;}
  const {game}=active, {score}=message;
  const current=this.bests[game.slug];
  if(current!=null&&(game.score?.lower?score>=current:score<=current))return;
  try {
   const {best}=await request('/arcade/scores/'+encodeURIComponent(game.slug),{score});
   const cached=this.bests[game.slug];
   if(cached==null||(game.score?.lower?best<cached:best>cached))this.bests[game.slug]=best;
   this.updateLabels();
  } catch(error) {
   if(this.active===active)this.best.textContent='Score could not be saved';
   else this.toast(error.message);
  }
 }
}
