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

// A city-mode scene must show the manifest's attribution as text, not HTML.
assert.match(world, /city-attribution/);
assert.match(world, /badge\.textContent\s*=\s*attribution/);
assert.match(world, /OpenStreetMap contributors/);
assert.match(world, /Open Government Licence/);

console.log('City opt-in wiring and text attribution assertions passed.');
