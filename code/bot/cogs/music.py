import discord
from discord.ext import commands
from discord import app_commands
import time
import asyncio

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Creating the group play, which is the master command to play a music, we will define sub-commands later
    group = app_commands.Group(name='play', description='Play a music from available music sources.')
    
    #test
    @group.command(name='youtube', description='Play a music from a Youtube link or title.')
    @app_commands.describe(song="Link or URL")
    async def youtube(self, interaction: discord.Interaction, song : str):
        # Check if the user is connected to a music channel
        if (interaction.user.voice):
            channel = interaction.user.voice.channel
            await channel.connect()

            # Send the original search message
            embed = discord.Embed(
                title=f'Searching for {song} on YouTube.',
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed)

            # Getting the sent message to edit it later
            message = await interaction.original_response()

            # Start search animation
            animation_task = asyncio.create_task(animated_search(song, message))

            await asyncio.sleep(5)

            # When found, stop the search animation
            animation_task.cancel()
            try:
                await animation_task
            except asyncio.CancelledError:
                pass

            embed = discord.Embed(
                        title=f'Found {song} on Youtube !',
                        color=discord.Color.green()
                    )
            await message.edit(embed=embed)

        else:
            # The user is not in a voice channel
            embed = discord.Embed(
                title=f'You are not in a voice channel.',
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)

async def animated_search(song, message):
    points = ['..', '...', '.']
    while True:
        for p in points:
            await asyncio.sleep(0)
            embed = discord.Embed(
                title=f'Searching for {song} on YouTube{p}',
                color=discord.Color.orange()
            )
            try:
                # Shield in case the routine is stopped during https request
                await asyncio.shield(message.edit(embed=embed))
            except discord.HTTPException as e:
                pass
            await asyncio.sleep(0.5)

async def retrieve_youtube_song(song):
    pass

async def setup(bot):
    await bot.add_cog(MusicCog(bot))