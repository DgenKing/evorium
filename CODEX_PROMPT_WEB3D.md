# Evorium in the browser: Three.js 3D world (build brief for Codex)

## 0. Read this first

**Evorium** is an AI social simulation of eight characters on one terrace in Ancoats, Manchester: The Crooked
Billet pub and Patel's News. The **brain** is a Python FastAPI server in this repo
(`/home/user/projects/evorium`, running on `http://127.0.0.1:8000`). It decides where everyone is, what they
do and what they say. Read **`AGENTS.md`** and **`EVORIUM.md`** (§2, §3, §10, §12) before starting, and follow
their rules.

We tried an Unreal Engine 5 client (see `CODEX_PROMPT_UNREAL.md` and the EVORIUM.md history). It worked, but
it's too heavy to ship. **Your job is to build the same thing as a web game in Three.js**, playable in a
desktop **and a phone** browser from a link:

- **The world:** your friend's 3D Shuttle Street, with The Crooked Billet and Patel's News, inside and out.
- **The player** (Rob): a fully animated third-person character who walks, runs and jumps, with a follow
  camera. It should feel like the Unreal template's mannequin.
- **The 8 characters:** animated people who stand, walk, sit and talk where the Python server says, using the
  existing read-only endpoint `GET /world/scene` (`evorium/scene.py`).
- **Talking:** the player walks up to a character and talks to them, using the existing `/player/*`
  endpoints.

**The server is the source of truth, and the browser is only a view and controller.** That's the same
principle as the 2D map (`evorium/static/map.js`, which you should read) and the Unreal client.

### What's on this machine (verified)

| Thing | Where or status |
|---|---|
| Node.js | v24, npm 11 |
| Browsers for headless screenshots | `/usr/bin/google-chrome`, `/usr/bin/chromium-browser`, Firefox |
| Image tools | `cwebp`, Python Pillow |
| The art kit (unpacked) | `/run/media/user/Data Storage/Evorium/AncoatsKit/Ancoats_Blender_Kit/`, containing `Ancoats.blend`, `unreal/Static/*.fbx`, `unreal/Textures/*.png`, `unreal/waypoints.json`, `unreal/material_manifest.json` and `START_HERE.md` (read it). The drive is encrypted, so if the path is missing, ask the owner to unlock "Data Storage". Treat the kit as **read-only**. |
| Blender | **Not installed by default** (see §0.2) |
| Animated characters | **Downloaded by the owner** (see §0.2) |
| Evorium static files | served by FastAPI at `/static` from `evorium/static/` |
| Existing endpoints you use | `GET /world/scene`, `GET /player`, `POST /player/profile`, `POST /player/enter {place}`, `POST /player/leave`, `POST /player/say {to_agent_id, text}`, `POST /player/end`, `GET /catchup`, `POST /catchup/seen` |
| Smoke server (fake replies, database copy) | `.venv/bin/python tools/smoke_unreal.py`, on port 8011. Read it first. It may need a small change so it also serves `/world3d` (it runs the same app, so it probably already does). |

### 0.1 Rules (do not break)

