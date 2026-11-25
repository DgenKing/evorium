import * as THREE from 'three';
/* Night on the street: stars, the moon (real phase), street-lamp glow and light pools.
   Everything fades in as daylight falls; clouds, rain, snow and fog hide the sky. */

const SYNODIC_DAYS = 29.530588853, NEW_MOON = Date.UTC(2000, 0, 6, 18, 14);

// 0 = new moon, 0.5 = full, then waning back towards 1.
export function moonPhase(date = new Date()) {
 const days = (date.getTime() - NEW_MOON) / 86400000;
 return ((days / SYNODIC_DAYS) % 1 + 1) % 1;
}

// How much sky shows through for the current weather: [stars, moon].
export function skyClarity(style) {
 if (!style || style.fog || style.wet || style.snow || style.dark) return [0, 0];
 if (style.condition === 'clear') return [1, 1];
 if (style.condition === 'cloudy') return [.35, .75];
 return [.6, .85];   // weather unknown: a fair night
}

function moonTexture(phase) {
 const size = 128, r = 30, c = size / 2, canvas = document.createElement('canvas');
 canvas.width = canvas.height = size;
 const g = canvas.getContext('2d');
 const halo = g.createRadialGradient(c, c, r * .8, c, c, c);
 halo.addColorStop(0, 'rgba(200,214,240,.28)'); halo.addColorStop(1, 'rgba(200,214,240,0)');
 g.fillStyle = halo; g.fillRect(0, 0, size, size);
 g.fillStyle = 'rgba(150,165,190,.18)';   // the dark side, faintly
 g.beginPath(); g.arc(c, c, r, 0, Math.PI * 2); g.fill();
 const waxing = phase < .5, angle = phase * Math.PI * 2;
 // A clipped disc makes both full moon and thin crescents reliable on Canvas.
 g.save(); g.beginPath(); g.arc(c, c, r, 0, Math.PI * 2); g.clip();
 g.fillStyle = '#f3efe0';
 if (waxing) { const edge = c + Math.cos(angle) * r; g.fillRect(edge, 0, size - edge, size); }
 else { const edge = c - Math.cos(angle) * r; g.fillRect(0, 0, edge, size); }
 g.restore();
 const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace;
 return texture;
}

function poolTexture() {
 const size = 64, canvas = document.createElement('canvas'); canvas.width = canvas.height = size;
 const g = canvas.getContext('2d'), gradient = g.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
 gradient.addColorStop(0, 'rgba(255,255,255,1)'); gradient.addColorStop(.45, 'rgba(255,255,255,.45)'); gradient.addColorStop(1, 'rgba(255,255,255,0)');
 g.fillStyle = gradient; g.fillRect(0, 0, size, size);
 return new THREE.CanvasTexture(canvas);
}

