import discord
from discord.ext import commands
import os
import asyncio
import re

class ThreadExporter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def sanitize_name(self, name):
        """Sanitize the name to be used as a file or directory name."""
        return re.sub(r'[\\/*?:"<>|]', '-', name)

    async def create_directory(self, name):
        """Create a directory with the given name."""
        sanitized_name = self.sanitize_name(name)
        if not os.path.exists(sanitized_name):
            os.makedirs(sanitized_name)

    async def save_thread_to_markdown(self, thread, directory):
        """Save the messages in a thread to a markdown file."""
        sanitized_thread_name = self.sanitize_name(thread.name)
        sanitized_directory_name = self.sanitize_name(directory)
        
        # Create the markdown file
        file_name = f"{sanitized_directory_name}/{sanitized_thread_name}.md"
        with open(file_name, "w") as f:
            f.write(f"# {thread.name}\n\n")

        # Fetch and write the messages
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
        threads = channel.threads
        for thread in threads:
            if isinstance(thread, discord.Thread):
                await self.save_thread_to_markdown(thread, directory_name)


        await ctx.send(f"Exported threads in {channel.mention} to markdown files.")



async def setup(bot):
    await bot.add_cog(ThreadExporter(bot))