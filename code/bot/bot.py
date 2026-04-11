# Main file for the Discord bot

import discord
from discord.ext import commands
from dotenv import load_dotenv
from ctypes.util import find_library
import os
import sys
import aiosqlite

DB_PATH = "code/bot/music.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_favorites (
                user_id TEXT NOT NULL,
                id TEXT NOT NULL,
                data TEXT NOT NULL,
                added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, id)
            )
        """)
        await db.commit()

# Import discord token
load_dotenv()

# Check if the temp_songs directory exists, if not create it
if not os.path.exists('code/bot/cogs/temp_songs/'):
    os.makedirs('code/bot/cogs/temp_songs/')

# Define cogs extensions
EXTENSIONS = ['fun', 'music_remaster']

print('[GoonerMusic] --- Starting bot...')

# Check if the Opus library is loaded
if not discord.opus.is_loaded():
    try:
        # Load Opus for voice support

        opus_candidates = []

        # If you are on Windows, load the opus.dll in the cogs folder
        if sys.platform.startswith('win'):
            opus_candidates.append('code/bot/cogs/opus.dll')

        # macOS Homebrew path
        elif sys.platform == 'darwin':
            opus_candidates.append('/opt/homebrew/lib/libopus.dylib')
            opus_candidates.append('/usr/local/lib/libopus.dylib')

        # Linux container and native Linux installs
        elif sys.platform.startswith('linux'):
            opus_candidates.extend([
                'libopus.so.0',
                '/usr/lib/x86_64-linux-gnu/libopus.so.0',
                '/usr/lib/aarch64-linux-gnu/libopus.so.0',
                '/usr/lib/libopus.so.0',
            ])

        found_opus = find_library('opus')
        if found_opus:
            opus_candidates.insert(0, found_opus)

        for opus_path in opus_candidates:
            try:
                discord.opus.load_opus(opus_path)
                break
            except OSError:
                continue
        else:
            raise RuntimeError('Opus library could not be found on this system.')
    except Exception:
        raise RuntimeError('Opus failed to load')

class GoonerMusic(commands.Bot):
    # Executed at startup
    async def setup_hook(self):
        # Initialize the database
        print('[GoonerMusic] --- Initializing database...')
        try:
            await init_db()
            print('[GoonerMusic] --- Database initialized.')
        except Exception as e:
            print(f'[GoonerMusic] *** Failed to initialize database : {e}')

        # Load the extensions
        print('[GoonerMusic] ---  Loading extensions...')
        for ext in EXTENSIONS:
            try:
                await self.load_extension(f'cogs.{ext}')
                print(f'[GoonerMusic] ---  Loaded {ext}.')
            except Exception as e:
                print(f'[GoonerMusic] *** Failed to load {ext}: {e}')
        
        # Slash commands sync (for dev, I can do it at every startup)
        try:
            synced = await self.tree.sync()
            print(f'[GoonerMusic] ---  Slash commands synchronized: {len(synced)}.')
        except Exception as e:
            print(f'[GoonerMusic] *** Sync error: {e}')

    # Executed when bot is ready (even after a crash)
    async def on_ready(self):
        print(f'[GoonerMusic] ---  Logged in as {self.user} (ID: {self.user.id})')
        print('[GoonerMusic] ---  Bot is ready and running.')

# Creating the bot
bot = GoonerMusic(command_prefix='!', intents=discord.Intents.all())

# Run on server(s)
token = os.getenv('DISCORD_TOKEN')
if token is None:
    raise ValueError("No DISCORD_TOKEN found in environment variables.")
bot.run(token)