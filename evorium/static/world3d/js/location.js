const AREA = 'Ancoats, Manchester';
const openSpaceTypes = new Set(['square', 'park', 'garden', 'playground', 'common', 'village_green']);

export function segmentDistanceSquared(x, z, [ax, az], [bx, bz]) {
 const dx = bx - ax, dz = bz - az;
 const length = dx * dx + dz * dz;
 const t = length ? Math.max(0, Math.min(1, ((x - ax) * dx + (z - az) * dz) / length)) : 0;
 return (x - ax - t * dx) ** 2 + (z - az - t * dz) ** 2;
}

export function containsPoint(shape, x, z) {
 let inside = false;
 for (let i = 0, j = shape.length - 1; i < shape.length; j = i++) {
  const [ax, az] = shape[i], [bx, bz] = shape[j];
  if ((az > z) !== (bz > z) && x < ax + (bx - ax) * (z - az) / (bz - az)) inside = !inside;
 }
 return inside;
}

export function nearestStreet(roads, x, z, radius = 15) {
 let name = '', best = radius ** 2;
 for (const road of roads) {
  if (!road.name) continue;
  for (let i = 1; i < road.line.length; i++) {
   const distance = segmentDistanceSquared(x, z, road.line[i - 1], road.line[i]);
   if (distance < best) {
    best = distance;
    name = road.name;
   }
  }
 }
 return name;
}

export function locationLabel(position, place, places, map) {
 const current = places.find(entry => entry.key === place);
 if (current?.indoor) return current.name;
 const {x, z} = position;
 const space = map?.open_spaces.find(entry =>
  entry.name && openSpaceTypes.has(entry.type) && containsPoint(entry.shape, x, z));
 if (space) return space.name;
 if (current?.kind === 'towpath') return current.name;
 const street = nearestStreet(map?.roads ?? [], x, z);
 return street ? `${street} · ${AREA}` : AREA;
}
