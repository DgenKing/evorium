# Evorium in 3D: Unreal Engine 5 third-person client (build brief for Codex)

## 0. Read this first

**Evorium** is an AI social simulation of eight characters on one terrace in Ancoats, Manchester: The Crooked
Billet pub and Patel's News. The **brain** already exists. It's a Python FastAPI server at
`/home/user/projects/evorium` that runs on `http://127.0.0.1:8000`, and it decides where everyone is, what they
do and what they say. Read `/home/user/projects/evorium/EVORIUM.md` (especially §2, §3 and §10) and
`/home/user/projects/evorium/AGENTS.md` before starting.

**Your job:** build the **body**, an Unreal Engine 5 **third-person game** where:
- the player walks around the 3D street, pub and shop;
- the 8 characters stand, walk and talk where the Python server says they are;
- the player can walk up to a character and talk to them, using the existing player endpoints.

Unreal is a **viewer and controller only**. It never decides anything about the simulation: all state comes
from the Python API, the same way the existing 2D map (`evorium/static/map.js`) works. Read `map.js` to see the
rules for spots, doors, bubbles and catching up at high speed; the 3D version should behave the same way.

### What's on this machine (all verified)

| Thing | Where |
|---|---|
| Unreal Engine 5.8.4 (Linux, precompiled) | `/run/media/user/Data Storage/Evorium/UnrealEngine-5.8.4` |
| Editor and command-line editor | `Engine/Binaries/Linux/UnrealEditor`, `Engine/Binaries/Linux/UnrealEditor-Cmd` |
| C++ build script and bundled clang | `Engine/Build/BatchFiles/Linux/Build.sh`, `Engine/Extras/ThirdPartyNotUE/SDKs/HostLinux/Linux_x64/v26_clang-20.1.8-rockylinux8` |
| Python editor scripting | `Engine/Plugins/Experimental/PythonScriptPlugin` |
| HTTP for Blueprints (optional) | `Engine/Plugins/Web/HttpBlueprint` |
| Third Person C++ template | `Templates/TP_ThirdPerson` (Games category) |
| Mannequin and animations | `Templates/TemplateResources/High/Characters/Content/Mannequins` |
| The friend's art kit | `/home/user/projects/evorium/Ancoats_Blender_Unreal_Kit.zip` (148 MB, 102 files) |
| Evorium server | `/home/user/projects/evorium`, running on port 8000 |
| GPU | **NVIDIA GTX 1060 6 GB**, old for UE5 (see §2) |

**Note the space in "Data Storage".** Quote every path. If Unreal Build Tool or any script fails because of the
space, create a symlink without one (for example `ln -s "/run/media/user/Data Storage/Evorium" ~/EvoriumDrive`)
and use that path. Never move or rename the engine.

### Rules

- **Never touch the live Evorium database** (`/home/user/projects/evorium/evorium.sqlite3`) or `config.py`.
  - For Python work, follow `AGENTS.md` and EVORIUM.md §12: append-only migrations, tests never call the real
    API, no new Python dependencies, and update EVORIUM.md and README.md afterwards.
  - For smoke tests, run a **second** Evorium server on a **copy** of the database (`EVORIUM_DB_PATH=<copy>`,
    `EVORIUM_LOG_FILE=`) on another port, e.g. 8011, with auto mode off. Point Unreal at it with a setting
    (§3.1).
- **Don't commit.** The owner commits. The Unreal project gets its own `.gitignore` (§1), but don't run
  `git init` there unless asked.
- **No marketplace or paid plugins, and no downloads.** Use only what ships with the engine, the template and
  the kit.
- **Don't run anything inside the kit except `Import_Ancoats.py`,** and read that script before running it.
- **Prefer C++ and Python scripts over hand-built Blueprints.** You can't click in the editor. Anything that has
  to be a Blueprint asset, create it from a Python editor script or as a thin Blueprint subclass of a C++
  class, so it can be rebuilt by script.
- **Headless first:** use `UnrealEditor-Cmd ... -run=pythonscript -script=...` (or `-ExecutePythonScript=`) with
  `-unattended -nullrhi -nosplash -nopause` for imports and level building. Only the owner opens the full
  editor to look.
- **You can't see the screen.** For anything visual (facing, scale, feet on the floor, lighting), write an
  automated check where possible (bounds, line traces, nav paths), and list what the owner must eyeball in
  `OWNER_CHECKLIST.md`.
