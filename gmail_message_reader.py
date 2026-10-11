"""
gmail_message_reader.py (v2)

Opens the victim's Gmail using session cookies (cookies.json),
asks you for a message ID, and shows that message straight from the inbox.

Requirements:
    pip install playwright
    python -m playwright install chromium

Place cookies.json (the exported Google session cookies) in the same folder.
"""

import json
import asyncio
from playwright.async_api import async_playwright

COOKIES_FILE = "cookies.json"

# Where the message ID comes from: the number after '#inbox/' in Gmail's address bar.


def load_cookies(path):
    """Read cookies.json and hand it back in the exact shape Playwright wants."""
    with open(path, "r", encoding="utf-8") as f:
        raw_cookies = json.load(f)

    cleaned = []
    for c in raw_cookies:
        cookie = {
            "name": c["name"],
            "value": c["value"],
            "domain": c["domain"],
            "path": c.get("path", "/"),
        }
        # Only add the optional fields if they exist, and only if valid.
        if "expires" in c:
            cookie["expires"] = c["expires"]
        if "httpOnly" in c:
            cookie["httpOnly"] = c["httpOnly"]
        if "secure" in c:
            cookie["secure"] = c["secure"]
        if "sameSite" in c and c["sameSite"] in ("Strict", "Lax", "None"):
            cookie["sameSite"] = c["sameSite"]
        cleaned.append(cookie)
    return cleaned


async def read_message(page):
    """Pull the sender, subject, date, and body straight off the rendered page."""
    return await page.evaluate(
        """() => {
            const result = { subject: "", from: "", date: "", body: "" };

            // Gmail has used these class names on its subject, sender, date,
            // and message body for many years. The right-most message in a
            // thread is the one that is expanded, which is the one you want.
            const subject = document.querySelector("h2.hP");
            if (subject) result.subject = subject.textContent.trim();

            const from = document.querySelector("span.gD");
            if (from) result.from = from.getAttribute("email") || from.textContent.trim();

            const date = document.querySelector("span.g3");
            if (date) result.date = date.textContent.trim();

            const body = document.querySelector("div.a3s");
            if (body) result.body = body.innerText.trim();

            // Safety net: if Gmail renamed its classes, grab everything
            // visible in the reading pane instead of giving up.
            if (!result.subject && !result.body) {
                const main = document.querySelector('div[role="main"]');
                if (main) result.body = main.innerText.trim();
            }
            return result;
        }"""
    )


async def main():
    user_input = input(
        "Paste the Gmail message ID (the number after '#inbox/' in the address "
        "bar), or the whole Gmail URL, then press Enter: "
    ).strip()

    if not user_input:
        print("Nothing was entered. Exiting.")
        return

    if user_input.lower().startswith("http"):
        # A whole URL was pasted - use it exactly as given.
        target_url = user_input
    else:
        # Trim accidental junk someone might paste around the ID.
        msg_id = user_input.rstrip("/").split("/")[-1].strip()
        if not msg_id:
            print("No message ID was found in what you pasted. Exiting.")
            return
        target_url = "https://mail.google.com/mail/u/0/#inbox/" + msg_id

    print("\n[1/4] Loading cookies from", COOKIES_FILE, "...")
    try:
        cookies = load_cookies(COOKIES_FILE)
    except FileNotFoundError:
        print("Could not find", COOKIES_FILE, "in this folder. Exiting.")
        return
    except (KeyError, json.JSONDecodeError) as e:
        print("cookies.json is not in the expected format:", e)
        return

    print("[2/4] Opening Chrome with the victim's session...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        try:
            await context.add_cookies(cookies)
        except Exception as e:
            print("The cookies could not be loaded into the browser:", e)
            await browser.close()
            return

        page = await context.new_page()

        try:
            # One single jump straight to the message: Gmail routes to it
            # as part of its own startup, which removes the race condition
            # the two-step version had.
            await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print("Could not reach Gmail:", e)
            await browser.close()
            return

        print("[3/4] Opening the message (Gmail gets up to 20 seconds to draw it)...")

        # Give Gmail repeated chances to draw the message on screen.
        info = {"subject": "", "from": "", "date": "", "body": ""}
        for attempt in range(10):
            await page.wait_for_timeout(2000)
            info = await read_message(page)
            if info["subject"] or info["body"]:
                break

        print("\n[4/4] Message contents:")
        print("-" * 60)
        print("From:   ", info["from"] or "(not found)")
        print("Date:   ", info["date"] or "(not found)")
        print("Subject:", info["subject"] or "(not found)")
        print("-" * 60)
        print(info["body"] or "(body could not be read automatically)")
        print("-" * 60)

        # Keep the window open so you can also read the inbox manually,
        # or copy the IDs of other emails straight from the address bar.
        input("\nGmail is still open. Browse it if you like, then press Enter here to close it. ")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
