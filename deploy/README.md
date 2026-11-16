# Run Evorium on a Linux home-network machine

These instructions assume a Linux machine with systemd, Python 3.11+ and a
reserved LAN address. Nothing here installs the service automatically.

1. Create a dedicated non-admin account and copy the project:

   ```bash
   sudo useradd --system --home-dir /opt/evorium --shell /usr/sbin/nologin evorium
   sudo mkdir -p /opt/evorium
   sudo cp -a /path/to/evorium/. /opt/evorium/
   sudo chown -R evorium:evorium /opt/evorium
   sudo -u evorium python3 -m venv /opt/evorium/.venv
   sudo -u evorium /opt/evorium/.venv/bin/pip install -r /opt/evorium/requirements.txt
   ```

   If moving the existing world, stop its original server first and copy the
   SQLite database with its journal/WAL files together, or use SQLite's backup
   API. Keep a separate backup. Do not run two servers against the same file.

2. Create `/opt/evorium/config.py` by hand from `config.example.py`. Enter your
   username in the browser's sign-in dialog can be anything. Keep this file
   local and readable only by the service account:

   ```bash
   sudo chown evorium:evorium /opt/evorium/config.py
   sudo chmod 600 /opt/evorium/config.py
   ```

3. Edit `deploy/evorium.service`: replace `192.168.1.50` with this machine's
   reserved LAN address. The service binds only to that address, port 8000.
   The database defaults to `/opt/evorium/evorium.sqlite3`; optionally set
   `Environment=EVORIUM_DB_PATH=/opt/evorium/your-world.sqlite3` in the unit.

4. Allow port 8000 only from your actual local subnet. For example, on a
   machine already using UFW, with LAN subnet `192.168.1.0/24`:

   ```bash
   sudo ufw allow from 192.168.1.0/24 to 192.168.1.50 port 8000 proto tcp
   sudo ufw status
   ```

   Remove any existing broader rule for port 8000. Preserve your existing SSH
   access rules before enabling a firewall. **Never forward port 8000 on the
   router.** HTTP Basic does not encrypt traffic: use only your trusted LAN;
   this service file does not provide public internet hosting or TLS.

5. Install and enable the unit:

   ```bash
   sudo cp /opt/evorium/deploy/evorium.service /etc/systemd/system/evorium.service
   sudo systemctl daemon-reload
   sudo systemctl enable --now evorium
   sudo systemctl status evorium
   sudo journalctl -u evorium -n 50
   ```

Open `http://192.168.1.50:8000` from the LAN. The saved auto-mode setting resumes
after a restart; your player chat is closed with notes. To apply code or config
changes, run `sudo systemctl restart evorium`. Back up the SQLite file regularly.
