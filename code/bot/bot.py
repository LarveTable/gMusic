# Main file for the Discord bot

import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import aiosqlite

DB_PATH = "code/bot/music.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_favorites (
                user_id TEXT NOT NULL,
                url TEXT NOT NULL,
                title TEXT,
                added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, url)
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

        # If you are on Windows, load the opus.dll in the cogs folder
        if os.name == 'nt':
            discord.opus.load_opus('code/bot/cogs/opus.dll')

        # This is the path for MacOS using homebrew
        if os.name == 'posix':
            discord.opus.load_opus('/opt/homebrew/lib/libopus.dylib')
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