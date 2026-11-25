export function lookupCast(cast, name) {
 if (!Object.hasOwn(cast, name) || !cast[name].model) throw Error('Missing cast model for '+name);
 return cast[name];
}

// Cache only requested models, and report a broken asset once per page load.
export function createCastCache(cast, loadModel, onError=()=>{}) {
 const pending = new Map();
 return {
  get(name) {
   if (!pending.has(name)) {
    pending.set(name, Promise.resolve().then(async () => {
     const model = lookupCast(cast, name).model;
     return await loadModel(model);
    }).catch(error => {
     onError({name, model:cast[name]?.model, error:String(error)});
     throw error;
    }));
   }
   return pending.get(name);
  },
  loaded() { return [...pending.keys()]; },
 };
}
