import * as THREE from 'three';
export class FollowCamera{
 constructor(camera,world){this.camera=camera;this.world=world;this.yaw=0;this.pitch=.22;this.distance=3.5;this.sensitivity=1;this.invert=false;}
 update(dt,position,input){this.yaw-=input.look.x*.004*this.sensitivity;this.pitch=THREE.MathUtils.clamp(this.pitch+input.look.y*.004*this.sensitivity*(this.invert?-1:1),-.35,1.1);this.distance=THREE.MathUtils.clamp(this.distance+input.zoom,1.8,6);const head=position.clone().add(new THREE.Vector3(0,1.5,0));const dir=new THREE.Vector3(Math.sin(this.yaw)*Math.cos(this.pitch),Math.sin(this.pitch),Math.cos(this.yaw)*Math.cos(this.pitch));const distance=this.world.cameraDistance(head,dir,this.distance);this.camera.position.copy(head).addScaledVector(dir,distance);this.camera.lookAt(head);}
}
