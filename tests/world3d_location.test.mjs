import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {locationLabel, nearestStreet} from '../evorium/static/world3d/js/location.js';
import {spawnAt} from '../evorium/static/world3d/js/player-position.js';

const read = name => JSON.parse(readFileSync(new URL(`../evorium/static/world3d/data/${name}.json`, import.meta.url)));
const map = read('map2d'), city = read('city');

test('the heading uses street lines from the same local grid as the 3D city', () => {
 assert.deepEqual(map.origin, city.origin);
 assert.deepEqual(map.bounds, [city.bounds.min, city.bounds.max]);
 for (const [x, z, name] of [[-97, 98, 'Henry Street'], [20, -49, 'Gun Street'], [46, 3, 'Blossom Street']]) {
  assert.equal(nearestStreet(map.roads, x, z), name);
  assert.equal(locationLabel({x, z}, 'street', [], map), `${name} · Ancoats, Manchester`);
 }
 assert.equal(nearestStreet(map.roads, 1000, 1000), '');
 assert.equal(locationLabel({x: 1000, z: 1000}, 'street', [], map), 'Ancoats, Manchester');
});

test('a registered interior or named open space wins over the nearest road', () => {
 const point = {x: 20, z: -49};
 const places = [{key: 'arcade', indoor: true, name: 'Gun Street Amusements'},
  {key: 'pub', indoor: true, name: 'The Crooked Billet'}];
 assert.equal(locationLabel(point, 'arcade', places, map), 'Gun Street Amusements');
 assert.equal(locationLabel(point, 'pub', places, map), 'The Crooked Billet');
 const square = map.open_spaces.find(space => space.id === 'way/198725251');
 const middle = square.shape.reduce(({x, z}, [a, b]) =>
  ({x: x + a / square.shape.length, z: z + b / square.shape.length}), {x: 0, z: 0});
 assert.equal(locationLabel(middle, 'street', [], map), 'Cutting Room Square');
});

test('unsafe checkpoints fall back to the Billet and a clear arcade checkpoint is kept', () => {
 const vector = () => ({y: 0, copy(point) { this.y = point.y; return this; },
  set(x, y, z) { return Object.assign(this, {x, y, z}); }});
 const player = {position: {clone: vector}, blockedByDoor: ({x}) => x === 7, collider: {
  clone: () => ({start: vector(), end: vector()}),
 }};
 const world = {
  bounds: city.bounds, cityTransform: {},
  open: {shop: false}, place: ({x}) => x === 2 ? 'arcade' : x === 5 ? 'shop' : 'street',
  groundHeight: x => x === 6 ? null : 0,
  octree: {capsuleIntersect: () => null},
 };
 const graph = {nodes: {a: [0, 0, 0], b: [10, 0, 0]}, edges: [['a', 'b']]};
 const shape = [[0, -2], [4, -2], [4, 2], [0, 2]];
 const context = {world, player, graph, mapData: {buildings: [{shape}]}};
 const fallback = {point: [-4.62, .06, -.9], yaw: 0};
 const checkpoint = {map: 'city', x: 2, y: .03, z: 0, yaw: .75};
 for (const saved of [null, {...checkpoint, x: 201}, {...checkpoint, x: 1},
  {...checkpoint, z: 30}, {...checkpoint, y: 2}, {...checkpoint, x: 5},
  {...checkpoint, yaw: NaN}, {...checkpoint, x: 6}, {...checkpoint, x: 7}]) {
  assert.equal(spawnAt(saved, context, fallback), fallback);
 }
 const restored = spawnAt(checkpoint, context, fallback);
 assert.deepEqual([restored.point.x, restored.point.y, restored.point.z, restored.yaw], [2, .015, 0, .75]);
 world.octree.capsuleIntersect = () => ({depth: .3});
 assert.equal(spawnAt(checkpoint, context, fallback), fallback);
});
