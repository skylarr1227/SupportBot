import asyncio
import calendar
from datetime import datetime, timedelta
from pytz import timezone
from discord.ext import commands
import discord

THEME_CHANNEL_ID = 
INSPECTION_CHANNEL_ID = 
PUBLIC_VOTING_CHANNEL_ID = 

class Contests(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.accepting_images = True
        self.bot.loop.create_task(self.check_time())
        self.bot.loop.create_task(self.count_votes())

    async def get_theme(self):
        now = datetime.now(timezone('UTC'))
        week_of_year = now.isocalendar()[1]
        day_of_week = calendar.day_name[now.weekday()].lower()
        result = await self.bot.supabase.table("contests").select(day_of_week).filter('week', 'eq', week_of_year).execute()
        return result.data[0][day_of_week]

    @commands.Cog.listener()
    async def on_ready(self):
        theme = await self.get_theme()
        channel = self.bot.get_channel(THEME_CHANNEL_ID)  
        await channel.send(f"Today's theme is: {theme}")

    async def inspect_image(self, user_id, image_url):
        channel = self.bot.get_channel(INSPECTION_CHANNEL_ID)  
        message = await channel.send(f"New image submission from <@{user_id}> for inspection:", embed=discord.Embed().set_image(url=image_url))
        await message.add_reaction("👍")
        await message.add_reaction("👎")

    async def post_image(self, user_id, image_url):
        channel = self.bot.get_channel(PUBLIC_VOTING_CHANNEL_ID) 
        message = await channel.send(f"Image submission from <@{user_id}>:", embed=discord.Embed().set_image(url=image_url))
        await message.add_reaction("👍")
        # Update the user's record in the "users" table in Supabase with the message ID
        await self.bot.supabase.table('users').update({'message_id': message.id}).match({'u_id': user_id}).execute()

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
                    await self.bot.supabase.table('users').upsert({'u_id': message.author.id, 'submitted': int(datetime.now(timezone('UTC')).timestamp())}).execute()
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
        while True:
            now = datetime.now(timezone('UTC'))
            if now.hour == 21:
                self.accepting_images = False
            else:
                self.accepting_images = True
            await asyncio.sleep(60)

    async def count_votes(self):
        while True:
            now = datetime.now(timezone('UTC'))

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
                xp_awards = [100, 80, 60, 40, 20]  # XP for 1st to 5th places
                for i, winner in enumerate(winners):
                    user = await self.bot.supabase.table('users').select('u_id, xp, level').filter('u_id', 'eq', winner).single().execute()
                    new_xp = user.data['xp'] + xp_awards[i]
                    new_level = new_xp // 100  # each level requires 100 XP
                    await self.bot.supabase.table('users').update({'xp': new_xp, 'level': new_level}).match({'u_id': winner}).execute()
            await asyncio.sleep(60)

async def setup(bot):
    await bot.add_cog(Contests(bot))