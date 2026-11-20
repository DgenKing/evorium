# Shuttle Street in a browser

Open `/world3d` or **3D** in the dashboard. The EVORIUM wordmark returns to `/`.
The Python server owns presence and conversations. This browser polls the public
`/world/scene` snapshot every 1.5 s (5 s after errors), and uses existing `/player/*`
and catch-up APIs. Movement and animation are cosmetic. The backend keeps its
single shared player: this is still an owner prototype, not multiplayer.

Desktop: WASD/arrows walk, Shift run, Space jump, drag mouse look, wheel zoom,
E talk within 2 m, N name tags, C collision wireframe, F1 debug HUD, Escape closes
chat/settings. Closing chat saves notes through `/player/end`. Only spoken text
is rendered; private rationale and NPC knowledge never appear in the player UI.

Phone: left-thumb joystick (push far to run), right drag look, two right-side
fingers pinch zoom, Jump button and contextual Talk. Landscape is suggested.
The chat panel follows `visualViewport` above the keyboard. Physical-device
usability and iOS tab memory still need owner testing.

Gear settings remember quality, names, invert look and sensitivity. Touch/narrow
screens start low; other desktops select medium/high from capabilities. Low
caps pixel ratio at 1, medium 1.5 and high 2. Sustained <28 fps steps down visual
settings at most twice. A quality selection reloads the corresponding asset set;
automatic drops adjust rendering immediately but retain already-loaded assets.
Override with `?quality=low|medium|high`.

Deterministic verification URLs: `/world3d?test=1&cam=street&quality=low`;
`cam=pub|shop|cast|player` also supported. This mode pauses local movement/polling,
fixes animation time, and exposes `__evoriumReady`, `__evoriumReport` and offline
checks. Physical movement/chat checks refuse any server without `/smoke/status`
confirming fake models. Never run automated player writes against port 8000.

Build details, licences, budgets and screenshot commands:
[`tools/web3d/README.md`](../../../tools/web3d/README.md) and `assets/LICENSES.md`.
The CC0 Standard bodies are stylized superhero stand-ins with clothing colour
masks, not bespoke portraits; low geometry and the shared lighting atlas simplify
small props. No night atlas, bloom, waving, facial animation or bespoke hair is shipped.
