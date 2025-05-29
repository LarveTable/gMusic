import discord
from discord.ext import commands
from discord import app_commands

class FunCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    #test
    @app_commands.command(name='leo', description='Insulte Léo.')
    async def leo(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title='Léo',
            description='est une pute',
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(FunCog(bot))