#!/usr/bin/env bash
# Install Evorium as an always-on service on a home Linux machine (e.g. the HP G4).
# Run it as the account that will own the game, from inside the cloned project folder:
#     cd ~/evorium && bash deploy/install_home_server.sh
# It asks for your password once (sudo) to install the system service.
# Safe to run again after `git pull`.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ME="$(id -un)"
cd "$DIR"

say() { printf '\n\033[1;33m==> %s\033[0m\n' "$*"; }

if [ "$ME" = "root" ]; then
  echo "Run this as the Evorium account, not as root."; exit 1
fi

say "Checking Python"
if ! command -v python3 >/dev/null; then
  echo "Python 3 is missing. Run: sudo apt install -y python3 python3-venv git"; exit 1
fi
python3 - <<'PY' || { echo "Python 3.11 or newer is needed."; exit 1; }
import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)
PY
python3 -c "import venv" 2>/dev/null || { echo "Run: sudo apt install -y python3-venv"; exit 1; }

say "Creating the Python environment and installing packages"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

say "Checking config.py"
if [ ! -f config.py ]; then
  cp config.example.py config.py
  chmod 600 config.py
  echo "Created config.py from the example. Open it, put in your DeepSeek key and a DASHBOARD_PASSWORD,"
  echo "or copy your existing config.py over it, then run this script again."
  exit 1
fi
chmod 600 config.py
if grep -q 'DEEPSEEK_API_KEY = "sk-\.\.\."' config.py; then
  echo "config.py still has the placeholder key. Put your real DeepSeek key in it, then run this again."; exit 1
fi
if grep -qE '^DASHBOARD_PASSWORD *= *""' config.py || ! grep -q '^DASHBOARD_PASSWORD' config.py; then
  echo "Set DASHBOARD_PASSWORD in config.py first: this server will be reachable from the internet."; exit 1
fi

say "Checking the world file"
if [ -f evorium.sqlite3 ]; then
  echo "Found evorium.sqlite3 ($(du -h evorium.sqlite3 | cut -f1)). It will be used as the world."
else
  echo "No evorium.sqlite3 yet: a fresh world will be created on first start."
  echo "(To move your existing world, stop the server on the main PC and copy its evorium.sqlite3 here first.)"
fi

say "Installing the system service (asks for your password)"
UNIT=/etc/systemd/system/evorium.service
sudo tee "$UNIT" >/dev/null <<EOF
[Unit]
Description=Evorium neighbourhood simulation
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$ME
Group=$(id -gn)
WorkingDirectory=$DIR
ExecStart=$DIR/.venv/bin/python -m uvicorn evorium.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5
TimeoutStopSec=120
UMask=0077
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now evorium
sleep 3
if systemctl is-active --quiet evorium; then
  echo "Evorium is running on http://127.0.0.1:8000 (this machine only; ngrok shares it, see HOME_SERVER.md)."
else
  echo "The service didn't start. Last log lines:"; sudo journalctl -u evorium -n 30 --no-pager; exit 1
fi

say "Auto-update from GitHub every 2 minutes (tests must pass, otherwise it rolls back)"
# The updater runs as this account; it may restart the game service and nothing else.
echo "$ME ALL=(root) NOPASSWD: /usr/bin/systemctl restart evorium" | sudo tee /etc/sudoers.d/evorium-restart >/dev/null
sudo chmod 440 /etc/sudoers.d/evorium-restart
sudo visudo -cf /etc/sudoers.d/evorium-restart >/dev/null || { sudo rm -f /etc/sudoers.d/evorium-restart; echo "sudoers rule invalid; removed it."; exit 1; }
sudo tee /etc/systemd/system/evorium-update.service >/dev/null <<EOF
[Unit]
Description=Update Evorium from GitHub (tests must pass)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$ME
Group=$(id -gn)
WorkingDirectory=$DIR
ExecStart=/usr/bin/bash $DIR/deploy/auto_update.sh
StandardOutput=append:$DIR/updates.log
StandardError=append:$DIR/updates.log
EOF
sudo tee /etc/systemd/system/evorium-update.timer >/dev/null <<EOF
[Unit]
Description=Check GitHub for Evorium updates every 2 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=2min
Persistent=true

[Install]
WantedBy=timers.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now evorium-update.timer
echo "Auto-update is on. Watch it with: tail -f $DIR/updates.log"

say "Nightly backup at 03:15 (keeps 14)"
LINE="15 3 * * * cd $DIR && .venv/bin/python deploy/backup_world.py >> $DIR/backups.log 2>&1"
( crontab -l 2>/dev/null | grep -v 'deploy/backup_world.py' ; echo "$LINE" ) | crontab -
.venv/bin/python deploy/backup_world.py || true

say "Done"
cat <<EOF
Useful commands:
  sudo systemctl status evorium          # is it running?
  sudo journalctl -u evorium -f          # live log (Ctrl+C to stop watching)
  sudo systemctl restart evorium         # restart by hand
  tail -f $DIR/updates.log               # see auto-updates from GitHub as they happen
  bash $DIR/deploy/auto_update.sh        # check GitHub for updates right now
Next: set up ngrok so others can reach it (deploy/HOME_SERVER.md, step 6).
EOF
