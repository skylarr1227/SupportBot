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
import time

logger = logging.getLogger('discord')
logger.setLevel(logging.ERROR)
handler = logging.FileHandler(filename='errors.log', encoding='utf-8', mode='a')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s\n'))
logger.addHandler(handler)

LOGGING_CHANNEL_ID = 1145417494182494359  
THEME_CHANNEL_ID = 1144325882257887312
INSPECTION_CHANNEL_ID = 1144006598709219429
PUBLIC_VOTING_CHANNEL_ID = 1144006673829199942
XP_AWARDS = [50, 40, 30, 20, 10] # XP for 1st to 5th places
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
        self.tasks = []  
        self.next_phase = None
        self.last_winner_announcement_date = None
        self.theme_message = None
        self.previous_phase = None
        self.STARTED = None
        self.tasks.append(self.bot.loop.create_task(self.initialize_contest()))
        self.tasks.append(self.bot.loop.create_task(self.check_time()))
        self.tasks.append(self.bot.loop.create_task(self.count_votes()))


    def cog_unload(self):
        if self.theme_message:
            loop = asyncio.get_event_loop()
            loop.create_task(self.edit_theme_message())
        for task in self.tasks:
            task.cancel()
   


    


    async def edit_theme_message(self):
        embed = self.theme_message.embeds[0]
        embed.color = 0xFF0000  # Set the color to red
        await self.theme_message.edit(embed=embed)

    async def purchase_coupon(self, connection, platform):
        coupon = await connection.fetchrow('SELECT * FROM coupons WHERE platform = $1 AND purchased IS NULL LIMIT 1', platform)
        if coupon:
            await connection.execute('UPDATE coupons SET purchased = NOW() WHERE id = $1', coupon['id'])
            return coupon['code']
        return None


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

    @commands.group()
    async def shop(self, ctx):
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(title="🛒 Shop", description="Please select the platform you signed up on and use:", color=0x00ff00)  
            embed.add_field(name="1. Android", value="`shop android`", inline=False)
            embed.add_field(name="2. iOS", value="`shop ios`", inline=False)
            embed.add_field(name="3. Web", value="`shop web`", inline=False)
            await ctx.send(embed=embed)

    @shop.command(name='android')
    async def shop_android(self, ctx):
        await ctx.send(embed=discord.Embed(title="Coming soon", description="Coupon codes for free subscriptions!"))
        pass

    @shop.command(name='ios')
    async def shop_ios(self, ctx):
        await ctx.send(embed=discord.Embed(title="Coming soon", description="Coupon codes for free subscriptions!"))
        pass

    @shop.command(name='web')
    async def shop_web(self, ctx):
        await ctx.send(embed=discord.Embed(title="Coming soon", description="Coupon codes for free subscriptions!"))
        pass




    @commands.command(name='cinfo')
    async def contest_stats(self, ctx):
        now = datetime.now(timezone('US/Eastern'))
        epoch_now = int(time.mktime(now.timetuple()))
        # Calculate the end time for each phase
        end_in_progress = datetime(now.year, now.month, now.day, 20, 0, tzinfo=timezone('US/Eastern'))
        end_voting = datetime(now.year, now.month, now.day, 21, 0, tzinfo=timezone('US/Eastern'))
        end_downtime = datetime(now.year, now.month, now.day, 23, 59, 59, tzinfo=timezone('US/Eastern')) + timedelta(seconds=1)
        # Convert to epoch
        epoch_end_in_progress = int(time.mktime(end_in_progress.timetuple()))
        epoch_end_voting = int(time.mktime(end_voting.timetuple()))
        epoch_end_downtime = int(time.mktime(end_downtime.timetuple()))
        # Determine the current phase
        current_phase = None
        if 0 <= now.hour < 20:
            current_phase = f"In Progress (Ends in <t:{int(epoch_end_in_progress)}:R>)"
        elif now.hour == 20:
            current_phase = f"Voting (Ends in <t:{int(epoch_end_voting)}:R>)"
        else:
            current_phase = f"Downtime (Ends in <t:{int(epoch_end_downtime)}:R>)"
        embed = discord.Embed(
            title=f"Contest Stats",
            description=f"Current Phase: {current_phase}\n\nOverview/times\nEnd of In-Progress Phase: <t:{int(epoch_end_in_progress)}:R>\nEnd of Voting Phase: <t:{int(epoch_end_voting)}:R>\nEnd of Downtime: <t:{int(epoch_end_downtime)}:R>",
            color=random.randint(0, 0xFFFFFF)
        )
        await ctx.send(embed=embed)


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
                    color=random.randint(0, 0xFFFFFF)  
                )
                await ctx.send(embed=embed)
            else:
                await connection.execute('INSERT INTO users(u_id, xp, level) VALUES($1, $2, $3)', user_id, 0, 0)
                await ctx.send("Welcome! You have been added to the system. You are at level 0 with 0 XP.")


    async def get_theme(self, target_date=None):
        if target_date is None:
            target_date = datetime.now(timezone('US/Eastern'))
        week_of_year = target_date.isocalendar()[1]
        day_of_week = calendar.day_name[target_date.weekday()].lower()
        async with self.bot.pool.acquire() as connection:
            query = f'SELECT {day_of_week} FROM contests WHERE week = $1'
            row = await connection.fetchrow(query, week_of_year)
            return row[day_of_week] if row else None

    async def initialize_contest(self):
        try:
            theme_channel = self.bot.get_channel(THEME_CHANNEL_ID)
            theme = await self.get_theme()
            now = datetime.now(timezone('US/Eastern'))
            week_of_year = now.isocalendar()[1]
            day_of_week = calendar.day_name[now.weekday()].capitalize()
            embed = discord.Embed(title=f"{day_of_week}'s Contest of week {week_of_year}", description=f"# Today's theme is\n{theme}", color=random.randint(0, 0xFFFFFF))
            self.theme_message = await theme_channel.send(embed=embed)
            self.phase_message = await theme_channel.send("Initializing contest phase...")
            await self.update_phase()
            print("Contest initialized")  
        except Exception as e:
            print(f"Failed to initialize contest: {e}")  

    async def update_phase(self):
        now = datetime.now(timezone('US/Eastern')) + timedelta(hours=self.time_offset) if self.debug else datetime.now(timezone('US/Eastern'))

        if self.previous_phase == "In Progress" and now.hour == 0:
            phase = "Ended or Expired"
            self.accepting_images = False
            await self.phase_message.edit(content=f"{phase}")
            await asyncio.sleep(60)  # Wait for a minute before moving to the next phase

        if 0 <= now.hour < 18:  # 12:00am - 5:59pm
            phase = "<:PRO2:1146213220546269255><:PRO:1146213269242126367>"
            self.accepting_images = True
            self.STARTED = now
        elif 18 <= now.hour < 19:  # 6:00pm - 6:59pm
            phase = "<:vote:1146208634322296923>"
            self.accepting_images = False
        else:  # 7:00pm - 11:59pm
            phase = "<:down3:1146208635953873016><:down2:1146208638843748372>"
            self.accepting_images = False

        self.previous_phase = phase  # Update the previous_phase variable

        if self.phase_message:
            await self.phase_message.edit(content=f"{phase}")



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
            first_attachment_url = message.attachments[0].url     
            await connection.execute('UPDATE artwork SET message_id = $1, link = 3$ WHERE submitted_by = $2', message.id, user_id, first_attachment_url)



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
                        await connection.execute('UPDATE artwork SET inspected_by = $1 WHERE submitted_by = $2', inspector_id, user_id)
                        await logging_channel.send(f"👍 <@{user_id}>, your image has been approved!")
                    elif str(payload.emoji) == "👎":
                        # DENY
                        await connection.execute('DELETE FROM artwork WHERE submitted_by = $1', user_id)
                        await logging_channel.send(f"👎 <@{user_id}>, your image has been denied.")
                    # Clear the reactions after inspection
                    await message.clear_reactions()



    async def check_time(self):
        last_phase = None
        downtime_message_sent = False  # Initialize the flag
        theme_channel = self.bot.get_channel(THEME_CHANNEL_ID)  
        while True:
            now = datetime.now(timezone('US/Eastern')) + timedelta(hours=self.time_offset) if self.debug else datetime.now(timezone('US/Eastern'))

            if 0 <= now.hour < 18:  # 12:00am - 5:59pm
                phase = "In Progress (12:00am - 5:59pm EST)"
                self.accepting_images = True
            elif 18 <= now.hour < 19:  # 6:00pm - 6:59pm
                phase = "Voting (6:00pm - 6:59pm EST)"
                self.accepting_images = False
            else:  # 7:00pm - 11:59pm
                phase = "Downtime (7:00pm - 11:59pm EST)"
                self.accepting_images = False

            if phase != last_phase:
                await self.update_phase()
                if phase == "Downtime" and not downtime_message_sent:
                    await theme_channel.send("The contest has ended for today. Downtime has started!")  # Send message on Downtime
                    downtime_message_sent = True  # Set the flag to True
                if phase != "Downtime":  # Reset the flag if the phase is not Downtime
                    downtime_message_sent = False
                last_phase = phase

            await asyncio.sleep(60)


    async def count_votes(self):
        while True:
            now = datetime.now(timezone('US/Eastern'))
            current_date = now.date()
            current_timestamp = int(now.timestamp())
            if now.hour == 22:
                if self.last_winner_announcement_date != current_date:
                    current_contest_start_time = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
                    channel = self.bot.get_channel(PUBLIC_VOTING_CHANNEL_ID)
                    theme_channel = self.bot.get_channel(THEME_CHANNEL_ID)
                    async with self.bot.pool.acquire() as connection:
                        # Filter artworks for today's contest only
                        rows = await connection.fetch('SELECT submitted_by, message_id FROM artwork WHERE submitted_on >= $1', current_contest_start_time)
                        for row in rows:
                            try:
                                message = await channel.fetch_message(row['message_id'])
                                for reaction in message.reactions:
                                    if str(reaction.emoji) == "👍":
                                        await connection.execute('UPDATE artwork SET upvotes = $1 WHERE submitted_by = $2 AND message_id = $3', reaction.count, row['submitted_by'], message.id)
                            except Exception as e:
                                print(f"Failed to fetch or process message: {e}")
                        # Fetch top 5 artworks by upvotes for today's contest
                        top_artworks = await connection.fetch('SELECT submitted_by, upvotes, link FROM artwork WHERE submitted_on >= $1 ORDER BY upvotes DESC, submitted_by ASC', current_contest_start_time)
                        if top_artworks:
                            awards = XP_AWARDS.copy()
                            winners = []
                            prev_upvotes = -1
                            tie_pool = []
                            tie_pool_xp = 0
                            for i, artwork in enumerate(top_artworks[:5]):
                                if artwork['upvotes'] == prev_upvotes:
                                    tie_pool.append(artwork['submitted_by'])
                                    tie_pool_xp += awards[i]
                                else:
                                    if tie_pool:
                                        distributed_xp = tie_pool_xp // len(tie_pool)
                                        for tied_winner in tie_pool:
                                            winners.append((tied_winner, distributed_xp))
                                    tie_pool = [artwork['submitted_by']]
                                    tie_pool_xp = awards[i]
                                prev_upvotes = artwork['upvotes']
    
                            if tie_pool:
                                distributed_xp = tie_pool_xp // len(tie_pool)
                                for tied_winner in tie_pool:
                                    winners.append((tied_winner, distributed_xp))
                            winner_mentions = ''
                            for i, (winner, xp) in enumerate(winners):
                                winner_mentions += f"{i + 1}. <@{winner}>\n"
                            first_place_artwork_link = top_artworks[0]['link']
                            embed = discord.Embed(
                                title=f"Daily Contest Announcement",
                                description=f"The winners of today's contest are:\n{winner_mentions}",
                                color=random.randint(0, 0xFFFFFF)
                            )
                            embed.set_image(url=first_place_artwork_link)
                            await theme_channel.send(embed=embed)
    
                            for winner, xp_award in winners:
                                user = await connection.fetchrow('SELECT u_id, xp, level, consecutive_wins FROM users WHERE u_id = $1', winner)
                                if user:
                                    new_xp = user['xp'] + xp_award
                                    new_level = new_xp // 100
                                    new_consecutive_wins = user['consecutive_wins'] + 1
                                    last_win_date = current_timestamp
                                    await connection.execute('UPDATE users SET xp = $1, level = $2, tokens = tokens + 1, consecutive_wins = $3, last_win_date = $4 WHERE u_id = $5',
                                                             new_xp, new_level, new_consecutive_wins, last_win_date, winner)
                                else:
                                    print(f"No user found for u_id: {winner}")
    
                    self.last_winner_announcement_date = current_date
            await asyncio.sleep(60)
    
    
    
    
    
async def setup(bot):
    await bot.add_cog(Contests(bot))