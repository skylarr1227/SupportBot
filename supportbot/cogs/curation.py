import discord
from discord.ext import commands
import re
import asyncpg
from datetime import datetime
from supportbot.core.utils import team
import asyncio

class CurationCog(commands.Cog):
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


    @commands.Cog.listener()
    async def on_message(self, message):
        if message.channel.id == 1158544647346458634:  # Replace with the actual channel ID
            url_pattern = r"https:\/\/dream\.ai\/listing\/([a-zA-Z0-9\-]+)"
            match = re.search(url_pattern, message.content)
            
            if match:
                task_id = match.group(1)
                author = str(message.author)
                date = datetime.utcnow()
                
                
                async with self.bot.pool.acquire() as connection:
                    await connection.execute(
                        'INSERT INTO curation (TASK_ID, AUTHOR, DATE) VALUES ($1, $2, $3)',
                        str(task_id), str(author), date
                    )
    
    
    @team()
    @commands.command()
    async def curation(self, ctx, page: int = 1):
        """Fetches a list of tasks from the 'curation' table and displays them in a paginated format."""
        async with self.bot.pool.acquire() as connection:
            rows = await connection.fetch('SELECT task_id, author, date FROM curation ORDER BY date ASC')

        pages = []
        for i in range(0, len(rows), 20):
            description = ""
            for row in rows[i:i+30]:
                task_id = row['task_id']
                author = row['author']
                date = row['date'].strftime('%Y-%m-%d %H:%M:%S')  
                link = f"[{task_id}](https://dream.ai/listing/{task_id})"
                description += f"Task ID: {link} - Author: {author} - Date: {date}\n"

            embed = discord.Embed(title="Tasks List from Curation", description=description, color=discord.Color.blue())
            pages.append(embed)

        # Check if the page number is valid
        if 1 <= page <= len(pages):
            await self.paginate(ctx, pages, page - 1)  # -1 because list index starts from 0
        else:
            await ctx.send("Invalid page number.")


# Replace the setup function if you already have one
async def setup(bot):
    await bot.add_cog(CurationCog(bot))