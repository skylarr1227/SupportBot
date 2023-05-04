import discord
from discord.ext import commands
from google_measurement_protocol import event, report
import aiohttp


TOKEN = 'nope'
WEBHOOK_URL = 'bootie-flakes'

intents = discord.Intents.default()
intents.messages = True
intents.reactions = True
intents.guilds = True
intents.message_content = True  


bot = commands.Bot(command_prefix='!', intents=intents)






@bot.event
async def on_ready():
    await bot.wait_until_ready()
    print(f'{bot.user.name} has connected to Discord!')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    print(f"Message from {message.author}: {message.content}")

    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f"Command not found. Error: {error}")
    else:
        await ctx.send(f"Command not found. Error: {error}")
        raise error

closed_tickets = {
    'RESOLVED': 0,
    'ON-GOING': 0,
    'WAITING': 0,
    'HOLD': 0,
    'CLOSED': 0,
    'KNOWN':0,
}

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')

async def send_webhook(old_status, new_status, thread, executor, author, original_message):
    payload = {
        'old_status': old_status,
        'new_status': new_status,
        'thread_jump_url': thread.jump_url,
        'executor_name': str(executor),
        'author_name': str(author),
        'original_message': original_message
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(WEBHOOK_URL, json=payload) as response:
            return response.status

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
    old_status = ctx.channel.name.split(']')[0][1:]

    if status == 'RESOLVED':
        closed_tickets[status] += 1

    new_name = f'[{status}] {ctx.channel.name.split("]")[1].strip()}'
    await ctx.channel.edit(name=new_name)

    # Find the original author and message of the thread
    original_author = None
    original_message = None
    async for message in ctx.channel.history(oldest_first=True, limit=1):
        original_author = message.author
        original_message = message.content

    response_status = await send_webhook(old_status, status, ctx.channel, ctx.author, original_author, original_message)

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
