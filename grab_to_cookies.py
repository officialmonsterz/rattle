#!/usr/bin/env python3
"""
grab_to_cookies.py

Turns the zip produced by browser_grab.py into cookies.json,
ready to be used with gmail_message_reader.py.

Run on Windows, under the SAME Windows user account whose browser
data was grabbed (Windows protects the cookie encryption key per
user, per machine).

Requirements:
    pip install cryptography

Usage:
    python grab_to_cookies.py rattle_grab_20240312_143005.zip
    python grab_to_cookies.py rattle_grab_20240312_143005.zip --domain google.com --out cookies.json
"""

import argparse
import base64
import ctypes
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from ctypes import wintypes
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Seconds between the Windows calendar start (year 1601) and 1970.
CHROMIUM_EPOCH_DIFF = 11644473600

SAME_SITE_CHROMIUM = {
    "no_restriction": "None",
    "lax": "Lax",
    "strict": "Strict",
}

SAME_SITE_FIREFOX = {
    0: "None",
    1: "Lax",
    2: "Strict",
}


# ============================================
# Windows DPAPI - the key that unlocks the safe
# ============================================

class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def dpapi_decrypt(data):
    """Ask Windows to unlock a blob protected with the current user's key."""
    if os.name != "nt":
        raise OSError("DPAPI decryption only works on Windows")

    buffer = ctypes.create_string_buffer(data, len(data))
    blob_in = DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()

    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    )
    if not ok:
        raise OSError("CryptUnprotectData failed")

    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def load_chromium_key(local_state_path):
    """Read the browser's master cookie key out of 'Local State'."""
    with open(local_state_path, "r", encoding="utf-8") as fh:
        state = json.load(fh)
    encoded = state.get("os_crypt", {}).get("encrypted_key")
    if not encoded:
        return None
    blob = base64.b64decode(encoded)
    if not blob.startswith(b"DPAPI"):
        return None
    return dpapi_decrypt(blob[5:])


def decrypt_chromium_value(encrypted_value, key):
    """Unlock a single cookie value. Returns the text, or None on failure."""
    if not encrypted_value:
        return ""
    prefix = encrypted_value[:3]
    if prefix in (b"v10", b"v11", b"v15", b"v20"):
        if key is None:
            return None
        try:
            payload = encrypted_value[3:]
            if prefix == b"v20":
                payload = payload[32:]  # v20 carries the site name hash first
            nonce = payload[:12]
            ciphertext = payload[12:]
            plain = AESGCM(key).decrypt(nonce, ciphertext, None)
            return plain.decode("utf-8", "replace")
        except Exception:
            return None
    # Very old cookies were protected directly by Windows.
    try:
        return dpapi_decrypt(encrypted_value).decode("utf-8", "replace")
    except OSError:
        return None


# ============================================
# Converters
# ============================================

def convert_chromium_db(db_path, local_state_path, domain_filter, counters):
    """Read one Chromium Cookies.sqlite copy into Playwright cookie dicts."""
    cookies = []
    key = load_chromium_key(local_state_path)

    con = sqlite3.connect(str(db_path))
    try:
        rows = con.execute(
            "SELECT host_key, name, value, encrypted_value, path, "
            "expires_utc, is_secure, is_httponly FROM cookies"
        ).fetchall()
    finally:
        con.close()

    for host, name, value, enc_value, path, expires_utc, is_secure, is_httponly in rows:
        counters["found"] += 1
        if domain_filter and domain_filter not in host:
            continue
        counters["matching"] += 1

        final_value = value if value else decrypt_chromium_value(enc_value, key)
        if final_value is None:
            counters["failed"] += 1
            continue
        if final_value == "":
            continue  # empty placeholder values are useless

        try:
            expires = int(expires_utc) / 1000000 - CHROMIUM_EPOCH_DIFF
        except (TypeError, ValueError):
            expires = -1

        cookies.append({
            "name": name,
            "value": final_value,
            "domain": host,
            "path": path or "/",
            "expires": expires,
            "httpOnly": bool(is_httponly),
            "secure": bool(is_secure),
            "sameSite": "Lax",
        })
    return cookies


