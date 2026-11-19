# Instructions for any AI working on Evorium (Codex, Claude, others)

Read `EVORIUM.md` first. It's the one working document for the whole project: the idea, current state, how it
works, history, known issues, next steps and the rules in §12. `README.md` covers how to run it.

## Always keep the docs up to date

After **every** piece of work (feature, fix, setting change, investigation with a finding, plan or prompt
written), before you finish:

1. **EVORIUM.md:**
   - add what was done to §5 History, under a dated session heading (create one for today if needed): what
     changed, why, and anything learned;
   - update §2 "Where it stands today" if the game now behaves differently;
   - update §3 "How it works" if the mechanics changed;
   - update §6 "Known issues": add new problems, remove fixed ones;
   - update §7 "Next steps": tick off what's done, add what's now next.
2. **README.md:** update anything a person running the game needs: commands, settings, routes, files, limits,
   costs.
3. If neither file needs a change, say so in your final message.

The aim is that anyone can open EVORIUM.md and know exactly where the project is.

Follow the rules in EVORIUM.md §12 (never lose the live database, append-only migrations, no secrets, no new
dependencies, tests never hit the real API, don't commit unless asked).
