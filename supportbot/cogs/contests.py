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
import time as _time


logger = logging.getLogger('discord')
logger.setLevel(logging.ERROR)
handler = logging.FileHandler(filename='errors.log', encoding='utf-8', mode='a')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s\n'))
logger.addHandler(handler)

LOGGING_CHANNEL_ID = 1148813364953358431  

INSPECTION_CHANNEL_ID = 1148813803774033981
PUBLIC_VOTING_CHANNEL_ID = 1148811099328753675
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

.set_offse4t

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
        self.THEME_CHANNEL_ID = 123
        self.prev_day_theme_message = None
    ### Helper Functions
    
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
            await connection.execute('UPDATE artwork SET message_id = $1, link = $3 WHERE submitted_by = $2', message.id, user_id, image_url)
    

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


    async def create_special_contest_channel(self):
        """Creates a new channel for the special contest in the specified category."""
        guild = self.bot.get_guild(914705867855773746)  
        category = discord.utils.get(guild.categories, name="Daily Contest Testing")  
        if not category:
            return  # Return if the category doesn't exist
        current_date = datetime.now().date()
        channel_name = f"special-contest-{current_date}"
        # Create the channel
        special_channel = await guild.create_text_channel(channel_name, category=category)
        # Save the channel ID
        self.special_channel_id = special_channel.id
        return special_channel

    async def delete_special_contest_channel(self):
        """Deletes the special contest channel."""
        guild = self.bot.get_guild(914705867855773746)  
        if hasattr(self, 'special_channel_id'):
            channel = guild.get_channel(self.special_channel_id)
            if channel:
                await channel.delete()
                del self.special_channel_id  

    async def get_theme(self, target_date=None):
        if target_date is None:
            target_date = datetime.now(timezone('US/Eastern'))
        week_of_year = target_date.isocalendar()[1]
        day_of_week = calendar.day_name[target_date.weekday()].lower()
        async with self.bot.pool.acquire() as connection:
            query = f'SELECT {day_of_week} FROM contests WHERE week = $1'
            row = await connection.fetchrow(query, week_of_year)
            return row[day_of_week] if row else None

    def cog_unload(self):
        if self.theme_message:
            loop = asyncio.get_event_loop()
            loop.create_task(self.edit_theme_message())
        for task in self.tasks:
            task.cancel()

    ### Submission and Inspection listeners
    
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
                        self.bot.SUBMITTED_TRACK.inc()
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
                        if message.embeds and message.embeds[0].image:
                            embed_image_url = message.embeds[0].image.url
                            await self.post_image(user_id, embed_image_url)
                        else:
                            print("No embeds found or no image URL in the first embed.")
                        
                        await connection.execute('UPDATE artwork SET inspected_by = $1 WHERE submitted_by = $2', inspector_id, user_id)
                        await logging_channel.send(f"👍 <@{user_id}>, your image has been approved!")
                    elif str(payload.emoji) == "👎":
                        # DENY
                        await connection.execute('DELETE FROM artwork WHERE submitted_by = $1', user_id)
                        await logging_channel.send(f"👎 <@{user_id}>, your image has been denied.")
                        #self.bot.SUBMITTED_TRACK.dec()
                    # Clear the reactions after inspection
                    await message.clear_reactions()

    
    ### Commands
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
        # Create datetime objects for the end of each phase today
        end_in_progress = now.replace(hour=17, minute=59, second=59, microsecond=999999)
        end_voting = now.replace(hour=18, minute=59, second=59, microsecond=999999)
        end_downtime = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        # Convert to epoch
        epoch_end_in_progress = int(_time.mktime(end_in_progress.timetuple()))
        epoch_end_voting = int(_time.mktime(end_voting.timetuple()))
        epoch_end_downtime = int(_time.mktime(end_downtime.timetuple()))
        # Determine the current phase and its epoch end time
        current_phase = None
        epoch_end = None
        if 0 <= now.hour < 21:
            current_phase = "In Progress"
            epoch_end = epoch_end_in_progress
        elif 21 <= now.hour < 22:
            current_phase = "Voting"
            epoch_end = epoch_end_voting
        else:
            current_phase = "Downtime"
            epoch_end = epoch_end_downtime
        
        embed = discord.Embed(
            title="Contest Stats",
            description=f"# Current Phase:\n {current_phase} (Ends at <t:{epoch_end}:R>)\n\n### Overview/Times\n- End of In-Progress Phase: <t:{epoch_end_in_progress}:R>\n- End of Voting Phase: <t:{epoch_end_voting}:R>\n- End of Downtime: <t:{epoch_end_downtime}:R>",
            color=random.randint(0, 0xFFFFFF)
        )
        await ctx.send(embed=embed)


    @commands.command(aliases=['level'])
    async def xp(self, ctx):
        user_id = ctx.author.id
        async with self.bot.pool.acquire() as connection:
            row = await connection.fetchrow('SELECT xp, level FROM users WHERE u_id = $1', user_id)
    
            if row:
                # Calculate the level based on the XP
                xp = row['xp']
                level = xp // 100  # 100 XP needed for each level
    
                # Calculate the percentage progress to the next level
                remaining_xp = xp % 100  # XP remaining to reach the next level
                percentage = int((remaining_xp / 100) * 100)  # Percentage of progress to next level
    
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
    


    
    ### Core functions, for starting, running, and keeping time etc.


    async def initialize_contest(self):
        try:
            user = self.bot.get_user(790722073248661525)
            await user.send('Do you want to start the contests? Please reply with yes or no.')
            response = await self.bot.wait_for('message', check=lambda message: message.author == user)
            if response.content.lower() != 'yes':
                return
            await user.send('Please enter the ID of the channel to post the message in.')
            response = await self.bot.wait_for('message', check=lambda message: message.author == user)
            channel_id = int(response.content)
            self.THEME_CHANNEL_ID = channel_id
            theme_channel = self.bot.get_channel(channel_id)    

            now = datetime.now(timezone('US/Eastern')) + timedelta(hours=self.time_offset) if self.debug else datetime.now(timezone('US/Eastern'))
            current_week = now.isocalendar()[1]
            async with self.bot.pool.acquire() as connection:
                row = await connection.fetchrow('SELECT special FROM contests WHERE week = $1', current_week)
                is_special_week = row['special'] if row else False  

            # Check if the phase message exists
            if self.phase_message is None:
                prev_day = now - timedelta(days=1)
                prev_theme = await self.get_theme(target_date=prev_day)
                prev_embed = discord.Embed(title="Previous Day's Theme", description=prev_theme, color=0xFF0000)
                self.phase_message = await theme_channel.send(embed=prev_embed) 

            await self.update_phase()
            self.bot.TOTAL_CONTESTS.inc()
            print("Contest initialized")
        except Exception as e:
            print(f"Failed to initialize contest: {e}")



    
    async def update_phase(self):
        """
        Updates the contest phase and sets the appropriate message and status flags.

        This function checks the current time and day of the week to determine
        what phase the contest is in. It also considers whether the current week
        is a special week or a regular week to set the phase.
        """
        now = datetime.now(timezone('US/Eastern')) + timedelta(hours=self.time_offset) if self.debug else datetime.now(timezone('US/Eastern'))
        current_phase = None

        # Fetch the 'is_special_week' value from the database
        async with self.bot.pool.acquire() as connection:
            current_week = now.isocalendar()[1]
            row = await connection.fetchrow('SELECT special FROM contests WHERE week = $1', current_week)
            is_special_week = row['special'] if row else False

        # If it's a special contest week
        if is_special_week:
            if 0 <= now.weekday() < 5:  # Monday to Friday
                current_phase = "<:PRO2:1146213220546269255><:PRO:1146213269242126367>"  # In Progress
                self.accepting_images = True
                self.STARTED = now
            elif now.weekday() == 5:  # Saturday
                current_phase = "<:vote:1146208634322296923>"  # Voting
                self.accepting_images = False
            elif now.weekday() == 6:  # Sunday
                current_phase = "<:down3:1146208635953873016><:down2:1146208638843748372>"  # Downtime
                self.accepting_images = False
        ### Regular Week Schedule 
        else:
            if now.weekday() == 0:  # Monday
                current_phase = "<:PRO2:1146213220546269255><:PRO:1146213269242126367>"  # In Progress
                self.accepting_images = True
                self.STARTED = now
            elif now.weekday() == 1:  # Tuesday
                if 0 <= now.hour < 12:  # 12:00am - 11:59am
                    current_phase = "<:vote:1146208634322296923>"  # Voting
                    self.accepting_images = False
                else:
                    current_phase = "<:down3:1146208635953873016><:down2:1146208638843748372>"  # Downtime
                    self.accepting_images = False
            elif now.weekday() == 2:  # Wednesday
                current_phase = "<:PRO2:1146213220546269255><:PRO:1146213269242126367>"  # In Progress
                self.accepting_images = True
                self.STARTED = now
            elif now.weekday() == 3:  # Thursday
                if 0 <= now.hour < 12:  # 12:00am - 11:59am
                    current_phase = "<:vote:1146208634322296923>"  # Voting
                    self.accepting_images = False
                else:
                    current_phase = "<:down3:1146208635953873016><:down2:1146208638843748372>"  # Downtime
                    self.accepting_images = False

        # Update the current phase message
        if self.phase_message:
            await self.phase_message.edit(content=f"{current_phase}")




    async def check_time(self):
        last_phase = None
        theme_channel = self.bot.get_channel(self.THEME_CHANNEL_ID)
        alert_sent_0930 = False
        alert_sent_2100 = False  # Changed to 9 PM
        downtime_message_sent = False
    
        async with self.bot.pool.acquire() as connection:
            row = await connection.fetchrow('SELECT contests_state FROM tasks WHERE contests_time = (SELECT MAX(contests_time) FROM tasks)')
            if row:
                state_data = row['contests_state']
                alert_sent_0930, alert_sent_2100, downtime_message_sent = map(bool, map(int, state_data.split(',')))
    
        while True:
            now = datetime.now(timezone('US/Eastern')) + timedelta(hours=self.time_offset) if self.debug else datetime.now(timezone('US/Eastern'))
            current_phase = None
            
            # Fetching the 'is_special_week' value from the database
            current_week = now.isocalendar()[1]
            async with self.bot.pool.acquire() as connection:
                row = await connection.fetchrow('SELECT special FROM contests WHERE week = $1', current_week)
                is_special_week = row['special'] if row else False
    
            # Time frames for each phase
            if now.weekday() in [0, 2]:  # Regular contests on Monday and Wednesday
                if 0 <= now.hour < 21:  # 12:00am - 8:59pm
                    current_phase = "In Progress (12:00am - 8:59pm EST)"
                elif 21 <= now.hour < 22:  # 9:00pm - 9:59pm
                    current_phase = "Voting (9:00pm - 9:59pm EST)"
                else:  # 10:00pm - 11:59pm
                    current_phase = "Downtime (10:00pm - 11:59pm EST)"
            elif is_special_week and 0 <= now.weekday() < 5:  # Special contest from Monday to Friday
                if 0 <= now.hour < 24:  # 12:00am - 11:59pm
                    current_phase = "Special Contest In Progress (12:00am - 11:59pm EST)"
            elif is_special_week and now.weekday() == 5:  # Special contest voting phase on Saturday
                current_phase = "Special Contest Voting (Whole Day)"
            elif is_special_week and now.weekday() == 6:  # Special contest downtime on Sunday
                current_phase = "Special Contest Downtime (Whole Day)"
            # Else, there is no contest (i.e., Friday, Saturday, Sunday for non-special weeks)
            if is_special_week and now.weekday() == 0 and now.hour == 0:  # Monday 12:00 AM
                await self.create_special_contest_channel()
            elif is_special_week and now.weekday() == 6 and now.hour == 23:  # Sunday 11:00 PM
                await self.delete_special_contest_channel()
            if current_phase != last_phase:
                await self.update_phase()
                if "Downtime" in current_phase and not downtime_message_sent:
                    self.bot.SUBMITTED_TRACK.set(0)
                    await theme_channel.send("The contest has ended for today. Enjoy a few hours of downtime!")
                    downtime_message_sent = True
                last_phase = current_phase
    
            current_time_str = now.strftime('%H:%M')
            state_changed = False
            if current_time_str == '09:00' and not alert_sent_0930:
                await theme_channel.send("Contest Alert! Plenty of time left in the 'In Progress' phase. It's 9:00 AM EST now.")
                alert_sent_0930 = True
                state_changed = True
            elif current_time_str == '21:00' and not alert_sent_2100:  # Changed to 9 PM
                await theme_channel.send("LAST CALL! Voting starts now and will be open until 10:00 PM EST!")
                alert_sent_2100 = True
                state_changed = True
            elif current_time_str == '00:00':
                alert_sent_0930 = False
                alert_sent_2100 = False
                downtime_message_sent = False
                state_changed = True
            
            if state_changed:
                state_str = f"{int(alert_sent_0930)},{int(alert_sent_2100)},{int(downtime_message_sent)}"
                async with self.bot.pool.acquire() as connection:
                    await connection.execute('INSERT INTO tasks (contests_state, contests_time) VALUES ($1, $2)', state_str, int(now.timestamp()))
            await asyncio.sleep(55) 
    


    async def count_votes(self):
        while True:
            now = datetime.now(timezone('US/Eastern'))
            current_date = now.date()
            current_timestamp = int(now.timestamp())
            if now.hour == 22:
                if self.last_winner_announcement_date != current_date:
                    current_contest_start_time = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
                    channel = self.bot.get_channel(PUBLIC_VOTING_CHANNEL_ID)
                    theme_channel = self.bot.get_channel(self.THEME_CHANNEL_ID)
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
            await asyncio.sleep(59)
    
    
    
    
async def setup(bot):
    await bot.add_cog(Contests(bot))
