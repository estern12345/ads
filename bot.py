import os
import json
import asyncio
import random
from telethon import TelegramClient, events
from aiohttp import web
from colorama import Fore, Style, init

init(autoreset=True)

CREDENTIALS_FOLDER = "sessions"
os.makedirs(CREDENTIALS_FOLDER, exist_ok=True)
DATA_FILE = "data.json"

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as f:
        json.dump({
            "groups": [],
            "ads": [],  # store {"chat_id": int, "message_id": int}
            "frequency": 45,
            "mode": "random",
            "last_sent_ad_index": 0
        }, f)

def load_data():
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

admin_id = 6249999953  # Set admin Telegram user ID here

async def start_web_server():
    async def handle(request):
        return web.Response(text="Service is running!")
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000)))
    await site.start()
    print(Fore.YELLOW + "Web server running.")

async def ad_sender(client):
    while True:
        try:
            data = load_data()
            if not data["groups"] or not data["ads"]:
                print(Fore.RED + "No groups or ads configured, skipping ad cycle.")
                await asyncio.sleep(60)
                continue

            print(Fore.CYAN + f"Starting ad cycle... Mode: {data['mode']}")
            last_index = data.get("last_sent_ad_index", 0)

            for gid in data["groups"]:
                if data["mode"] == "random":
                    ad = random.choice(data["ads"])
                else:  # order mode
                    ad = data["ads"][last_index % len(data["ads"])]
                    last_index += 1

                try:
                    await client.forward_messages(gid, ad["message_id"], ad["chat_id"])
                    print(Fore.GREEN + f"Forwarded ad {ad['message_id']} from {ad['chat_id']} to group {gid}")
                except Exception as e:
                    print(Fore.RED + f"Failed to forward ad to {gid}: {e}")
                await asyncio.sleep(random.uniform(10, 20))

            data["last_sent_ad_index"] = last_index % len(data["ads"])
            save_data(data)

            print(Fore.CYAN + f"Ad cycle complete. Sleeping {data['frequency']} minutes.")
            await asyncio.sleep(data['frequency'] * 60)
        except Exception as e:
            print(Fore.RED + f"Error in ad_sender: {e}")
            await asyncio.sleep(30)

async def command_handler(client):
    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        global admin_id
        sender = await event.get_sender()
        if not event.is_private or not sender:
            return

        # Only admin allowed
        if sender.id != admin_id:
            await event.reply("To buy anything DM @EscapeEternity! This is just a Bot.")
            return

        cmd = event.raw_text.strip()
        data = load_data()

        if cmd.startswith("!addgroup"):
            try:
                gid = int(cmd.split()[1])
                if gid not in data["groups"]:
                    data["groups"].append(gid)
                    save_data(data)
                    await event.reply(f"Added group {gid}")
                else:
                    await event.reply("Group already added.")
            except:
                await event.reply("Usage: !addgroup <group_id>")

        elif cmd.startswith("!rmgroup"):
            try:
                gid = int(cmd.split()[1])
                if gid in data["groups"]:
                    data["groups"].remove(gid)
                    save_data(data)
                    await event.reply(f"Removed group {gid}")
                else:
                    await event.reply("Group not found.")
            except:
                await event.reply("Usage: !rmgroup <group_id>")

        elif cmd.startswith("!setads"):
            # Example: !setads 12345678 111|||12345678 112
            parts = cmd[len("!setads"):].strip()
            if not parts:
                await event.reply("Usage: !setads chat_id message_id|||chat_id message_id|||...")
                return
            ads_raw = parts.split("|||")
            new_ads = []
            try:
                for ad_str in ads_raw:
                    chat_id_str, msg_id_str = ad_str.strip().split()
                    new_ads.append({"chat_id": int(chat_id_str), "message_id": int(msg_id_str)})
                data["ads"] = new_ads
                data["last_sent_ad_index"] = 0
                save_data(data)
                await event.reply(f"Set {len(new_ads)} ads successfully.")
            except Exception as e:
                await event.reply("Error parsing ads. Format: chat_id message_id|||chat_id message_id|||...")

        elif cmd.startswith("!setfreq"):
            try:
                freq = int(cmd.split()[1])
                data["frequency"] = freq
                save_data(data)
                await event.reply(f"Frequency set to {freq} minutes.")
            except:
                await event.reply("Usage: !setfreq <minutes>")

        elif cmd.startswith("!setmode"):
            try:
                mode = cmd.split()[1]
                if mode in ["random", "order"]:
                    data["mode"] = mode
                    save_data(data)
                    await event.reply(f"Mode set to {mode}.")
                else:
                    await event.reply("Use: !setmode random | order")
            except:
                await event.reply("Usage: !setmode random|order")

        elif cmd == "!status":
            await event.reply(
                f"Groups: {data['groups']}\n"
                f"Ads count: {len(data['ads'])}\n"
                f"Mode: {data['mode']}\n"
                f"Frequency: {data['frequency']} minutes"
            )

        elif cmd == "!test":
            if not data["groups"]:
                await event.reply("No groups added. Use !addgroup <group_id>")
                return
            if not data["ads"]:
                await event.reply("No ads set. Use !setads command.")
                return
            # Forward last ad to all groups
            last_index = data.get("last_sent_ad_index", 0) - 1
            if last_index < 0:
                last_index = len(data["ads"]) - 1
            ad = data["ads"][last_index]

            failed = []
            for gid in data["groups"]:
                try:
                    await client.forward_messages(gid, ad["message_id"], ad["chat_id"])
                except Exception as e:
                    failed.append(str(gid))
            if failed:
                await event.reply(f"Failed to forward to groups: {', '.join(failed)}")
            else:
                await event.reply("Forwarded latest ad to all groups.")

        else:
            await event.reply("Unknown command. Use !status, !addgroup, !rmgroup, !setads, !setfreq, !setmode, !test")

async def main():
    session_name = "session1"
    path = os.path.join(CREDENTIALS_FOLDER, f"{session_name}.json")

    if not os.path.exists(path):
        print(Fore.RED + f"No credentials file at {path}")
        return

    with open(path, "r") as f:
        credentials = json.load(f)

    proxy_args = tuple(credentials.get("proxy")) if credentials.get("proxy") else None
    client = TelegramClient(
        os.path.join(CREDENTIALS_FOLDER, session_name),
        credentials["api_id"],
        credentials["api_hash"],
        proxy=proxy_args
    )

    await client.connect()
    if not await client.is_user_authorized():
        print("Login session invalid")
        return

    await client.send_message("me", "✅ Bot started successfully!")

    await asyncio.gather(
        start_web_server(),
        command_handler(client),
        ad_sender(client)
    )

if __name__ == "__main__":
    asyncio.run(main())
