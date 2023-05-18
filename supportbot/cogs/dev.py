import discord
from discord.ext import commands
from supportbot.core.utils import team


class Dev(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @team()
    @commands.command()
    async def load_cog(self, ctx, cog_name: str):
        try:
            self.bot.load_extension(f'supportbot.cogs.{cog_name}')
            await ctx.send(f'Cog {cog_name} has been loaded.')
        except commands.ExtensionError as e:
            await ctx.send(f'Failed to load cog {cog_name}: {e}')
            self.bot.logger.exception(f"Failed to load cog {cog_name}")
    
    @team()
    @commands.command()
    async def unload_cog(self, ctx, cog_name: str):
        try:
            self.bot.unload_extension(f'supportbot.cogs.{cog_name}')
            await ctx.send(f'Cog {cog_name} has been unloaded.')
        except commands.ExtensionError as e:
            await ctx.send(f'Failed to unload cog {cog_name}: {e}')
            self.bot.logger.exception(f"Failed to unload cog {cog_name}")
    
    @team()
    @commands.command()
    async def sync(self, ctx):
        await self.bot.tree.sync()
        await ctx.send("Synced.")

    

async def setup(bot):
    await bot.add_cog(Dev(bot))