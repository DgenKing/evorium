import assert from 'node:assert/strict';
import fs from 'node:fs';

const read = path => fs.readFileSync(new URL(path, import.meta.url), 'utf8');
const main = read('../evorium/static/world3d/js/main.js');
const assets = read('../evorium/static/world3d/js/assets.js');
const world = read('../evorium/static/world3d/js/world.js');

// The city is the normal map; ?city=0 gives the old street, and ?test=1 pages keep the old street unless ?city=1.
assert.ok(main.includes("const cityEnabled=params.has('city')?params.get('city')==='1':!test;"), 'city is the default outside tests');
assert.match(main, /loadData\(cityEnabled\)/);
assert.ok(main.includes('data.cast,cityEnabled)'), 'city flag reaches the asset loader');
assert.match(assets, /cityEnabled\?\[['"]city['"]\]/);
assert.match(assets, /if\(cityEnabled\)\s*\{[^}]*city-collision/s);
assert.ok(assets.includes("if(cityEnabled){const [city,cityCollision]") && assets.includes("city-props.glb"));
assert.match(world, /assets\.cityProps\?\.scene/);

// Map credits are kept off the game screen: as text in the settings panel, the guide and the website.
const page = read('../evorium/static/world3d/index.html'), guide = read('../evorium/static/guide.html'), site = read('../website/index.html');
assert.ok(!world.includes("badge.id='city-attribution'"), 'no attribution badge over the game');
assert.match(world, /credit\.textContent\s*=\s*attribution/);
for (const text of [page, guide, site]) { assert.match(text, /OpenStreetMap contributors/); assert.match(text, /Open Government Licence/); }

console.log('City opt-in wiring and text attribution assertions passed.');
