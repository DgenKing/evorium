import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const source = await fs.readFile(path.join(root, 'evorium/static/world3d/js/night.js'), 'utf8');
const isolated = source.replace("import * as THREE from 'three';", 'const THREE = {};');
const url = `data:text/javascript;base64,${Buffer.from(isolated).toString('base64')}`;
const {moonPhase, skyClarity} = await import(url);

const newMoon = moonPhase(new Date('2000-01-06T18:14:00Z'));
const fullMoon = moonPhase(new Date('2000-01-21T11:42:00Z'));
assert.ok(newMoon < 0.001 || newMoon > 0.999, `new moon phase should wrap to zero, got ${newMoon}`);
assert.ok(Math.abs(fullMoon - 0.5) < 0.015, `full moon phase should be about 0.5, got ${fullMoon}`);
assert.deepEqual(skyClarity({condition: 'clear'}), [1, 1]);
assert.deepEqual(skyClarity({condition: 'cloudy'}), [.35, .75]);
assert.deepEqual(skyClarity({condition: 'rain', wet: true}), [0, 0]);
assert.deepEqual(skyClarity({condition: 'fog', fog: true}), [0, 0]);
assert.deepEqual(skyClarity({condition: 'snow', snow: true}), [0, 0]);

const city = JSON.parse(await fs.readFile(path.join(root, 'evorium/static/world3d/data/city.json'), 'utf8'));
assert.equal(city.lamps.length, 74, 'city manifest should include all lamp head positions');
assert.ok(city.lamps.every(p => p.length === 3 && p.every(Number.isFinite)));
console.log('Night phase, weather clarity and city lamp manifest checks passed');
