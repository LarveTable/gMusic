import discord
from discord.ext import commands
from discord import app_commands
import os
from cogs.youtube_dlp import YTDownload
import asyncio
from collections import deque

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Lock to secure concurrent ensure_voice calls
        self.ensure_voice_lock = asyncio.Lock()
        # Lock to secure concurrent play calls, when choosing between playing and waitlist
        self.play_lock = asyncio.Lock()
        # Waiting list for the songs
        self.waitlist = deque()
        # Message object for the current player info
        self.player = None

    # Creating the group play, which is the master command to play a music
    play_group = app_commands.Group(name='play', description='Play a music from available music sources.')
    
    # Sub-command to play a music from a Youtube link or title
    @play_group.command(name='youtube', description='Play a music from a Youtube link or title.')
    @app_commands.describe(query="Link or URL")
    @app_commands.autocomplete(query=YTDownload.preview_results)
    async def youtube(self, interaction: discord.Interaction, query : str):
        # Ensure the bot is in the user's voice channel, or connect it (can't use before_invoke with app_commands)
        try:
            await self.ensure_voice(interaction)
        except commands.CommandError:
            return
        # From now on, the bot is guaranteed to be in the user's voice channel thanks to 'ensure_voice'
        # Tell the user that the search is initiated
        searching_embed = discord.Embed(
                    title=f'🔍 Searching for **{query}** on YouTube...',
                    description=os.getenv('SEARCHING'),
                    color=discord.Color.orange()
                )
        await interaction.response.send_message(embed=searching_embed, ephemeral=True)

        # Search for the song on youtube
        try :
            # Get the YTDownload data
            data = await YTDownload.search(query)
            # If found, play it
            if data:
                found_embed = discord.Embed(
                                    title=f'✅ Found **{data["title"]}** on Youtube and downloaded it !',
                                    description=os.getenv('FOUND'),
                                    color=discord.Color.green()
                                )
                await interaction.edit_original_response(embed=found_embed)

                # Get the voice client
                voice_client = interaction.guild.voice_client

                # Enter the lock
                async with self.play_lock:
                    # Add the song to the waitlist
                    self.waitlist.append(data)

                    # Check if the bot is already playing
                    if not voice_client.is_playing():
                        # If not, actually play the song
                        await self.play_next(interaction)
                    else:
                        # The song stays in the waitlist while the current one is playing
                        waitlist_embed = discord.Embed(
                                title=f'⏳ **{data["title"]}** has been added to the waiting list !',
                                description=f'Already playing music, '+ os.getenv('ALREADY_PLAYING')+f'\nPosition #{len(self.waitlist)}',
                                color=discord.Color.green()
                            )
                        await interaction.edit_original_response(embed=waitlist_embed)
                        # Send a message to the channel for everyone to see
                        global_waitlist_embed = discord.Embed(
                                title=f'⏳ **{data["title"]}** has been added to the waiting list by -'+f'{interaction.user.name}-',
                                description=f'Position #{len(self.waitlist)}',
                                color=discord.Color.green()
                            )
                        await interaction.channel.send(embed=global_waitlist_embed)
                        # Push the player message back to the bottom to prevent it from being too far up due to the waitlist messages
                        await self.ensure_player()
            # No results found
            else:
                not_found_embed = discord.Embed(
                                    title=f'❌ No results found for **{query}** on Youtube.',
                                    description='Try again with a different query.',
                                    color=discord.Color.red()
                                )
                await interaction.edit_original_response(embed=not_found_embed)
        except Exception as e : 
            print(e)
            # Unexpected error
            error_embed = discord.Embed(
                                title=f'❌ Unexpected error.',
                                description='Check console for more details.',
                                color=discord.Color.red()
                            )
            await interaction.edit_original_response(embed=error_embed)

    # Function to ensure the player message is always at the bottom of the chat
    async def ensure_player(self):
        # Retrieve the original player message
        msg = self.player.embeds[0]
        # Retrieve the original player message channel
        channel = self.player.channel
        # Delete the old player message
        await self.player.delete()
        # Send it again
        self.player = await channel.send(embed=msg)

    # Function to play a song in the bot's voice channel, executed everytime a song ends if the waiting list has something in it
    async def play_next(self, interaction: discord.Interaction):
        # Get the bot's voice
        voice_client = interaction.guild.voice_client
        # Delete previous player if it exists
        if self.player:
            await self.player.delete()
        # If something is in the waiting list
        if len(self.waitlist) > 0:
            # Retrieve the data from the next song in queue
            data = self.waitlist.popleft()

            # Send the player message
            playing_embed = discord.Embed(
                    title=f'▶️ Now playing {data["title"]}',
                    color=discord.Color.green()
                )
            playing_embed.set_thumbnail(url=data['thumbnail'])
            playing_embed.add_field(name='Duration', value=f"{data['duration'] // 60}:{data['duration'] % 60:02d}", inline=True)
            playing_embed.add_field(name='Uploader', value=data['uploader'], inline=True)
            playing_embed.add_field(name='Views', value=data['view_count'], inline=True)
            playing_embed.add_field(name='Likes', value=data['like_count'], inline=True)
            playing_embed.add_field(name='Upload date', value=data['upload_date'], inline=True)
            playing_embed.set_footer(text=f'URL: {data["webpage_url"]}')
            self.player = await interaction.channel.send(embed=playing_embed)

            # Audio source
            source = discord.FFmpegPCMAudio(f'code/bot/cogs/temp_songs/{data["id"]}.{data["ext"]}')
            # Audio player (to manage volume)
            audio_player = discord.PCMVolumeTransformer(source, volume=0.5)
            # Play, 'after' will run this functions everytime the current song ends
            voice_client.play(audio_player, after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(interaction), self.bot.loop))
        # If there's nothing in the waiting list
        else:
            finished_embed = discord.Embed(
                title='🏁 Finished playing '+os.getenv('FINISHED_PLAYING'),
                color=discord.Color.green()
            )
            self.player = await interaction.channel.send(embed=finished_embed)
        
    # Ensure the bot is/will connected/connect to the user voice channel
    async def ensure_voice(self, interaction: discord.Interaction):
        # Initialize error variables
        error_embed = None
        error_exception = None
        # Locking to prevent simultaneous connections (two clients trying to ensure voice at the same time)
        async with self.ensure_voice_lock:
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
                        error_embed = discord.Embed(
                            title='❌ The bot is already playing in a different channel.',
                            color=discord.Color.red()
                        )
                        error_exception = commands.CommandError('Bot is playing and author not in the same channel.')
                    # If it's not playing music and user not in the same channel (should not happen but I have to make sure)
                    elif not bot_voice.is_playing() and bot_voice.channel != user_voice.channel:
                        # Connect to user's voice channel
                        await bot_voice.disconnect()
                        await user_voice.channel.connect()
                # If the bot is not connected to a voice channel
                else:
                    # Connect to user's voice channel
                    await user_voice.channel.connect()
            # If the user is not in a voice channel
            else:
                error_embed = discord.Embed(
                    title='❌ You are not in a voice channel.',
                    color=discord.Color.red()
                )
                error_exception = commands.CommandError('Author is not in a voice channel.')
        # If there was an error, send the message after releasing the lock
        if error_embed:
            await interaction.response.send_message(embed=error_embed, ephemeral=True, delete_after=10)
            raise error_exception
        
# This function is used to setup the cog
async def setup(bot):
    await bot.add_cog(MusicCog(bot))