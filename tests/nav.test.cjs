/* Shared burger menu: node tests/nav.test.cjs */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {currentPage, PAGES} = require('../evorium/static/nav.js');

test('menu lists exactly Dashboard, Map, 3D, Timeline and Guide (no Home)', () => {
  assert.deepEqual(PAGES.map(p => p.label), ['Dashboard', 'Map', '3D', 'Timeline', 'Guide']);
  assert.ok(!PAGES.some(p => /home/i.test(p.label)));
});

test('the current page is highlighted correctly', () => {
  assert.equal(currentPage('/game', ''), 'dashboard');
  assert.equal(currentPage('/game', '#dashboard'), 'dashboard');
  assert.equal(currentPage('/game', '#map'), 'map');
  assert.equal(currentPage('/world3d', ''), '3d');
  assert.equal(currentPage('/timeline-page', ''), 'timeline');
  assert.equal(currentPage('/guide', ''), 'guide');
});
