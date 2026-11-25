export function lookupCast(cast,name){return cast[name]||cast.player;}

// Pure and injectable: no network activity until a character is requested.
export function createCastCache(cast,loadModel,loadFallback,onFallback=()=>{}){
 const pending=new Map();
 return {get(name){const config=lookupCast(cast,name),key=config.fallback?name:config.model;
 if(config.fallback){
  if(!pending.has(key))pending.set(key,(async()=>{onFallback({name,model:config.body,planned:true,error:'Dedicated model unavailable'});return {...await loadFallback(),fallback:true};})());
  return pending.get(key);
 }
 if(!pending.has(key))pending.set(key,(async()=>{try{return{gltf:await loadModel(key),fallback:false};}catch(error){onFallback({name,model:key,error:String(error)});const old=await loadFallback();return{...old,fallback:true};}})());
 return pending.get(key);
 },loaded(){return [...pending.keys()];}};
}
