# Web3D verification — 20 November 2026

Verified using fake models, a read-only backup of the live save, localhost:8011 and Chrome SwiftShader. No live player writes or model calls. All stages have working implementations; the polish and real-device gaps below remain.

| Stage | Result |
|---|---|
| 0.2 | Blender 5.3.0, both CC0 Standard archives, unlocked kit and official npm registry pass outside sandbox. |
| 1 | Reproducible export, character inventory/rig check, 15 exact waypoints, 44 hulls, 746 route nodes / 4,697 verified edges; all markers reachable from either end. |
| 2 | Physical capsule walk through pub and shop and back; jump/landing, wall, closed-door and camera collision pass. Desktop and phone layout captured. |
| 3 | Cycles CPU indirect bake, 128 samples, secondary UVs, 2048 high / 1024 low; runtime night dimming. |
| 4 | Four visible smoke NPCs match snapshot IDs and waypoint positions; public cards, poses and speech captured; 60× clock crosses 19:00 and routines refresh. |
| 5 | pub/leave/shop/leave calls and fake dialogue pass; reply text appears in panel, with no rationale rendered. |

Python: **226 passed**. Map: **7 passed**. Web3D Node assertions pass. Twenty PNGs pass the blank-image and character-presence checks. No browser report errors. Avatar/capsule positions match in every capture.

## Measured assets

| Preset | Downloaded assets | Geometry (one male/female) | Estimated textures incl. mipmaps/atlas |
|---|---:|---:|---:|
| low | 3.40 MB | 124,232 | 45.44 MB |
| high | 5.15 MB | 173,338 | 271.93 MB |

Vendor modules add about 2.4 MB uncompressed; data JSON adds a small transfer. Texture estimates exclude renderer buffers, JavaScript, geometry and collision/octree memory.

## Browser measurements

Total calls/triangles include shadow passes; the visible count excludes them. SwiftShader uses CPU software rendering and does not measure physical phone/GTX 1060 performance.

| Device / preset | Total draw calls | Visible triangles | FPS |
|---|---:|---:|---:|
| desktop / low | 76–90 | 126,627–139,238 | 4.0–4.9 |
| desktop / high | 167–181 | 199,154–216,268 | 1.8–2.0 |
| phone / low | 43–80 | 76,750–136,465 | 6.3–10.6 |
| phone / high | 134–171 | 145,715–211,504 | 2.1–2.4 |

## Screenshot review

All five cameras were inspected at 1280×720 and 390×844, in low and high (20 captures). Contact sheet: `raw/screens/contact-sheet.png`; individual images and JSON reports are in the same ignored folder.

- Street: brick terrace, both named frontages, open doors and pavement; phone portrait narrows the view.
- Pub: bar/pumps, booth and stools, animated Dez/Jess and public speech bubbles. Tightened low simplification restores thin furniture supports. Bubbles near the viewport edge can still crop.
- Shop: Raj at the till, stock aisles, chillers and signs. Corrected the test camera after its first placement was blocked by the open doorway.
- Cast: alternate pub framing shows body scales, tints and gestures. These are bald Superhero stand-ins with simple clothing masks.
- Player: Rob stands outside the pub. Fixed test-mode actor/capsule synchronization; the report now asserts exact alignment. Touch controls and portrait hint fit the narrow viewport.

Physics: jump **1.03 m**, masonry stop **x −8.60 m**, camera wall clearance distance **0.77 m**, closed-door stop **z 0.60 m**. Four walking destinations finish within **0.13 m**, with **zero final collision penetration**.

## Remaining gaps

- Real iOS memory, keyboard and touch feel, and hardware FPS require physical-device checks.
- NPC catch-up uses snaps; departure fades, separation and seated-pose/hair polish remain.
- Automatic quality drops adjust rendering but retain loaded assets; manual preset selection reloads the correct set.
- A shared indirect atlas gives small props limited texel density; no separately baked AO/night atlas or bloom.
- NPC speech bubbles near viewport edges may crop.
- The server retains its shared single player; this is an owner prototype.

Rebuild and check commands are in `README.md`. No commits, live server restarts, source-kit writes, configuration changes, website changes or Unreal-project changes were made.
