import discord
from discord.ext import commands
from zenpy import Zenpy
import pandas as pd
from io import StringIO
import os

zentoken = os.environ.get("ZENTOKEN")
zenmail = os.environ.get("ZENMAIL")


class ZendeskCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.zenpy_client = Zenpy(**{
            'email' : zenmail,
            'token' : zentoken,
            'subdomain' : 'wombo'
        })

    @commands.command()
    async def get_tickets(self, ctx, search_query):
        tickets = self.zenpy_client.search(search_query)
        df = pd.DataFrame(tickets)
        csv_buffer = StringIO()
        df.to_csv(csv_buffer)
        csv_buffer.seek(0)
        await ctx.send(file=discord.File(fp=csv_buffer, filename='tickets.csv'))

def setup(bot):
    bot.add_cog(ZendeskCog(bot))
