import os
import json
import asyncio
import random
from telethon import TelegramClient, events
from telethon.tl.functions.messages import GetHistoryRequest
from aiohttp import web
from colorama import Fore, init

init(autoreset=True)

CREDENTIALS_FOLDER = "sessions"
os.makedirs(CREDENTIALS_FOLDER, exist_ok=True)
DATA_FILE = "data.json"

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as f:
        json.dump({
            "groups": [],
            "ads": ["Default ad message 1", "Default ad message 2"],
            "frequency": 45,
            "mode": "random"
        }, f)

def load_data():
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

admin_id = 6249999953  # Set manually

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
    repeat = 1
    ad_index = 0
    while True:
        try:
            data = load_data()
            print(Fore.CYAN + f"Ad cycle {repeat}")
            for gid in data["groups"]:
                if data["mode"] == "random":
                    msg = random.choice(data["ads"])
                else:
                    msg = data["ads"][ad_index % len(data["ads"])]
                    ad_index += 1
                try:
                    await client.send_message(gid, msg)
                    print(Fore.GREEN + f"Sent to {gid}: {msg[:40]}")
                except Exception as e:
                    print(Fore.RED + f"Error sending to {gid}: {e}")
                await asyncio.sleep(random.uniform(10, 20))
            print(Fore.CYAN + f"Cycle done. Sleeping {data['frequency']} mins.")
            await asyncio.sleep(data['frequency'] * 60)
            repeat += 1
        except Exception as e:
            print(Fore.RED + f"Ad loop error: {e}")
            await asyncio.sleep(30)

async def command_handler(client):
    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        sender = await event.get_sender()
        if not event.is_private or not sender:
            return

        if sender.id != admin_id:
            await event.reply("To buy anything DM @EscapeEternity! This is just a Bot.")
            return

        cmd = event.raw_text.strip()
        data = load_data()

        if cmd in ["!help", "/help"]:
            await event.reply(
                "**🤖 Bot Admin Commands**\n"
                "`!status` – Show current settings\n"
                "`!addgroup <group_id>` – Add group ID to send ads\n"
                "`!rmgroup <group_id>` – Remove group ID\n"
                "`!setads msg1 ||| msg2` – Set ad messages\n"
                "`!setfreq <minutes>` – Set delay between ad cycles\n"
                "`!setmode random|order` – Send ads randomly or in order\n"
                "`!test` – Forward latest saved message to you"
            )

        elif cmd == "!status":
            await event.reply(
                f"**Groups:** {data['groups']}\n"
                f"**Ads:** {len(data['ads'])} messages\n"
                f"**Mode:** {data['mode']}\n"
                f"**Frequency:** {data['frequency']} min"
            )

        elif cmd.startswith("!addgroup"):
            try:
                gid = int(cmd.split()[1])
                if gid not in data["groups"]:
                    data["groups"].append(gid)
                    save_data(data)
                    await event.reply(f"✅ Added group `{gid}`")
                else:
                    await event.reply(f"Group `{gid}` already exists.")
            except:
                await event.reply("❌ Usage: `!addgroup <group_id>`")

        elif cmd.startswith("!rmgroup"):
            try:
                gid = int(cmd.split()[1])
                if gid in data["groups"]:
                    data["groups"].remove(gid)
                    save_data(data)
                    await event.reply(f"✅ Removed group `{gid}`")
                else:
                    await event.reply(f"Group `{gid}` not found.")
            except:
                await event.reply("❌ Usage: `!rmgroup <group_id>`")

        elif cmd.startswith("!setads"):
            parts = cmd.split(" ", 1)
            if len(parts) > 1:
                data["ads"] = parts[1].split("|||")
                save_data(data)
                await event.reply("✅ Updated ads.")
            else:
                await event.reply("❌ Usage: `!setads msg1 ||| msg2 ||| msg3`")

        elif cmd.startswith("!setfreq"):
            try:
                freq = int(cmd.split()[1])
                data["frequency"] = freq
                save_data(data)
                await event.reply(f"✅ Frequency set to {freq} minutes.")
            except:
                await event.reply("❌ Usage: `!setfreq <minutes>`")

        elif cmd.startswith("!setmode"):
            try:
                mode = cmd.split()[1]
                if mode in ["random", "order"]:
                    data["mode"] = mode
                    save_data(data)
                    await event.reply(f"✅ Mode set to `{mode}`.")
                else:
                    await event.reply("❌ Use: `!setmode random` or `!setmode order`")
            except:
                await event.reply("❌ Usage: `!setmode <random|order>`")

        elif cmd == "!test":
            try:
                history = await client(GetHistoryRequest(peer="me", limit=1, offset_id=0,
                                                         offset_date=None, max_id=0, min_id=0,
                                                         add_offset=0, hash=0))
                if history.messages:
                    await client.forward_messages(sender.id, history.messages[0].id, "me")
                    await event.reply("✅ Forwarded last saved message.")
                else:
                    await event.reply("⚠️ No messages in Saved Messages.")
            except Exception as e:
                await event.reply(f"❌ Error: {e}")

        else:
            await event.reply("❓ Unknown command. Type `!help`")

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
