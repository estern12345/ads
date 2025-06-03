import os
import json
import asyncio
import random
from telethon import TelegramClient, events
from telethon.tl.functions.messages import GetHistoryRequest
from aiohttp import web
from colorama import Fore, Style, init

init(autoreset=True)

CREDENTIALS_FOLDER = "sessions"
os.makedirs(CREDENTIALS_FOLDER, exist_ok=True)
DATA_FILE = "data.json"

# Initialize or fix corrupted JSON
def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        print(Fore.RED + "Corrupted or missing data.json, resetting...")
        data = {
            "groups": [],
            "frequency": 45,
            "mode": "random",
            "last_sent_ad_index": 0
        }
        save_data(data)
        return data

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

async def start_web_server():
    async def handle(request):
        return web.Response(text="✅ Bot is running on Render")
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
            ads = await client(GetHistoryRequest(peer="me", limit=20, offset_id=0,
                                                 offset_date=None, max_id=0, min_id=0,
                                                 add_offset=0, hash=0))
            saved_messages = [m for m in ads.messages if m.message or m.media]

            if not saved_messages:
                print(Fore.RED + "No saved messages found.")
                await asyncio.sleep(60)
                continue

            print(Fore.CYAN + f"Running ad cycle to {len(data['groups'])} group(s)...")
            for gid in data["groups"]:
                try:
                    if data["mode"] == "random":
                        msg = random.choice(saved_messages)
                    else:
                        index = data["last_sent_ad_index"] % len(saved_messages)
                        msg = saved_messages[index]
                        data["last_sent_ad_index"] += 1
                        save_data(data)

                    await client.forward_messages(gid, msg.id, "me")
                    print(Fore.GREEN + f"Forwarded ad to {gid}")
                    await asyncio.sleep(random.uniform(10, 20))
                except Exception as e:
                    print(Fore.RED + f"Error sending to group {gid}: {e}")

            print(Fore.CYAN + f"Cycle done. Sleeping {data['frequency']} minutes.")
            await asyncio.sleep(data["frequency"] * 60)
        except Exception as e:
            print(Fore.RED + f"Error in ad_sender: {e}")
            await asyncio.sleep(30)

async def command_handler(client):
    admin_id = None

    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        nonlocal admin_id
        sender = await event.get_sender()

        if not event.is_private:
            return

        if admin_id is None:
            admin_id = sender.id
        elif sender.id != admin_id:
            await event.reply("To buy anything DM @EscapeEternity! This is just a Bot.")
            return

        data = load_data()
        cmd = event.raw_text.strip()

        if cmd.startswith("!addgroup"):
            try:
                gid = int(cmd.split()[1])
                if gid not in data["groups"]:
                    data["groups"].append(gid)
                    save_data(data)
                    await event.reply(f"✅ Added group {gid}")
                else:
                    await event.reply("Group already in list.")
            except:
                await event.reply("❌ Usage: !addgroup <group_id>")

        elif cmd.startswith("!rmgroup"):
            try:
                gid = int(cmd.split()[1])
                data["groups"] = [g for g in data["groups"] if g != gid]
                save_data(data)
                await event.reply(f"✅ Removed group {gid}")
            except:
                await event.reply("❌ Usage: !rmgroup <group_id>")

        elif cmd.startswith("!setfreq"):
            try:
                freq = int(cmd.split()[1])
                data["frequency"] = freq
                save_data(data)
                await event.reply(f"✅ Frequency set to {freq} minutes")
            except:
                await event.reply("❌ Usage: !setfreq <minutes>")

        elif cmd.startswith("!setmode"):
            try:
                mode = cmd.split()[1].lower()
                if mode in ["random", "order"]:
                    data["mode"] = mode
                    save_data(data)
                    await event.reply(f"✅ Mode set to {mode}")
                else:
                    await event.reply("❌ Use: !setmode random | order")
            except:
                await event.reply("❌ Usage: !setmode <random/order>")

        elif cmd == "!status":
            await event.reply(f"👥 Groups: {data['groups']}\n📤 Mode: {data['mode']}\n⏱ Frequency: {data['frequency']} min")

        elif cmd == "!test":
            try:
                ads = await client(GetHistoryRequest(peer="me", limit=1, offset_id=0,
                                                     offset_date=None, max_id=0, min_id=0,
                                                     add_offset=0, hash=0))
                if not ads.messages:
                    await event.reply("❌ No saved message found.")
                    return
                msg = ads.messages[0]
                for gid in data["groups"]:
                    await client.forward_messages(gid, msg.id, "me")
                    await asyncio.sleep(3)
                await event.reply("✅ Sent test ad to all selected groups.")
            except Exception as e:
                await event.reply(f"❌ Error: {e}")

        else:
            await event.reply("❓ Unknown command. Use !status, !addgroup, !setfreq, !setmode, !test, !rmgroup")

async def main():
    session_name = "session1"
    path = os.path.join(CREDENTIALS_FOLDER, f"{session_name}.json")

    if not os.path.exists(path):
        print(Fore.RED + f"No credentials file found at {path}")
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
        print(Fore.RED + "Telegram account not logged in.")
        return

    await asyncio.gather(
        start_web_server(),
        command_handler(client),
        ad_sender(client)
    )

if __name__ == "__main__":
    asyncio.run(main())
