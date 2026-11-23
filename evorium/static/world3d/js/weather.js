import * as THREE from 'three';
export function weatherStyle(reading,quality='low'){
 const condition=reading?.condition||'unknown',snow=condition==='snow',wet=!!reading?.raining;
 return {condition,snow,wet,count:snow?(quality==='low'?40:220):wet?(quality==='low'?60:360):0,
  fog:condition==='fog',dark:wet||snow};
}
export class WeatherFX{
 constructor(scene,quality){this.scene=scene;this.quality=quality;this.kind='';this.style=weatherStyle();}
 setQuality(quality){this.quality=quality;this.set(this.reading);}
 set(reading){this.reading=reading;const style=weatherStyle(reading,this.quality);this.style=style;const kind=style.snow?'snow':style.wet?'rain':'none';
 const key=kind+':'+style.count;if(key===this.kind)return;this.kind=key;
 if(this.object){this.scene.remove(this.object);this.object.geometry.dispose();this.object.material.dispose();this.object=null;}
 if(!style.count)return;const positions=new Float32Array(style.count*(style.snow?3:6));
 for(let i=0;i<style.count;i++){const offset=i*(style.snow?3:6);positions[offset]=Math.sin(i*73.1)*12;positions[offset+1]=(i*.173)%8;positions[offset+2]=.5+((i*.371)%5);if(!style.snow){positions[offset+3]=positions[offset];positions[offset+4]=positions[offset+1]+.16;positions[offset+5]=positions[offset+2];}}
 const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.BufferAttribute(positions,3));
 this.object=style.snow?new THREE.Points(geometry,new THREE.PointsMaterial({color:0xf2f6ff,size:.055,transparent:true,opacity:.75,depthWrite:false})):new THREE.LineSegments(geometry,new THREE.LineBasicMaterial({color:0xbacddb,transparent:true,opacity:.38,depthWrite:false}));this.object.frustumCulled=false;this.scene.add(this.object);
 }
 update(dt){if(!this.object)return;const a=this.object.geometry.attributes.position,step=this.style.snow?3:6;
 for(let i=0;i<a.array.length;i+=step){a.array[i+1]-=Math.min(dt,.05)*(this.style.snow?.45:8);if(a.array[i+1]<0)a.array[i+1]=8;if(step===6)a.array[i+4]=a.array[i+1]+.16;}
 a.needsUpdate=true;
 }
}
