from discord.ext import commands, tasks
import discord
from datetime import datetime, timedelta
import asyncio
from supportbot.core.utils import team, support
import time

async def wait_until(timestamp):
    """Pause execution until the specified timestamp."""
    now = time.time()
    delay = timestamp - now
    if delay > 0:
        await asyncio.sleep(delay)

class StreakCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel_ids = [
            774124295524712480,
            909558376793505842,
            931252727743410196,
            980877272938602578
            ]
        self.bot.loop.create_task(self.initialize_daily_records_loop())
        self.bot.loop.create_task(self.check_streaks_loop())

    async def initialize_daily_records_loop(self):
        await self.bot.wait_until_ready()
        await self.initialize_daily_records()  # Run immediately on startup
        while not self.bot.is_closed():
            now = time.time()
            # Calculate the next run time in Unix timestamp format for the next day at 00:01
            next_run = now + (86400 - (now % 86400)) + 60
            await wait_until(next_run)
            await self.initialize_daily_records()

    async def check_streaks_loop(self):
        await self.bot.wait_until_ready()
        await self.check_streaks()  # Run immediately on startup
        while not self.bot.is_closed():
            now = time.time()
            # Calculate the next run time in Unix timestamp format for the next day at 00:05
            next_run = now + (86400 - (now % 86400)) + 300
            await wait_until(next_run)
            await self.check_streaks()


    async def initialize_daily_records(self):
        # Get the start of the day in Unix timestamp format for current_date
        now = time.time()
        midnight_utc = datetime.utcfromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0)
        current_date = int(midnight_utc.timestamp())
        yesterday = current_date - 86400

        records = await self.bot.pool.fetch("SELECT DISTINCT user_id FROM streaks WHERE date = $1 AND streak_count > 0", yesterday)
        for record in records:
            user_id = record['user_id']
            await self.bot.pool.execute("INSERT INTO streaks(user_id, message_count, date) VALUES($1, 0, $2) ON CONFLICT(user_id, date) DO NOTHING", user_id, current_date)



    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if message.channel.id not in self.channel_ids:
            return

        user_id = message.author.id
        display_name = message.author.display_name

        # Get the start of the day in Unix timestamp format
        now = time.time()
        midnight_utc = datetime.utcfromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0)
        current_date = int(midnight_utc.timestamp())

        # Fetch last message time and message count from database
        record = await self.bot.pool.fetchrow("""
            SELECT last_message, message_count FROM streaks WHERE user_id = $1 AND date = $2
        """, user_id, current_date)

        current_time = int(time.time())
        if record:
            last_message_time = record['last_message']
            if last_message_time and (current_time - last_message_time) < 300:
                return

        message_count = record['message_count'] if record and record['message_count'] is not None else 0
        await self.bot.pool.execute("""
            INSERT INTO streaks(user_id, message_count, last_message, date, display_name)
            VALUES($1, 1, $2, $3, $4)
            ON CONFLICT(user_id, date)
            DO UPDATE SET message_count = streaks.message_count + 1, last_message = $2, display_name = $4
        """, user_id, current_time, current_date, display_name)

        new_message_count = message_count + 1
        if new_message_count == 5:
            alert_channel_id = 1164278374445875240  
            alert_channel = self.bot.get_channel(alert_channel_id)
            await alert_channel.send(f"{display_name} has reached 5 messages today!")



    async def check_streaks(self):
        now = time.time()
        midnight_utc = datetime.utcfromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday = int(midnight_utc.timestamp()) - 86400  # Subtract one day's worth of seconds

        # Fetch records for yesterday
        records = await self.bot.pool.fetch("SELECT * FROM streaks WHERE date = $1", yesterday)
        guild_id = 774124295026376755
        guild = self.bot.get_guild(guild_id)
        current_date = int(midnight_utc.timestamp())

        for record in records:
            user_id = record['user_id']
            message_count = record['message_count']
            streak_count = record['streak_count']  # This should fetch the streak count from the previous day
            member = guild.get_member(user_id)
            if not member:
                continue
            display_name = member.display_name

            # If the user has sent 5 or more messages yesterday, increment their streak count
            if message_count >= 5:
                streak_count += 1
            else:
                # Reset their streak if they haven't sent 5 messages
                streak_count = 0

            # Update roles based on the new streak count
            await self.update_roles(member, streak_count)

            # Update the database with the new streak count for the current date
            await self.bot.pool.execute("""
                INSERT INTO streaks(user_id, streak_count, date, display_name)
                VALUES($1, $2, $3, $4)
                ON CONFLICT(user_id, date)
                DO UPDATE SET streak_count = EXCLUDED.streak_count, display_name = EXCLUDED.display_name
            """, user_id, streak_count, current_date, display_name)




    async def update_roles(self, member, streak):
        role_ids = {
            1: 1164160849645158481,
            2: 1164160866061656195,
            3: 1164160879554744380,
            4: 1164160890929696882,
            6: 1164160915793522741,
            7: 1164160929152380938,
            8: 1164160946185457765,
            9: 1164160967739981865,
            11: 1164161002200379464,
            12: 1164161013424345218,
            13: 1164161025503924284,
            14: 1164161037520605326,
            16: 1164161058181754950,
            17: 1164190078218801275,
            18: 1164190117242617876,
            19: 1164190128957304922,
            21: 1164190152776753254,
            22: 1164190161895170229,
            23: 1164190170761924640,
            24: 1164190183994957824,
            26: 1164190210280657018,
            27: 1164190221571739669,
            28: 1164190238533496853,
            29: 1164190276865232966
        }   

        milestone_roles = {
            5: 1164160902879248384, 
            10: 1164160989038661724,
            15: 1164161048283201576,
            20: 1164190140613267497,
            25: 1164190200763777034,
            30: 1164190288697364592
        }  

        roles_to_remove = [role for role in member.roles if role.id in role_ids.values() or role.id in milestone_roles.values()]
        await member.remove_roles(*roles_to_remove)

        # Add new role based on current streak count
        new_role_id = role_ids.get(streak)
        if new_role_id:
            new_role = discord.utils.get(member.guild.roles, id=new_role_id)
            await member.add_roles(new_role)
            alert_channel_id = 1164278374445875240  
            alert_channel = self.bot.get_channel(alert_channel_id)
            await alert_channel.send(f"{member.display_name} has achieved a streak of {streak} days and gained a new role!")

    #
        milestone_role_id = milestone_roles.get(streak)
        if milestone_role_id:
            milestone_role = discord.utils.get(member.guild.roles, id=milestone_role_id)
            await member.add_roles(milestone_role)

            # Send an alert for gaining a milestone streak role
            alert_channel_id = 1164278374445875240  
            alert_channel = self.bot.get_channel(alert_channel_id)
            await alert_channel.send(f"🎉 {member.display_name} has reached a milestone of {streak} days and gained a special role!")

    @team()
    @commands.command(aliases=['streaks', 'leaderboard'])
    async def streak_leaderboard(self, ctx):
        """Displays the streak leaderboard."""
        query = """
        SELECT s1.user_id, s1.streak_count
        FROM streaks s1
        INNER JOIN (
            SELECT user_id, MAX(date) as max_date
            FROM streaks
            GROUP BY user_id
        ) s2 ON s1.user_id = s2.user_id AND s1.date = s2.max_date
        ORDER BY s1.streak_count DESC
        """
        records = await self.bot.pool.fetch(query)
        pages = self.create_leaderboard_pages(records)
        
        # Create initial embed
        embed = discord.Embed(title="Streak Leaderboard", description=pages[0])
        message = await ctx.send(embed=embed)
        
        # Add reactions for pagination
        await message.add_reaction("⬅️")
        await message.add_reaction("➡️")
        
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["⬅️", "➡️"]
        
        page = 0
        while True:
            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
            except asyncio.TimeoutError:
                return

            if str(reaction.emoji) == "⬅️":
                page -= 1
                if page < 0:
                    page = len(pages) - 1
            elif str(reaction.emoji) == "➡️":
                page += 1
                if page >= len(pages):
                    page = 0

            await message.edit(embed=discord.Embed(title="Streak Leaderboard", description=pages[page]))
            await message.remove_reaction(reaction, user)

    def create_leaderboard_pages(self, records):
        """Creates paginated content for the leaderboard."""
        items_per_page = 10
        pages = []
        for i in range(0, len(records), items_per_page):
            page = ""
            for j, record in enumerate(records[i:i + items_per_page], start=i+1):
                member = self.bot.get_user(record['user_id'])
                if member:
                    page += f"{j}. {member.name} - {record['streak_count']} days\n"
            pages.append(page)
        return pages
    

    @team()
    @commands.command()
    async def reset_streak(self, ctx, member: discord.Member):
        current_date = datetime.utcnow().date()
        await self.bot.pool.execute("INSERT INTO streaks(user_id, message_count, streak_count, date) VALUES($1, 0, 0, $4) ON CONFLICT(user_id, date) DO UPDATE SET message_count = 0, streak_count = 0", member.id, current_date)
        await self.update_roles(member, 0)
        await ctx.send(f"Streak for {member.mention} has been reset.")


async def setup(bot):
    await bot.add_cog(StreakCog(bot))
