import * as THREE from 'three';
import {Octree} from 'three/addons/math/Octree.js';

const material = (color, options={}) => new THREE.MeshStandardMaterial({color, roughness:.76, ...options});
const glow = color => new THREE.MeshBasicMaterial({color});

// The Henry Street kit's mock mill backdrop crosses this surveyed footprint.
// Clip its rendered fragments here, keeping the adjoining kit and its exterior intact.
function cutBackdrops(set, group, outline, height) {
 const transform=group.matrixWorld.clone().invert();
 const points=outline.map(([x,z])=>new THREE.Vector2(x,z));
 const materials=new Set(), depth=new THREE.MeshDepthMaterial({depthPacking:THREE.RGBADepthPacking});
 function clip(finish){
  if(materials.has(finish))return;
  materials.add(finish);
  const previous=finish.onBeforeCompile;
  finish.onBeforeCompile=function(shader,renderer){
   previous.call(this,shader,renderer);
   shader.uniforms.arcadeInverse={value:transform};
   shader.uniforms.arcadeOutline={value:points};
   shader.vertexShader=`uniform mat4 arcadeInverse;
varying vec3 arcadeLocal;
`+shader.vertexShader.replace('#include <project_vertex>',`
    arcadeLocal=(arcadeInverse * modelMatrix * vec4(transformed,1.0)).xyz;
    #include <project_vertex>
   `);
   shader.fragmentShader=`varying vec3 arcadeLocal;
uniform vec2 arcadeOutline[${points.length}];
`+shader.fragmentShader.replace('void main() {',`void main() {
    if(arcadeLocal.y>-.05 && arcadeLocal.y<${height.toFixed(3)} &&
       arcadeLocal.x>-11.58 && arcadeLocal.x<6.74 && arcadeLocal.z>-.06 && arcadeLocal.z<24.66){
     bool inside=false;
     for(int i=0;i<${points.length};i++){
      vec2 a=arcadeOutline[i],b=arcadeOutline[(i+1)%${points.length}];
      if((a.y>arcadeLocal.z)!=(b.y>arcadeLocal.z)){
       if(arcadeLocal.x<(b.x-a.x)*(arcadeLocal.z-a.y)/(b.y-a.y)+a.x)inside=!inside;
      }
     }
     if(inside)discard;
    }
   `);
  };
  finish.needsUpdate=true;
 }
 clip(depth);
 set.traverse(mesh=>{
  if(!mesh.isMesh)return;
  for(const finish of [mesh.material].flat())clip(finish);
  if(mesh.castShadow)mesh.customDepthMaterial=depth;
 });
}

