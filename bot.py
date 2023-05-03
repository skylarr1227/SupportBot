import discord
from discord.ext import commands
import aiohttp

TOKEN = 'BOT_TOKEN'
WEBHOOK_URL = 'WEBHOOK_URL'

intents = discord.Intents.default()
intents.messages = True
intents.reactions = True
intents.guilds = True
intents.threads = True

prefix = '!'
bot = commands.Bot(command_prefix=prefix, intents=intents)

closed_tickets = {
    'RESOLVED': 0,
    'ON-GOING': 0,
    'WAITING': 0,
    'HOLD': 0,
    'CLOSED': 0,
    'DUPLICATE':0,
}

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')

async def send_webhook(old_status, new_status, thread, executor, author):
    payload = {
        'old_status': old_status,
        'new_status': new_status,
        'thread_jump_url': thread.jump_url,
        'executor_name': str(executor),
        'author_name': str(author),
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(WEBHOOK_URL, json=payload) as response:
            return response.status

@bot.command(name='set-status')
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

    # Find the original author of the thread
    thread_messages = await ctx.channel.history(oldest_first=True, limit=1).flatten()
    original_author = thread_messages[0].author if thread_messages else None

    response_status = await send_webhook(old_status, status, ctx.channel, ctx.author, original_author)

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
