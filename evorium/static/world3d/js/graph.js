export const distance=(a,b)=>Math.hypot(...a.map((v,i)=>v-b[i]));
export function nearest(graph,position){return Object.keys(graph.nodes).reduce((a,b)=>distance(graph.nodes[a],position)<distance(graph.nodes[b],position)?a:b);}
export function pathfind(graph,start,end){
 if(!graph.nodes[start]||!graph.nodes[end])return [];
 const neighbors=graph.neighbors||new Map(Object.keys(graph.nodes).map(n=>[n,[]]));
 if(!graph.neighbors)for(const [a,b] of graph.edges){neighbors.get(a)?.push(b);neighbors.get(b)?.push(a);}
 const open=new Set([start]),cost={[start]:0},from={};
 while(open.size){
 const current=[...open].reduce((a,b)=>(cost[a]+distance(graph.nodes[a],graph.nodes[end]))<(cost[b]+distance(graph.nodes[b],graph.nodes[end]))?a:b);
 if(current===end){const result=[end];while(from[result[0]])result.unshift(from[result[0]]);return result;}
 open.delete(current);
 for(const n of neighbors.get(current)){const c=cost[current]+distance(graph.nodes[current],graph.nodes[n]);if(c<(cost[n]??Infinity)){cost[n]=c;from[n]=current;open.add(n);}}
 }return [];
}
// City mode uses a binary min-heap so larger route graphs do not scan every open node.
export function pathfindFast(graph,start,end){
 if(!graph.nodes[start]||!graph.nodes[end])return [];
 const neighbors=graph.neighbors||new Map(Object.keys(graph.nodes).map(n=>[n,[]]));
 if(!graph.neighbors)for(const [a,b] of graph.edges){neighbors.get(a)?.push(b);neighbors.get(b)?.push(a);}
 const heap=[];const push=item=>{let i=heap.push(item)-1;while(i){const p=(i-1)>>1;if(heap[p].priority<=item.priority)break;heap[i]=heap[p];i=p;}heap[i]=item;};
 const pop=()=>{const first=heap[0],last=heap.pop();if(heap.length){let i=0;while(true){let c=i*2+1;if(c>=heap.length)break;if(c+1<heap.length&&heap[c+1].priority<heap[c].priority)c++;if(heap[c].priority>=last.priority)break;heap[i]=heap[c];i=c;}heap[i]=last;}return first;};
 const cost=new Map([[start,0]]),from=new Map();push({node:start,priority:distance(graph.nodes[start],graph.nodes[end])});
 while(heap.length){const current=pop().node;if(current===end){const result=[end];while(from.has(result[0]))result.unshift(from.get(result[0]));return result;}
 for(const next of neighbors.get(current)||[]){const candidate=cost.get(current)+distance(graph.nodes[current],graph.nodes[next]);if(candidate<(cost.get(next)??Infinity)){cost.set(next,candidate);from.set(next,current);push({node:next,priority:candidate+distance(graph.nodes[next],graph.nodes[end])});}}
 }return [];
}
export function transformRoutes(data,position=[0,0],rotationDegrees=0){
 const angle=rotationDegrees*Math.PI/180,c=Math.cos(angle),s=Math.sin(angle),move=p=>{const x=p[0],z=p[2];p[0]=position[0]+x*c+z*s;p[2]=position[1]-x*s+z*c;};
 for(const node of Object.values(data.routes.nodes))move(node);
 for(const waypoint of Object.values(data.waypoints)){move(waypoint.position);waypoint.yaw+=angle;}
}
export function buildCityRouteGraph(navmesh,waypoints,fallbackGraph={nodes:{},edges:[]}){
 const vertices=navmesh?.vertices||[],polygons=navmesh?.polygons||[];
 if(!vertices.length||!polygons.length)return fallbackGraph;
 let nodes={},edges=[],centres=[];
 if(navmesh.graph?.nodes&&navmesh.graph?.edges){nodes={...navmesh.graph.nodes};edges=navmesh.graph.edges.map(e=>[...e]);centres=Object.values(nodes);}
 else{for(let i=0;i<polygons.length;i++){const points=polygons[i].map(index=>vertices[index]).filter(Boolean);if(!points.length)continue;const centre=[0,1,2].map(axis=>points.reduce((sum,p)=>sum+p[axis],0)/points.length);nodes[`C${i}`]=centre;centres[i]=centre;}const edgeOwners=new Map();for(let i=0;i<polygons.length;i++){const poly=polygons[i];for(let j=0;j<poly.length;j++){const a=poly[j],b=poly[(j+1)%poly.length],key=a<b?`${a}:${b}`:`${b}:${a}`,owner=edgeOwners.get(key);if(owner!==undefined&&centres[owner]&&centres[i])edges.push([`C${owner}`,`C${i}`]);else edgeOwners.set(key,i);}}for(const portal of navmesh.portals||[]){const a=Number(portal.a),b=Number(portal.b);if(Number.isInteger(a)&&Number.isInteger(b)&&centres[a]&&centres[b])edges.push([`C${a}`,`C${b}`]);}}
 const endpoints={STREET_LEFT:fallbackGraph.nodes.STREET_LEFT,STREET_RIGHT:fallbackGraph.nodes.STREET_RIGHT,UPSTAIRS:fallbackGraph.nodes.UPSTAIRS};for(const [name,waypoint] of Object.entries(waypoints||{}))endpoints[name]=waypoint.position;
 const baseNodes=Object.entries(nodes);
 for(const [name,position] of Object.entries(endpoints)){if(!Array.isArray(position)||position.length<3)continue;nodes[name]=position;let best=null,bestDistance=Infinity;for(const [node,point] of baseNodes){const d=distance(position,point);if(d<bestDistance){best=node;bestDistance=d;}}if(best)edges.push([name,best]);}
 const unique=new Map();for(const [a,b] of edges){if(a===b||!nodes[a]||!nodes[b])continue;const key=a<b?`${a}\0${b}`:`${b}\0${a}`;unique.set(key,a<b?[a,b]:[b,a]);}
 const cleanEdges=[...unique.values()],neighbors=new Map(Object.keys(nodes).map(name=>[name,[]]));for(const [a,b] of cleanEdges){neighbors.get(a).push(b);neighbors.get(b).push(a);}return {nodes,edges:cleanEdges,neighbors};
}
export function slotPosition(waypoint,slot=0){const [x,y,z]=waypoint.position;return [x+Math.cos(waypoint.yaw)*slot*.7,y,z-Math.sin(waypoint.yaw)*slot*.7];}
