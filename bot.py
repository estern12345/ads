# filename: main.py

import os
import json
import asyncio
import random
import time
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.tl.functions.messages import GetHistoryRequest
from aiohttp import web
from colorama import Fore, init

init(autoreset=True)

# Configuration
CREDENTIALS_FOLDER = "sessions"
DATA_FILE = "data.json"
ADMIN_IDS = [6249999953]  # Add more admin IDs if needed
BACKUP_INTERVAL = 86400  # 24 hours
start_time = time.time()

# Ensure session folder exists
os.makedirs(CREDENTIALS_FOLDER, exist_ok=True)

# Load or initialize bot data
def load_data():
    if not os.path.exists(DATA_FILE):
        data = {
            "groups": [],
            "frequencies": {},
            "mode": "random",
            "last_sent_ad_index": 0,
            "admins": ADMIN_IDS,
            "logs": [],
            "last_sent": {},
            "daily_count": {},
        }
        save_data(data)
        return data
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except:
        print(Fore.RED + "⚠️ Corrupted data.json — resetting.")
        os.remove(DATA_FILE)
        return load_data()

def save_data(data):
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(Fore.RED + f"[Save Error]: {e}")

# Web server for Render
async def start_web_server():
    async def handle(request):
        return web.Response(text="✅ Telegram Bot is running.")
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000)))
    await site.start()

# Forward ads to groups
async def ad_sender(client):
    while True:
        try:
            data = load_data()
            now = datetime.now()
            today_str = now.strftime('%Y-%m-%d')

            # Reset daily counters at midnight
            for gid in list(data.get("daily_count", {})):
                if data["daily_count"][gid].get("date") != today_str:
                    data["daily_count"][gid] = {"date": today_str, "count": 0}
            save_data(data)

            # Fetch saved messages
            ads = await client(GetHistoryRequest(peer="me", limit=20, offset_id=0,
                                                 offset_date=None, max_id=0, min_id=0,
                                                 add_offset=0, hash=0))
            saved_messages = [m for m in ads.messages if m.message or m.media]
            if not saved_messages:
                await asyncio.sleep(60)
                continue

            for gid in data["groups"]:
                str_gid = str(gid)
                freq = data["frequencies"].get(str_gid, data.get("frequency", 45))
                last_sent = data["last_sent"].get(str_gid, 0)
                count_info = data["daily_count"].get(str_gid, {"date": today_str, "count": 0})

                if time.time() - last_sent < freq * 60 or count_info["count"] >= 75:
                    continue

                msg = random.choice(saved_messages) if data["mode"] == "random" else saved_messages[data["last_sent_ad_index"] % len(saved_messages)]
                if data["mode"] == "order":
                    data["last_sent_ad_index"] += 1

                await client.forward_messages(gid, msg.id, "me")
                data["last_sent"][str_gid] = time.time()
                data["daily_count"][str_gid] = {
                    "date": today_str,
                    "count": count_info["count"] + 1
                }
                data.setdefault("logs", []).append({
                    "group": gid,
                    "timestamp": now.isoformat()
                })
                save_data(data)
                await asyncio.sleep(random.uniform(10, 20))
        except Exception as e:
            print(Fore.RED + f"[Sender Error]: {e}")
            await asyncio.sleep(30)
        await asyncio.sleep(60)

# Auto-backup every 24h
async def backup_data(client):
    while True:
        await asyncio.sleep(BACKUP_INTERVAL)
        try:
            await client.send_file(ADMIN_IDS[0], DATA_FILE, caption="🗄 Auto-backup of data.json")
        except Exception as e:
            print(Fore.RED + f"[Backup Error]: {e}")

