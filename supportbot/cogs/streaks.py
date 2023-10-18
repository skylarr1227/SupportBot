from discord.ext import commands, tasks
import discord
from datetime import datetime, timedelta, time
import asyncio
from supportbot.core.utils import team, support


class StreakCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel_ids = [1234567890, 0987654321]  # Replace with your channel IDs
        self.initialize_daily_records.start(at=time(hour=0, minute=1))
        self.check_streaks.start(at=time(hour=0, minute=5))

    @tasks.loop(hours=24)
    async def initialize_daily_records(self):
        current_date = datetime.utcnow().date()
        yesterday = current_date - timedelta(days=1)
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
        current_date = datetime.utcnow().date()
        await self.bot.pool.execute("""
            INSERT INTO streaks(user_id, message_count, last_message, date)
            VALUES($1, 1, $2, $3)
            ON CONFLICT(user_id, date)
            DO UPDATE SET message_count = streaks.message_count + 1, last_message = $2
        """, user_id, datetime.utcnow(), current_date)

    @tasks.loop(hours=24)
    async def check_streaks(self):
        yesterday = datetime.utcnow().date() - timedelta(days=1)
        records = await self.bot.pool.fetch("SELECT * FROM streaks WHERE date = $1", yesterday)
        for record in records:
            user_id = record['user_id']
            message_count = record['message_count']
            streak_count = record['streak_count']
            member = self.bot.get_user(user_id)
            if member is None:
                continue

            current_date = datetime.utcnow().date()
            if message_count >= 5:
                streak_count += 1
                await self.update_roles(member, streak_count)
                await self.bot.pool.execute("INSERT INTO streaks(user_id, streak_count, date) VALUES($1, $2, $3) ON CONFLICT(user_id, date) DO UPDATE SET streak_count = $2", user_id, streak_count, current_date)
            else:
                await self.update_roles(member, 0)
                await self.bot.pool.execute("INSERT INTO streaks(user_id, streak_count, date) VALUES($1, 0, $3) ON CONFLICT(user_id, date) DO UPDATE SET streak_count = 0", user_id, current_date)


    async def update_roles(self, member, streak):
        role_ids = [
            1164160849645158481, # 1
            1164160866061656195, # 2
            1164160879554744380, # 3
            1164160890929696882, # 4
            1164160915793522741, # 6
            1164160929152380938, # 7
            1164160946185457765, # 8
            1164160967739981865, # 9
            1164161002200379464, # 11
            1164161013424345218, # 12 
            1164161025503924284, # 13 
            1164161037520605326, # 14
            1164161058181754950, # 16
            1164190078218801275, # 17
            1164190117242617876, # 18
            1164190128957304922, # 19 
            1164190152776753254, # 21
            1164190161895170229, # 22
            1164190170761924640, # 23
            1164190183994957824, # 24
            1164190210280657018, # 26
            1164190221571739669, # 27
            1164190238533496853, # 28
            1164190276865232966 # 29

            ]  
        milestone_roles = {
            5: 1164160902879248384, 
            10: 1164160989038661724,
            15: 1164161048283201576,
            20: 1164190140613267497,
            25: 1164190200763777034,
            30: 1164190288697364592
            }  

        roles_to_remove = [role for role in member.roles if role.id in role_ids or role.id in milestone_roles.values()]
        await member.remove_roles(*roles_to_remove)

        new_role = discord.utils.get(member.guild.roles, id=streak)
        if new_role:
            await member.add_roles(new_role)

        if streak in milestone_roles:
            milestone_role = discord.utils.get(member.guild.roles, id=milestone_roles[streak])
            if milestone_role:
                await member.add_roles(milestone_role)

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
