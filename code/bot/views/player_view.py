import discord
from discord.ext import commands
from discord import ui
from typing import TYPE_CHECKING
import asyncio

if TYPE_CHECKING:
    from cogs.music_remaster import MusicCog

# The view used to display the player (LayoutView to use discord's v2 components)
class PlayerLayout(ui.LayoutView):    
    def __init__(self, cog):
        super().__init__(timeout=None)
        # Get the music cog to access its variables and methods
        self.music_cog = cog

    # Callback called before every button callback in this view
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        try:
            # Use the cog's nice function to ensure the user can perform the action
            await self.music_cog.ensure_context(interaction)
            return True
        # If the user is not allowed to, return false
        except commands.CommandError:
            return False
        # If there's another error
        except Exception as e:
            print(f"Erreur dans interaction_check: {e}")
            return False
        
# The container used in the PlayerView, displays every element of the player, using v2 components
class PlayerContainer(ui.Container):
        # ID of the PlayerContainer will always be 0 to find it easily
        def __init__(self, cog: "MusicCog", data: dict, id = None, accent_colour = None):
            super().__init__(accent_colour=accent_colour, id=id)
            # State of the play/pause button
            self.paused = False
            # State of the mute button
            self.muted = False
            # State of the loop button
            self.loop = False
            # Get the music cog to access its variables and methods
            self.music_cog = cog
            # The current song data
            self.data = data

            # Initialize the fields with the data values, after container creation
            self.title_section.accessory = ui.Button(url=self.data["webpage_url"], label="Link")
            self.data_section.accessory = ui.Thumbnail(media=data['thumbnail'])
            self.data_section.clear_items()
            self.data_section.add_item(ui.TextDisplay(content=f"# **{data["title"]}**\n*{data['uploader']}*\n\n⏱️*{data['duration'] // 60}:{data['duration'] % 60:02d}*"))
            # Get the music cog current volume to display it
            volume_display = self.volume_action_row.find_item(1)
            if volume_display:
                volume_display.label = f"Volume : {int(self.music_cog.current_volume*100)}"

        # Header of the player + link of the song
        title_section = ui.Section(accessory=ui.Button(label="Loading")) # Fake accessory, will be initialized in the init
        title_section.add_item(ui.TextDisplay(content="## 🎶 Now playing"))

        # Simple separator for style
        title_separator = ui.Separator()

        # Section for the thumbnail + title, artist and song duration
        data_section = ui.Section(accessory=ui.Button(label="Loading"))
        data_section.add_item(ui.TextDisplay(content="Loading"))

        # Another simple separator
        data_separator = ui.Separator()

        # Context is ensured by the layout's interaction_check function, the user can perform every action bellow without further check

        # First row containing player related control
        play_action_row = ui.ActionRow()
        # Previous button
        @play_action_row.button(emoji="⏮️", disabled=True)
        async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message('Previous', ephemeral=True)
        # Play/pause button
        @play_action_row.button(emoji="⏸️")
        async def pause_play_button(self, interaction: discord.Interaction, button: discord.ui.Button):
             # Get bot's voice_client
            voice_client = interaction.guild.voice_client
            # If the bot is connected and playing
            if voice_client and voice_client.is_playing():
                try:
                    # Try to pause
                    voice_client.pause()
                except Exception as e:
                    print(f'[BOT] --- Voice client pause error : {e}')
            # If the voice client is connected
            elif voice_client and voice_client.is_paused():
                try:
                    # Try to resume
                    voice_client.resume()
                except Exception as e:
                    print(f'[BOT] --- Voice client resume error : {e}')
            # Invert the paused state and change the emoji
            self.paused = not self.paused
            button.emoji = "▶️" if self.paused else "⏸️"
            await interaction.response.edit_message(view=self.view)
        # Skip button
        @play_action_row.button(emoji="⏭️")
        async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            # Get bot's voice_client
            voice_client = interaction.guild.voice_client
            # Try to stop the voice, so the next song will play by triggering the after lambda
            if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
                try:
                    voice_client.stop()
                except Exception as e:
                    print(f'[BOT] --- Voice client stop error : {e}')
            # Tell the channel about the skip
            if len(self.music_cog.waitlist) == 0:
                skipped_embed = discord.Embed(
                                    title=f'⏩ Music skipped by -{interaction.user.name}-.',
                                    description='No more songs in the waiting list.',
                                    color=discord.Color.green()
                                )
                await interaction.response.send_message(embed=skipped_embed)
                return
            skipped_embed = discord.Embed(
                                    title=f'⏩ Music skipped by -{interaction.user.name}-.',
                                    description=f'Will now play **{self.music_cog.waitlist[0]["title"]}**.',
                                    color=discord.Color.green()
                                )
            await interaction.response.send_message(embed=skipped_embed)
        # Stop button
        @play_action_row.button(emoji="⏹️", style=discord.ButtonStyle.danger)
        async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            # Get bot's voice_client
            voice_client = interaction.guild.voice_client
            # Call the cleanup function that will ensure variables cleanup
            await self.music_cog.cleanup()
            # Try to stop the voice client
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
            self.music_cog.disconnect_timer = asyncio.create_task(self.music_cog.disconnect_after_delay(voice_client))

        # Simple invisible separator
        play_separator = ui.Separator(visible=False)

        # Second row containing volume controls
        volume_action_row = ui.ActionRow()
        # Mute button
        @volume_action_row.button(emoji="🔇", id=2) # Id 2 to change its style in the cog's volume command
        async def mute_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            # Get the voice_client
            voice_client = interaction.guild.voice_client
            if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
                # Set the voice_client volume, using the music cog lock
                async with self.music_cog.volume_lock:
                    # Change the muted state
                    self.muted = not self.muted
                    # Change the button style for feedback
                    button.style = discord.ButtonStyle.danger if self.muted else discord.ButtonStyle.secondary
                    # Either 0 or the current volume depending on button state
                    voice_client.source.volume = 0.0 if self.muted else self.music_cog.current_volume
                    # Update the volume display of the view, different from the command update
                    volume_display = self.volume_action_row.find_item(1)
                    if volume_display:
                        volume_display.label = f"Volume : {int(self.music_cog.current_volume*100) if not self.muted else "0"}"
                # Update the view
                await interaction.response.edit_message(view=self.view)
        # Lower volume button
        @volume_action_row.button(emoji="🔈")
        async def lower_volume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            # Get the voice_client
            voice_client = interaction.guild.voice_client
            if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
                # Set the voice_client volume, using the music cog lock
                async with self.music_cog.volume_lock:
                    # Lower the volume, -10%
                    voice_client.source.volume = max(0.0, ((self.music_cog.current_volume*100) - 10)/100)
                    # Store the current volume in the music cog
                    self.music_cog.current_volume = voice_client.source.volume
                    # Update the view
                    await self.update_volume_command(voice_client)
            await interaction.response.edit_message(view=self.view)
        # Fake button to display the current volume level
        @volume_action_row.button(label="Volume : 100", disabled=True, id=1) # Id 1 to reference it and change its label (0 is this container)
        async def volume_display(self, interaction: discord.Interaction, button: discord.ui.Button):
            pass
        # Up volume button
        @volume_action_row.button(emoji="🔉")
        async def up_volume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            # Get the voice_client
            voice_client = interaction.guild.voice_client
            if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
                # Set the voice_client volume, using the music cog lock
                async with self.music_cog.volume_lock:
                    # Up the volume, +10%
                    voice_client.source.volume = min(1.0, ((self.music_cog.current_volume*100) + 10)/100)
                    # Store the current volume in the music cog
                    self.music_cog.current_volume = voice_client.source.volume
                    # Update the view
                    await self.update_volume_command(voice_client)
            await interaction.response.edit_message(view=self.view)

        # Invisible separator
        volume_separator = ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large)

        # Last row containing misc buttons
        misc_action_row = ui.ActionRow()
        # Loop song button
        @misc_action_row.button(emoji="🔁", label="Off", disabled=True)
        async def loop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.loop = not self.loop
            button.label = "On" if self.loop else "Off"
            button.style = discord.ButtonStyle.success if self.loop else discord.ButtonStyle.secondary
            await interaction.response.edit_message(view=self.view)
        # Show waiting list button
        @misc_action_row.button(emoji="🗄️", style=discord.ButtonStyle.primary, disabled=True)
        async def waitlist_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message('Waitlist', ephemeral=True)
        # Favorite button
        @misc_action_row.button(emoji="⭐", style=discord.ButtonStyle.primary, disabled=True)
        async def favorite_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message('Favorite', ephemeral=True)

        # Command to update the view when the user calls "/play volume", or lower and up volume
        async def update_volume_command(self, voice_client):
            # Update the volume display in the view
            volume_display = self.volume_action_row.find_item(1)
            if volume_display:
                volume_display.label = f"Volume : {int(self.music_cog.current_volume*100)}"
            # Update the mute button style if needed
            mute_button = self.volume_action_row.find_item(2)
            # If the button is in the 'muted' state and the volume is set to a value different from 0
            if mute_button and mute_button.style == discord.ButtonStyle.danger and voice_client.source.volume != 0:
                mute_button.style = discord.ButtonStyle.secondary
                # Update the muted variable in the container
                self.muted = False