- After each stage, write down what was done and what is left in the project's `README.md`, and add a short
  dated entry to Evorium's EVORIUM.md §5 and §10.

---

## 1. Stage 1: project and kit import

1. **Unpack the kit** into its own new folder: `/run/media/user/Data Storage/Evorium/AncoatsKit/`. Don't
   unpack into the project or the engine.
2. **Create the project** `EvoriumUnreal` at `/run/media/user/Data Storage/Evorium/EvoriumUnreal/` from
   `Templates/TP_ThirdPerson` (the **Games → Third Person**, **C++** template).
   - Copy the template, then rename `TP_ThirdPerson` to `EvoriumUnreal` everywhere it matters: the
     `.uproject`, the `Source/` module and target names, the `Config/DefaultEngine.ini` redirects, and the class
     names. Use `ActiveClassRedirects`/`ActiveGameNameRedirects` where needed.
   - Keep the template's mannequin content and Input (Enhanced Input) assets.
   - Enable the **PythonScriptPlugin** and **EditorScriptingUtilities** plugins (and `HttpBlueprint` only if
     you use it). The C++ `HTTP` and `Json` modules are enough for runtime.
3. **Build the editor target:**
   `Build.sh EvoriumUnrealEditor Linux Development -Project=".../EvoriumUnreal.uproject" -WaitMutex`.
   It must compile cleanly.
