import {request} from './net.js';
import {messageLine,PlayerChat} from './player-chat.js';
export const $=id=>document.getElementById(id);
export class UI{
 constructor(input,actors){this.input=input;this.actors=actors;this.target=null;this.busy=false;this.direct=new PlayerChat(this);
 $('close-chat').onclick=()=>this.closeChat();$('chat-form').onsubmit=e=>{e.preventDefault();this.send();};$('close-card').onclick=()=>$('card').hidden=true;
 const viewport=()=>{if(window.visualViewport)$('chat').style.bottom=Math.max(12,innerHeight-visualViewport.height-visualViewport.offsetTop+12)+'px';};window.visualViewport?.addEventListener('resize',viewport);viewport();
 }
 banner(text){$('connection').textContent=text;$('connection').hidden=!text;}
 toast(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(this.toastTimer);this.toastTimer=setTimeout(()=>$('toast').hidden=true,Math.max(5500,text.length*60));}
 card(p){$('card').hidden=false;$('card-name').textContent=p.first;$('card-detail').textContent=[p.activity,p.mood].filter(Boolean).join(' · ');$('portrait').hidden=!p.portrait;if(p.portrait)$('portrait').src=p.portrait;}
 talk(actor){
  if(!actor||this.busy)return;
  return actor.person.kind==='player'
   ? this.direct.open(actor.person.account,actor.person.name)
   : this.chat(actor);
 }
 openPanel(name,maxLength){
  this.input.blocked=true;this.input.reset();
  $('chat').hidden=false;$('chat-name').textContent=name;$('chat-log').replaceChildren();
  $('message').maxLength=maxLength;$('message').value='';$('message').focus();
 }
 async chat(actor){
  if(!actor||actor.person.kind==='player'||this.busy||this.direct.peer)return;
  if(this.target)this.target.chatting=false;
  this.target=actor;actor.chatting=true;
  this.openPanel(actor.person.first,500);
  try{
   const state=await request('/player');
   if(this.target===actor)for(const m of state.conversation?.messages||[])this.line(m.speaker_name,m.text);
  }catch(e){this.toast(e.message);}
 }
 line(name,text){
  const line=messageLine(document,name,text);
  $('chat-log').append(line);line.scrollIntoView({block:'nearest'});
 }
 async pollPlayer(){
 if(this.busy||this.polling||Date.now()-(this.polledAt||0)<3000)return;
 this.polling=true;this.polledAt=Date.now();
 try{const state=await request('/player');const notice=[state.police?.notice,...(state.police?.outcomes||[]).map(o=>'Police follow-up: '+o)].filter(Boolean).join(' · ');$('police-notice').textContent=notice;$('police-notice').hidden=!notice;
 const conv=state.conversation;
 if(conv&&!this.target&&!this.direct.peer&&!this.busy){const actor=this.actors.people.get(conv.agent_b_id);if(actor){this.target=actor;actor.chatting=true;this.openPanel(actor.person.first,500);for(const m of conv.messages||[])this.line(m.speaker_name,m.text);}}
 }finally{this.polling=false;}
 }
 async send(){
  const text=$('message').value.trim();
  if(!text||this.busy||(!this.target&&!this.direct.peer))return;
  this.busy=true;$('send').disabled=true;
  try{
   if(this.direct.peer)await this.direct.send(text);
   else{
    const r=await request('/player/say',{to_agent_id:this.target.person.id,text});
    this.line('You',text);this.line(this.target.person.first,r.reply.text);this.actors.say(this.target,r.reply.text);
   }
   $('message').value='';
  }catch(e){this.toast(e.message);}finally{this.busy=false;$('send').disabled=false;}
 }
 async closeChat(){
  if(this.busy)return;
  this.direct.hideInbox();
  if(this.direct.peer)this.direct.close();
  else if(this.target){
   try{await request('/player/end',{});}catch(e){this.toast(e.message);return;}
   this.target.chatting=false;this.target=null;
  }
  $('chat').hidden=true;this.input.blocked=false;$('message').blur();
 }
 async initial(skipCatchup=false){
 $('dismiss-catchup').onclick=async()=>{try{if($('catchup-items').childElementCount)await request('/catchup/seen',{});$('catchup').hidden=true;}catch(e){this.toast(e.message);}};
 try{const state=await request('/player');if(!state.name){$('profile').hidden=false;this.input.blocked=true;$('profile-form').onsubmit=async e=>{e.preventDefault();try{await request('/player/profile',{name:$('name').value,about:''});$('profile').hidden=true;this.input.blocked=false;}catch(e){this.toast(e.message);}};}if(skipCatchup)return;const c=await request('/catchup');if(c.items?.length&&!this.direct.peer){$('catchup').hidden=false;$('catchup-text').textContent=c.paragraph||c.text||c.narration||'';$('catchup-items').replaceChildren(...c.items.map(item=>{const li=document.createElement('li');li.textContent=typeof item==='string'?item:item.text;return li;}));}}catch(e){this.toast(e.message);}}
}
