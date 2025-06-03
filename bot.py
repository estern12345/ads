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
os.makedirs("data", exist_ok=True)

# Load or initialize config
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

admin_id = None  # Will be set once admin sends command

casual_pool = [
    "Hey, how's it going?",
    "What’s up everyone?",
    "Anyone active here?",
    "Just checking in!",
    "Hope you're all good!"
]

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
    casual_used = set()
    ad_index = 0
    while True:
        try:
            data = load_data()
            print(Fore.CYAN + f"Ad cycle {repeat}")
            for gid in data["groups"]:
                if random.randint(1, 100) <= 20:
                    msg = random.choice([m for m in casual_pool if m not in casual_used])
                    casual_used.add(msg)
                else:
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
        global admin_id
        sender = await event.get_sender()
        if not event.is_private or not sender:
            return
        if admin_id is None:
            admin_id = sender.id
        elif sender.id != admin_id:
            await event.reply("You are not authorized.")
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
            except: await event.reply("Usage: !addgroup <group_id>")

        elif cmd.startswith("!rmgroup"):
            try:
                gid = int(cmd.split()[1])
                data["groups"] = [g for g in data["groups"] if g != gid]
                save_data(data)
                await event.reply(f"Removed group {gid}")
            except: await event.reply("Usage: !rmgroup <group_id>")

        elif cmd.startswith("!setads"):
            parts = cmd.split(" ", 1)
            if len(parts) > 1:
                data["ads"] = parts[1].split("|||")
                save_data(data)
                await event.reply("Updated ads.")
            else:
                await event.reply("Usage: !setads msg1 ||| msg2 ||| msg3")

        elif cmd.startswith("!setfreq"):
            try:
                freq = int(cmd.split()[1])
                data["frequency"] = freq
                save_data(data)
                await event.reply(f"Set frequency to {freq} minutes.")
            except: await event.reply("Usage: !setfreq <minutes>")

        elif cmd.startswith("!setmode"):
            mode = cmd.split()[1]
            if mode in ["random", "order"]:
                data["mode"] = mode
                save_data(data)
                await event.reply(f"Ad mode set to {mode}.")
            else:
                await event.reply("Use: !setmode random | order")

        elif cmd == "!status":
            await event.reply(
                f"Groups: {data['groups']}\nAds: {len(data['ads'])} messages\n"
                f"Mode: {data['mode']}\nFrequency: {data['frequency']} min"
            )

        else:
            await event.reply("Unknown command. Try !status, !addgroup, !setads")

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
