# Main file for the Discord bot

import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import time

# Import discord token
load_dotenv()

# Define cogs extensions
ext = ['fun', 'music']

print('Starting bot...')

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
bot = GoonerMusic(command_prefix='', intents=discord.Intents.all())

# Run on server(s)
bot.run(os.getenv('DISCORD_TOKEN'))