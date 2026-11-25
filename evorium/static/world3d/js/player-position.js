import {containsPoint, segmentDistanceSquared} from './location.js';

const kitBounds = {min: [-12, -9.6], max: [11, 5.5]};
const playableRooms = new Set(['pub', 'shop', 'arcade']);

function nearRoute({nodes, edges}, x, z, metres) {
 return edges.some(([a, b]) => {
  const [ax, , az] = nodes[a], [bx, , bz] = nodes[b];
  return segmentDistanceSquared(x, z, [ax, az], [bx, bz]) <= metres ** 2;
 });
}

export function playableStart(saved, {world, player, graph, mapData}) {
 if (!saved || ![saved.x, saved.y, saved.z, saved.yaw].every(Number.isFinite)) return null;
 const {x, y, z} = saved;
 const {min, max} = world.bounds ?? kitBounds;
 if (x < min[0] || x > max[0] || z < min[1] || z > max[1]) return null;

 const point = player.position.clone().set(x, y, z);
 const place = world.place(point);
 if (world.open[place] === false) return null;

 const room = playableRooms.has(place);
 if (world.cityTransform && !room && (!mapData || mapData.buildings.some(building =>
  !building.replaced_by_henry && containsPoint(building.shape, x, z)))) return null;
 // The city graph runs down the street centres; also allow the adjoining pavements.
 if (!nearRoute(graph, x, z, world.cityTransform ? 8 : 2)) return null;

 const ground = world.groundHeight(x, z);
 if (ground === null || Math.abs(y - ground) > .55) return null;
 point.y = ground + .015;
 if (player.blockedByDoor(point)) return null;
 const capsule = player.collider.clone();
 capsule.start.copy(point).y += .35;
 capsule.end.copy(point).y += 1.4;
 if (world.octree.capsuleIntersect(capsule)?.depth > .025) return null;
 return {point, yaw: saved.yaw};
}

export function spawnAt(saved, context, fallback) {
 return playableStart(saved, context) ?? fallback;
}

export function trackPosition(map, player, context) {
 const url = '/player/position';
 const position = player.position.clone();
 const read = () => ({
  map, x: Math.round(position.x * 100) / 100, y: position.y,
  z: Math.round(position.z * 100) / 100,
  yaw: Math.round(player.actor.root.rotation.y * 1000) / 1000,
 });
 let previous = read(), lastAttempt = performance.now(), pending = false;
 let lastMove = performance.now();
 function capture() {
  if (player.grounded) position.copy(player.position);
 }
 async function checkpoint(beacon = false) {
  capture();
  if (pending && !beacon) return;
  const current = read();
  if (current.x === previous.x && current.z === previous.z && current.yaw === previous.yaw) return;
  if (!playableStart(current, context)) return;
  const json = JSON.stringify(current);
  if (beacon && navigator.sendBeacon?.(url, new Blob([json], {type: 'application/json'}))) {
   previous = current;
   return;
  }
  pending = true;
  try {
   const response = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: json, keepalive: beacon});
   if (response.ok) previous = current;
  } catch {
   // A future checkpoint retries after a connection failure.
  } finally {
   pending = false;
  }
 }
 addEventListener('pagehide', () => checkpoint(true));
 document.addEventListener('visibilitychange', () => {
  if (document.hidden) checkpoint(true);
 });
 return (now, moving) => {
  capture();
  if (moving) lastMove = now;
  if (now - lastAttempt >= 5000 && lastMove >= lastAttempt) {
   lastAttempt = now;
   checkpoint();
  }
 };
}
