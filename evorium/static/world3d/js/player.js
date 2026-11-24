import * as THREE from 'three';
import {Capsule} from 'three/addons/math/Capsule.js';
import {selectAnimation} from './anim.js';
export class Player{
 constructor(actor,world){this.actor=actor;this.world=world;this.position=new THREE.Vector3(-4.62,.01,2);this.actor.root.position.copy(this.position);this.velocity=new THREE.Vector3();this.grounded=false;this.wasGrounded=false;this.place='street';this.collider=new Capsule(new THREE.Vector3(),new THREE.Vector3(),.35);}
 setCollider(){this.collider.start.copy(this.position).y+=.35;this.collider.end.copy(this.position).y+=1.4;}
 update(dt,input,yaw){
 const direction=new THREE.Vector3(input.x,0,input.y).applyAxisAngle(new THREE.Vector3(0,1,0),yaw);if(direction.length()>1)direction.normalize();const speed=input.run?4:1.6;this.velocity.x=direction.x*speed;this.velocity.z=direction.z*speed;if(input.jump&&this.grounded)this.velocity.y=5;this.wasGrounded=this.grounded;
 const substeps=5;
 for(let i=0;i<substeps;i++){const h=dt/substeps;this.velocity.y-=12*h;const old=this.position.clone();this.position.addScaledVector(this.velocity,h);this.setCollider();this.grounded=false;let result=this.world.octree.capsuleIntersect(this.collider);
 if(result){if(result.normal.y>.5){this.grounded=true;this.velocity.y=Math.max(0,this.velocity.y);}else if(this.wasGrounded&&direction.lengthSq()>0){const raised=this.collider.clone();raised.translate(new THREE.Vector3(0,.2,0));if(!this.world.octree.capsuleIntersect(raised)){this.position.y+=.2;result=null;}}
 if(result)this.position.addScaledVector(result.normal,result.depth+.00001);}
 const doorProbe=this.position.clone().add(new THREE.Vector3(0,1,0));
 if(this.world.cityTransform){const {x,z,yaw}=this.world.cityTransform;doorProbe.sub(new THREE.Vector3(x,0,z)).applyAxisAngle(new THREE.Vector3(0,1,0),-yaw);}
 for(const [place,box] of Object.entries(this.world.blockers))if(!this.world.open[place]&&box.clone().expandByScalar(.35).containsPoint(doorProbe)){this.position.copy(old);}
 const bounds=this.world.bounds;if(bounds?.min&&bounds?.max){this.position.x=THREE.MathUtils.clamp(this.position.x,bounds.min[0]+1,bounds.max[0]-1);this.position.z=THREE.MathUtils.clamp(this.position.z,bounds.min[1]+1,bounds.max[1]-1);}else{this.position.x=THREE.MathUtils.clamp(this.position.x,-12,11);this.position.z=THREE.MathUtils.clamp(this.position.z,-9.6,5.5);}if(this.position.y<-3){if(this.world.cityTransform){const t=this.world.cityTransform,c=Math.cos(t.yaw),s=Math.sin(t.yaw);this.position.set(t.x-4.62*c+2*s,.1,t.z+4.62*s+2*c);}else this.position.set(-4.62,.1,2);this.velocity.set(0,0,0);}
 }
 if(direction.lengthSq()>.01){const target=Math.atan2(direction.x,direction.z);this.actor.root.rotation.y+=Math.atan2(Math.sin(target-this.actor.root.rotation.y),Math.cos(target-this.actor.root.rotation.y))*Math.min(1,dt*12);}
 this.actor.root.position.copy(this.position);this.actor.animate(selectAnimation({speed:direction.length()*speed,grounded:this.grounded,verticalSpeed:this.velocity.y,wasGrounded:this.wasGrounded}),dt);this.actor.root.position.copy(this.position);this.place=this.world.place(this.position);
 }
}
