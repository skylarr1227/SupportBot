from discord.ext import commands

import discord
import json

class Prometheus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

   


async def setup(bot):
    await bot.add_cog(Prometheus(bot))