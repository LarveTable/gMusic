import discord
from discord.ext import commands
from discord import app_commands
import os
from cogs.youtube_dlp import YTDownload
import asyncio
from collections import deque
from views.player_view import PlayerContainer, PlayerLayout

class MusicCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Lock to secure concurrent ensure_voice calls (via /play youtube)
        self.ensure_voice_lock = asyncio.Lock()
        # Lock to secure concurrent play calls, when choosing between playing and waitlist
        self.play_lock = asyncio.Lock()
        # Waiting list for the songs
        self.waitlist = deque()
        # Message object for the current player info
        self.player = None
        # Disconnect timer task
        self.disconnect_timer = None
        # Store the voice channel id to be able to ensure long sessions
        self.current_voice_channel_id = None
        # Same for the text channel id
        self.current_text_channel_id = None
        # Same for the guild
        self.current_guild_id = None
        # Lock to secure the UI player
        self.ui_lock = asyncio.Lock()
        # Store the player's view
        self.player_view = None
        # Store the volume
        self.current_volume = 0.3
        # Lock to prevent concurrent volume changes
        self.volume_lock = asyncio.Lock()

    # Creating the group play, which is the master command to play a music
    play_group = app_commands.Group(name='play', description='Play a music from available music sources.')
    
    # Sub-command to play a music from a Youtube link or title
    @play_group.command(name='youtube', description='⏯️ Play a music from a Youtube link or title.')
    @app_commands.describe(query="Link or URL")
    @app_commands.autocomplete(query=YTDownload.preview_results)
    async def youtube(self, interaction: discord.Interaction, query : str):
        # Delete any preview task this user launched
        YTDownload.cancel_user_task(interaction.user.id)
        # Defer the interaction to prevent timeouts
        await interaction.response.defer(ephemeral=True, thinking=True)
        # Ensure the bot is in the user's voice channel, or connect it (can't use before_invoke with app_commands)
        try:
            await self.ensure_voice(interaction)
        except commands.CommandError:
            return
        # From now on, the bot is guaranteed to be in the user's voice channel thanks to 'ensure_voice'
        # Cancel disconnect timer if set
        if self.disconnect_timer:
            self.disconnect_timer.cancel()
            self.disconnect_timer = None
            print("[BOT] --- Cancelled inactivity timer.")
        # Tell the user that the search is initiated
        searching_embed = discord.Embed(
                    title=f'🔍 Searching for **{query}** on YouTube...',
                    description=os.getenv('SEARCHING'),
                    color=discord.Color.orange()
                )
        await interaction.edit_original_response(embed=searching_embed)

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
                    if not voice_client.is_playing() and not voice_client.is_paused():
                        # If not, actually play the song
                        await self.play_next()
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
            print(f"[BOT] --- Unexpected error : {e}")
            # Unexpected error
            error_embed = discord.Embed(
                                title=f'❌ Unexpected error.',
                                description='Check console for more details.',
                                color=discord.Color.red()
                            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
    
    # Sub-command to stop the current music and clear the waiting list
    @play_group.command(name='stop', description='⏹️ Stop the current music and clear the waiting list.')
    async def stop(self, interaction: discord.Interaction):
        # Get bot's voice_client
        voice_client = interaction.guild.voice_client
        # Ensure the command can be ran
        try:
            await self.ensure_context(interaction)
        except:
            # Return if we could not ensure (response is done)
            return
        # Call the cleanup function that will ensure variables cleanup
        await self.cleanup()
        # Try to stop the voice
        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            try:
                voice_client.stop()
            except Exception as e:
                print(f'[BOT] --- Voice client stop error : {e}')
        stopped_embed = discord.Embed(
                                title=f'⏹️ Music stopped by -{interaction.user.name}-.',
                                description='Leaving the voice channel in 1 minute.',
                                color=discord.Color.green()
                            )
        await interaction.response.send_message(embed=stopped_embed)
        # Start the disconnect timer
        self.disconnect_timer = asyncio.create_task(self.disconnect_after_delay(voice_client))
    
    # Sub-command to skip the current music
    @play_group.command(name='skip', description='⏩ Skip the current music.')
    async def skip(self, interaction: discord.Interaction):
        # Get bot's voice_client
        voice_client = interaction.guild.voice_client
        # Ensure the command can be ran
        try:
            await self.ensure_context(interaction)
        except:
            # Return if we could not ensure (response is done)
            return
        # Try to stop the voice, so the next song will play by triggering the after lambda
        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            try:
                voice_client.stop()
            except Exception as e:
                print(f'[BOT] --- Voice client stop error : {e}')
        # Tell the channel about the skip
        if len(self.waitlist) == 0:
            skipped_embed = discord.Embed(
                                title=f'⏩ Music skipped by -{interaction.user.name}-.',
                                description='No more songs in the waiting list.',
                                color=discord.Color.green()
                            )
            await interaction.response.send_message(embed=skipped_embed)
            return
        skipped_embed = discord.Embed(
                                title=f'⏩ Music skipped by -{interaction.user.name}-.',
                                description=f'Will now play **{self.waitlist[0]["title"]}**.',
                                color=discord.Color.green()
                            )
        await interaction.response.send_message(embed=skipped_embed)
    
    # Sub-command to change the volume
    @play_group.command(name='volume', description='🔊 Change the music volume (0 to 100).')
    @app_commands.describe(volume="The volume value")
    async def volume(self, interaction: discord.Interaction, volume: app_commands.Range[int, 0, 100]):
        # Get bot's voice_client
        voice_client = interaction.guild.voice_client
        # Ensure the command can be ran
        try:
            await self.ensure_context(interaction)
        except:
            # Return if we could not ensure (response is done)
            return
        # Try to change the volume using provided value
        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            try:
                async with self.volume_lock:
                    voice_client.source.volume = volume / 100
                    # Store the new value
                    self.current_volume = voice_client.source.volume
                    # Try to get the player container
                    player_container: PlayerContainer = self.player_view.find_item(0)
                    if player_container:
                        # Update the view using the container itself
                        await player_container.update_volume_command(voice_client)
            except Exception as e:
                print(f'[BOT] --- Volume change error : {e}')
        # Tell the channel about the volume change
        skipped_embed = discord.Embed(
                            title=f'🔊 Volume changed to {volume}% by -{interaction.user.name}-.',
                            color=discord.Color.green()
                        )
        await interaction.response.send_message(embed=skipped_embed, delete_after=20)
        # Push the player to the bottom
        await self.ensure_player()

    # Clean up the bot's variables
    async def cleanup(self):
        print("[BOT] --- Cleaning up...")
        # Delete previous player if it exists
        async with self.ui_lock:
            if self.player:
                try:
                    await self.player.delete()
                except discord.NotFound:
                    # Message was already deleted (by user or by ensure_player)
                    pass
            # Stop listening to interactions from the view before getting rid of it (memory management)
            if self.player_view:
                self.player_view.stop()
        # Clear variables
        self.waitlist.clear()
        self.player = None
        self.player_view = None
        self.current_voice_channel_id = None
        self.current_guild_id = None
        self.current_text_channel_id = None
        if self.disconnect_timer:
            self.disconnect_timer.cancel()
            self.disconnect_timer = None

    # Function to ensure the player message is always at the bottom of the chat
    async def ensure_player(self):
        async with self.ui_lock:
            try:
                # Retrieve the original player message channel
                channel = self.bot.get_channel(self.current_text_channel_id)
                # Delete the old player message
                await self.player.delete()
                # Send it again
                self.player = await channel.send(view=self.player_view)
            except discord.NotFound:
                pass
            except Exception as e:
                raise e
    
    # Function to disconnect the bot after 1 min of inactivity (provided voice client since the cleanup has been done)
    async def disconnect_after_delay(self, voice_client: discord.VoiceProtocol):
        print("[BOT] --- Started inactivity timer.")
        # Wait 1 minute after the last song ends
        await asyncio.sleep(60)

        # Reset timer variable
        self.disconnect_timer = None

        # If the voice client is still up
        if voice_client and voice_client.is_connected():
            await voice_client.disconnect()
            print("[BOT] --- Disconnected for inactivity.")

    # Ensure the user can actually execute this command (i.e the user and the bot are in the same voice channel % other things)
    async def ensure_context(self, interaction: discord.Interaction):
        # Get the bot's voice client
        bot_voice = interaction.guild.voice_client
        # Get the user's voice
        user_voice = interaction.user.voice
        # If the user is not in a voice channel
        if not user_voice:
            no_user_embed = discord.Embed(
                    title='❌ You are not in a voice channel.',
                    color=discord.Color.red()
                )
            await interaction.response.send_message(embed=no_user_embed, ephemeral=True, delete_after=10)
            raise commands.CommandError("User not in a voice channel.")
        
        # If the bot is not in a voice channel or not playing
        if not bot_voice or (not bot_voice.is_playing() and not bot_voice.is_paused()):
            no_user_embed = discord.Embed(
                    title='❌ The bot is not playing.',
                    description='Maybe wait for the next song to start ?',
                    color=discord.Color.red()
                )
            await interaction.response.send_message(embed=no_user_embed, ephemeral=True, delete_after=10)
            raise commands.CommandError("Bot not in a voice channel.")

        # If the user is not in the bot's voice channel
        if user_voice.channel != bot_voice.channel:
            no_user_embed = discord.Embed(
                    title='❌ You are not in the bot\'s voice channel.',
                    color=discord.Color.red()
                )
            await interaction.response.send_message(embed=no_user_embed, ephemeral=True, delete_after=10)
            raise commands.CommandError("UUser and bot not in the same voice channel.")
        

    # Ensure the bot is still in the original voice channel to play the next song
    async def ensure_next(self):
        # Get the guild
        guild = self.bot.get_guild(self.current_guild_id)

        # If these ids are not stored, it means that the bot has been manually stopped, so cleanup has already been done
        if not self.current_voice_channel_id or not self.current_guild_id or not self.current_text_channel_id:
            return None

        # Get the bot's voice
        voice_client = guild.voice_client

        # Normal case, everything if fine
        if voice_client and voice_client.is_connected():
            return voice_client

        # At this point, the bot is not connected anymore and this is not normal
        print("[BOT] --- Bot disconnected but waiting list not empty, attempting to reconnect...")
        try:
            # Get the original voice channel
            channel = self.bot.get_channel(self.current_voice_channel_id)
            # Check if channel exists and there is at least one person inside
            if channel and len(channel.members) > 0:
                # Try to connect to it
                await channel.connect()
                print("[BOT] --- Successfully reconnected.")
                # Return the new voice_client
                return guild.voice_client
            else:
                print("[BOT] --- Channel does not exist or no one inside.")
        except Exception as e:
            print(f"[BOT] --- Failed to reconnect to channel : {e}")
        
        # If we're still there, cleanup and tell the user that the reconnect failed
        await self.cleanup()
        no_voice_embed = discord.Embed(
                    title=f'❌ Can\'t reconnect and keep playing in the original voice channel.',
                    description="If you wish to play again, join a voice channel and call /play.",
                    color=discord.Color.red()
                )
        await self.bot.get_channel(self.current_text_channel_id).send(embed=no_voice_embed, delete_after=30)
        return None

    # Function to play a song in the bot's voice channel, executed everytime a song ends if the waiting list has something in it
    async def play_next(self):
        # Ensure we can play the next song with a valid voice_client
        voice_client = await self.ensure_next()
        # If voice_client not valid, we cannot continue, cleanup has been done and user has been notified
        if not voice_client:
            return
        # Get the channel (should exist now thanks to ensure_next)
        channel = self.bot.get_channel(self.current_text_channel_id)
        # Delete previous player if it exists
        async with self.ui_lock:
            # Stop listening to the view's interactions
            if self.player_view:
                self.player_view.stop()
                self.player_view = None
                
            if self.player:
                try:
                    await self.player.delete()
                except discord.NotFound:
                    # Message was already deleted (by user or by ensure_player)
                    pass
                self.player = None
        # If something is in the waitinpg list
        if len(self.waitlist) > 0:
            # Retrieve the data from the next song in queue
            data = self.waitlist.popleft()

            # The player container that will display the player's components
            player_container = PlayerContainer(
                accent_colour=discord.Colour.gold(),
                id=0,
                cog=self,
                data=data
            )

            async with self.ui_lock:
                # The player view that will contain the player container
                self.player_view = PlayerLayout(self)
                # Add the container to the view
                self.player_view.add_item(player_container)
                # Send the message with the player view
                self.player = await channel.send(view=self.player_view)

            # Audio source
            source = discord.FFmpegPCMAudio(f'code/bot/cogs/temp_songs/{data["id"]}.{data["ext"]}')
            # Audio player (to manage volume)
            async with self.volume_lock:
                audio_player = discord.PCMVolumeTransformer(source, volume=self.current_volume)
            # Play, 'after' will run this functions everytime the current song ends
            voice_client.play(audio_player, after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(), self.bot.loop))
        # If there's nothing in the waiting list
        else:
            finished_embed = discord.Embed(
                title='🏁 Finished playing '+os.getenv('FINISHED_PLAYING'),
                description='Leaving the voice channel in 1 minute.',
                color=discord.Color.green()
            )
            await channel.send(embed=finished_embed, delete_after=20)
            # Start the disconnect timer if the bot is still in the voice channel
            if voice_client and voice_client.is_connected():
                # Clean up before the disconnect happens
                await self.cleanup()
                self.disconnect_timer = asyncio.create_task(self.disconnect_after_delay(voice_client))
        
    # Ensure the bot is/will connected/connect to the user voice channel, and store the useful ids
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
                    if (bot_voice.is_playing() or bot_voice.is_paused()) and bot_voice.channel != user_voice.channel:
                        # The bot is already playing music in another channel
                        error_embed = discord.Embed(
                            title='❌ The bot is already playing in a different channel.',
                            color=discord.Color.red()
                        )
                        error_exception = commands.CommandError('Bot is playing and author not in the same channel.')
                    # If it's not playing music and user not in the same channel (should not happen but I have to make sure)
                    elif not bot_voice.is_playing() and not bot_voice.is_paused() and bot_voice.channel != user_voice.channel:
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
            # If interaction is defered, use followup
            if interaction.response.is_done():
                sent_msg = await interaction.followup.send(embed=error_embed, ephemeral=True, wait=True)
                # Delete the followup message after 10 seconds
                await sent_msg.delete(delay=10.0)
            # If the interaction is not defered
            else:
                await interaction.response.send_message(embed=error_embed, ephemeral=True, delete_after=10)
            raise error_exception
        
        # If there was no error
        # Store the voice channel after ensuring connection
        if interaction.guild.voice_client:
            self.current_voice_channel_id = interaction.guild.voice_client.channel.id
        
        # Store the text channel
        self.current_text_channel_id = interaction.channel.id
        # Store the guild (to retrieve voice_client later)
        self.current_guild_id = interaction.guild.id
        
# This function is used to setup the cog
async def setup(bot):
    await bot.add_cog(MusicCog(bot))