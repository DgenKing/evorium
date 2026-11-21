/* Shared burger menu: node tests/nav.test.cjs */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {currentPage, PAGES} = require('../evorium/static/nav.js');

test('menu lists exactly Dashboard, Map, 3D and Timeline (no Home)', () => {
  assert.deepEqual(PAGES.map(p => p.label), ['Dashboard', 'Map', '3D', 'Timeline']);
  assert.ok(!PAGES.some(p => /home/i.test(p.label)));
});

test('the current page is highlighted correctly', () => {
  assert.equal(currentPage('/', ''), 'dashboard');
  assert.equal(currentPage('/', '#dashboard'), 'dashboard');
  assert.equal(currentPage('/', '#map'), 'map');
  assert.equal(currentPage('/world3d', ''), '3d');
  assert.equal(currentPage('/timeline-page', ''), 'timeline');
});