export class Night {
 constructor(scene) {
  this.scene = scene; this.sky = new THREE.Group(); this.sky.renderOrder = -1; scene.add(this.sky);
  const count = 900, positions = new Float32Array(count * 3), colors = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {   // fixed pseudo-random stars over the upper sky
   const u = ((i * 0.6180339887) % 1), v = ((i * 0.7548776662) % 1), theta = u * Math.PI * 2, y = .08 + .92 * Math.sqrt(v), ring = Math.sqrt(1 - y * y);
   positions.set([Math.cos(theta) * ring, y, Math.sin(theta) * ring], i * 3);
   const b = .55 + .45 * ((i * 0.381966) % 1); colors.set([b, b, b * (1.02 + .06 * ((i * .13) % 1))], i * 3);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3)); geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  this.stars = new THREE.Points(geometry, new THREE.PointsMaterial({size: 1.7, sizeAttenuation: false, vertexColors: true, transparent: true, opacity: 0, depthWrite: false, fog: false}));
  this.stars.frustumCulled = false; this.sky.add(this.stars);
  this.phase = moonPhase();
  this.moon = new THREE.Sprite(new THREE.SpriteMaterial({map: moonTexture(this.phase), transparent: true, opacity: 0, depthWrite: false, fog: false}));
  this.moon.position.set(.12, .42, -.9).normalize(); this.moon.scale.setScalar(.16); this.sky.add(this.moon);
  this.lampLights = []; this.lampTimer = 0; this.lamps = [];
  this.shuttleHeads = []; this.shuttleLights = [];
 }

 // The kit street has two fixed lamp posts in its exported street mesh.
 addShuttleLamps(group, lightCount) {
  const fixtures = [[-9, 6.45, .22], [6.68, 5.85, .25]], poolGeometry = new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2);
  this.shuttlePools = new THREE.InstancedMesh(poolGeometry,
   new THREE.MeshBasicMaterial({map: poolTexture(), color: 0xffc27a, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -4}), fixtures.length);
  const transform = new THREE.Object3D();
  fixtures.forEach(([x, y, z], i) => {
   const head = new THREE.Mesh(new THREE.SphereGeometry(.14, 8, 6), new THREE.MeshBasicMaterial({color: 0xffd49a, transparent: true, opacity: 0, depthWrite: false}));
   head.position.set(x, y, z); group.add(head); this.shuttleHeads.push(head);
   transform.position.set(x, .06, z); transform.scale.set(6.5, 1, 6.5); transform.updateMatrix(); this.shuttlePools.setMatrixAt(i, transform.matrix);
   if (i < lightCount) { const light = new THREE.PointLight(0xffc98a, 0, 13, 2); light.position.set(x, y - .15, z); group.add(light); this.shuttleLights.push(light); }
  });
  this.shuttlePools.frustumCulled = false; group.add(this.shuttlePools);
 }

 // Street lamps from the city manifest (positions in the city's own space, metres).
 addLamps(lamps, materials) {
  this.lamps = (lamps || []).map(p => new THREE.Vector3(...p));
  this.heads = materials;
  if (!this.lamps.length) return;
  const pools = new THREE.InstancedMesh(new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2),
   new THREE.MeshBasicMaterial({map: poolTexture(), color: 0xffc27a, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -4}), this.lamps.length);
  const t = new THREE.Object3D();
  this.lamps.forEach((p, i) => { t.position.set(p.x, p.y - 4.18 + .06, p.z); t.scale.setScalar(9); t.updateMatrix(); pools.setMatrixAt(i, t.matrix); });
  pools.frustumCulled = false; this.pools = pools; this.scene.add(pools);
  for (let i = 0; i < 4; i++) { const light = new THREE.PointLight(0xffc98a, 0, 14, 2); light.visible = false; this.scene.add(light); this.lampLights.push(light); }
 }

 update(dt, daylight, style, camera, lightCount) {
  const night = THREE.MathUtils.clamp((.45 - daylight) / .3, 0, 1), [starSky, moonSky] = skyClarity(style);
  if (camera) {
   this.sky.position.copy(camera.position); this.sky.scale.setScalar(camera.far * .9);
   // Keep the moon in the upper sky while the player turns through narrow streets.
   this.moon.position.set(.12, .42, -.9).normalize().applyQuaternion(camera.quaternion);
  }
  this.stars.material.opacity = night * starSky; this.stars.visible = this.stars.material.opacity > .01;
  const newMoon = Math.min(this.phase, 1 - this.phase) < .03;
  this.moon.material.opacity = newMoon ? 0 : night * moonSky; this.moon.visible = this.moon.material.opacity > .01;
  for (const material of this.heads || []) { material.emissive?.setHex(0xffd49a); material.emissiveIntensity = night * 2.2; }
  if (this.pools) this.pools.material.opacity = night * .5;
  for (const head of this.shuttleHeads) { head.material.opacity = night; head.visible = night > .01; }
  if (this.shuttlePools) { this.shuttlePools.material.opacity = night * .5; this.shuttlePools.visible = night > .01; }
  for (const light of this.shuttleLights) { light.intensity = night * 13; light.visible = night > .01; }
  // Real light only from the few lamps nearest the camera; the rest glow and pool.
  this.lampTimer -= dt;
  if (camera && this.lamps.length && this.lampTimer <= 0) {
   this.lampTimer = .4;
   const nearest = this.lamps.map(p => [p.distanceToSquared(camera.position), p]).sort((a, b) => a[0] - b[0]);
   this.lampLights.forEach((light, i) => { light.visible = i < lightCount && night > 0; if (light.visible) light.position.copy(nearest[i][1]).add(new THREE.Vector3(0, -.15, 0)); });
  }
  for (const light of this.lampLights) light.intensity = night * 16;
 }
}
