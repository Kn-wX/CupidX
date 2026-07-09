import os
import re
import base64
import requests
from colorama import Fore, Style

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fetch_emoji_image(emoji_id, animated):
    ext = 'gif' if animated else 'webp'
    url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}"
    try:
        r = requests.get(url)
        if r.status_code == 200:
            return r.content
        elif r.status_code in (301, 302):
            location = r.headers.get('Location')
            if location:
                r2 = requests.get(location)
                if r2.status_code == 200:
                    return r2.content
    except Exception:
        pass
    return None


def run_sync(token):
    """Syncs all custom emojis referenced in utils/emoji.py to the bot's
    Application Emojis (Discord Developer Portal), then rewrites detectfile.py
    so any ID that changed (or got newly uploaded) stays in sync.
    Safe to run on every startup — skips anything already matching."""
    if not token:
        print(f"{Fore.YELLOW}✖ Skipping EmojiSync:{Style.RESET_ALL} No token found.")
        return

    emoji_py_path = os.path.join(BASE_DIR, "utils", "detectfile.py")
    try:
        with open(emoji_py_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as err:
        print(f"{Fore.RED}✖ EmojiSync Failed:{Style.RESET_ALL} Could not read emoji.py ({err})")
        return

    matches = set(re.findall(r"<(a?):(\w+):(\d+)>", content))

    if not matches:
        print(f"{Fore.CYAN}◈ EmojiSync:{Style.RESET_ALL} No custom emojis found in detectfile.py to sync.")
        return

    print(f"{Fore.MAGENTA}★ Starting Application Emoji Sync...{Style.RESET_ALL}")

    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json"
    }

    r = requests.get("https://discord.com/api/v10/users/@me", headers=headers)
    if r.status_code != 200:
        print(f"{Fore.RED}✖ EmojiSync API Error:{Style.RESET_ALL} Failed to fetch bot info [HTTP {r.status_code}]")
        return
    app_id = r.json().get("id")

    r = requests.get(f"https://discord.com/api/v10/applications/{app_id}/emojis", headers=headers)
    if r.status_code != 200:
        print(f"{Fore.RED}✖ EmojiSync API Error:{Style.RESET_ALL} Failed to fetch application emojis [HTTP {r.status_code}]")
        return

    data = r.json()
    app_emojis = data.get("items", []) if isinstance(data, dict) else data

    print(f"{Fore.CYAN}◈ EmojiSync:{Style.RESET_ALL} Found {Fore.YELLOW}{len(matches)}{Style.RESET_ALL} unique emojis in emoji.py | Application has {Fore.GREEN}{len(app_emojis)}{Style.RESET_ALL} app emojis")

    updated = False
    skipped = 0
    uploaded = 0
    fixed = 0
    failed = 0

    for animated_str, name, old_id in matches:
        animated = (animated_str == 'a')

        existing = next((e for e in app_emojis if e['id'] == old_id), None) or next((e for e in app_emojis if e['name'] == name), None)

        if existing:
            new_id = existing['id']
            if old_id != new_id:
                old_str = f"<{animated_str}:{name}:{old_id}>"
                new_str = f"<{animated_str}:{existing['name']}:{new_id}>"
                content = content.replace(old_str, new_str)
                updated = True
                fixed += 1
                print(f"{Fore.YELLOW}↻ Fixing ID:{Style.RESET_ALL} {name} -> {new_id}")
            else:
                skipped += 1
            continue

        image_data = fetch_emoji_image(old_id, animated)
        if not image_data:
            print(f"{Fore.RED}✖ Could not fetch image:{Style.RESET_ALL} {name} [ID: {old_id}]")
            failed += 1
            continue

        mime_type = "image/gif" if animated else "image/webp"
        base64_data = base64.b64encode(image_data).decode('utf-8')
        image_uri = f"data:{mime_type};base64,{base64_data}"

        post_data = {"name": name, "image": image_uri}
        r2 = requests.post(f"https://discord.com/api/v10/applications/{app_id}/emojis", headers=headers, json=post_data)

        if r2.status_code in (200, 201):
            new_emoji = r2.json()
            new_id = new_emoji['id']

            old_str = f"<{animated_str}:{name}:{old_id}>"
            new_str = f"<{animated_str}:{new_emoji['name']}:{new_id}>"
            content = content.replace(old_str, new_str)

            app_emojis.append(new_emoji)
            updated = True
            uploaded += 1
            print(f"{Fore.GREEN}✔ Uploaded:{Style.RESET_ALL} {name} [Saved as ID: {new_id}]")
        else:
            print(f"{Fore.RED}✖ Discord Rejected:{Style.RESET_ALL} {name} -> {r2.text}")
            failed += 1

    if updated:
        try:
            with open(emoji_py_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"{Fore.MAGENTA}★ EmojiSync:{Style.RESET_ALL} emoji.py updated to reflect current app emoji IDs.")
        except Exception as err:
            print(f"{Fore.RED}✖ Sync Write Blocked:{Style.RESET_ALL} Could not update emoji.py ({err})")

    summary_parts = []
    if skipped: summary_parts.append(f"{skipped} already synced")
    if fixed: summary_parts.append(f"{fixed} IDs fixed")
    if uploaded: summary_parts.append(f"{uploaded} newly uploaded")
    if failed: summary_parts.append(f"{failed} failed")

    if summary_parts:
        print(f"{Fore.MAGENTA}★ EmojiSync Completed:{Style.RESET_ALL} " + " | ".join(summary_parts))
