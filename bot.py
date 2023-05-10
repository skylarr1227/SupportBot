
import discord
from discord.ext import commands
from discord.ext.commands import CommandError, MissingRequiredArgument
from supabase-py import create_client, Client
from discord_components import DiscordComponents, Button, ButtonStyle, InteractionType
import os
import asyncio

TOKEN = ''
SUPABASE_URL = ""
SUPABASE_API_KEY = os(environ.get("SUPABASE_API_KEY")

intents = discord.Intents.default()
intents.messages = True
intents.reactions = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

closed_tickets = {
    'RESOLVED': 0,
    'ON-GOING': 0,
    'WAITING': 0,
    'HOLD': 0,
    'CLOSED': 0,
    'KNOWN': 0,
}

supabase: Client = create_client(SUPABASE_URL, SUPABASE_API_KEY)

@bot.event
async def on_ready():
    await bot.wait_until_ready()
    print(f'{bot.user.name} has connected to Discord!')

async def store_in_supabase(old_status, new_status, thread, executor, author, original_message):
    payload = {
        'old_status': old_status,
        'new_status': new_status,
        'thread_jump_url': thread.jump_url,
        'support_rep': int(executor),
        'author_id': int(author),
        'original_message': original_message
    }

    # Insert the data into the Supabase "tickets" table
    response = supabase.table("tickets").insert(payload).execute()

    # Check if the insert was successful
    if response.get("status_code") == 201:
        return 200
    else:
        return response.get("status_code")

async def store_prompt(prompt, images, nsfw_triggered):
    data = {
        'prompt': prompt,
        'images': images,
        'nsfw_triggered': nsfw_triggered
    }
    
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, supabase.table("nsfw_tracking").insert(data).execute)
    return response


@bot.event
async def on_thread_update(before, after):
    # Replace THREAD_ID with the ID of the thread you want to monitor
    if after.id == 1053787533139521637:
        if before.applied_tags != after.applied_tags:
            last_applied_tag = after.applied_tags[-1] if after.applied_tags else None
            if last_applied_tag:
                new_name = f"{last_applied_tag} - {after.name}"
                if new_name != after.name:
                    await after.edit(name=new_name)


clicked_users = set()

@bot.event
async def on_button_click(res):
    if res.component.label == "Send User ID":
        if res.user.id not in clicked_users:
            await res.respond(
                type=InteractionType.ChannelMessageWithSource,
                content=f"{res.user.name}'s User ID: {res.user.id}"
            )
            clicked_users.add(res.user.id)
        else:
            return


@bot.event
async def on_thread_create(thread):
    if thread.parent_id == 1053787533139521637:
        if not thread.name.startswith('[NEW]'):
            new_name = f'[NEW] {thread.name}'
            await thread.edit(name=new_name)
            print(f"Thread name updated to: {new_name}")
        # Automatically join the thread
        await thread.join()

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, MissingRequiredArgument):
        await ctx.send(f"Missing required argument: {error.param.name}")
    elif isinstance(error, CommandError):
        await ctx.send(f"An error occurred while processing the command: {error}")
    else:
        # You can either pass the error to the default handler or log it here
        print(f"Unhandled error: {error}")

@bot.command(name='n')
async def record(ctx, prompt: str, nsfw_triggered: bool, *image_urls: str):
    # Insert the record into the Supabase table
    labeled_images = {str(index + 1): url for index, url in enumerate(image_urls)}
    
    response = await store_prompt(prompt, labeled_images, nsfw_triggered)

    if 'error' in response:
        await ctx.send(f"Error: {response['error']['message']}")
    else:
        await ctx.send("Recorded successfully.")

@bot.command()
async def send_button(ctx):
    await ctx.send(
        "Click this button to have your video set back to the original style.",
        components=[
            Button(style=ButtonStyle.green, label="Send User ID")
        ]
    )




@bot.command(name='state')
async def set_status(ctx, status: str):
    global closed_tickets

    if status.lower() not in ['resolved', 'on-going', 'waiting', 'hold']:
        await ctx.send("Invalid status. Use one of the following: [RESOLVED], [ON-GOING], [WAITING], [HOLD].")
        return

    if not isinstance(ctx.channel, discord.Thread):
        await ctx.send("This command can only be used in a thread.")
        return

    status = status.upper()

    if ']' in ctx.channel.name:
        old_status = ctx.channel.name.split(']')[0][1:]
        new_name = f'[{status}] {ctx.channel.name.split("]")[1].strip()}'
    else:
        old_status = "UNKNOWN"
        new_name = f'[{status}] {ctx.channel.name}'

    if status == 'RESOLVED':
        closed_tickets[status] += 1

    await ctx.channel.edit(name=new_name)

    # Find the original author and message of the thread
    original_author = None
    original_message = None
    async for message in ctx.channel.history(oldest_first=True, limit=1):
        original_author = message.author
        original_message = message.content

    response_status = await store_in_supabase(old_status, status, ctx.channel, ctx.author.id, original_author.id, original_message)

    if response_status == 200:
        await ctx.send(f"Thread name updated to: {new_name}")
    else:
        await ctx.send("An error occurred while updating the thread name. Please try again.")




@bot.command(name='closed-count')
async def closed_count(ctx):
    global closed_tickets

    count_message = "Closed ticket counts:\n"
    for status, count in closed_tickets.items():
        count_message += f"{status}: {count}\n"

    await ctx.send(count_message)

@bot.command(name='lock')
@commands.has_permissions(manage_messages=True)
async def lock(ctx):
    if not isinstance(ctx.channel, discord.Thread):
        await ctx.send("This command can only be used in a thread.")
        return

    await ctx.channel.edit(locked=True)
    await ctx.send("Thread locked.")

@bot.command(name='unlock')
@commands.has_permissions(manage_messages=True)
async def unlock(ctx):
    if not isinstance(ctx.channel, discord.Thread):
        await ctx.send("This command can only be used in a thread.")
        return

    await ctx.channel.edit(locked=False)
    await ctx.send("Thread unlocked.")


@bot.command(name='combine')
@commands.has_permissions(manage_messages=True)
async def combine(ctx, thread_id: int, master_thread_id: int, num_messages: int):
    # Validate the number of messages
    if num_messages < 1 or num_messages > 100:
        await ctx.send("Please enter a valid number of messages (1-100).")
        return
    # Fetch the source thread
    thread = bot.get_channel(thread_id)
    if thread is None or not isinstance(thread, discord.Thread):
        await ctx.send(f"No thread found with ID {thread_id}.")
        return
    # Fetch the master thread
    master_thread = bot.get_channel(master_thread_id)
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
