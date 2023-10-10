import discord
from discord.ext import commands
import os
import asyncio

class ThreadExporter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def create_directory(self, name):
        """Create a directory with the given name."""
        if not os.path.exists(name):
            os.makedirs(name)

    async def save_thread_to_markdown(self, thread, directory):
        """Save the messages in a thread to a markdown file."""
        # Create the markdown file
        file_name = f"{directory}/{thread.name}.md"
        with open(file_name, "w") as f:
            f.write(f"# {thread.name}\n\n")

        async for message in thread.history(oldest_first=True):
            content = message.content.replace('\n', '  \n')
            with open(file_name, "a") as f:
                f.write(f"{message.author.display_name}: {content}  \n")

    @commands.command()
    @commands.is_owner() 
    async def export_threads(self, ctx, channel_id: int):
        """Export threads in a forum channel to markdown files."""
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            await ctx.send("Please specify a valid text channel ID within a category.")
            return
        directory_name = f"{channel.category.name}_{channel.name}"
        await self.create_directory(directory_name)
        threads = await channel.threads()
        for thread in threads:
            if isinstance(thread, discord.Thread):
                await self.save_thread_to_markdown(thread, directory_name)


        await ctx.send(f"Exported threads in {channel.mention} to markdown files.")



async def setup(bot):
    await bot.add_cog(ThreadExporter(bot))