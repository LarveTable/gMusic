import discord
from discord.ext import commands
from discord import app_commands
from cogs.youtube_dlp import YTDownload
import os

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.waitlist = []
        self.lock = False
        self.message = None
        self.channel = None

    # Creating the group play, which is the master command to play a music, we will define sub-commands later
    play_group = app_commands.Group(name='play', description='Play a music from available music sources.')
    
    # Sub-command to play a music from a Youtube link or title
    @play_group.command(name='youtube', description='Play a music from a Youtube link or title.')
    @app_commands.describe(query="Link or URL")
    async def youtube(self, interaction: discord.Interaction, query : str):
        """
        Play a music from a Youtube link or title.
        This command will search for the song on YouTube and play it in the voice channel the user is connected to.
        If the song is a link, it will play it directly. If the song is a title, it will search for it on YouTube.
        If the bot is not connected to a voice channel, it will connect to the user's voice channel.
        If the user is not connected to a voice channel, it will send an error message.
        If the bot is already playing music, it will send an error message.
        If the song is not found, it will send an error message.
        If there is an error while searching for the song, it will send an error message.

        Parameters:
        - interaction: The interaction object from Discord.
        - song: The song to play, either a YouTube link or a title.
        Returns:
        - None
        """

        # Check if the bot is already connected and playing music
        if ((interaction.guild.voice_client and not interaction.guild.voice_client.is_playing() and not self.lock)
            or (self.waitlist == [] and not interaction.guild.voice_client)):

            # Check if the user is connected to a music channel then proceed
            # SHOULD CHECK FOR ANY USER IN THE CHANNEL, NOT JUST THE COMMAND ISSUER
            if (interaction.user.voice):

                # Set the lock to True to prevent multiple commands from being executed at the same time
                self.lock = True

                # Set the channel to the current interaction channel
                self.channel = interaction.channel
                
                if (self.waitlist == []):
                    song = query
                else:
                    # Retrieve the song from the waitlist
                    song = self.waitlist.pop(0)

                # User feedback for the search, needed to avoid the infinite loading state
                if not interaction.response.is_done():
                    # Initiation message
                    embed = discord.Embed(
                        title='Initiating...',
                        color=discord.Color.orange()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    await interaction.delete_original_response()

                # Send the original search message
                embed = discord.Embed(
                    title=f'Searching for {song} on YouTube. '+os.getenv('SEARCHING'),
                    color=discord.Color.orange()
                )

                # If the message is already set, delete it and send a new one
                if self.message is not None:
                    await self.message.delete()

                # Send the embed message to the channel
                self.message = await self.channel.send(embed=embed)

                # Search for the song on YouTube
                try:
                    # If the song is a link, we will use it directly, otherwise we will search for it
                    if 'http' in song or 'www' in song:
                        yt = await YTDownload.from_url(song)
                    else:
                        yt = await YTDownload.from_search(song)

                    # If the song is found, we will play it
                    if (yt != None):
                        embed = discord.Embed(
                                    title=f'Found {yt['title']} on Youtube '+os.getenv('FOUND')+' !',
                                    color=discord.Color.green()
                                )
                        await self.message.edit(embed=embed)

                        # If the bot is not connected to the user's voice channel, connect to the user's voice channel
                        if not interaction.guild.voice_client or not interaction.guild.voice_client.channel == interaction.user.voice.channel:
                            channel = interaction.user.voice.channel
                            await channel.connect()

                        # If the bot is already connected, just play the music
                        # The message should be displayed as the most recent message in the channel
                        voice_client = interaction.guild.voice_client
                        if voice_client.is_connected():
                            voice_client.play(discord.FFmpegPCMAudio(yt['path']), after=lambda e: self.bot.loop.create_task(self.finished_playing(interaction)))
                            embed = discord.Embed(
                                title=f'Now playing {yt['title']}',
                                color=discord.Color.green()
                            )
                            embed.set_thumbnail(url=yt['thumbnail'])
                            embed.add_field(name='Duration', value=f"{yt['duration'] // 60}:{yt['duration'] % 60:02d}", inline=True)
                            embed.add_field(name='Uploader', value=yt['uploader'], inline=True)
                            embed.add_field(name='Views', value=yt['view_count'], inline=True)
                            embed.add_field(name='Likes', value=yt['like_count'], inline=True)
                            embed.add_field(name='Upload date', value=yt['upload_date'], inline=True)
                            embed.set_footer(text=f'URL: {yt["url"]}')
                            await self.message.edit(embed=embed)

                    else:
                        embed = discord.Embed(
                                    title=f'{song} not found on Youtube ! I am not a fucking magician.',
                                    description='Please try again with a different song or link.',
                                    color=discord.Color.red()
                                )
                        await self.message.edit(embed=embed)

                except Exception as e:
                    print(e)
                    embed = discord.Embed(
                                title=f'Error while searching. Fucking code is broken.',
                                description='Please try again later or contact the developer.',
                                color=discord.Color.red()
                            )
                    await self.message.edit(embed=embed)
                    await self.next.callback(self=self, interaction=interaction)

            else:
                # SHOULD CHECK IF INTERACTION HAS BEEN RESPONDED TO AND IF SO INITIATE STOP ELSE DO THIS

                # The user is not in a voice channel
                embed = discord.Embed(
                    title=f'You are not in a voice channel, '+ os.getenv('NOT_IN_VOICE_CHANNEL'),
                    description='Please join a voice channel and try again. Maybe ?',
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

        else:
            # Add the song to the waitlist
            self.waitlist.append(query)
            print(f'Added {query} to the waitlist. Current waitlist: {self.waitlist}')

            # The user is not in a voice channel
            embed = discord.Embed(
                title='The song has been added to the waiting list.',
                description=f'Already playing music, '+ os.getenv('ALREADY_PLAYING'),
                color=discord.Color.green()
            )
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed)
            else:
                await interaction.response.send_message(embed=embed)

    # Sub-command to play the next song in the waitlist
    @play_group.command(name='next', description='Play the next song in the waitlist and stop the current one.')
    async def next(self, interaction: discord.Interaction):
        """
        Play the next song in the waitlist and stop the current one.
        This command will stop the current music and play the next song in the waitlist.
        If there is no music playing, it will send an error message.
        If there is no song in the waitlist, it will send an error message.

        Parameters:
        - interaction: The interaction object from Discord.
        Returns:
        - None
        """

        # Check if the bot is connected to a voice channel
        if (interaction.guild.voice_client):

            # Check if there is a song in the waitlist
            if (self.waitlist != []):

                # Stop the current music
                voice_client = interaction.guild.voice_client
                if voice_client.is_playing():
                    voice_client.stop()
                
                # Message to indicate that the next song is being played
                embed = discord.Embed(
                    title='Skipping... Playing the next song in the waitlist.',
                    description=f'Now playing {self.waitlist[0]}',
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed)

            else:
                embed = discord.Embed(
                    title='There is no song in the waiting list.',
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(
                title='I am not connected to a voice channel '+os.getenv('NOT_CONNECTED'),
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)

    # Sub-command to stop the current music
    @play_group.command(name='stop', description='Stop the current music.')
    async def stop(self, interaction: discord.Interaction):
        # Check if the bot is connected to a voice channel
        if (interaction.guild.voice_client):

            # Delete the message
            await self.message.delete()

            # Clear the message
            self.message = None

            # Clear the channel
            self.channel = None

            # Unlock the lock to allow the next command to be executed
            self.lock = False

            # Clear the waitlist
            self.waitlist = [] 

            voice_client = interaction.guild.voice_client
            # Stop the music
            if voice_client.is_playing():
                voice_client.stop()
            embed = discord.Embed(
                title='Music stopped. Leaving the voice channel '+os.getenv('STOPPED'),
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

            # Delete all the music files in the temp_songs folder
            for file in os.listdir('code/bot/cogs/temp_songs/'):
                file_path = os.path.join('code/bot/cogs/temp_songs/', file)
                if os.path.isfile(file_path):
                    os.remove(file_path)

            # Disconnect from the voice channel
            await voice_client.disconnect()
        else:
            embed = discord.Embed(
                title='I am not connected to a voice channel '+os.getenv('NOT_CONNECTED'),
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)

    # Just a function to edit the message when the music is finished playing
    async def finished_playing(self, interaction):

        if self.message is None:
            # If the message is not set, we will not do anything
            return
        
        """# Get message id to counter the 15min timeout of the interaction
        id = self.message.id

        # Get the message again to avoid the 15min timeout of the interaction
        message = await interaction.channel.fetch_message(id)"""

        # Check if the bot is connected to a voice channel
        if (interaction.guild.voice_client):
            # If the waitlist is empty, we will edit the message to say that the music is finished playing
            if (self.waitlist == []):

                # Unlock the lock to allow the next command to be executed
                self.lock = False

                embed = discord.Embed(
                                    title='Finished playing '+os.getenv('FINISHED_PLAYING'),
                                    color=discord.Color.green()
                                )
                await self.message.edit(embed=embed)

            # If the waitlist is not empty, we will play the next song in the waitlist
            else:
                # Set the lock to False to allow the next command to be executed
                self.lock = False
                await self.youtube.callback(self=self, interaction=interaction, query="")

# This function is used to setup the cog
async def setup(bot):
    await bot.add_cog(MusicCog(bot))