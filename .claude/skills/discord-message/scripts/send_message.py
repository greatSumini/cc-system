#!/usr/bin/env python3
"""Discord DM 전송 스크립트"""

import sys
import json
import urllib.request
import urllib.error

def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

HEADERS_BASE = {
    "User-Agent": "DiscordBot (https://github.com/greatSumini/life-os, 1.0)",
    "Content-Type": "application/json",
}

def create_dm_channel(bot_token: str, user_id: str) -> str:
    url = "https://discord.com/api/v10/users/@me/channels"
    payload = json.dumps({"recipient_id": user_id}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={**HEADERS_BASE, "Authorization": f"Bot {bot_token}"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["id"]

def send_message(bot_token: str, channel_id: str, content: str) -> dict:
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    payload = json.dumps({"content": content}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={**HEADERS_BASE, "Authorization": f"Bot {bot_token}"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: send_message.py <config_path> <message>"}))
        sys.exit(1)

    config_path = sys.argv[1]
    message = sys.argv[2]

    config = load_config(config_path)
    bot_token = config["bot_token"]
    user_id = config["user_id"]

    try:
        channel_id = create_dm_channel(bot_token, user_id)
        result = send_message(bot_token, channel_id, message)
        print(json.dumps({"success": True, "message_id": result["id"]}))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(json.dumps({"error": f"HTTP {e.code}: {body}"}))
        sys.exit(1)

if __name__ == "__main__":
    main()
