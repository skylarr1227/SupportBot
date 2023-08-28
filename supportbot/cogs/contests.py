import asyncio
import calendar
from datetime import datetime, timedelta
from pytz import timezone
from discord.ext import commands
import discord
import functools
from supportbot.core.utils import team
import os
import logging
import asyncpg
import random

logger = logging.getLogger('discord')
logger.setLevel(logging.ERROR)
handler = logging.FileHandler(filename='errors.log', encoding='utf-8', mode='a')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s\n'))
logger.addHandler(handler)

LOGGING_CHANNEL_ID = 1145417494182494359  
THEME_CHANNEL_ID = 1144325882257887312
INSPECTION_CHANNEL_ID = 1144006598709219429
PUBLIC_VOTING_CHANNEL_ID = 1144006673829199942
XP_AWARDS = [100, 80, 60, 40, 20] # XP for 1st to 5th places
STRIPE_AUTH = os.environ.get("STRIPE_AUTH")
if STRIPE_AUTH is None:
    logger.error("The STRIPE_AUTH environment variable is missing!\nStripe coupon codes will not be generated until this is corrected in the .env file!")


def generate_progress_bar(percentage):
    filled_emoji = "<:xxp2:1145574506421833769>"
    last_filled_emoji = "<:xxp:1145574909632839720>"
    total_slots = 10
    filled_slots = percentage // 10  # Since each slot is 10%
    if filled_slots == 10:
        progress_bar = filled_emoji * 9 + last_filled_emoji
    elif filled_slots > 0:
        progress_bar = filled_emoji * (filled_slots - 1) + last_filled_emoji + "╍" * (total_slots - filled_slots)
    else:
        progress_bar = "╍" * total_slots
    return f"{progress_bar} {percentage}%"


