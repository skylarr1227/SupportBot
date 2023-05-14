
import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import CommandError, MissingRequiredArgument
from supabase import create_client, Client
from discord_components import DiscordComponents, Button, ButtonStyle, InteractionType  # this was just to test the one send button command see if it was easier-can be removed.
import os
import asyncio
from dotenv import load_dotenv

load_dotenv("support.env")

TOKEN = os(environ.get("DISCORD_TOKEN")) # this is the bot token
SUPABASE_URL = os(environ.get("SUPABASE_URL")) # this is the supabase url
SUPABASE_API_KEY = os(environ.get("SUPABASE_API_KEY")) # this is the supabase api key for the database 

intents = discord.Intents.default()
intents.messages = True
intents.reactions = True
intents.guilds = True
intents.message_content = True

async def get_prefix(bot, message):
    prefixes = ['<@1000125868938633297>']
    if message.author.id == 790722073248661525:
        prefixes.append('.')
        return commands.when_mentioned_or(*prefixes)(bot, message)
    if not message.guild:
        return "?"
    return commands.when_mentioned_or(*prefixes)(bot, message)

class SupportBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(
            command_prefix=get_prefix,
            max_messages=None,
            intents=intents,
            heartbeat_timeout=120,
            guild_ready_timeout=10,
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True),
            *args,
            **kwargs,
        )
        self.WOMBO_TEAM = [790722073248661525, 381887137362083841, 149706927868215297, 291970766419787788]
        self.WOMBO_SUPPORT = [
            790722073248661525, 
            381887137362083841, 
            149706927868215297, 
            291970766419787788, 
            986262236479750174,
            702554894032175246,
            395788963475881985,
            988106635874533467
        ]

        self.closed_tickets = {
            'RESOLVED': 0,
            'ON-GOING': 0,
            'WAITING': 0,
            'HOLD': 0,
            'CLOSED': 0,
            'KNOWN': 0,
        }

        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_API_KEY)

bot = SupportBot()

@bot.event
async def on_ready(self):
    await self.wait_until_ready()
    await self.on_ready()
    print(f'{self.user.name} has connected to Discord!')


def team():
    def predicate(self, ctx):
        return ctx.author.id in self.WOMBO_TEAM
    return commands.check(predicate)

def support():
    def predicate(self, ctx):
        return ctx.author.id in self.WOMBO_SUPPORT
    return commands.check(predicate)

async def store_in_supabase(self, old_status, new_status, thread, executor, author, original_message):
    payload = {
        'old_status': old_status,
        'new_status': new_status,
        'thread_jump_url': thread.jump_url,
        'support_rep': int(executor),
        'author_id': int(author),
        'original_message': original_message
    }
    # Insert the data into the Supabase "tickets" table
    response = self.supabase.table("tickets").insert(payload).execute()
    # Check if the insert was successful
    if response.get("status_code") == 201:
        return 200
    else:
        return response.get("status_code")


async def store_prompt(self, prompt, images, nsfw_triggered):
    data = {
        'prompt': prompt,
        'images': images,
        'nsfw_triggered': nsfw_triggered
    }
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, self.supabase.table("nsfw_tracking").insert(data).execute)
    return response



@support()
@commands.command(name='n')
async def record(self, ctx, prompt: str, nsfw_triggered: bool, *image_urls: str):
    # Insert the record into the Supabase table
    labeled_images = {str(index + 1): url for index, url in enumerate(image_urls)}
    response = await self.store_prompt(prompt, labeled_images, nsfw_triggered)      
    if 'error' in response:
        await ctx.send(f"Error: {response['error']['message']}")
    else:
        await ctx.send("Recorded successfully.")       

@support()
@app_commands.command()
async def send_button(self, interaction: discord.Interaction):
    await interaction.response.send_message(
        "Click this button to be added to the list of people to have your video set back to the original style.",
        components=[
            Button(style=ButtonStyle.green, label="Send User ID")
        ]
    )