def convert_firefox_db(db_path, domain_filter, counters):
    """Read one Firefox cookies.sqlite copy into Playwright cookie dicts.
    Firefox cookie values are stored in plain text, so no unlocking needed."""
    cookies = []

    con = sqlite3.connect(str(db_path))
    try:
        rows = con.execute(
            "SELECT host, name, value, path, expiry, isSecure, isHttpOnly, sameSite "
            "FROM moz_cookies"
        ).fetchall()
    finally:
        con.close()

    for host, name, value, path, expiry, is_secure, is_httponly, samesite in rows:
        counters["found"] += 1
        if domain_filter and domain_filter not in host:
            continue
        counters["matching"] += 1
        if not value:
            continue

        cookies.append({
            "name": name,
            "value": value,
            "domain": host,
            "path": path or "/",
            "expires": int(expiry) if expiry else -1,
            "httpOnly": bool(is_httponly),
            "secure": bool(is_secure),
            "sameSite": SAME_SITE_FIREFOX.get(samesite, "None"),
        })
    return cookies


def find_local_state(cookie_db):
    """Walk upward from a Cookies.sqlite copy to find its 'Local State'."""
    for parent in cookie_db.parents:
        candidate = parent / "Local State"
        if candidate.is_file():
            return candidate
    return None


# ============================================
# Main
# ============================================

def main():
    parser = argparse.ArgumentParser(
        description="Turn a rattle_grab zip into cookies.json for the Gmail reader."
    )
    parser.add_argument("zip_path", help="the rattle_grab_*.zip produced by browser_grab.py")
    parser.add_argument("--out", default="cookies.json", help="output file (default: cookies.json)")
    parser.add_argument(
        "--domain",
        default="google.com",
        help="only keep cookies whose site contains this text (default: google.com); "
        "use --domain all to keep every cookie",
    )
    args = parser.parse_args()

    if os.name != "nt":
        print("WARNING: Chromium cookie values can only be unlocked on Windows.")
        print("Firefox cookies will still convert on any system.\n")

    zip_path = Path(args.zip_path)
    if not zip_path.is_file():
        print("Could not find the zip:", zip_path)
        sys.exit(1)

    domain_filter = None if args.domain.lower() == "all" else args.domain

    temp_dir = Path(tempfile.mkdtemp(prefix="rattle_convert_"))
    all_cookies = []
    counters = {"found": 0, "matching": 0, "failed": 0}
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(temp_dir)

        for db in sorted(temp_dir.rglob("*")):
            if not db.is_file():
                continue

            if db.name == "cookies.sqlite" and "firefox" in str(db).lower():
                print(f"[*] converting Firefox cookies: {db.relative_to(temp_dir)}")
                all_cookies += convert_firefox_db(db, domain_filter, counters)
                continue

            if db.name == "Cookies.sqlite":
                print(f"[*] converting Chromium cookies: {db.relative_to(temp_dir)}")
                local_state = find_local_state(db)
                if local_state is None:
                    print("    no matching 'Local State' found - values stay locked")
                    continue
                all_cookies += convert_chromium_db(db, local_state, domain_filter, counters)

        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(all_cookies, fh, indent=2)

        print()
        print("cookies seen in databases :", counters["found"])
        print("cookies kept (site filter):", counters["matching"])
        print("cookies saved to", args.out, ":", len(all_cookies))
        if counters["failed"]:
            print("cookies that failed to unlock:", counters["failed"])
            print(
                "HINT: if MANY cookies fail to unlock, this Chrome profile uses the "
                "newer 'app-bound' encryption. Try Edge, Brave, an older Chrome "
                "profile, Firefox cookies, or the Rattle remote-browser flow instead."
            )
        if not all_cookies:
            print("No cookies were saved. Check that the zip really contains browser data.")
            sys.exit(2)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