# Handle commands and reply logs
async def command_handler(client):
    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        sender = await event.get_sender()
        sender_id = sender.id
        data = load_data()
        cmd = event.raw_text.strip()
        is_admin = sender_id in data["admins"]
        is_pm = event.is_private

        if not is_admin and is_pm:
            await client.send_message(
                ADMIN_IDS[0],
                f"📩 DM from {sender.first_name} (@{sender.username})\n🆔 {sender_id}\n📝 {cmd}"
            )
            await event.respond("To buy anything DM @EscapeEternity! This is just a Bot.")
            return

        # If someone replies to an ad, log it
        if event.is_group and event.is_reply:
            replied_msg = await event.get_reply_message()
            if replied_msg.from_id and replied_msg.from_id.user_id == (await client.get_me()).id:
                if sender.bot:
                    return
                gname = (await event.get_chat()).title
                await client.send_message(
                    ADMIN_IDS[0],
                    f"🆕 Someone replied to ad in {gname}:\n{event.raw_text}"
                )

        if not is_admin:
            return

        # Admin Commands
        if cmd.startswith("!addgroup"):
            try:
                gid = int(cmd.split()[1])
                if gid not in data["groups"]:
                    data["groups"].append(gid)
                    save_data(data)
                    await event.reply(f"✅ Added group {gid}")
                else:
                    await event.reply("Already added.")
            except:
                await event.reply("❌ Usage: !addgroup <group_id>")

        elif cmd.startswith("!join") and not is_pm:
            gid = event.chat_id
            if gid not in data["groups"]:
                data["groups"].append(gid)
                save_data(data)
                await event.reply("✅ This group has been added to ad list.")
            else:
                await event.reply("Group already added.")

        elif cmd.startswith("!rmgroup"):
            try:
                gid = int(cmd.split()[1])
                data["groups"] = [g for g in data["groups"] if g != gid]
                save_data(data)
                await event.reply(f"✅ Removed group {gid}")
            except:
                await event.reply("❌ Usage: !rmgroup <group_id>")

        elif cmd.startswith("!setfreq"):
            parts = cmd.split()
            try:
                if len(parts) == 2:
                    data["frequency"] = int(parts[1])
                    save_data(data)
                    await event.reply(f"✅ Global frequency set to {parts[1]} mins")
                elif len(parts) == 3:
                    gid, freq = parts[1], int(parts[2])
                    data["frequencies"][gid] = freq
                    save_data(data)
                    await event.reply(f"✅ Frequency for group {gid} set to {freq} mins")
            except:
                await event.reply("❌ Usage: !setfreq <min> or !setfreq <group_id> <min>")

        elif cmd.startswith("!setmode"):
            try:
                mode = cmd.split()[1].lower()
                if mode in ["random", "order"]:
                    data["mode"] = mode
                    save_data(data)
                    await event.reply(f"✅ Mode set to {mode}")
                else:
                    await event.reply("❌ Use: random or order")
            except:
                await event.reply("❌ Usage: !setmode <random/order>")

        elif cmd == "!status":
            await event.reply(
                f"👥 Groups: {data['groups']}\n"
                f"📤 Mode: {data['mode']}\n"
                f"⏱ Frequency: {data.get('frequency', 45)} mins"
            )

        elif cmd == "!groups":
            await event.reply("📋 Groups:\n" + "\n".join(map(str, data["groups"])))

        elif cmd.startswith("!log"):
            try:
                days = int(cmd.split()[1])
                cutoff = datetime.now() - timedelta(days=days)
                logs = [f"{log['timestamp']}: Group {log['group']}" for log in data.get("logs", []) if datetime.fromisoformat(log["timestamp"]) >= cutoff]
                await event.reply("\n".join(logs) if logs else "No logs found.")
            except:
                await event.reply("❌ Usage: !log <days>")

        elif cmd.startswith("!addadmin"):
            try:
                new_id = int(cmd.split()[1])
                if new_id not in data["admins"]:
                    data["admins"].append(new_id)
                    save_data(data)
                    await event.reply("✅ Admin added.")
                else:
                    await event.reply("Already an admin.")
            except:
                await event.reply("❌ Usage: !addadmin <user_id>")

        elif cmd == "!uptime":
            uptime = timedelta(seconds=int(time.time() - start_time))
            await event.reply(f"⏱ Uptime: {uptime}")

        elif cmd == "!backup":
            await client.send_file(sender_id, DATA_FILE, caption="🗄 Manual Backup")

        elif cmd == "!restore":
            await event.reply("📥 Send the backup file (data.json) as reply to this message.")

        elif event.file and event.reply_to_msg_id:
            file_name = event.file.name or ""
            if "data.json" in file_name:
                await event.download_media(file=DATA_FILE)
                await event.reply("✅ Backup restored. Restart bot to apply changes.")

        elif cmd == "!help":
            await event.reply(
                "🛠 **Bot Commands:**\n"
                "!addgroup <id>\n!rmgroup <id>\n!setfreq <min>\n"
                "!setfreq <group_id> <min>\n!setmode random/order\n"
                "!status\n!groups\n!log <days>\n"
                "!addadmin <user_id>\n!uptime\n!backup\n!restore\n"
                "!join (from group)\n!help"
            )

# Main
async def main():
    session_name = "session1"
    session_path = os.path.join(CREDENTIALS_FOLDER, f"{session_name}.json")
    if not os.path.exists(session_path):
        print(Fore.RED + f"⚠️ No session file at {session_path}")
        return

    with open(session_path, "r") as f:
        creds = json.load(f)

    client = TelegramClient(os.path.join(CREDENTIALS_FOLDER, session_name), creds["api_id"], creds["api_hash"])
    await client.connect()
    if not await client.is_user_authorized():
        print(Fore.RED + "🔒 Session unauthorized.")
        return

    await client.send_message(ADMIN_IDS[0], "✅ Bot started on Render.")

    await asyncio.gather(
        start_web_server(),
        command_handler(client),
        ad_sender(client),
        backup_data(client)
    )

if __name__ == "__main__":
    asyncio.run(main())
