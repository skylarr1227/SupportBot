import discord
from discord.ext import commands, menus
from supportbot.core.utils import team
import os
import aiohttp
from datetime import datetime
import asyncio
from io import StringIO
import sys
import traceback

from discord import Embed


GREEN = "\N{LARGE GREEN CIRCLE}"
API_PASS = os.environ.get("API_PASS")
API_LINK = os.environ.get("API_LINK")
OS = discord.Object(id=774124295026376755)
BASE_URL = "https://dream.ai/listing/"

class TaskMenu(menus.ListPageSource):
    def __init__(self, data):
        super().__init__(data, per_page=30)  

    async def format_page(self, menu, entries):
        offset = menu.current_page * self.per_page
        embed = Embed(title="Task Listings", colour=0x3498db)
        for index, entry in enumerate(entries, start=offset):
            url = BASE_URL + str(entry['task_id'])
            if entry['name']:
                embed.add_field(name=f"Task {index + 1}: {entry['name']}", value=url, inline=False)
            else:
                embed.add_field(name=f"Task {index + 1}", value=url, inline=False)
        return embed



    
class Dev(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def paginate(self, ctx, pages, start_page=0):
        """Utility function to paginate embeds"""
        current_page = start_page
        msg = await ctx.send(embed=pages[current_page])

        # Add reactions
        await msg.add_reaction("◀️")
        await msg.add_reaction("▶️")

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["◀️", "▶️"]

        while True:
            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=60, check=check)

                if str(reaction.emoji) == "▶️" and current_page < len(pages) - 1:
                    current_page += 1
                elif str(reaction.emoji) == "◀️" and current_page > 0:
                    current_page -= 1

                await msg.edit(embed=pages[current_page])
                await msg.remove_reaction(reaction, user)

            except asyncio.TimeoutError:
                await msg.clear_reactions()
                break




    @team()
    @commands.command()
    async def links(self, ctx, page: int = 0):
        """Fetches a list of tasks and displays them in a paginated format."""
        async with self.bot.pool.acquire() as connection:
            rows = await connection.fetch('SELECT task_id, name FROM art WHERE name IS NOT NULL order by created_at ASC')

        pages = []
        for i in range(0, len(rows), 30):  # Assuming you want 10 items per page
            description = ""
            for row in rows[i:i+30]:
                task_id = row['task_id']
                name = row['name']
                description += f"https://dream.ai/listing/{task_id} - {name}\n"

            embed = discord.Embed(title="Tasks List", description=description, color=discord.Color.blue())
            pages.append(embed)

        # Check if the page number is valid
        if 0 <= page < len(pages):
            await self.paginate(ctx, pages, page - 1)  # -1 because list index starts from 0
        else:
            await ctx.send("Invalid page number.")



    



    @team()
    @commands.command()
    async def reload_all_cogs(self, ctx):
        for cog_name, _ in self.bot.cogs.items():
            try:
                self.bot.reload_extension(f'cogs.{cog_name}')
                await ctx.send(f'Cog {cog_name} has been reloaded.')
            except Exception as e:
                await ctx.send(f'Error reloading cog {cog_name}: {e}')           

    

    @team()
    @commands.command(name='eval')
    @commands.is_owner() 
    async def _eval(self, ctx, *, code):
        """
        Executes a given code (Python).
        """
        old_stdout = sys.stdout
        sys.stdout = output = StringIO()
        try:
            exec(code)
        except Exception as e:
            value = output.getvalue()
            traceback_message = traceback.format_exc()
            result = f"{value}\n{traceback_message}\n{str(e)}"
        else:
            value = output.getvalue()
            result = value
        sys.stdout = old_stdout
        pages = [discord.Embed(title=f"Eval Result (Page {i+1}/{len(result)//1000 + 1})", description=f"```python\n{page}\n```", color=0x42f5f5) for i, page in enumerate([result[i:i+1000] for i in range(0, len(result), 1000)])]
        await self.paginate(ctx, pages)

    @team()
    @commands.command()
    async def cogs(self, ctx):
        """View the currently loaded cogs."""
        cogs = sorted([x.replace("supportbot.", f"{GREEN} - ") for x in ctx.bot.extensions.keys()])
        embed = discord.Embed(
            title=f"{len(cogs)} loaded:",
            description=f"\n".join(cogs),
            color=0xFF0060,
        )
        await ctx.send(embed=embed)


    @team()
    @commands.command()
    async def load(self, ctx, cog_name: str):
        try:
            await self.bot.load_extension(f'supportbot.cogs.{cog_name}')
            await ctx.send(f'Cog {cog_name} has been loaded.')
        except commands.ExtensionError as e:
            await ctx.send(f'Failed to load cog {cog_name}: {e}')
            self.bot.logger.exception(f"Failed to load cog {cog_name}")
    
    @team()
    @commands.command()
    async def unload(self, ctx, cog_name: str):
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