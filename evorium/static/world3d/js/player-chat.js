import {request} from './net.js';

const byId = id => document.getElementById(id);
const path = (action, peer) => '/player-chat/' + action + '?peer=' + encodeURIComponent(peer);

export function messageLine(doc, name, text) {
 const line=doc.createElement('p'), label=doc.createElement('strong'), body=doc.createElement('span');
 label.textContent=name+': ';
 body.textContent=text;
 line.append(label,body);
 return line;
}

export class PlayerChat {
 constructor(ui) {
  this.ui=ui;
  this.contacts=[];
  this.unread=[];
  this.stream=new Map();
  this.readThrough=new Map();
  this.announced=new Set();
  this.generation=0;
  this.peer=null;
  this.cursor=null;
 }

 start(peer) {
  byId('player-messages').onclick=()=>this.toggleInbox();
  this.poll();
  if(peer)this.open(peer);
 }

 toggleInbox() {
  const panel=byId('player-inbox');
  panel.hidden=!panel.hidden;
  byId('player-messages').setAttribute('aria-expanded',String(!panel.hidden));
  if(!panel.hidden)this.renderInbox();
 }

 hideInbox() {
  byId('player-inbox').hidden=true;
  byId('player-messages').setAttribute('aria-expanded','false');
 }

 async open(peer, name) {
  if(!peer||this.ui.busy)return;
  const generation=++this.generation;
  this.hideInbox();
  if (this.ui.target) this.ui.target.chatting=false;
  this.ui.target=null;
  this.peer=peer;
  this.stream.clear();
  this.latestId=0;
  this.ui.openPanel(name || this.contacts.find(p=>p.account===peer)?.name || peer,300);
  byId('player-message-toast').hidden=true;
  byId('catchup').hidden=true;
  this.schedule(0);
  try {
   const messages=await request(path('thread',peer));
   if(this.generation!==generation)return;
   if(messages.length&&!name){
    const latest=messages.at(-1);
    byId('chat-name').textContent=latest.sender===peer?latest.sender_name:latest.recipient_name;
   }
   for(const message of messages)this.stream.set(message.id,message);
   this.renderThread();
   await this.markRead(peer);
  } catch(error) {
   if(this.generation===generation)this.ui.toast(error.message);
  }
 }

 close() {
  ++this.generation;
  this.peer=null;
  this.stream.clear();
  this.schedule(10000);
 }

 async send(text) {
  const message=await request(path('send',this.peer),{text});
  this.accept(message);
  this.ui.actors.directSpeech(message);
 }

 accept(message) {
  const mine=message.sender!==this.peer && message.recipient===this.peer;
  if((message.sender!==this.peer&&!mine)||!this.peer||this.stream.has(message.id))return;
  this.stream.set(message.id,message);
  if(message.id<this.latestId)this.renderThread();
  else{
   this.latestId=message.id;
   this.ui.line(mine?'You':message.sender_name,message.text);
  }
 }

 renderThread() {
  byId('chat-log').replaceChildren();
  for(const message of [...this.stream.values()].sort((a,b)=>a.id-b.id)){
   this.latestId=message.id;
   this.ui.line(message.sender===this.peer?message.sender_name:'You',message.text);
  }
 }

 async markRead(peer) {
  const previous=this.readThrough.get(peer)||0;
  const through=Math.max(previous,...[...this.stream.values()].filter(m=>m.sender===peer).map(m=>m.id));
  if(through<=previous)return;
  this.readThrough.set(peer,through);
  this.updateUnread();
  try {
   await request(path('read',peer),{through});
  } catch {
   if(this.readThrough.get(peer)===through)this.readThrough.set(peer,previous);
   this.updateUnread();
  }
 }

 updateUnread() {
  const unseen=this.unread.filter(m=>m.id>(this.readThrough.get(m.sender)||0));
  byId('player-unread-dot').hidden=!unseen.length;
  if(!unseen.length)byId('player-message-toast').hidden=true;
  if(!byId('player-inbox').hidden)this.renderInbox(unseen);
  return unseen;
 }

 renderInbox(unseen=this.unread.filter(m=>m.id>(this.readThrough.get(m.sender)||0))) {
  const senders=new Set(unseen.map(m=>m.sender));
  const list=byId('player-inbox-list');
  list.replaceChildren();
  if(!this.contacts.length) {
   const item=document.createElement('li');
   item.textContent='No other player accounts.';
   list.append(item);
  }
  for(const contact of this.contacts) {
   const item=document.createElement('li'), button=document.createElement('button');
   button.type='button';
   button.textContent=contact.name+(senders.has(contact.account)?' · Unread':'');
   button.onclick=()=>this.open(contact.account,contact.name);
   item.append(button);
   list.append(item);
  }
 }

 notify(message) {
  const toast=byId('player-message-toast');
  this.previewId=message.id;
  toast.textContent=message.sender_name+': '+message.text;
  toast.onclick=()=>this.open(message.sender,message.sender_name);
  toast.hidden=false;
 }

 showAway(messages) {
  if(!messages.length)return;
  const list=byId('catchup-private');
  list.replaceChildren(...messages.map(message=>{
   const item=document.createElement('li'), button=document.createElement('button');
   button.type='button';
   button.textContent=message.sender_name+': '+message.text;
   button.onclick=()=>this.open(message.sender,message.sender_name);
   item.append(button);
   return item;
  }));
  byId('catchup').hidden=false;
 }

 schedule(delay) {
  clearTimeout(this.timer);
  this.timer=setTimeout(()=>this.poll(),delay);
 }

 async poll() {
  if(this.polling)return;
  this.polling=true;
  const initial=this.cursor===null;
  try {
   const data=await request('/player-chat'+(initial?'':'?after='+this.cursor));
   this.cursor=data.cursor;
   this.contacts=data.contacts;
   this.unread=data.unread;
   for(const message of data.messages) {
    const received=message.recipient===data.account;
    const peer=received?message.sender:message.recipient;
    if(this.peer===peer)this.accept(message);
    if(received)this.ui.actors.directSpeech(message);
   }
   if(this.peer){
    if(initial)for(const message of [...data.unread].reverse())this.accept(message);
    await this.markRead(this.peer);
   }
   const unseen=this.updateUnread().filter(m=>m.sender!==this.peer);
   if(initial && !this.peer)this.showAway(unseen);
   const preview=unseen.find(m=>!this.announced.has(m.id));
   if(preview)this.notify(preview);
   else if(!unseen.some(message=>message.id===this.previewId))byId('player-message-toast').hidden=true;
   this.announced=new Set(unseen.map(m=>m.id));
  } catch(error) {
   if(this.peer)this.ui.toast(error.message);
  } finally {
   this.polling=false;
   this.schedule(this.peer?2000:10000);
  }
 }
}
