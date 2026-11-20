# Run Evorium on the always-on HP G4

This sets the HP G4 up as Evorium's home server. The game runs there all the time as a service. It starts
by itself after a power cut or reboot, backs the world up every night, and is shared on the internet through

This assumes the G4 runs **Ubuntu or another Linux with systemd**.

---

## 1. Make the new user account (on the G4)

Log in to the G4 with your normal admin account and open a terminal:

```bash
sudo usermod -aG sudo evorium   # lets it install the service (you can remove this afterwards)
```

Log out, then log in as **evorium**.

## 2. Install the basics (as evorium)

```bash
sudo apt update
sudo apt install -y python3 python3-venv git openssh-server
```

`openssh-server` lets you copy files to the G4 from your main PC in step 4.

## 3. Get the game

The GitHub repo is public, so no login is needed:

```bash
cd ~
git clone https://github.com/DgenKing/evorium.git
cd evorium
```

## 4. Bring your config and your world across (from your MAIN PC)

1. **Stop the game on your main PC** first (Ctrl+C in its terminal). Never run two copies of the same world.
2. Find the G4's address: on the G4, run `hostname -I`, which shows something like `<server-address>`.
3. On your **main PC**:
   ```bash
   scp ~/projects/evorium/config.py ~/projects/evorium/evorium.sqlite3 evorium@<server-address>:~/evorium/
   ```
   Use the G4's real address. A USB stick works too: copy both files into `~/evorium/` on the G4.
   ```bash
   nano ~/evorium/config.py
   ```

From now on the **G4 holds the real world.** Don't start auto mode on your main PC's old copy, or you'll
have two worlds drifting apart and paying for both.

## 5. Install it as an always-on service (on the G4)

```bash
cd ~/evorium
bash deploy/install_home_server.sh
```

**evorium** service, starts it, turns on **auto-update from GitHub** every 2 minutes, and sets up a **nightly backup** (a systemd timer) at 03:15 (keeping 14 days, in
`~/evorium/backups/`).

Check it with:
```bash
sudo systemctl status evorium
```

## 6. Share it with ngrok (on the G4)

1. Install ngrok and log in. Your authtoken is at https://dashboard.ngrok.com/get-started/your-authtoken:
   ```bash
   sudo snap install ngrok
   ngrok config add-authtoken YOUR_TOKEN
   ```
2. **Claim your free fixed address,** so the link never changes: in the ngrok dashboard go to **Domains**
   (sometimes called "Static domain"), and create your one free domain, for example
   `evorium-rob.ngrok-free.app`.
3. Add a tunnel to ngrok's config file. Run `ngrok config check` to see where the file is (usually
   `~/.config/ngrok/ngrok.yml`), open it with `nano`, and add the following under what's already there. Keep
   the `authtoken` line as it is:
   ```yaml
   tunnels:
     evorium:
       proto: http
       addr: 8000
       domain: evorium-rob.ngrok-free.app
   ```
4. Test it: `ngrok start evorium`. Open `https://evorium-rob.ngrok-free.app` on your phone (free ngrok shows
   a one-time "You are about to visit…" page; click through). Stop it with Ctrl+C.
5. **Make ngrok always-on too.** The snap version of ngrok can't install its own service (`ngrok service install`
   fails with "permission denied"), so run it as a normal systemd service instead. Use your account name and
   your domain:
   ```bash
   sudo tee /etc/systemd/system/evorium-ngrok.service >/dev/null <<'EOF'
   [Unit]
   Description=ngrok tunnel for Evorium
   After=network-online.target evorium.service
   Wants=network-online.target

   [Service]
   User=<server-user>
   ExecStart=/snap/bin/ngrok http 8000 --url=YOUR-DOMAIN.ngrok-free.dev --log=stdout
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   EOF
   sudo systemctl daemon-reload && sudo systemctl enable --now evorium-ngrok
   ```
   It now starts by itself after reboots, like the game. On the free plan, `ngrok http 8000` alone also uses
   your account's free fixed domain.

Your link is `https://evorium-rob.ngrok-free.app` (the dashboard), and the 3D world will be `/world3d` once

## 7. Keep the G4 awake

In **Settings → Power**, set "Automatic suspend" to **Off**, and "Power button" to **Power off** (not
suspend). In the BIOS (F10 at start-up on HP), set **After Power Loss** to **Power On**, so it comes back
by itself after a power cut.

---

## How updates work (GitHub → G4, automatic)

You work on your main PC and `git push`. That's all. Every 2 minutes the G4 checks GitHub's `main` branch.
When there's something new, it:
1. **backs up the world**;
2. pulls the new code, installing packages if `requirements.txt` changed;
3. **runs all the tests**;
4. **if they pass, restarts the game on the new code. If they fail, rolls back** and keeps the game running on
   the old code. A push that failed is tried only once; your next push gets a fresh try.

Everything is logged in `~/evorium/updates.log`. **Never edit code on the G4 itself.** The updater stops if it
finds local edits, so it never overwrites them. `config.py`, `evorium.sqlite3` and `backups/` never come
from GitHub; they only exist on the G4.

Codex and others: push only finished work to `main`, because it goes live within minutes.

## Everyday commands (on the G4)

| What | Command |
|---|---|
| Is it running? | `sudo systemctl status evorium` |
| Watch the live log | `sudo journalctl -u evorium -f` (Ctrl+C stops watching, not the game) |
| Restart | `sudo systemctl restart evorium`, or the **Restart server** button on the dashboard |
| See auto-updates | `tail -f ~/evorium/updates.log` |
| Check GitHub right now | `bash ~/evorium/deploy/auto_update.sh` |
| Why did an update fail? | `cat ~/evorium/last_update_tests.txt` |
| Back up now | `cd ~/evorium && .venv/bin/python deploy/backup_world.py` |
| Restore a backup | `sudo systemctl stop evorium`, copy a file from `backups/` over `evorium.sqlite3`, `sudo systemctl start evorium` |
| ngrok status | `systemctl status evorium-ngrok`, or the ngrok dashboard |

## Good to know

- **Players and friends all share one player (Rob)** until multiplayer accounts are built (EVORIUM.md §8).
  That's fine for friends, not for the public.
- **Home upload speed** limits how fast the 3D files download for each visitor. Fine for a handful of people.
- **Working on the code:** develop on your main PC and `git push` to `main`. The G4 picks it up within
  about 2 minutes by itself (see below). Use a **copy** of the world on the main PC (`EVORIUM_DB_PATH=...`) if
  you need one for testing.