"""class MusicPlayerView(View):
    def __init__(self, cog: MusicCog, interaction: discord.Interaction):
        super().__init__(timeout=None) # Timeout=None signifie que les boutons restent actifs indéfiniment (attention à la mémoire, voir note plus bas)
        self.cog = cog
        self.interaction = interaction # L'interaction d'origine ou le channel
        self.voice_client = interaction.guild.voice_client

    # --- BOUTON PLAY / PAUSE ---
    @discord.ui.button(label="Pause", style=discord.ButtonStyle.primary, emoji="⏯️", row=0)
    async def play_pause(self, interaction: discord.Interaction, button: Button):
        if self.voice_client.is_paused():
            self.voice_client.resume()
            button.label = "Pause"
            button.style = discord.ButtonStyle.primary
            await interaction.response.edit_message(view=self) # On met à jour le bouton
        elif self.voice_client.is_playing():
            self.voice_client.pause()
            button.label = "Resume"
            button.style = discord.ButtonStyle.green
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message("Rien n'est en cours de lecture.", ephemeral=True)

    # --- BOUTON SKIP ---
    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary, emoji="⏭️", row=0)
    async def skip(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer() # On accuse réception pour éviter l'erreur "Interaction Failed"
        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            # stop() déclenche le 'after' callback qui lancera la prochaine chanson
            self.voice_client.stop()
            # On peut désactiver la vue car le message va être supprimé par play_next
            self.stop() 

    # --- BOUTON STOP ---
    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️", row=0)
    async def stop_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        # On appelle ta méthode cleanup existante
        await self.cog.cleanup(interaction.guild.voice_client)
        # On supprime la vue pour qu'on ne puisse plus cliquer
        self.stop()
        
    # --- BOUTONS VOLUME (Bonus) ---
    @discord.ui.button(label="-10%", style=discord.ButtonStyle.secondary, emoji="🔉", row=1)
    async def volume_down(self, interaction: discord.Interaction, button: Button):
        if self.voice_client.source:
            # On baisse de 10%
            new_vol = max(0.0, self.voice_client.source.volume - 0.1)
            self.voice_client.source.volume = new_vol
            await interaction.response.send_message(f"Volume: {int(new_vol*100)}%", ephemeral=True)
        else:
            await interaction.response.send_message("Audio source not valid.", ephemeral=True)

    @discord.ui.button(label="+10%", style=discord.ButtonStyle.secondary, emoji="🔊", row=1)
    async def volume_up(self, interaction: discord.Interaction, button: Button):
        if self.voice_client.source:
            # On monte de 10% (max 200% pour éviter la saturation extrême)
            new_vol = min(2.0, self.voice_client.source.volume + 0.1)
            self.voice_client.source.volume = new_vol
            await interaction.response.send_message(f"Volume: {int(new_vol*100)}%", ephemeral=True)
        else:
            await interaction.response.send_message("Audio source not valid.", ephemeral=True)

    # --- SÉCURITÉ : VÉRIFIER QUI CLIQUE ---
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        try:
            # On appelle ta fonction existante via le cog
            # Si tout va bien, elle ne fait rien et le code continue
            await self.cog.ensure_context(interaction)
            return True
            
        except commands.CommandError:
            # Si ensure_context échoue, elle a DÉJÀ envoyé un message d'erreur à l'utilisateur
            # et elle a levé une erreur.
            # On attrape l'erreur ici pour ne pas faire crasher le bot, 
            # et on retourne False pour bloquer le clic sur le bouton.
            return False
            
        except Exception as e:
            # Sécurité pour d'autres erreurs imprévues
            print(f"Erreur dans interaction_check: {e}")
            return False
            """