export function createArcade(world, data, layout) {
 const group = new THREE.Group(), collision = new THREE.Group();
 const [wx,wz] = layout.origin;
 const floor = world.ground(wx,wz)+.03;
 for(const root of [group,collision]){
  root.position.set(wx,floor,wz);
  root.rotation.y=layout.yaw;
 }
 const brick=material(0x624039), dark=material(0x282035), metal=material(0x352647);
 const blue=glow(0x54e4ef), pink=glow(0xfc63bc), gold=glow(0xf6cf71);
 function box(x,y,z,w,h,d,finish,solid=false,parent=group){
  const geometry=new THREE.BoxGeometry(w,h,d);
  const mesh=new THREE.Mesh(geometry,finish);mesh.position.set(x,y,z);
  parent.add(mesh);
  if(solid){const hull=new THREE.Mesh(geometry);hull.position.copy(mesh.position);collision.add(hull);}
  return mesh;
 }
 function wall(a,b,height=layout.height,y=height/2){
  const x=(a[0]+b[0])/2,z=(a[1]+b[1])/2,d=Math.hypot(a[0]-b[0],a[1]-b[1]);
  const panel=box(x,y,z,d+.1,height,.22,brick,true);
  panel.rotation.y=-Math.atan2(b[1]-a[1],b[0]-a[0]);
  collision.children.at(-1).rotation.copy(panel.rotation);
 }
 const outline=layout.room_outline;
 for(let i=0;i<outline.length;i++){
  const a=outline[i],b=outline[(i+1)%outline.length];
  if(i===layout.door_segment){
   wall(a,[1.45,0]);wall([-1.45,0],b);wall([1.45,0],[-1.45,0],2.25,layout.height-1.125);
  }else wall(a,b);
 }
 function surface(y,finish,solid=false,flip=false){
  const shape=new THREE.Shape(outline.map(([x,z])=>new THREE.Vector2(x,-z)));
  const mesh=new THREE.Mesh(new THREE.ShapeGeometry(shape),finish);
  mesh.rotation.x=-Math.PI/2;mesh.position.y=y;
  if(flip)mesh.material.side=THREE.DoubleSide;
  group.add(mesh);
  if(solid) collision.add(mesh.clone());
 }
 surface(0,dark,true);surface(layout.height,material(0x21212b),false,true);
 box(0,3.57,-.24,11.8,1.18,.33,metal);
 box(0,2.91,-.44,11.8,.04,.06,blue);
 box(0,4.23,-.44,11.8,.04,.06,pink);
 function sign(text,x,y,z,w,h,color,side=0){
  const canvas=document.createElement('canvas');canvas.width=512;canvas.height=100;
  const ctx=canvas.getContext('2d');ctx.clearRect(0,0,512,100);ctx.fillStyle=color;
  ctx.shadowColor=color;ctx.shadowBlur=16;ctx.font='bold 52px system-ui';
  ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(text,256,50,498);
  const map=new THREE.CanvasTexture(canvas);map.colorSpace=THREE.SRGBColorSpace;
  const face=new THREE.Mesh(new THREE.PlaneGeometry(w,h),new THREE.MeshBasicMaterial({map,transparent:true,depthWrite:false}));
  face.rotation.y=side;face.position.set(x,y,z);group.add(face);return face;
 }
 sign('GUN STREET',3.15,3.65,-.425,5.1,1.05,'#79fff9',Math.PI);
 const flicker=sign('AMUSEMENTS',-2.55,3.65,-.425,6.15,1.05,'#ff82ce',Math.PI);
 sign('CHANGE',3.8,2.52,2.63,2.05,.53,'#ffe18c',Math.PI);
 const boothClosed=sign('BOOTH CLOSED',3.8,1.85,2.62,2.15,.49,'#ffb499',Math.PI);
 const shutter=box(3.8,1.61,2.68,2.45,1.23,.1,metal);
 box(3.8,.53,2.75,2.7,1.06,.72,metal,true);
 box(3.8,1.11,2.75,2.8,.10,.8,gold);
 for(const x of [2.48,5.12])box(x,1.78,2.75,.09,1.34,.10,metal);
 // Two rows of two-player pushers. Controls sit on the aisle side.
 for(const [row,xs,z] of [[0,[-8,-5.7,-3.4],5.15],[1,[-8.9,-6.55,-4.2],10.15]]){
  for(const x of xs){
   const accent=row?blue:pink;
   box(x,.55,z,1.9,1.1,.95,metal,true);
   box(x,1.15,z+.03,1.81,.12,.77,accent);
   box(x,1.58,z+.35,1.8,.68,.14,metal);
   box(x,1.64,z+.25,1.66,.36,.05,accent);
   for(const seat of [-.48,.48])box(x+seat,1.19,z-.36,.14,.05,.12,gold);
  }
 }
 for(const z of [8.8,10.2,11.6,13]){
  box(5.83,1.02,z,.82,2.04,1.08,metal,true);
  box(5.39,1.53,z,.09,.68,.76,gold);
  for(const dz of [-.25,0,.25])box(5.32,1.56,z+dz,.06,.29,.16,pink);
  box(5.36,.93,z,.13,.09,.77,blue);
 }
 // Claw glass, toy shapes and the hanging grabber.
 box(4.15,.48,7.05,1.45,.96,1.36,metal,true);
 const glass=material(0x66bccc,{transparent:true,opacity:.18,depthWrite:false});
 box(4.15,1.63,7.05,1.38,1.34,1.27,glass);
 box(4.15,2.35,7.05,1.49,.14,1.39,blue);
 box(4.15,2.02,7.05,.035,.51,.035,gold);
 for(const dx of [-.12,.12])box(4.15+dx,1.77,7.05,.054,.22,.054,gold);
 for(let i=0;i<5;i++)box(3.66+i*.24,1.05+(i%2)*.09,7.16-(i%2)*.29,.2,.19,.18,i%2?pink:gold);
 // Air hockey stands clear of the practice spots and the back aisle.
 box(-4.5,.82,17.75,2.1,.14,2.45,metal,true);
 box(-4.5,.91,17.75,1.84,.035,2.22,material(0x85b9bf));
 box(-4.5,.939,17.75,1.8,.02,.036,pink);
 for(const x of [-5.33,-3.68])for(const z of [16.79,18.7])box(x,.37,z,.14,.74,.14,metal,true);
 for(const z of [16.96,18.54])box(-4.5,.96,z,.20,.05,.17,pink);
 const pads=material(0x563350);
 for(const id of ['cabinet-1','cabinet-2','cabinet-3','cabinet-4','pool-table']){
  const [x,z]=layout.spots[id], pool=id==='pool-table';
  const marker=box(x,.008,z,pool?2.25:.85,.014,pool?2.7:1.04,pads);
  marker.name=id;
 }
 const home=layout.spots['arcade-home'];
 box(home[0],1,24.45,1.15,2,.15,metal);
 sign('STAIRS',home[0],2.37,24.34,1.28,.36,'#ffe18c',Math.PI);
 for(const [x,z,color,power] of [[0,-1,0xff5da9,17],[-4,5,0x736bff,25],[2,9,0x56ebff,19],[-5,16,0xef61cb,27],[-2,22,0x627eff,19]]){
  const light=new THREE.PointLight(color,power,11,1.65);
  light.position.set(x,2.8,z);group.add(light);
 }
 for(const z of [2,6,11,17,22])box(-3.8,4.83,z,7,.06,.08,z%2?pink:blue);
 world.scene.add(group);
 world.collisionRoot.add(collision);
 world.collisionRoot.updateMatrixWorld(true);
 world.octree=new Octree().fromGraphNode(world.collisionRoot);
 const positions={...layout.nodes,...layout.spots};
 group.updateMatrixWorld(true);
 cutBackdrops(world.set,group,outline,layout.height);
 for(const [id,[x,z]] of Object.entries(positions)){
  const position=group.localToWorld(new THREE.Vector3(x,0,z)).toArray();
  data.routes.nodes[id]=position;
  data.routes.neighbors.set(id,[]);
  if(id in layout.spots)data.waypoints[id]={position,yaw:layout.yaw};
 }
 for(const [a,b] of layout.edges){
  if(!data.routes.neighbors.has(a)||!data.routes.neighbors.has(b))throw Error('Broken arcade route: '+a+' → '+b);
  data.routes.edges.push([a,b]);data.routes.neighbors.get(a).push(b);data.routes.neighbors.get(b).push(a);
 }
 function contains(position){
  const p=group.worldToLocal(new THREE.Vector3(position.x,position.y||0,position.z));
  let inside=false;
  for(let i=0,j=outline.length-1;i<outline.length;j=i++){
   const [ax,az]=outline[i],[bx,bz]=outline[j];
   if((az>p.z)!==(bz>p.z) && p.x<(bx-ax)*(p.z-az)/(bz-az)+ax)inside=!inside;
  }
  return inside;
 }
 return {contains,group,
  setBooth(open){shutter.visible=boothClosed.visible=!open;},
  update(time){flicker.visible=!(time%1700>1510&&time%1700<1590);}
 };
}
