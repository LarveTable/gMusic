# Main file for the Discord bot

import discord
from discord.ext import commands
from dotenv import load_dotenv
import os

# Import discord token
load_dotenv()

# Check if the temp_songs directory exists, if not create it
if not os.path.exists('code/bot/cogs/temp_songs/'):
    os.makedirs('code/bot/cogs/temp_songs/')

# Define cogs extensions
ext = ['fun', 'music']

print('Starting bot...')

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
    async def on_ready(self):
        for e in ext:
            await self.load_extension(f'cogs.{e}')

        # Syncronize the slash commands
        try:
            synced = await bot.tree.sync()
            print(f'Slash commands syncronized : {len(synced)}')
        except Exception as e:
            print(e)

        print("Bot initialized.") 

# Creating the bot
bot = GoonerMusic(command_prefix='!', intents=discord.Intents.all())

# Run on server(s)
token = os.getenv('DISCORD_TOKEN')
if token is None:
    raise ValueError("No DISCORD_TOKEN found in environment variables.")
bot.run(token)