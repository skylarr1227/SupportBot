import discord
from discord.ext import commands
import re
import asyncpg
from datetime import datetime

class CurationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
                        task_id, author, date
                    )

# Replace the setup function if you already have one
async def setup(bot):
    await bot.add_cog(CurationCog(bot))