# Instructions for any AI working on Evorium (Codex, Claude, others)

**`EVORIUM.md` is the only project document.** Read it first, and follow its rules in §15.

After **every** piece of work (feature, fix, setting change, investigation with a finding, plan or prompt),
before you finish, update `EVORIUM.md`:
- add a dated entry to §14 History: what changed, why, and anything learned;
- update §2 (where it stands), §3 (how it works), §5 (running it), §6 (home server), §7 (3D game), §9 (known
  issues) and §10 (next steps) wherever they're affected.

**Every new feature players would notice also gets a short entry on the website** (`website/index.html`,
section "What's new", newest first): a date, a short headline and one or two plain sentences. Also fix any website
text the feature makes out of date (e.g. the number of APCs). Keep it brief; it's a progress log, not a manual.

**Don't create other Markdown files** (no new READMEs, notes or reports). Put it in `EVORIUM.md`. The only other
`.md` files are `README.md` (a pointer), this file, `CLAUDE.md`, and `evorium/static/world3d/assets/LICENSES.md`.
If nothing in `EVORIUM.md` needs changing, say so in your final message.

Key rules (details in §15): never lose the live world (it's on the G4 server); append-only migrations; never
print or commit secrets; no dotenv; tests never call the real API or depend on the machine's own `config.py`;
no new runtime dependencies without asking; don't commit unless asked. **A push to `main` goes live on the G4
within minutes**, so only finished, tested work belongs on `main`.
