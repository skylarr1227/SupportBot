from discord.ext import commands
from prometheus_client import save_to_file, load_from_file
import discord


class Prometheus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def save_metrics(self, ctx):
        """
        Save current Prometheus metrics to a file.
        """
        try:
            # Save metrics to a file
            save_to_file('/home/ubuntu/s/file.prom')  # Replace with your desired path
            await ctx.send("Successfully saved metrics to file.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @commands.command()
    async def load_metrics(self, ctx):
        """
        Load Prometheus metrics from a file.
        """
        try:
            # Load metrics from a file
            load_from_file('/home/ubuntu/s/file.prom')  # Replace with your desired path
            await ctx.send("Successfully loaded metrics from file.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")


async def setup(bot):
    await bot.add_cog(Prometheus(bot))