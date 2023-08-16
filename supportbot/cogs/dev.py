import discord
from discord.ext import commands
from supportbot.core.utils import team
import os
import aiohttp
from datetime import datetime

API_PASS = os.environ.get("API_PASS")
API_LINK = os.environ.get("API_LINK")
OS = discord.Object(id=774124295026376755)

class Dev(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @team()
    @commands.command()
    async def load_cog(self, ctx, cog_name: str):
        try:
            await self.bot.load_extension(f'supportbot.cogs.{cog_name}')
            await ctx.send(f'Cog {cog_name} has been loaded.')
        except commands.ExtensionError as e:
            await ctx.send(f'Failed to load cog {cog_name}: {e}')
            self.bot.logger.exception(f"Failed to load cog {cog_name}")
    
    @team()
    @commands.command()
    async def unload_cog(self, ctx, cog_name: str):
        try:
            await self.bot.unload_extension(f'supportbot.cogs.{cog_name}')
            await ctx.send(f'Cog {cog_name} has been unloaded.')
        except commands.ExtensionError as e:
            await ctx.send(f'Failed to unload cog {cog_name}: {e}')
            self.bot.logger.exception(f"Failed to unload cog {cog_name}")
    
    @team()
    @commands.command()
    async def sync(self, ctx):
        await self.bot.tree.sync()
        await ctx.send("Synced.")

    @team()
    @commands.command()
    async def check_user(self, ctx, user_id, after, before):
        # Parse the date strings into datetime objects
        after_date = datetime.strptime(after, '%Y-%m-%d')
        before_date = datetime.strptime(before, '%Y-%m-%d')

        # Format the datetime objects into ISO 8601 format
        after_iso = after_date.isoformat() + 'Z'
        before_iso = before_date.isoformat() + 'Z'

        password = API_PASS
        params = {
            'user_id': user_id,
            'after_date': after_iso,
            'before_date': before_iso,
            'password': password,
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(API_LINK, params=params) as resp:
                await ctx.send(await resp.text())

    @team()
    @commands.command(name="db")
    async def unsafeedb(self, ctx, *, query: str):
        """DEV: No timeout EDB"""
        # Sanity checks
        low_exe = query.lower()
        if low_exe != self.safe_edb:
            self.safe_edb = low_exe
            if "update" in low_exe and "where" not in low_exe:
                await ctx.send(
                    "**WARNING**: You attempted to run an `UPDATE` without a `WHERE` clause. If you are **absolutely sure** this action is safe, run this command again."
                )
                return
            if "drop" in low_exe:
                await ctx.send(
                    "**WARNING**: You attempted to run a `DROP`. If you are **absolutely sure** this action is safe, run this command again."
                )
                return
            if "delete from" in low_exe:
                await ctx.send(
                    "**WARNING**: You attempted to run a `DELETE FROM`. If you are **absolutely sure** this action is safe, run this command again."
                )
                return
        try:
            result = self.supabase.raw(query)
        except Exception as e:
            await ctx.send(f"```py\n{e}```")
            raise
        result = str(result)
        if len(result) > 1950:
            result = result[:1950] + "\n\n..."
        await ctx.send(f"```py\n{result}```")


async def setup(bot):
    await bot.add_cog(Dev(bot))