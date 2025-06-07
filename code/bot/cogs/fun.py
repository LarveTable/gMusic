import discord
from discord.ext import commands
from discord import app_commands
from cogs.secret_jokes import jokes
import random

class FunCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    #test
    @app_commands.command(name='leo', description='Insulte Léo.')
    async def leo(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title='Léo',
            description='est un caca',
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
    
    # The command issuer gets a random 'secret' joke with his name in it
    @app_commands.command(name='secret', description='A random \'secret\' joke.')
    async def secret(self, interaction: discord.Interaction, user: discord.User = None):
        """
        Responds with a random 'secret' joke, optionally directed at a specified user.
        Parameters:
        - interaction: The interaction object from Discord.
        - user: The user to direct the joke at. If not specified, the joke is directed at the command issuer.
        Returns:
        - None
        """

        # If no user is specified, use the command issuer
        if user is None:
            user = interaction.user
        
        # Get a random joke from the jokes list
        joke = random.choice(jokes)
        
        # Format the joke with the user's name
        formatted_joke = user.name + ', ' + joke.format(user=user.name)
        
        # Send the embed as a response to the interaction
        await interaction.response.send_message(formatted_joke, tts=True)

async def setup(bot):
    await bot.add_cog(FunCog(bot))