- **Never touch** the live `evorium.sqlite3`, `config.py`, the `website/` folder, or the Unreal project.
  - Python changes follow EVORIUM.md §12: append-only migrations (you shouldn't need any), tests never call
    the real API, and update EVORIUM.md and README.md afterwards.
- **No build step for the game itself.** Use plain ES modules with an import map.
  - **Vendor Three.js** (pinned, current stable release; record the version) into `evorium/static/vendor/three/`,
    with only the files used: `three.module.min.js` and the needed `examples/jsm/...` addons.
  - Get it from the official `three` npm package via `npm pack three@<version>` in a scratch folder, then copy
    the files in. No CDN at runtime.
  - Include Three.js's MIT licence file.
- **Tools are allowed only in the asset pipeline**, under `tools/web3d/`: Blender scripts, Node scripts, and
  `@gltf-transform/cli` as a devDependency in `tools/web3d/package.json`. Its `node_modules/` is git-ignored.
  The game must never need them at runtime.
- **Licences:** write `evorium/static/world3d/assets/LICENSES.md` listing:
  - the art kit ("Shuttle Street / Ancoats kit, made for Evorium by the owner's friend; used with
    permission");
  - Quaternius packs (CC0);
  - Three.js (MIT).
  - Add any other asset only if it's CC0 or MIT, and record its source URL.
- **Public-player safety:** never show NPC `rationale` in the player UI. Show only what characters *say*.
- **Escape all text** put into HTML (use `textContent`, never `innerHTML` with server strings).
- **No "Home" link** in any navigation. The EVORIUM wordmark links to `/`.
- **Don't commit.** The owner commits. Git-ignore raw downloads and pipeline intermediates (§1).
- **Stop and ask** only if something is truly blocked: a missing prerequisite, a sandbox refusal, or no
  network for `npm`. Otherwise carry on through every stage, and report at the end of each one.

### 0.2 Owner prerequisites (check them first, and stop with a clear message if any is missing)

1. **Blender 4.3 or later on the PATH** (`blender --version`). The owner installs it with
   `sudo snap install blender --classic`. You need it to export the kit from `Ancoats.blend` to glTF and to
   bake lighting.
2. **Quaternius character packs (CC0)**, downloaded by the owner (free "Standard" zips) into
   `~/Downloads/evorium-characters/`:
   - **Universal Base Characters**: https://quaternius.itch.io/universal-base-characters (also
     https://quaternius.com/packs/universalbasecharacters.html);
   - **Universal Animation Library**: https://quaternius.itch.io/universal-animation-library (also
     https://quaternius.com/packs/universalanimationlibrary.html).
   - Unzip them into `tools/web3d/raw/characters/` (git-ignored). Read their licence files and confirm CC0.
     Use the **glTF** versions.
3. **The kit drive unlocked** (the path above exists).
4. **Network access for `npm`** (to get `three` and `@gltf-transform/cli`).

---

## 1. File layout

```
evorium/static/world3d/
  index.html            # the game page: canvas, overlays, import map
  css/world3d.css
  js/
    main.js             # boot, loop, quality, wiring
    quality.js          # presets + auto-detect + FPS auto-downgrade
    assets.js           # loaders (GLTFLoader + meshopt), progress, low/high sets
    world.js            # set, lights, sky, fog, day/night, door volumes, collision octree
    player.js           # third-person controller (Octree + Capsule), animation state machine
    camera.js           # follow camera with wall collision, zoom
    input.js            # keyboard/mouse + touch joystick/look/jump/talk
    npcs.js             # NPC actors, route graph, movement, bubbles, sitting, catch-up
    cast.js             # body/tint/scale per character (reads data/cast.json)
    net.js              # /world/scene polling, /player/* calls, error handling
    ui.js               # name tags, bubbles, chat panel, catch-up panel, settings, HUD
    graph.js            # pure: route graph + A* (unit-tested)
    anim.js             # pure: state selection (unit-tested)
  data/
    cast.json           # character → body, tint colours, scale, portrait
    waypoints.json      # exported from Blender (Y-up metres, three.js space)
    routes.json         # walk graph: nodes + edges (street, doors, interiors)
    clips.json          # our state names → Quaternius clip names
  assets/
    high/  shuttle_street.glb  collision.glb  characters.glb  animations.glb
    low/   (same names, smaller textures)
    LICENSES.md
evorium/static/vendor/three/      # vendored three.js (pinned) + LICENSE
tools/web3d/
  package.json                    # devDependencies: @gltf-transform/cli
  export_set.py                   # Blender: .blend → set/collision/waypoints
  bake_lighting.py                # Blender: lightmap bake (Stage 3)
  build_characters.mjs            # merge Quaternius body + needed clips, inspect bone names
  optimise.sh                     # gltf-transform → high/low sets
  README.md                       # how to rebuild every asset from scratch
  raw/                            # git-ignored downloads/intermediates
tests/world3d.test.mjs            # Node unit tests for pure modules
tests/test_world3d_route.py       # FastAPI route test
```

- **Routes:** add `GET /world3d` to `evorium/main.py`, serving `static/world3d/index.html`. Add a "3D" link
  to the dashboard header next to Map and Timeline (no Home link).
- **`.gitignore`:** add `tools/web3d/raw/` and `tools/web3d/node_modules/`.

---

## 2. Stage 1: asset pipeline (kit → web)

### 2.1 Export the set from Blender (`tools/web3d/export_set.py`)

Run it with `blender -b "<kit>/Ancoats.blend" -P tools/web3d/export_set.py -- --out tools/web3d/raw/`.

- **Open scene "01 Street"** and inspect the collections. Log them all to `raw/blend_inventory.txt`: the set
  pieces (street, pub, shop and their furnished ground floors), the mill backdrop and upper floors, the
  **collision collection** ("hidden in the viewport and excluded from renders"), and
  **`Street | Gameplay waypoints`**.
- **Export the visible set** (street, pub, shop and backdrop; **no cast**) to `raw/shuttle_street.glb`:
  - glTF binary, +Y up, modifiers applied, custom normals, materials as glTF PBR, textures embedded;
  - `export_lights=False` (we light in three.js);
  - merge static meshes by material where it lowers draw calls, but keep the **pub interior**, **shop
    interior**, **pub windows (glass)** and **shop windows (glass)** as separately named nodes, so windows can
    glow at night and interiors can be lit separately;
  - keep sign meshes intact.
- **Export the collision collection** to `raw/collision.glb` (geometry only, no materials). If the hulls are
  `UCX_*` convex pieces, export them as-is.
- **Export waypoints** to `raw/waypoints.json`:
  - each empty or marker in the waypoints collection, by name (PUB_ENTRY, PUB_HOST, PUB_BOOTH, PUB_DART,
    PUB_BAR, PUB_WINDOW, NEWS_ENTRY, NEWS_TILL, NEWS_QUEUE, NEWS_RACK, NEWS_CHILLER, NEWS_PARCELS,
    STREET_LINK, STREET_WAIT, CYCLE_RAIL);
  - **position converted to glTF/three.js space**: Blender (x, y, z) → three.js (x, z, −y), in metres;
  - facing as a yaw in radians in three.js space;
  - cross-check against `<kit>/unreal/waypoints.json` (Blender metres) and log any mismatch over 5 cm.
- **Check ground truth:** from Blender, ray-cast down from each waypoint to confirm it's over a floor, and
  ray-cast through PUB_ENTRY and NEWS_ENTRY outward to confirm the doorways are open. Write the results to the
  inventory.
- **Generate a starting `data/routes.json`:** a walk graph whose nodes are both street ends (left and right,
  off-screen), a pavement point in front of each door, each door threshold (just outside and just inside), an
  interior hub per shop, every waypoint, and Dez's "upstairs" point at the back of the pub. Edges connect
  nodes with clear straight lines. Verify every edge by ray-casting against collision in Blender at waist
  height; drop or bend any that hit, and log them.

### 2.2 Characters (`tools/web3d/build_characters.mjs`)

- **Inspect** the Universal Base Characters glTFs (the "Regular" male and female, and "Teen" if useful) and
  the Universal Animation Library glTF. Log mesh names, materials, the skeleton bone names, and **every
  animation clip name with its duration** to `raw/characters_inventory.txt`.
- **Map our states to clips** in `data/clips.json`, choosing from the inventory:
  - `idle`, `walk`, `run` (jog), `jump_start`, `jump_loop` or `fall`, `land`;
  - `sit` (sit loop on a chair), `sit_down` and `stand_up` if they exist;
  - `talk` (any talking or gesturing idle), `wave`, `turn_left` and `turn_right` if they exist.
  - If there's no jump, use the nearest airborne clip, and note it.
- **Check the rig:** the bodies and the animation library share Quaternius's universal humanoid rig. Verify the
  bone names match. If they don't, write a bone-name map and retarget with
  `SkeletonUtils.retargetClip` (three addons), in a Node or headless-browser script.
- **Output:**
  - `raw/characters.glb`: the male and female Regular bodies;
  - `raw/animations.glb`: **only the clips listed in `clips.json`**, about 10–14. Don't ship all 120.

### 2.3 Optimise (`tools/web3d/optimise.sh`, using `npx gltf-transform`)

- Steps: `dedup`, `prune`, `weld`, `resample` (animations), `meshopt` compression and `webp` textures.
- **high/**: textures up to 2048 px. **low/**: everything downscaled to 1024 px (character textures 512 px),
  with tiny props dropped if you can identify them.
- **Budgets** (print a size report and fail loudly if over):
  - **low:** under 12 MB total download, under 150k triangles in view, and comfortably under iOS Safari's tab
    memory, so aim for under 250 MB of estimated GPU memory;
  - **high:** under 30 MB, under 400k triangles.
- Copy the results into `evorium/static/world3d/assets/{high,low}/`, and `waypoints.json` and `routes.json`
  into `data/`.
- Vendor three's `meshopt_decoder.module.js` with the other addons.

**Stage 1 is done when:**
- every asset rebuilds from `tools/web3d/README.md` commands;
- the inventories are written;
- the waypoints cross-check passes;
- the size reports are under budget.

---

## 3. Stage 2: walk around Shuttle Street (desktop and phone)

### 3.1 Renderer and scene (`world.js`, `main.js`)

- `WebGLRenderer` with `antialias` on desktop high only, `outputColorSpace = SRGBColorSpace`,
  `toneMapping = ACESFilmicToneMapping` (exposure about 1.0), and shadows per quality preset.
- **Load** `shuttle_street.glb` (the low or high set, from the quality preset) with a loading screen showing
  the EVORIUM wordmark, a progress bar, and the line "The street doesn't stop when you leave."
- **Overcast Manchester daylight:**
  - a `HemisphereLight` (cool sky, warm ground);
  - one `DirectionalLight` (soft, from the south-west) that casts shadows only on medium and high, with its
    shadow camera tightly fitted around the street;
  - a gradient sky (a big inverted sphere or `scene.background` gradient);
  - light `Fog`, so the mill backdrop fades.
- **Interiors:**
  - pub: two or three warm `PointLight`s (high: up to 4, low: 1 plus emissive);
  - shop: one cool rectangular light or point light;
  - on low quality, fake the interior glow with emissive materials only.
- **Day and night:** read `daylight` from `/world/scene` (0 = night, 1 = day) and tween over 10 s:
  sun and hemisphere intensity, sky colours, fog colour, window emissive (glowing warm at night), and street
  lamp emissive.
  - When `pub_open` or `shop_open` is false, that place's interior lights go off and its door gets an
    invisible blocking box.

### 3.2 Collision (`world.js`)

- Build a three.js **`Octree`** (`examples/jsm/math/Octree.js`) from `collision.glb`. If the kit's hulls are
  missing or bad, fall back to the visible set's floors and walls, and log which.
- Add invisible walls at both street ends and behind the pavement, so the player can't leave the playable area.
- **Debug view** (key `C`): show collision as a wireframe.

### 3.3 The player (`player.js`, `camera.js`, `input.js`, `anim.js`)

The model is the three.js `games_fps` example's capsule-and-octree technique, but in third person.
- **Collider:** a `Capsule` (radius 0.35 m, height 1.75 m), with gravity, ground detection, step-up of small
  kerbs (up to 0.2 m), and sliding along walls.
- **Body:** a Quaternius Regular male body as **Rob**, with a neutral tint (cast.json `player`).
  - Speeds: walk 1.6 m/s, run 4.0 m/s, about 1 m jump.
  - Rotate the body smoothly to the movement direction, relative to the camera.
- **Animation state machine** (`anim.js` is pure and unit-tested): from speed, grounded and vertical speed, it
  picks idle, walk, run, jump_start, fall or land, with 0.2 s crossfades. `AnimationMixer` per character, one
  shared `AnimationClip` set.
- **Follow camera:**
  - behind and above the shoulder (distance 3.5 m, height 1.6 m), orbiting with the mouse or touch drag;
  - mouse wheel or pinch zooms between 1.8 and 6 m;
  - **a ray from the head to the camera position against the octree**, so the camera moves in when a wall is
    in the way. Never clip through walls, especially indoors.
- **Desktop controls:** WASD or arrows to move, Shift to run, Space to jump, mouse drag to look (pointer lock
  optional on click), E to talk, N for name tags, F1 for the debug HUD, Esc to close panels.
- **Phone controls** (`input.js`):
  - a **virtual joystick** on the left half (it appears where the thumb lands; push further to run);
  - drag on the right half to look;
  - a round **Jump** button, plus a **Talk** button that appears only when someone is in range;
  - pinch to zoom;
  - `touch-action: none` on the canvas; stop page scroll and bounce; `100dvh` layout; landscape suggested
    with a gentle hint (not forced); safe-area insets respected.

### 3.4 Quality presets (`quality.js`)

| Preset | Pixel ratio cap | Shadows | Assets | Point lights | Antialias | Post |
|---|---|---|---|---|---|---|
| low | 1.0 | off | low/ | 1 + emissive | off | none |
| medium | 1.5 | 1024, directional only | high/ | 2 | FXAA pass or off | none |
| high | 2.0 | 2048, soft | high/ | up to 4 | MSAA | subtle bloom on windows and lamps (optional) |

- **Auto-detect:** a touch device or narrow screen means low. Otherwise medium, and high if
  `renderer.capabilities.maxTextureSize >= 16384` and `devicePixelRatio <= 2`.
- **FPS watchdog:** if the average drops below 28 fps for 5 s, step down one preset, at most twice, and show a
  small toast.
- **Settings menu** (gear icon): preset, name tags, invert look, sensitivity. Remember the choice in
  `localStorage`.
- Override with the URL `?quality=low|medium|high`.

**Stage 2 is done when:** on desktop and in a phone-sized headless screenshot you can see the street, pub and
shop; the player walks in and out of both doors, can't walk through walls or off the map, jumps, and the
camera never clips through walls. Prove it with the §7 checks.

---

## 4. Stage 3: make it look good (baked lighting)

- `tools/web3d/bake_lighting.py` (Blender, Cycles):
  - give the static set a second UV map for lightmaps (Smart UV Project or Lightmap Pack, margin 0.02);
  - set up lighting that matches the three.js design (overcast sky and sun, warm pub interior lights, cool
    shop light);
  - bake **combined indirect + ambient occlusion** into lightmap textures: 2048 px for high, 1024 px for low;
  - use GPU (CUDA or OptiX on the GTX 1060) if available, otherwise CPU; samples about 128 with denoise;
  - write `raw/lightmaps/*.png` and a re-export of the set with `TEXCOORD_1`.
- **In three.js,** set `material.lightMap` and `lightMapIntensity` per material, and lower the real-time
  light intensities to match, so the scene isn't doubly lit.
  - At night, blend in a separately baked **night lightmap** (pub glow spilling onto the pavement) if time and
    size allow. Otherwise tint the day lightmap down and rely on emissive windows and point lights.
- **Fallback if baking fails or Blender is missing:** a baked **AO-only** map, or none, with the Stage 2 real-time
  lighting. Write down which you shipped.
- Re-run the budgets.

---

## 5. Stage 4: the characters come alive

### 5.1 Cast (`data/cast.json`, `cast.js`)

Use the Quaternius Regular bodies, told apart by **tint, scale and build**. The colours come from `map.js`
`SPRITES` (hair, top, trousers, skin), so the 2D map and the 3D world agree. Tint by material slot if the body
has separate skin, top, trousers and hair materials. Otherwise use vertex colours or a small `onBeforeCompile`
mask by UV region, and as a last resort a gentle whole-body multiply.

| `name` from the API | Body | Scale | Notes |
|---|---|---|---|
| Dez Whitworth | male | 1.00, slightly wider | stocky; green-grey top |
| Tommy Shaw | male | 0.96 | older; slightly stooped idle if a clip exists |
| Raj Patel | male | 0.98 | |
| Mohammed "Mo" Iqbal | male | 1.02 | |
| Simon Ferris | male | 1.01 | charcoal "suit" tint |
| Jess Hartley | female | 0.98 | |
| Chloe Barlow | female | 0.97 | |
| Brenda Ashworth | female | 0.92 | |
| player (Rob) | male | 1.00 | neutral cream top, blue trousers |

- **Name tags:** `CSS2DRenderer` labels above each head (first name; "Mo" for Mohammed). They fade beyond
  12 m and are hidden behind walls (ray test, throttled). `N` toggles them.
- **Tap or click a character** to open a small card: portrait (`portrait` from `/world/scene` if present,
  otherwise initials), first name, activity and mood. This matches the Map tab popup but with **no private
  data**.

### 5.2 Following the server (`net.js`, `npcs.js`, `graph.js`)

- **Poll** `GET /world/scene` every 1.5 s (real time), with back-off to 5 s on errors. On failure, show a calm
  banner, "Can't reach the Evorium server; retrying…", and keep the world running.
- **Each character** has a target: `place` + `waypoint` + `slot`. The world position is the waypoint position,
  plus `slot × 0.7 m` along the waypoint's right vector. Yaw is the waypoint yaw.
- **Movement:**
  - A\* on `routes.json` (`graph.js` is pure and unit-tested) from the nearest node to the target waypoint;
    walk the path at 1.4 m/s (Raj and Dez 1.5, Tommy and Brenda 1.1), snapped to the ground with a downward
    ray on the octree;
  - smooth turning;
  - NPCs don't use physics;
  - avoid overlap at the final spot with the slot offsets; while walking, a simple separation nudge (0.5 m) is
    enough.
- **Arrive:** a character who becomes `visible` spawns at the nearer street end and walks in through the right
  door.
- **Leave:** a character who becomes invisible walks out of the door to a street end, then is removed. **Dez
  going upstairs** walks to the "upstairs" node and fades out over 1 s.
- **Catch up:** if `speed > 10`, or the character is over 25 s of walking behind, teleport to the target (fade
  out, then in).
- **Arrival poses:**
  - PUB_BOOTH and PUB_WINDOW → `sit` (find the seat height from the collision or set geometry; add a per-
    waypoint seat offset in `waypoints.json` if needed);
  - PUB_HOST, PUB_BAR and NEWS_TILL → `idle` facing the customer side;
  - others → `idle`.
  - Add small idle variety: an occasional weight shift or look-around if clips exist, with random offsets so
    they're not in sync.
- **Speech:** when `line` and `line_at` change, show a speech bubble over the speaker (a `CSS2DObject`, max
  220 characters, 6 s or until the next line). Speaker and listener (`talking_to`) turn to face each other and
  play `talk`. The bubble is readable on a phone (word wrap; max width 70 vw).

**Stage 4 is done when:**
- against the smoke server, all visible characters appear at the right spots, matching the dashboard;
- setting the smoke dashboard to 60× moves them about along routes, through doors and not through walls;
- running a conversation shows bubbles;
- the headless checks in §7 assert spawned characters match `/world/scene`.

---

## 6. Stage 5: the player joins in

- **Door volumes:** `Box3` volumes just inside each door. Entering calls `POST /player/enter {"place":"pub"}`
  or `{"place":"shop"}`; leaving to the street calls `POST /player/leave`.
  - On HTTP 409 (shut), show the message and gently push the player back out.
  - Debounce, so standing in the doorway doesn't spam calls.
- **Talk:**
  - Within 2 m of a visible NPC in the same place, show "Press E to talk to Dez" (desktop) or the **Talk**
    button (phone).
  - Opening the **chat panel** (an HTML overlay) shows the conversation so far, a text box and Send. Send calls
    `POST /player/say {"to_agent_id", "text"}`, then shows `reply.text` in the panel and as a bubble.
    **Never show `reply.rationale`.**
  - The NPC stops, faces the player and plays `talk`.
  - Close calls `POST /player/end`.
  - Show the API's error text on 409 or 503 (for example "DeepSeek is paused while the service recovers").
  - While open, keys go to the panel and Esc closes it.
  - **On phones,** use `visualViewport` so the panel sits above the on-screen keyboard and the input stays
    visible.
- **Profile:** if `GET /player` has no name, ask once in a small name box, which calls `POST /player/profile`.
- **Catch-up:** after loading, call `GET /catchup`. If it has items, show a "While you were away" panel
  (paragraph plus bullets, using `textContent`). Dismiss calls `POST /catchup/seen`.
- **Debug HUD** (F1): sim time and speed, last poll, preset, fps, `renderer.info` (draw calls, triangles,
  textures, geometries), the player's position and place, and who is where.

---

## 7. Verification (do this at every stage; it's how you "see")

1. **Unit tests** (`node tests/world3d.test.mjs`, no packages): A\* paths on a small graph and on the real
   `routes.json` (every waypoint reachable from both street ends); anim state selection; quality auto-detect
   from fake capabilities; slot offset maths; cast lookup.
2. **Python test:** `GET /world3d` returns the page; the static assets exist; the `/world/scene` tests still
   pass. The whole suite stays green (`python -m pytest -q`).
3. **A test mode in the page:** `?test=1&cam=street|pub|shop|cast|player&quality=low|high`. It places the camera
   deterministically, freezes time and random seeds, loads everything, then sets `window.__evoriumReady = true`
   and writes a JSON summary to `window.__evoriumReport` (loaded assets, draw calls, triangles, characters
   spawned and where, collision ok, errors).
4. **Headless screenshots** (`tools/web3d/screenshots.mjs`), using Chrome directly through the DevTools
   Protocol (Node's built-in WebSocket and `child_process`; no Playwright install):
   - launch `google-chrome --headless=new --use-angle=swiftshader --enable-unsafe-swiftshader
     --remote-debugging-port=9333`;
   - open each test URL at **1280×720** and **390×844** (phone, mobile user agent, touch emulation);
   - wait for `__evoriumReady`, then capture PNGs to `tools/web3d/raw/screens/` and the report JSON;
   - **fail the run** if the report has errors, characters are missing, or an image is mostly a single colour
     (blank canvas).
   - Look at your own screenshots, and describe in your stage report what each shows and anything wrong
     (floating feet, black textures, wrong facing, a camera inside a wall).
5. **Movement test** (in the test mode): script the player from the street to PUB_BAR and back out, and to
   NEWS_TILL. Assert it arrives within 2 m, never ends up inside collision, and the door enter and leave calls
   happen.
6. **Against the smoke server:** start `tools/smoke_unreal.py` (port 8011), open
   `http://127.0.0.1:8011/world3d?test=1&cam=pub`, and assert the spawned characters match its `/world/scene`.
   Then speed it to 60× and confirm positions update.

---

## 8. Finish

- `tools/web3d/README.md`: prerequisites, how to rebuild every asset, budgets, and how to run the checks.
- `evorium/static/world3d/README.md`: controls (desktop and phone), quality settings, test URLs and known gaps.
- **EVORIUM.md** (per AGENTS.md):
  - a dated §5 entry (what was built, decisions, budgets measured, what you couldn't verify);
  - update §2 (3D web client exists), §3 (how the 3D client works, the endpoints used) and §10 (web 3D, the
    Quaternius cast, kit pipeline);
  - add to §6 any known gaps;
  - in §7, replace the Unreal step with this web client's next steps.
- **README.md:** `/world3d`, how to open it on a phone on the same Wi-Fi, which means starting uvicorn with
  and how to rebuild assets.
- **Final message:** files created or changed; each stage's "done when" result with the numbers (download
  sizes, triangles, draw calls, fps in headless if measurable); what each screenshot showed; anything
  unfinished or simplified. Don't commit.

## 9. If you get stuck

- **Blender export problems:** export the three FBX set pieces from `<kit>/unreal/Static/` through Blender
  (import FBX, export glTF) instead of the .blend scene, and use `<kit>/unreal/waypoints.json` converted
  (x, z, −y) for waypoints.
- **Character rig mismatch:** ship one body with its own bundled clips first (if the base characters include
  any), and record the retargeting as a gap.
- **No usable jump clip:** a short procedural hop (vertical motion only), with the run or idle clip playing.
- **Headless WebGL fails:** try `--use-gl=angle --use-angle=swiftshader`, then `--use-gl=egl`. If every option
  fails, keep the unit, movement and report tests, and tell the owner the screenshots need a real browser.
- **Over budget on low:** drop the backdrop mill detail, use 512 px textures on distant meshes, merge more
  materials, and remove interior props that aren't seen from the main spots.