@support()
@app_commands.command(name='state')
async def set_status(self, interaction: discord.Interaction, status: str):
    global closed_tickets
    if status.lower() not in ['resolved', 'on-going', 'waiting', 'hold']:
        await interaction.response.send_message("Invalid status. Use one of the following: [RESOLVED], [ON-GOING], [WAITING], [HOLD].")
        return
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message("This command can only be used in a thread.")
        return
    status = status.upper()
    if ']' in interaction.channel.name:
        old_status = interaction.channel.name.split(']')[0][1:]
        new_name = f'[{status}] {interaction.channel.name.split("]")[1].strip()}'
    else:
        old_status = "UNKNOWN"
        new_name = f'[{status}] {interaction.channel.channel.name}'
    if status == 'RESOLVED':
        closed_tickets[status] += 1
    await interaction.channel.edit(name=new_name)
    # Find the original author and message of the thread
    original_author = None
    original_message = None
    async for message in interaction.channel.history(oldest_first=True, limit=1):
        original_author = message.author
        original_message = message.content
    response_status = await self.store_in_supabase(old_status, status, interaction.channel, interaction.user.id, original_author.id, original_message)
    if response_status == 200:
        await interaction.response.send_message(f"Thread name updated to: {new_name}")
    else:
        await interaction.response.send_message("An error occurred while updating the thread name. Please try again.")

@team()
@commands.command()
async def load_cog(ctx, cog_name: str):
    try:
        bot.load_extension(f'cogs.{cog_name}')
        await ctx.send(f'Cog {cog_name} has been loaded.')
    except commands.ExtensionError as e:
        await ctx.send(f'Failed to load cog {cog_name}: {e}')
@team()
@commands.command()
async def unload_cog(ctx, cog_name: str):
    try:
        bot.unload_extension(f'cogs.{cog_name}')
        await ctx.send(f'Cog {cog_name} has been unloaded.')
    except commands.ExtensionError as e:
        await ctx.send(f'Failed to unload cog {cog_name}: {e}')

@team()
@commands.command(name='closed-count')
async def closed_count(ctx):
    global closed_tickets
    count_message = "Closed ticket counts:\n"
    for status, count in closed_tickets.items():
        count_message += f"{status}: {count}\n"
    await ctx.send(count_message)

@support()
@commands.command(name='lock')
@commands.has_permissions(manage_messages=True)
async def lock(ctx):
    if not isinstance(ctx.channel, discord.Thread):
        await ctx.send("This command can only be used in a thread.")
        return
    await ctx.channel.edit(locked=True)
    await ctx.send("Thread locked.")

@support()
@commands.command(name='unlock')
@commands.has_permissions(manage_messages=True)
async def unlock(ctx):
    if not isinstance(ctx.channel, discord.Thread):
        await ctx.send("This command can only be used in a thread.")
        return
    await ctx.channel.edit(locked=False)
    await ctx.send("Thread unlocked.")


@commands.command(name='combine')
@commands.has_permissions(manage_messages=True)
async def combine(self, ctx, thread_id: int, master_thread_id: int, num_messages: int):
    # Validate the number of messages
    if num_messages < 1 or num_messages > 100:
        await ctx.send("Please enter a valid number of messages (1-100).")
        return
    # Fetch the source thread
    thread = self.bot.get_channel(thread_id)
    if thread is None or not isinstance(thread, discord.Thread):
        await ctx.send(f"No thread found with ID {thread_id}.")
        return
    # Fetch the master thread
    master_thread = self.bot.get_channel(master_thread_id)
    if master_thread is None or not isinstance(master_thread, discord.Thread):
        await ctx.send(f"No master thread found with ID {master_thread_id}.")
        return
    # Retrieve messages from the source thread
    messages = await thread.history(limit=num_messages).flatten()
    # Combine messages and prepare a summary
    combined_message = f"Combined messages from thread {thread.name} ({thread_id}):\n\n"
    for message in messages:
        combined_message += f"{message.author}: {message.content}\n"
    # Check if the combined message is too long for a single message
    if len(combined_message) > 2000:
        await ctx.send("The combined message is too long. Please consider fetching fewer messages.")
        return
    # Send the combined message to the master thread
    await master_thread.send(combined_message)
    # Lock and close (archive) the original thread, and update its status
    await thread.edit(locked=True, archived=True, name=f"[ON-GOING] {thread.name}")
    # Leave a message in the original thread with the link to the master thread
    await thread.send(f"Your support request has been combined into a combined known-issue post: {master_thread.jump_url}\nThis support post is now locked and closed please follow this new post for future updates/resolution.")
    await ctx.send("The messages have been combined into the 'Known Issue' post, and the original post has been locked and closed.")


bot.run(TOKEN)
