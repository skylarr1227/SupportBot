import discord
from discord.ext import commands





class Contest_util(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    async def is_special_week(self, now):
        current_week = now.isocalendar()[1]
        async with self.bot.pool.acquire() as connection:
            row = await connection.fetchrow('SELECT special FROM contests WHERE week = $1', current_week)
            return row['special'] if row else False



    def determine_phase(self, now, is_special_week):
        """
        Determines the current phase based on the day and time.
        Parameters:
            now (datetime): Current datetime object
        """
        current_phase = None
        if now.weekday() in [0, 2]:  # Monday and Wednesday
            if 0 <= now.hour < 24:
                current_phase = "Submission Phase (12:00am - 11:59pm EST)"
        elif now.weekday() in [1, 3]:  # Tuesday and Thursday
            if 0 <= now.hour < 22:
                current_phase = "Voting Phase (12:00am - 9:59pm EST)"
            elif 22 <= now.hour < 23:
                current_phase = "Downtime (10:00pm - 11:00pm EST)"
        elif is_special_week and 0 <= now.weekday() < 5:  # Monday to Friday
            if 0 <= now.hour < 24:
                current_phase = "Special Contest Submission Phase (12:00am - 11:59pm EST)"
        elif is_special_week and now.weekday() == 5:  # Saturday
            current_phase = "Special Contest Voting (Whole Day)"
        elif is_special_week and now.weekday() == 6:  # Sunday
            current_phase = "Special Contest Downtime (Whole Day)"
        return current_phase

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


async def setup(bot):
    await bot.add_cog(Contest_util(bot))
