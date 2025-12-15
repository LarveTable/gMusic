import discord
from discord.ext import commands
from discord import app_commands
import os
from cogs.youtube_dlp import YTDownload

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Creating the group play, which is the master command to play a music
    play_group = app_commands.Group(name='play', description='Play a music from available music sources.')
    
    # Sub-command to play a music from a Youtube link or title
    @play_group.command(name='youtube', description='Play a music from a Youtube link or title.')
    @app_commands.describe(query="Link or URL")
    @app_commands.autocomplete(query=YTDownload.preview_results)
    async def youtube(self, interaction: discord.Interaction, query : str):
        # From now on, the bot is guaranteed to be in the user's voice channel thanks to 'ensure_voice'
        pass

    # Ensure the bot is/will connected/connect to the user voice channel, 
    # Defined as before_invoke hook (called before the command is invoked)
    @youtube.before_invoke
    async def ensure_voice(self, interaction: discord.Interaction):
        # Get the bot's voice client
        bot_voice = interaction.guild.voice_client
        # Get the user's voice
        user_voice = interaction.user.voice
        # Check if user is connected to a channel
        if user_voice:
            # Check if bot is connected to a channel
            if bot_voice:
                # If it's playing music and user not in the same channel
                if bot_voice.is_playing() and bot_voice.channel != user_voice.channel:
                    # The bot is already playing music in another channel
                    embed = discord.Embed(
                        title='The bot is already playing in a different channel.',
                        color=discord.Color.red()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)
                    raise commands.CommandError('Bot is playing and author not in the same channel.')
                # If it's not playing music and user not in the same channel (should not happen but I have to make sure)
                elif not bot_voice.is_playing() and bot_voice.channel != user_voice.channel:
                    # Connect to user's voice channel
                    await user_voice.channel.connect()
            # If the bot is not connected to a voice channel
            else:
                # Connect to user's voice channel
                await user_voice.channel.connect()
        # If the user is not in a voice channel
        else:
            embed = discord.Embed(
                title='You are not in a voice channel.',
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)
            raise commands.CommandError('Author is not in a voice channel.')