export const distance=(a,b)=>Math.hypot(...a.map((v,i)=>v-b[i]));
export function nearest(graph,position){return Object.keys(graph.nodes).reduce((a,b)=>distance(graph.nodes[a],position)<distance(graph.nodes[b],position)?a:b);}
export function pathfind(graph,start,end){
 if(!graph.nodes[start]||!graph.nodes[end])return [];
 const neighbors=new Map(Object.keys(graph.nodes).map(n=>[n,[]]));
 for(const [a,b] of graph.edges){neighbors.get(a).push(b);neighbors.get(b).push(a);}
 const open=new Set([start]),cost={[start]:0},from={};
 while(open.size){
 const current=[...open].reduce((a,b)=>(cost[a]+distance(graph.nodes[a],graph.nodes[end]))<(cost[b]+distance(graph.nodes[b],graph.nodes[end]))?a:b);
 if(current===end){const result=[end];while(from[result[0]])result.unshift(from[result[0]]);return result;}
 open.delete(current);
 for(const n of neighbors.get(current)){const c=cost[current]+distance(graph.nodes[current],graph.nodes[n]);if(c<(cost[n]??Infinity)){cost[n]=c;from[n]=current;open.add(n);}}
 }return [];
}
export function slotPosition(waypoint,slot=0){const [x,y,z]=waypoint.position;return [x+Math.cos(waypoint.yaw)*slot*.7,y,z-Math.sin(waypoint.yaw)*slot*.7];}
