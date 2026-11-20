#!/usr/bin/env bash
# Pull new code from GitHub and restart Evorium, but only if the tests pass.
# Run every 2 minutes by the evorium-update.timer (installed by install_home_server.sh).
# Run by hand any time:  bash deploy/auto_update.sh
#
# Never touches config.py, evorium.sqlite3 or backups/ (they're git-ignored and stay on this machine).
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BRANCH="${EVORIUM_BRANCH:-main}"
cd "$DIR" || exit 1
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*"; }

git fetch --quiet origin "$BRANCH" || { log "Can't reach GitHub; will try again next time."; exit 0; }
OLD="$(git rev-parse HEAD)"
NEW="$(git rev-parse "origin/$BRANCH")"
[ "$OLD" = "$NEW" ] && exit 0   # nothing new
FAILED_MARK="$DIR/.update_failed"
# A commit that already failed is tried once only; the next push gets a fresh attempt.
[ -f "$FAILED_MARK" ] && [ "$(cat "$FAILED_MARK")" = "$NEW" ] && exit 0
fail() { echo "$NEW" > "$FAILED_MARK"; exit 1; }

log "New code on GitHub: ${OLD:0:7} -> ${NEW:0:7}"

# Local edits on the server would block the update; they shouldn't exist, so refuse loudly rather than lose them.
if ! git diff --quiet || ! git diff --cached --quiet; then
  log "Code files were edited on this server; not updating. See: git status"; fail
fi

.venv/bin/python deploy/backup_world.py --keep 30 || log "Backup failed (carrying on; the nightly backup still runs)."

if ! git merge --ff-only --quiet "origin/$BRANCH"; then
  log "GitHub history doesn't follow on from this server's copy; not updating. Fix by hand: git status"; fail
fi

if ! git diff --quiet "$OLD" "$NEW" -- requirements.txt; then
  log "requirements.txt changed; installing packages."
  .venv/bin/pip install --quiet -r requirements.txt || { log "pip failed; rolling back."; git reset --hard --quiet "$OLD"; fail; }
fi

log "Running tests."
if ! EVORIUM_LOG_FILE= .venv/bin/python -m pytest -q -x >"$DIR/last_update_tests.txt" 2>&1; then
  log "Tests FAILED; rolling back to ${OLD:0:7}. The game keeps running the old code. Details: last_update_tests.txt"
  git reset --hard --quiet "$OLD"
  fail
fi

sudo -n /usr/bin/systemctl restart evorium || { log "Couldn't restart the service (sudo rule missing? re-run install_home_server.sh)."; fail; }
sleep 5
if systemctl is-active --quiet evorium; then
  log "Updated and restarted on ${NEW:0:7}: $(git log -1 --format=%s)"
  rm -f "$FAILED_MARK"
else
  log "New code didn't start; rolling back to ${OLD:0:7}."
  git reset --hard --quiet "$OLD"
  sudo -n /usr/bin/systemctl restart evorium
  fail
fi
