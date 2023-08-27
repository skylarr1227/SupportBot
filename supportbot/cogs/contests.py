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

logger = logging.getLogger('diswcord')
logger.setLevel(logging.ERROR)
handler = logging.FileHandler(filename='errors.log', encoding='utf-8', mode='a')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s\n'))
logger.addHandler(handler)

THEME_CHANNEL_ID = 1144325882257887312
INSPECTION_CHANNEL_ID = 1144006598709219429
PUBLIC_VOTING_CHANNEL_ID = 1144006673829199942
XP_AWARDS = [100, 80, 60, 40, 20] # XP for 1st to 5th places
STRIPE_AUTH = os.environ.get("STRIPE_AUTH")
if STRIPE_AUTH is None:
    logger.error("The STRIPE_AUTH environment variable is missing!\nStripe coupon codes will not be generated until this is corrected in the .env file!")


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

    def cog_unload(self):
        for task in self.tasks:
            task.cancel()

    async def execute_supabase_query(self, func, *args, **kwargs):
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))
        except Exception as e:
            logger.error(f"An error occurred while executing the query: {e}")  # Logging to file
            print(f"An error occurred while executing the query: {e}")  # Logging 
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
        await self.update_phase()  # Immediately update the phase
        await ctx.send(f"Time offset has been set to {offset} hours, and the phase has been updated.")

    @commands.command(aliases=['level'])
    async def xp(self, ctx):
        user_id = ctx.author.id
        query = self.bot.supabase.table('users').select('xp, level').filter('u_id', 'eq', user_id).single()
        user_data = await self.execute_supabase_query(query.execute)

        if user_data and user_data.data:
            xp = user_data.data['xp']
            level = user_data.data['level']
            if xp == 0:
                percentage = 0
            else:
                xp_next_level = 100 * (level + 1)
                percentage = (xp - (100 * level)) * 10 // (xp_next_level - (100 * level))

            

            progress_bar = {
                0: "╍╍╍╍╍╍╍╍╍╍ 0%",
                10: "<:10:1139230034217947237> ▰╍╍╍╍╍╍╍╍╍ 10%",
                20: "<:20:1139230035711119411> ▰▰╍╍╍╍╍╍╍╍ 20%",
                30: "<:30:1139230037405610205> ▰▰▰╍╍╍╍╍╍╍ 30%",
                40: "<:40:1139230021307863140> ▰▰▰▰╍╍╍╍╍╍ 40%",
                50: "<:50:1139230023673462845> ▰▰▰▰▰╍╍╍╍╍ 50%",
                60: "<:60:1139230026030649374> ▰▰▰▰▰▰╍╍╍╍ 60%",
                70: "<:70:1139230027767099412> ▰▰▰▰▰▰▰╍╍╍ 70%",
                80: "<:80:1139230029528715364> ▰▰▰▰▰▰▰▰╍╍ 80%",
                90: "<:90:1139230030757626016> ▰▰▰▰▰▰▰▰▰╍ 90%",
                100: "<:100:1139230032968040479> ▰▰▰▰▰▰▰▰▰▰ 100%",
            }

            await ctx.send(f"Your XP progress to next level:\n{progress_bar[percentage]}")
        else:
            # User not found in 'users' table, insert with default values
            query = self.bot.supabase.table('users').insert({'u_id': user_id, 'xp': 0, 'level': 0})
            await self.execute_supabase_query(query.execute)
            await ctx.send("Welcome! You have been added to the system. You are at level 0 with 0 XP.")



    async def get_theme(self):
        now = datetime.now(timezone('US/Eastern'))
        week_of_year = now.isocalendar()[1]
        day_of_week = calendar.day_name[now.weekday()].lower()
        query = self.bot.supabase.table("contests").select(day_of_week).filter('week', 'eq', week_of_year)
        result = await self.execute_supabase_query(query.execute)
        return result.data[0][day_of_week] if result else None

    async def initialize_contest(self):
        theme_channel = self.bot.get_channel(THEME_CHANNEL_ID)
        theme = await self.get_theme()
        await theme_channel.send(f"Today's theme is:\n{theme}")
        # Send initial phase message
        self.phase_message = await theme_channel.send("Initializing contest phase...")
        await self.update_phase()

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
        # Update 'message_id' in 'artwork' table
        query = self.bot.supabase.table('artwork').update({'message_id': message.id}).match({'u_id': user_id})
        await self.execute_supabase_query(query.execute)


    @commands.Cog.listener()
    async def on_message(self, message):
        if isinstance(message.channel, discord.DMChannel) and len(message.attachments) > 0:
            user_id = message.author.id

            # Check if the user exists in the users table
            query = self.bot.supabase.table('users').select().filter('u_id', 'eq', user_id).single()
            user_data = await self.execute_supabase_query(query.execute)

            # Insert a new user if not exists in 'users' table
            if not user_data or not user_data.data:
                query = self.bot.supabase.table('users').upsert({'u_id': user_id, 'xp': 0, 'level': 0})
                await self.execute_supabase_query(query.execute)

                now = datetime.now(timezone('US/Eastern'))
            current_contest_start_time = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()

            # Check if the user has already submitted an image for the current contest
            query = (
                self.bot.supabase.table('artwork')
                .select('submitted')
                .filter('u_id', 'eq', user_id)
                .filter('submitted', 'gte', current_contest_start_time)
)
            artwork_data = await self.execute_supabase_query(query.execute)

            if artwork_data and artwork_data.data:
                await message.author.send('You have already submitted an image for the current contest. Only one submission is allowed.')
                return

            # Insert a new artwork submission into the 'artwork' table
            artwork_data = {
                'submitted_by': user_id,
                'submitted_on': int(now.timestamp()),
                'message_id': None,  # Will be updated later
                'upvotes': 0,
                'inspected_by': None  # Will be updated later
            }
            query = self.bot.supabase.table('artwork').insert(artwork_data)
            await self.execute_supabase_query(query.execute)

            reply = await message.reply("Do you want to submit this image for the daily contest? (yes/no)")
            def check(m):
                return m.author == message.author and m.channel == message.channel and m.content.lower() in ["yes", "no"]

            try:
                reply = await self.bot.wait_for('message', check=check, timeout=60.0)
            except asyncio.TimeoutError:
                await message.author.send('Sorry, you took too long to reply.')
            else:
                if reply.content.lower() == 'yes' and self.accepting_images:
                    query = self.bot.supabase.table('users').upsert({'u_id': message.author.id, 'submitted': int(datetime.now(timezone('US/Eastern')).timestamp())})
                    await self.execute_supabase_query(query.execute)
                    await self.inspect_image(message.author.id, message.attachments[0].url)
                    await message.author.send('Your image has been submitted for manual inspection.')
                elif reply.content.lower() == 'no':
                    await message.author.send('Okay, your image was not submitted.')

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.channel_id == INSPECTION_CHANNEL_ID:
            channel = self.bot.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)

            if message.embeds and message.embeds[0].description:
                user_id = int(message.embeds[0].description)
                inspector_id = payload.user_id  # Get the ID of the team member who reacted

                if str(payload.emoji) == "👍":
                    # Approve the image
                    await self.post_image(user_id, message.embeds[0].image.url)

                    # Update 'inspected_by' in 'artwork' table
                    query = self.bot.supabase.table('artwork').update({'inspected_by': inspector_id}).match({'u_id': user_id})
                    await self.execute_supabase_query(query.execute)

                elif str(payload.emoji) == "👎":
                    # Disapprove the image
                    query = self.bot.supabase.table('artwork').delete().match({'u_id': user_id})
                    await self.execute_supabase_query(query.execute)
                    await message.author.send('Your image has been rejected.')  # You'll need to adjust this line to correctly send a message to the user


    async def check_time(self):
        last_phase = None
        while True:
            now = datetime.now(timezone('US/Eastern')) + timedelta(hours=self.time_offset) if self.debug else datetime.now(timezone('US/Eastern'))
            if now.hour < 21:
                phase = "In Progress"
            elif now.hour == 21:
                phase = "Voting"
            else:
                phase = "Downtime"
            if phase != last_phase:
                await self.update_phase()
                last_phase = phase
            await asyncio.sleep(60)


    async def count_votes(self):
        while True:
            now = datetime.now(timezone('UTC'))  # Keeping this in UTC for consistency
            if now.hour == 22:
                channel = self.bot.get_channel(PUBLIC_VOTING_CHANNEL_ID)
                query = self.bot.supabase.table('artwork').select('u_id, message_id')
                result = await self.execute_supabase_query(query.execute)

                if result and result.data:
                    for row in result.data:
                        try:
                            message = await channel.fetch_message(row['message_id'])
                            for reaction in message.reactions:
                                if str(reaction.emoji) == "👍":
                                    # Update the 'upvotes' column in the 'artwork' table
                                    query = self.bot.supabase.table('artwork').update({'upvotes': reaction.count}).match({'u_id': row['u_id'], 'message_id': row['message_id']})
                                    await self.execute_supabase_query(query.execute)
                        except Exception as e:
                            print(f"Failed to fetch or process message: {e}")
                            continue

                # Now, you can sort the artworks by the 'upvotes' directly in the database
                # and announce the winners, update XP, etc.

                query = self.bot.supabase.table('artwork').select('u_id, upvotes').order('upvotes', ascending=False).limit(5)
                top_artworks = await self.execute_supabase_query(query.execute)

                if top_artworks and top_artworks.data:
                    winners = [artwork['u_id'] for artwork in top_artworks.data]
                    await channel.send(f"The winners are: {', '.join(f'<@{winner}>' for winner in winners)}")

                    # Update XP and levels for winners
                    for i, winner in enumerate(winners):
                        query = self.bot.supabase.table('users').select('u_id, xp, level').filter('u_id', 'eq', winner).single()
                        user = await self.execute_supabase_query(query.execute)
                        if user and user.data:
                            new_xp = user.data['xp'] + XP_AWARDS[i]
                            new_level = new_xp // 100  # each level requires 100 XP
                            query = self.bot.supabase.table('users').update({'xp': new_xp, 'level': new_level}).match({'u_id': winner})
                            await self.execute_supabase_query(query.execute)
            await asyncio.sleep(60)



async def setup(bot):
    await bot.add_cog(Contests(bot))