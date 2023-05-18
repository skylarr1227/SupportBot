import discord
from discord.ext import commands
from discord import app_commands
from supportbot.core.utils import team, support, store_in_supabase, store_prompt
import typing
from typing import Optional, Literal

GREEN = "\N{LARGE GREEN CIRCLE}"
RED = "\N{LARGE RED CIRCLE}"

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    

    @support()
    @app_commands.command()
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def record(self, interaction, prompt: str, nsfw_triggered: bool, image_urls: str):
        # Insert the record into the Supabase table
        image_urls = image_urls.split(" ")
        labeled_images = {str(index + 1): url for index, url in enumerate(image_urls)}
        response = await store_prompt(self.bot, prompt, labeled_images, nsfw_triggered)      
        await interaction.response.send_message("Recorded successfully.")       

    @support()
    @app_commands.command()
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def set_status(self, interaction: discord.Interaction, status: typing.Literal["resolved", "on-going", "waiting", "hold", "closed"]):
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message("This command can only be used in a thread.", ephemeral=True)
            return
        status = status.upper()
        if ']' in interaction.channel.name:
            old_status = interaction.channel.name.split(']')[0][1:]
            new_name = f'[{status}] {interaction.channel.name.split("]")[1].strip()}'
        else:
            old_status = "UNKNOWN"
            new_name = f'[{status}] {interaction.channel.name}'
        await interaction.channel.edit(name=new_name)
        # Find the original author and message of the thread
        original_author = None
        original_message = None
        async for message in interaction.channel.history(oldest_first=True, limit=1):
            original_author = message.author
            original_message = message.content
        response_status = await store_in_supabase(self.bot, old_status, status, interaction.channel, interaction.user.id, original_author.id, original_message)
        await interaction.response.send_message(f"Thread name updated to: {new_name}")

    @support()
    @app_commands.command()
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def lock(self, interaction):
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message("This command can only be used in a thread.", ephemeral=True)
            return
        await interaction.channel.edit(locked=True)
        await interaction.response.send_message("Thread locked.")

    @support()
    @app_commands.command(name='unlock')
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def unlock(self, interaction):
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message("This command can only be used in a thread.", ephemeral=True)
            return
        await interaction.channel.edit(locked=False)
        await interaction.response.send_message("Thread unlocked.")
   
    #@support()
    #@app_commands.command(name='add_notion')
    #@app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    #async def summarize(self, interaction):
    #    # Check if it's a thread
    #    if interaction.channel.thread is None:
    #        await interaction.response.send_message("This command can only be used in a thread.")
    #        return
#
#    #    thread = interaction.channel.thread
#    #    messages = await thread.history(limit=1).flatten()
    #    first_message = messages[0] if messages else ""
#
#    #    # Create a new page in Notion
#    #    new_page = await self.bot.notion.pages.create(
    #        parent={"database_id": "b48e1f0a4f2e4a758992ba1931a35669"},
    #        properties={
    #            "Name": {
    #                "title": [
    #                    {
    #                        "text": {
    #                            "content": thread.name,
    #                        },
    #                    },
    #                ],
    #            },
    #            "Problem": {
    #                "rich_text": [
    #                    {
    #                        "text": {
    #                            "content": first_message.content,
    #                        },
    #                    },
    #                ],
    #            },
    #            "Resolution": {
    #                "rich_text": [
    #                    {
    #                        "text": {
    #                            "content": "",
    #                        },
    #                    },
    #                ],
    #            },
    #        },
    #    )
#
    #    await interaction.response.send_message(f"Done.")


    @support()  
    @app_commands.command(name='close')
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def close(self, interaction, thread: discord.Thread = None, close_notes: str = "None Given", status: Literal["resolved", "closed", "known"]):
        # Check if it's a thread
        thread = interaction.channel 
        if not isinstance(thread, discord.Thread):
            await interaction.response.send_message("This command can only be used in a thread.", ephemeral=True)
            return
        # Update the thread's name to indicate its status
        await thread.edit(name=f"[{status.upper()}] {thread.name}")
        # Store close notes in Supabase
        response = await store_in_supabase(self.bot, thread.id, close_notes)
        if response:  
            await interaction.response.send_message(f"Close notes saved successfully in Supabase.")
        else:
            await interaction.response.send_message(f"Failed to save close notes in Supabase.")

        await interaction.response.send_message(f"Thread '{thread.name}' has been locked, closed, and the following close notes have been added: '{close_notes}'. Status set to '{status}'.")
        # Lock and close (archive) the thread
        await thread.edit(locked=True, archived=True)


    @support()
    @app_commands.command(name='combine')
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def combine(self, interaction, thread: discord.Thread, master_thread: discord.Thread, num_messages: int):
        # Validate the number of messages
        if num_messages < 1 or num_messages > 100:
            await interaction.response.send_message("Please enter a valid number of messages (1-100).", ephemeral=True)
            return
        # Retrieve messages from the source thread
        messages = [m async for m in thread.history(limit=num_messages)]
        # Combine messages and prepare a summary
        combined_message = f"Combined messages from thread {thread.name} ({thread.id}):\n\n"
        for message in messages:
            combined_message += f"**__{message.author}__**: {message.content}\n"
        # Check if the combined message is too long for a single message
        if len(combined_message) > 2000:
            await interaction.response.send_message("The combined message is too long. Please consider fetching fewer messages.", ephemeral=True)
            return
        # Send the combined message to the master thread
        await master_thread.send(combined_message)
        
        # Leave a message in the original thread with the link to the master thread
        await thread.send(
            f"Your support request has been combined into a combined known-issue post: {master_thread.jump_url}\n"
            "This support post is now locked and closed. Please follow this new post for future updates/resolution."
        )
        await interaction.response.send_message("The messages have been combined into the 'Known Issue' post, and the original post has been locked and closed.")
        # Lock and close (archive) the original thread, and update its status
        await thread.edit(locked=True, archived=True, name=f"[ON-GOING] {thread.name}")


async def setup(bot):
    await bot.add_cog(Tickets(bot))