4. **Low-spec settings,** in `Config/DefaultEngine.ini` (the GTX 1060 6 GB can't run UE5 defaults smoothly):
   - Global illumination: **None** instead of Lumen (`r.DynamicGlobalIlluminationMethod=0`). Reflections:
     **Screen Space** (`r.ReflectionMethod=2`).
   - Nanite off for imported meshes. Virtual shadow maps off (`r.Shadow.Virtual.Enable=0`); use regular
     shadow maps.
   - Default scalability **Medium**. Anti-aliasing TSR at a lower screen percentage, or FXAA, so it runs at
     30+ fps.
   - Add a console variable or setting so the owner can raise quality later.
5. **Import the kit** by running `AncoatsKit/Ancoats_Blender_Kit/unreal/Import_Ancoats.py` headless. Read it
   first.
   - It expects the **legacy FBX importer**. If 5.8 uses Interchange for FBX, switch with
     `Interchange.FeatureFlags.Import.FBX false`, as the kit's `START_HERE.md` says, or adapt the script's
     options to Interchange. Make the script runnable from the command line, since `Path(__file__)` must
     resolve to the kit's `unreal` folder.
   - Import settings from `START_HERE.md`:
     - The three set pieces (`SM_ShuttleStreet`, `SM_CrookedBillet`, `SM_PatelsNews`) get Convert Scene and
       Convert Scene Unit, scale 1.0, custom normals kept, no auto collision, and One Convex Hull per UCX.
     - The props get simple collision.
     - Characters import as skeletal meshes with animations, one skeleton each.
     - BaseColor maps are sRGB; Roughness and Normal maps are not sRGB, Normal maps use Normalmap compression
       and the green channel is flipped; `M_ClearGlass` is translucent.
   - Everything lands under `/Game/Ancoats/...`. Log every asset created and every warning to
     `Saved/Logs/ancoats_import.txt`.
6. **Build the level** `/Game/Evorium/Maps/ShuttleStreet` from a Python script (`Scripts/build_level.py`). It
   must be **re-runnable**, rebuilding the level from scratch each time.
   - **Set pieces:** place the three at the **same origin** with the same rotation. Don't place the separate
     prop FBXs, which duplicate props already in the sets.
   - **Lighting:** a directional light (sun), sky light, sky atmosphere, exponential height fog and a post
     process volume, at an overcast Manchester daylight look. Warm point lights inside the pub and cool ones
     in the shop (no Lumen, so interiors need their own lights).
   - **Player start** on the pavement outside the pub door, facing the shops.
   - **Navigation:** a NavMeshBoundsVolume covering the street, pub and shop floors, then build navigation.
     Verify with the navigation system that a path exists between: street → pub door → PUB_BAR, street → shop
     door → NEWS_TILL, and pub → shop. If the doors are blocked by collision, report which hull blocks it and
     fix only by adjusting collision in Unreal, not the meshes.
   - **Set the level** as the game default and editor startup map, and the game mode to the project's C++
     game mode.
7. **Waypoints:** convert `AncoatsKit/.../unreal/waypoints.json` (15 spots, positions in **metres in Blender
   axes**: +X along the shops to the right, +Y into the shops, +Z up, facing in degrees from −Y) into Unreal
   space.
   - Expect metres × 100, with **Y flipped** (Blender is right-handed, Unreal left-handed). **Prove the
     conversion:** check that PUB_ENTRY and NEWS_ENTRY land in the door openings of the imported meshes
     (bounds and line traces), that inside spots are over the floor (trace down hits the floor within 5 cm),
     and that facing points the way the activity describes (PUB_HOST faces the customer side of the bar).
   - Save the result as `Content/Evorium/Data/Waypoints.json` (key, location cm, yaw), plus a
     `DT_Waypoints` data table if convenient.
   - Place an `AEvoriumWaypoint` marker actor (C++, editor-only arrow and label) at each spot, in the level.
8. **Project `.gitignore`:** `Binaries/`, `Intermediate/`, `Saved/`, `DerivedDataCache/`, `.vscode/`, `*.sln`
   and the kit folder.

**Stage 1 is done when:**
- the editor target compiles;
- the import log has no errors;
- the level builds from script;
- nav paths exist to the bar, the till and between the shops;
- the waypoints pass their checks;
- `OWNER_CHECKLIST.md` says how to open the project and press Play to walk around the street in third
  person.

---

## 2. Stage 2: the cast

### Body mapping (decided by the owner)

The kit's faces are baked into each body texture, so Evorium's 2D portraits don't go on the 3D faces. Use this
mapping. Put it in `Content/Evorium/Data/Cast.json`, so it can change without code.

| Evorium character (API `name`) | Kit skeletal mesh | Clothing tint |
|---|---|---|
| Raj Patel | `SK_Sanjay_Patel` | none (original) |
| Tommy Shaw | `SK_Frank_Doyle` | none (original) |
| Jess Hartley | `SK_Amina_Okafor` | none |
| Mohammed "Mo" Iqbal | `SK_Imran_Malik` | none |
| Chloe Barlow | `SK_Ewa_Kowalska` | none |
| Brenda Ashworth | `SK_Val_Mercer` | none |
| Dez Whitworth | `SK_Frank_Doyle` | dark green-grey work shirt look (clearly different from Tommy) |
| Simon Ferris | `SK_Frank_Doyle` | charcoal suit look (clearly different again) |

Not used yet: `SK_Janine_Ward`, `SK_Rory_Campbell`.

- **Tints:** each character gets a **material instance** of a master material with a `TintColour` parameter and
  a `TintStrength` parameter. Apply the tint to clothing only if you can isolate it (for example by a mask
  derived from the atlas); otherwise use a subtle whole-body multiply that leaves faces readable. Dez, Tommy
  and Simon must be told apart at a glance from 5 m.
- **Name tags:** a small world-space name tag above each head (first name only; "Mo" for Mohammed), visible
  within about 8 m. It can be switched off with a key (`N`).

### Animation

- The kit characters share a **20-bone FK skeleton** with only an idle clip. The template's Manny has full
  locomotion.
- Using the **IK Rig and IK Retargeter Python APIs**, create one IK rig for the kit skeleton, one for Manny,
  and a retargeter. Retarget at least: idle, walk, run, and a sit or lean if one exists. Retarget onto one kit
  skeleton (the hierarchy is shared), and use it for all 8 via a common skeleton or compatible skeletons.
  Report honestly if auto-mapping needs manual chain fixes.
- Make one Animation Blueprint per skeleton, or a shared one, created by script where possible. Give it a speed
  to blend idle/walk/run.
- **Fallback if retargeting fails:** use the template **Manny** mesh for NPCs, tinted per character, with the
  name tags, and record the kit-body work as unfinished. The game must still be playable.

### The NPC class

`AEvoriumNPC`: a C++ `ACharacter` with:
- the skeletal mesh and tint from `Cast.json`;
- the AI controller `AEvoriumNPCController`, using `MoveToLocation` on the navmesh;
- a speech-bubble widget component, a name tag, and an "is talking" state.

**Stage 2 is done when:** a test map or level script spawns all 8 at their waypoints in idle, with tints and
name tags, and each can be sent to another waypoint by a console command (`Evorium.MoveTo Dez PUB_BAR`).

---

## 3. Stage 3: connect to Evorium

### 3.1 Python side: one new read-only endpoint, `GET /world/scene`

Add it to `evorium/main.py`, with its logic in a new `evorium/scene.py`. It's **read-only**: no writes and no
model calls. Unreal polls it every 1–2 s (real time).

**Response:**

```json
{
  "sim_at": "2026-11-19 20:44", "sim_time": "Thursday 19 November, 20:44", "speed": 1,
  "daylight": 0.0,
  "pub_open": true, "shop_open": false,
  "notices": [{"place": "pub", "text": "Quiz night returns Thursday 8pm"}],
  "characters": [
    {"id": 1, "name": "Dez Whitworth", "first": "Dez", "kind": "npc",
     "visible": true, "place": "pub", "waypoint": "PUB_HOST", "slot": 0,
     "activity": "behind the bar", "mood": "worried",
     "talking_to": 4, "conversation_id": 61, "line": "No miracle, love — just quiet.", "line_at": "…",
     "portrait": "/static/portraits/dez.png"}
  ],
  "player": {"id": 9, "name": "Rob", "place": "pub", "talking_to": null}
}
```

- **`daylight`** runs from 0 (night) to 1 (day), from the sim clock, using the same sunrise and sunset logic as
  `map.js` night tint.
- **`place`** is `pub`, `shop`, `street` or `away`. A character who is `away` (home, work elsewhere, on the
  phone) is `visible: false`.
- **Waypoints** are assigned **in Python**, deterministically, by the same rules as `map.js` `targetFor`:
  - staff behind the bar → `PUB_HOST` (Dez) and `PUB_BAR` (Jess);
  - Tommy's usual table → `PUB_WINDOW`;
  - darts → `PUB_DART`;
  - other pub customers → `PUB_BOOTH`, then `PUB_BAR`, then `PUB_WINDOW`;
  - Raj behind the counter → `NEWS_TILL`; shop customers → `NEWS_QUEUE`, `NEWS_RACK`, `NEWS_CHILLER`;
  - street → `STREET_WAIT` or `STREET_LINK`.
- **`slot`** is 0, 1, 2… when several people share a waypoint. Unreal offsets each slot about 70 cm along the
  waypoint's right vector.
- **`line`** is the latest message in a conversation that is running or ended in the last 2 real minutes. Never
  include rationales or private knowledge.
- **`portrait`** is a URL only if the file exists (5 do today: dez, jess, tommy, raj, chloe).
- **Tests** (fake data, temp database): spot assignment, slots, away/visible, no private fields (rationale,
  facts, stats) in the response, and it works with zero conversations.
- Update README.md (routes) and EVORIUM.md (§3, §5, §10) as `AGENTS.md` requires.

### 3.2 Unreal side

- **Settings:** `UEvoriumSettings` (Project Settings → Evorium, saved in `Config/DefaultGame.ini`) holds:
  - `ServerUrl` (default `http://127.0.0.1:8000`);
  - `PollSeconds` (1.5);
  - `SlotSpacingCm` (70);
  - `ShowNameTags`.
  - A command-line override `-EvoriumServer=http://127.0.0.1:8011` for smoke tests.
- **`UEvoriumWorldSubsystem`** (a C++ world subsystem) uses the `HTTP` and `Json` modules to:
  - poll `/world/scene`, parse it, and spawn or update one `AEvoriumNPC` per character;
  - **arrive:** a newly visible character spawns at the nearest street edge (left or right end of the street,
    off-camera) and walks in through the right door;
  - **leave:** a character who becomes invisible walks out of the door to the nearest street edge, then is
    hidden. Dez is the exception: going upstairs, he walks to the pub's back area and fades out;
  - **move:** a waypoint change makes the character walk to the new spot (door routing comes free from the
    navmesh). On arrival they turn to the waypoint yaw;
  - **catch up at speed:** if speed is above 10×, or a character is more than about 30 s of walking behind,
    teleport them to the target instead (as `map.js` catches up);
  - **talk:** show `line` in a speech bubble over the speaker for about 6 s or until the next line, and turn
    the two speakers to face each other;
  - **day and night:** set the sun angle, intensity and pub/shop light intensity from `daylight`. When a place
    is closed, its interior lights go off and its door gets a blocking volume;
  - **notices:** show a small notice decal or plane on the pub or shop front when `notices` has one;
  - **errors:** if the server is unreachable, show "Evorium server not reachable at …" on screen and keep
    retrying every 5 s. Never crash.
- **Debug HUD** (toggle `F1`): sim time, speed, server URL, last poll time, and who is where.

**Stage 3 is done when:**
- with the smoke server (on a database copy, port 8011) and `-EvoriumServer=http://127.0.0.1:8011`, the
  characters appear where the dashboard says they are;
- changing the smoke server's speed to 60× makes them move about;
- running a conversation on the smoke server shows the lines in bubbles;
- add an automated check that runs the game headless for 30 s against the smoke server and asserts the actors
  spawned match `/world/scene`.

---

## 4. Stage 4: the player (third person, talking)

- **The player is Rob** (the API's player). Use the template's third-person character and camera. The body is
  the template Manny with a neutral tint, unless the owner later chooses `SK_Rory_Campbell` (make it a setting
  in `Cast.json`).
- **Entering and leaving:** trigger volumes just inside each door.
  - Walking in calls `POST /player/enter {"place":"pub"}` or `{"place":"shop"}`.
  - Walking out to the street calls `POST /player/leave`.
  - If the place is shut (the API answers 409), show the message and push the player back out of the door
    gently.
- **Talking:**
  - Within 2 m of a visible character who is in the same place, a prompt shows "Press E to talk to Dez".
  - **E** opens a chat panel (C++ `UUserWidget` built in code: message history, a text box, Send, Close). Send
    calls `POST /player/say {"to_agent_id": id, "text": "…"}` and shows the `reply.text` in the panel and as
    a bubble over the character.
  - **Close** calls `POST /player/end`.
  - Show the API's error text on 409/503 (for example "DeepSeek is paused while the service recovers").
  - While the panel is open, mouse and keyboard go to the panel; Esc closes it.
  - The NPC stops and faces the player while talking.
- **Player profile:** the first time, if the API's player name is empty, show a small name box that calls
  `POST /player/profile`.
- **Catch-up:** on start, call `GET /catchup`. If it has items, show "While you were away" as a dismissable
  panel (Dismiss calls `POST /catchup/seen`).

**Stage 4 is done when:**
- against the smoke server, a scripted test (an automation test or Python PIE script) walks the player into
  the pub, checks `/player` shows `place=pub`, sends one line to a present NPC using a **fake reply** (the
  smoke server must not call DeepSeek; use a test hook or a stub client on the Python side for this test
  only), and walks out;
- the owner checklist explains how to try it for real against port 8000.

---

## 5. Stage 5: polish and handover

- **Packaging (optional, if it builds):** a Linux Development build into
  `/run/media/user/Data Storage/Evorium/EvoriumUnreal_Build/`, with a `run.sh` that passes
  `-EvoriumServer=http://127.0.0.1:8000`.
- **Performance:** measure frame time in the street and inside the pub headless with `stat unit` where possible.
  Note what the owner should see on the GTX 1060 and which settings to lower if it's under 30 fps.
- **`OWNER_CHECKLIST.md`**, in plain words, covering:
  - how to open the project;
  - how to start the Evorium server first;
  - controls: WASD, mouse, E to talk, N name tags, F1 debug, Esc;
  - what to eyeball: characters facing the right way, feet on the floor, tints telling Dez, Tommy and Simon
    apart, door sizes, interior lighting;
  - how to rebuild the level (`Scripts/build_level.py`);
  - known gaps.
- **Final message:** list every file created or changed (Unreal project and Evorium repo), every stage's
  "done when" result, what you couldn't verify without seeing the screen, and anything unfinished. Don't
  commit.

---

## 6. How the owner starts you (for reference)

Start Codex from the Evorium folder on the data drive, with the Python repo and Unreal's settings folders
writable and localhost networking allowed:

```bash
cd "/run/media/user/Data Storage/Evorium"
codex -C "/run/media/user/Data Storage/Evorium" \
  --add-dir /home/user/projects/evorium \
  --add-dir /home/user/.config/Epic --add-dir /home/user/UnrealEngine \
  -s workspace-write -c 'sandbox_workspace_write.network_access=true'
```

If Unreal won't start inside the sandbox (GPU, shared memory or the Zen/trace servers), stop and tell the owner
exactly what failed. They may restart you with `-s danger-full-access`. Don't ask for that unless the sandbox is
the proven cause.
