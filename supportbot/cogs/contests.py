import asyncio
import calendar
from datetime import datetime, timedelta
from pytz import timezone
from discord.ext import commands
import discord
import functools

THEME_CHANNEL_ID = 1141383309591588934
INSPECTION_CHANNEL_ID = 1144006598709219429
PUBLIC_VOTING_CHANNEL_ID = 1144006673829199942
XP_AWARDS = [100, 80, 60, 40, 20] # XP for 1st to 5th places

class Contests(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.debug = False
        self.time_offset = 0
        self.accepting_images = True
        self.phase_message = None  
        self.bot.loop.create_task(self.check_time())
        self.bot.loop.create_task(self.count_votes())

    async def execute_supabase_query(self, func, *args, **kwargs):
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))
        except Exception as e:
            print(f"An error occurred while executing the query: {e}")  # Logging 
            return None

    @commands.command(name='setdebug')
    async def set_debug(self, ctx, debug: bool):
        self.debug = debug
        status = "enabled" if debug else "disabled"
        await ctx.send(f"Debug mode has been {status}.")

    @commands.command(name='setoffset')
    async def set_offset(self, ctx, offset: int):
        self.time_offset = offset
        await ctx.send(f"Time offset has been set to {offset} hours.")

    @commands.command(aliases=['level'])
    async def xp(self, ctx):
        user_id = str(ctx.author.id)
        query = self.bot.supabase.table('users').select('xp, level').filter('u_id', 'eq', user_id).single()
        user_data = await self.execute_supabase_query(query.execute)

        if user_data and user_data.data:
            xp = user_data.data['xp']
            level = user_data.data['level']
            xp_next_level = 100 * (level + 1)  # Assuming 100 XP per level
            percentage = (xp - (100 * level)) * 10 // (xp_next_level - (100 * level))

            progress_bar = {
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
            await ctx.send("Could not retrieve your information.")



    async def get_theme(self):
        now = datetime.now(timezone('UTC'))
        week_of_year = now.isocalendar()[1]
        day_of_week = calendar.day_name[now.weekday()].lower()
        query = self.bot.supabase.table("contests").select(day_of_week).filter('week', 'eq', week_of_year)
        result = await self.execute_supabase_query(query.execute)
        return result.data[0][day_of_week] if result else None

    @commands.Cog.listener()
    async def on_ready(self):
        theme_channel = self.bot.get_channel(THEME_CHANNEL_ID)
        theme = await self.get_theme()
        await theme_channel.send(f"Today's theme is: {theme}")
        # Send initial phase message
        self.phase_message = await theme_channel.send("Initializing contest phase...")
        await self.update_phase()

    async def update_phase(self):
        now = datetime.now(timezone('UTC')) + timedelta(hours=self.time_offset) if self.debug else datetime.now(timezone('UTC'))
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
        message = await channel.send(f"New image submission from <@{user_id}> for inspection:", embed=discord.Embed().set_image(url=image_url))
        await message.add_reaction("👍")
        await message.add_reaction("👎")

    async def post_image(self, user_id, image_url):
        channel = self.bot.get_channel(PUBLIC_VOTING_CHANNEL_ID) 
        message = await channel.send(f"Image submission from <@{user_id}>:", embed=discord.Embed().set_image(url=image_url))
        await message.add_reaction("👍")
        query = self.bot.supabase.table('users').update({'message_id': message.id}).match({'u_id': user_id})
        await self.execute_supabase_query(query.execute)


    @commands.Cog.listener()
    async def on_message(self, message):
        if isinstance(message.channel, discord.DMChannel) and len(message.attachments) > 0:
            reply = await message.reply("Do you want to submit this image for the daily contest? (yes/no)")
            def check(m):
                return m.author == message.author and m.channel == message.channel and m.content.lower() in ["yes", "no"]

            try:
                reply = await self.bot.wait_for('message', check=check, timeout=60.0)
            except asyncio.TimeoutError:
                await message.author.send('Sorry, you took too long to reply.')
            else:
                if reply.content.lower() == 'yes' and self.accepting_images:
                    query = self.bot.supabase.table('users').upsert({'u_id': message.author.id, 'submitted': int(datetime.now(timezone('UTC')).timestamp())})
                    await self.execute_supabase_query(query.execute)
                    await self.inspect_image(message.author.id, message.attachments[0].url)
                    await message.author.send('Your image has been submitted for manual inspection.')
                elif reply.content.lower() == 'no':
                    await message.author.send('Okay, your image was not submitted.')

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.channel_id == INSPECTION_CHANNEL_ID and payload.user_id in self.bot.WOMBO_SUPPORT:
            channel = self.bot.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)

            if str(payload.emoji) == "👍":
                user_id = message.embeds[0].description.split("<@")[1].split(">")[0]
                image_url = message.embeds[0].image.url
                await self.post_image(user_id, image_url)

    async def check_time(self):
        last_phase = None
        while True:
            now = datetime.now(timezone('UTC')) + timedelta(hours=self.time_offset) if self.debug else datetime.now(timezone('UTC'))
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
            now = datetime.now(timezone('UTC')) + timedelta(hours=self.time_offset) if self.debug else datetime.now(timezone('UTC'))
            if now.hour == 22:
                channel = self.bot.get_channel(PUBLIC_VOTING_CHANNEL_ID)
                vote_counts = {}
                result = await self.bot.supabase.table('users').select('u_id, message_id').execute()

                for row in result.data:
                    message = await channel.fetch_message(row['message_id'])
                    for reaction in message.reactions:
                        if str(reaction.emoji) == "👍":
                            vote_counts[row['u_id']] = reaction.count

                winners = sorted(vote_counts, key=vote_counts.get, reverse=True)[:5]
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