class Contests(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.debug = True
        self.time_offset = 0
        self.accepting_images = True
        self.phase_message = None
        self.tasks = []  # To keep track of all tasks
        self.tasks.append(self.bot.loop.create_task(self.initialize_contest()))
        self.tasks.append(self.bot.loop.create_task(self.check_time()))
        self.tasks.append(self.bot.loop.create_task(self.count_votes()))
        self.last_winner_announcement_date = None

    def cog_unload(self):
        for task in self.tasks:
            task.cancel()
   
    



    @team()
    @commands.command(name='setdebug')
    async def set_debug(self, ctx, debug: bool):
        self.debug = debug
        status = "enabled" if debug else "disabled"
        await ctx.send(f"Debug mode has been {status}.")

    @team()
    @commands.command(name='setoffset')
    async def set_offset(self, ctx, offset: int):
        self.time_offset = offset
        await self.update_phase()  
        await ctx.send(f"Time offset has been set to {offset} hours, and the phase has been updated.")

    @commands.command(aliases=['level'])
    async def xp(self, ctx):
        user_id = ctx.author.id
        async with self.bot.pool.acquire() as connection:
            row = await connection.fetchrow('SELECT xp, level FROM users WHERE u_id = $1', user_id)

            if row:
                xp = row['xp']
                level = row['level']
                if xp == 0:
                    percentage = 0
                else:
                    xp_next_level = 100 * (level + 1)
                    percentage = (xp - (100 * level)) * 10 // (xp_next_level - (100 * level))

                progress_bar_str = generate_progress_bar(percentage)
                embed = discord.Embed(
                    title=f"XP and Level Info for {ctx.author.name}",
                    description=f"Current Level: {level}\n{progress_bar_str}",
                    color=random.randint(0, 0xFFFFFF)  # Random color
                )
                await ctx.send(embed=embed)
            else:
                await connection.execute('INSERT INTO users(u_id, xp, level) VALUES($1, $2, $3)', user_id, 0, 0)
                await ctx.send("Welcome! You have been added to the system. You are at level 0 with 0 XP.")


    async def get_theme(self):
        now = datetime.now(timezone('US/Eastern'))
        week_of_year = now.isocalendar()[1]
        day_of_week = calendar.day_name[now.weekday()].lower()
        async with self.bot.pool.acquire() as connection:
            query = f'SELECT {day_of_week} FROM contests WHERE week = $1'
            row = await connection.fetchrow(query, week_of_year)
            return row[day_of_week] if row else None

    async def initialize_contest(self):
        try:
            theme_channel = self.bot.get_channel(THEME_CHANNEL_ID)
            theme = await self.get_theme()
            await theme_channel.send(f"Today's theme is:\n{theme}")
            self.phase_message = await theme_channel.send("Initializing contest phase...")
            await self.update_phase()
            print("Contest initialized")  # Debugging print statement
        except Exception as e:
            print(f"Failed to initialize contest: {e}")  # Debugging print statement

    async def update_phase(self):
        now = datetime.now(timezone('US/Eastern')) + timedelta(hours=self.time_offset) if self.debug else datetime.now(timezone('US/Eastern'))
        if now.hour < 21:
            phase = "In Progress"
            self.accepting_images = True
        elif now.hour == 21:
            phase = "Voting"
            self.accepting_images = False
        else:
            phase = "Downtime"
            self.accepting_images = False
        if self.phase_message:
            await self.phase_message.edit(content=f"The contest is now in the {phase} phase.")


    async def inspect_image(self, user_id, image_url):
        channel = self.bot.get_channel(INSPECTION_CHANNEL_ID)
        message = await channel.send(embed=discord.Embed(description=f"{user_id}").set_image(url=image_url))
        await message.add_reaction("👍")
        await message.add_reaction("👎")

    async def post_image(self, user_id, image_url):
        channel = self.bot.get_channel(PUBLIC_VOTING_CHANNEL_ID)
        message = await channel.send(f'<@{user_id}>', embed=discord.Embed(description=f"{user_id}").set_image(url=image_url))
        await message.add_reaction("👍")
        async with self.bot.pool.acquire() as connection:
            await connection.execute('UPDATE artwork SET message_id = $1 WHERE submitted_by = $2', message.id, user_id)



    @commands.Cog.listener()
    async def on_message(self, message):
        if isinstance(message.channel, discord.DMChannel) and len(message.attachments) > 0:
            user_id = message.author.id
            async with self.bot.pool.acquire() as connection:
                # Check if the user exists in the users table
                row = await connection.fetchrow('SELECT * FROM users WHERE u_id = $1', user_id)
                if not row:
                    await connection.execute('INSERT INTO users(u_id, xp, level) VALUES($1, $2, $3)', user_id, 0, 0)
                now = datetime.now(timezone('US/Eastern'))
                current_contest_start_time = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
                # Check if the user has already submitted an image for the current contest
                row = await connection.fetchrow('SELECT submitted_by FROM artwork WHERE submitted_by = $1 AND submitted_on >= $2', user_id, current_contest_start_time)
                if row:
                    await message.author.send('You have already submitted an image for the current contest. Only one submission is allowed.')
                    return
                # Insert a new artwork submission
                
                reply = await message.reply("Do you want to submit this image for the daily contest? (yes/no)")
                def check(m):
                    return m.author == message.author and m.channel == message.channel and m.content.lower() in ["yes", "no"]
                try:
                    reply = await self.bot.wait_for('message', check=check, timeout=60.0)
                except asyncio.TimeoutError:
                    await message.author.send('Sorry, you took too long to reply.')
                else:
                    if reply.content.lower() == 'yes' and self.accepting_images:
                        await connection.execute('INSERT INTO artwork(submitted_by, submitted_on, message_id, upvotes, inspected_by) VALUES($1, $2, $3, $4, $5)', user_id, int(now.timestamp()), None, 0, None)
                        await connection.execute('UPDATE users SET submitted = $1 WHERE u_id = $2', int(now.timestamp()), user_id)
                        await self.inspect_image(user_id, message.attachments[0].url)
                        await message.author.send('Your image has been submitted for manual inspection.')
                    elif reply.content.lower() == 'no':
                        await message.author.send('Okay, your image was not submitted.')
            

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == 1082909042944524308:
            return
        if payload.channel_id == INSPECTION_CHANNEL_ID:
            channel = self.bot.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            logging_channel = self.bot.get_channel(LOGGING_CHANNEL_ID)
            if message.embeds and message.embeds[0].description:
                user_id = int(message.embeds[0].description)
                inspector_id = payload.user_id 
                async with self.bot.pool.acquire() as connection:
                    if str(payload.emoji) == "👍":
                        # APPROVE
                        await self.post_image(user_id, message.embeds[0].image.url)
                        await connection.execute('UPDATE artwork SET inspected_by = $1 WHERE u_id = $2', inspector_id, user_id)
                        await logging_channel.send(f"👍 <@{user_id}>, your image has been approved!")
                    elif str(payload.emoji) == "👎":
                        # DENY
                        await connection.execute('DELETE FROM artwork WHERE u_id = $1', user_id)
                        await logging_channel.send(f"👎 <@{user_id}>, your image has been denied.")


    async def check_time(self):
        last_phase = None
        while True:
            now = datetime.now(timezone('US/Eastern')) + timedelta(hours=self.time_offset) if self.debug else datetime.now(timezone('US/Eastern'))
            if 0 <= now.hour < 20:
                phase = "In Progress"
                self.accepting_images = True
            elif now.hour == 20:
                phase = "Voting"
                self.accepting_images = False
            else:  # 21 to 23
                phase = "Downtime"
                self.accepting_images = False
                
            if phase != last_phase:
                await self.update_phase()
                last_phase = phase
                
            await asyncio.sleep(60)
    

    async def count_votes(self):
        while True:
            now = datetime.now(timezone('US/Eastern'))
            current_date = now.date()
            if now.hour == 22:
                if self.last_winner_announcement_date != current_date:
                    current_contest_start_time = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
                    channel = self.bot.get_channel(PUBLIC_VOTING_CHANNEL_ID)
                    async with self.bot.pool.acquire() as connection:
                        rows = await connection.fetch('SELECT u_id, message_id FROM artwork WHERE submitted_on >= $1', current_contest_start_time)
                        for row in rows:
                            try:
                                message = await channel.fetch_message(row['message_id'])
                                for reaction in message.reactions:
                                    if str(reaction.emoji) == "👍":
                                        await connection.execute('UPDATE artwork SET upvotes = $1 WHERE u_id = $2 AND message_id = $3', reaction.count, row['u_id'], row['message_id'])
                            except Exception as e:
                                print(f"Failed to fetch or process message: {e}")

                        top_artworks = await connection.fetch('SELECT u_id, upvotes FROM artwork ORDER BY upvotes DESC LIMIT 5')
                        if top_artworks:
                            winners = [artwork['u_id'] for artwork in top_artworks]
                            await channel.send(f"The winners are: {', '.join(f'<@{winner}>' for winner in winners)}")
                            for i, winner in enumerate(winners):
                                user = await connection.fetchrow('SELECT u_id, xp, level FROM users WHERE u_id = $1', winner)
                                if user:
                                    new_xp = user['xp'] + XP_AWARDS[i]
                                    new_level = new_xp // 100  # each level requires 100 XP
                                    await connection.execute('UPDATE users SET xp = $1, level = $2 WHERE u_id = $3', new_xp, new_level, winner)
                                else:
                                    print(f"No user found for u_id: {winner}")

                    self.last_winner_announcement_date = current_date
            await asyncio.sleep(60)





async def setup(bot):
    await bot.add_cog(Contests(bot))