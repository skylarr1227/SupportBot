import discord
from discord.ext import commands
from discord import app_commands
from supportbot.core.utils import team, support, store_in_supabase, store_prompt
import typing
import re
import asyncio
from collections import defaultdict
from typing import Optional, Literal
from supportbot.cogs.strings import linking_title, linking_description
import datetime
import requests


KNOWN_ISSUES = [1102722546232729620]

GREEN = "\N{LARGE GREEN CIRCLE}"
RED = "\N{LARGE RED CIRCLE}"

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        

    async def get_commit(self, ctx):
        COMMAND = f"cd /home/ubuntu/s/SupportBot/supportbot && git branch -vv"

        proc = await asyncio.create_subprocess_shell(
            COMMAND, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await proc.communicate()
        stdout = stdout.decode().split("\n")

        for branch in stdout:
            if branch.startswith("*"):
                return branch

        raise ValueError()
    
    async def get_data_from_supabase(self, id):
        # Use your API key here
        response = self.bot.supabase.from_("nsfw_tracking").select("*").eq("id", id).execute()
        if response.data:
            return response.data[0]
        else:
            return None


    @support()
    @app_commands.command()
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def info(self, interaction, id: int):
        """Information about a failed NSFW prompt/check by id"""
        data = await self.get_data_from_supabase(id)
        if data is None:
            await interaction.response.send_message("ID not found.")
            return
        embed = discord.Embed(title=f"Information for ID: {data['id']}", color=0x00ff00)

        # Parse the created_at timestamp to discord timestamp format
        created_at = datetime.datetime.strptime(data['created_at'], "%Y-%m-%dT%H:%M:%S.%f%z")

        embed.add_field(name="Created at", value=f"<t:{int(created_at.timestamp())}>", inline=False)

        # Display images or clickable links
        
        if 'images' in data and isinstance(data['images'], dict):
            for i in range(1, 5):
                key = str(i)
                if key in data['images']:
                    embed.add_field(name=f"Image {i}", value=f"[Link]({data['images'][key]})", inline=False)
        # Display the prompt
        embed.add_field(name="Prompt", value=data['prompt'])

        # Display the style
        embed.add_field(name="Style", value=data['style'])
        embed.add_field(name="NSFW Triggered", value=data['nsfw_triggered'], inline=False)
        # Map platform numbers to strings
        platform_map = {0: "Web", 1: "Mobile", 2: "Wombot", 3: "All"}
        embed.add_field(name="Platform", value=platform_map.get(data['platform'], "Unknown"))

        await interaction.response.send_message(embed=embed)

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
   
    @team()
    @commands.command(name='pull', aliases=['gitpull', 'git_pull', 'git-pull'])
    async def refresh(self, ctx):
        COMMAND = "cd /home/ubuntu/s/SupportBot && git pull"
        addendum = ""

        proc = await asyncio.create_subprocess_shell(
            COMMAND, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await proc.communicate()
        stdout = stdout.decode()

        if "no tracking information" in stderr.decode():
            COMMAND = "cd /home/ubuntu/s/SupportBot && git pull"
            proc = await asyncio.create_subprocess_shell(
                COMMAND, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            stdout = stdout.decode()
            addendum = "\n\n**Warning: no upstream branch is set.  I automatically pulled from origin/clustered but this may be wrong.  To remove this message and make it dynamic, please run `git branch --set-upstream-to=origin/<branch> <branch>`**"

        embed = discord.Embed(title="Git pull", description="", color=0xFFB6C1)

        if "Fast-forward" not in stdout:
            if "Already up to date." in stdout:
                embed.description = "Code is up to date."
            else:
                embed.description = "Pull failed: Fast-forward strategy failed.  Look at logs for more details."
                ctx.bot.logger.warning(stdout)
            embed.description += addendum
            await ctx.send(embed=embed)
            return

        cogs = []
        main_files = []

        try:
            current = await self.get_commit(ctx)
        except ValueError:
            pass
        else:
            embed.description += f"`{current[2:]}`\n"

        cogs = re.findall(r"\ssupportbot\/cogs\/(\w+)", stdout)
        if len(cogs) > 1:
            embed.description += f"The following cogs were updated and needs to be reloaded: `{'`, `'.join(cogs)}`.\n"
        elif len(cogs) == 1:
            embed.description += f"The following cog was updated and needs to be reloaded: `{cogs[0]}`.\n"
        else:
            embed.description += "No cogs were updated.\n"

        main_files = re.findall(r"\ssupportbot\/(?!cogs)(\S*)", stdout)
        if len(main_files) > 1:
            embed.description += f"The following non-cog files were updated and require a restart: `{'`, `'.join(main_files)}`."
        elif main_files:
            embed.description += f"The following non-cog file was updated and requires a restart: `{main_files[0]}`."
        else:
            embed.description += "No non-cog files were updated."

        embed.description += addendum

        await ctx.send(embed=embed)



    #@support()
    #@app_commands.command(name='add_notion')
    #@app_commands.default_permissions(manage_messages=True)
    #@app_commands.checks.has_permissions(manage_messages=True)
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
    help = app_commands.Group(name="help", description="Helpful commands, information, and more")
     
    @help.command(name='link_premium')
    async def link_premium(self, interaction):
        """Link your Discord account to your WOMBO Premium account."""
        embed = discord.Embed(title=linking_title, description=linking_description, color=discord.Color.blue())
        embed.set_thumbnail(url="https://url-to-thumbnail.png")
        embed.set_image(url="https://global-uploads.webflow.com/61d7278cd8cf5c868e8e869d/61d72be485ac65cce2478f9c_wombo-logo-p-500.png") 
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @support()
    @app_commands.command(name='report')
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def ticket_report(self, interaction: discord.Interaction):
        """Send a report of closed tickets in the last 24 hours."""
        headers = {"Content-Type": "application/json"}
        yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
        yesterday_str = yesterday.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Fetch tickets closed in the last 24 hours
        response = requests.get(
            self.bot.api_url + f"search/tickets?query='status:5 AND updated_at:>'{yesterday_str}'",
            auth=(self.bot.api_key, "X"),
            headers=headers,
        )

        # Check for a successful response
        if response.status_code == 200:
            tickets = response.json()
            agent_tickets = {}

            # Count tickets closed by each agent
            for ticket in tickets:
                agent_id = ticket["responder_id"]
                if agent_id in agent_tickets:
                    agent_tickets[agent_id] += 1
                else:
                    agent_tickets[agent_id] = 1

            # Fetch agents' names
            for agent_id in agent_tickets.keys():
                response = requests.get(
                    self.bot.api_url + f"agents/{agent_id}",
                    auth=(self.bot.api_key, "X"),
                    headers=headers,
                )
                if response.status_code == 200:
                    agent = response.json()
                    agent_tickets[agent_id] = (agent["contact"]["name"], agent_tickets[agent_id])

            # Send the report
            report = "\n".join(
                f"Agent {name} closed {count} tickets in the last 24 hours."
                for name, count in agent_tickets.values()
            )
            await interaction.response.send_message(report)
        else:
            await interaction.response.send_message("Could not fetch tickets.")


    @help.command(name='known_issues')
    async def update_known_issues(self, interaction):
        """Show the known issues reported by users and aknowleged by the WOMBO team, in the #known-issues channel with links-only visible to you."""
        thread_groups = defaultdict(list)
        await interaction.response.defer(ephemeral=True)
        for channel_id in KNOWN_ISSUES:
            channel = self.bot.get_channel(channel_id)
            if isinstance(channel, discord.ForumChannel):
                threads = channel.threads
                for thread in threads:
                    if not thread.archived and thread.id != 1114313493450072084:
                        first_message = await thread.fetch_message(thread.last_message_id)
                        tag_match = re.search(r'\[(\w+)\]', thread.name)
                        if tag_match is not None:
                            tag = tag_match.group(1)
                            # Remove the leading tag in brackets from the thread name
                            thread_name = re.sub(r'\[\w+\]\s*', '', thread.name)
                        else:
                            tag = "Other"
                        thread_name = thread.name
                        # Remove the leading word in all caps surrounded by brackets from the message content
                        cleaned_message = re.sub(r'\[\w+\]\s*', '', first_message.content)
                        # Extract the first 20 words from the cleaned content of the message
                        first_20_words = " ".join(cleaned_message.split()[:20])
                        first_20_words = re.sub(r'\[\w+\]\s*', '', first_20_words)
                        thread_groups[tag].append((thread_name, first_20_words, thread.id))
        embed = discord.Embed(title="Known Issues by Platform", color=discord.Color.red())
        # Construct the description of the embed by iterating over each group of threads
        description = ""
        for tag, threads in thread_groups.items():
            description += f"## {tag} Issues\n"
            for thread_name, first_20_words, thread_id in threads:
                description += f"- **{thread_name}** - {first_20_words}... [continue reading here](https://discord.com/channels/774124295026376755/{channel_id}/{thread_id})\n"
            description += "\n"

        embed.description = description
        await interaction.followup.send(embed=embed, ephemeral=True)


    @support()  
    @app_commands.command(name='close')
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def close(self, interaction, close_notes: str, status: Literal["resolved", "closed", "known"]):
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