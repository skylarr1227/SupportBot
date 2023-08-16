import discord
from discord.ext import commands
from discord import app_commands
from supportbot.core.utils import team, support, store_in_supabase, store_prompt

announcer_role_name = "announcer_role_placeholder"


class Announcements(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.announcer_role_name = "announcer_role_placeholder"  # You'll replace this with your actual role name
        self.review_message = None  # The message used for review

    @team()
    @app_commands.command()
    async def set_announcement(self, interaction, announcement:str):
        # Insert the announcement into the database
        ctx = await self.bot.get_context(interaction)
        query = f"""
        INSERT INTO announcements (announcement)
        VALUES ({announcement})
        """
        await self.bot.db.execute(query)

        await ctx.send(f"Announcement set: {announcement}")

    @team()
    @app_commands.command()
    async def submit_announcement_addition(self, interaction, addition:str):
        # Append the submission to the submissions array in the database
        ctx = await self.bot.get_context(interaction)
        query = f"""
        UPDATE announcements
        SET submissions = array_append(submissions, {addition})
        WHERE id = 1
        """
        await self.bot.db.execute(query)

        await ctx.send(f"Your submission has been received: {addition}")

    @team()
    @app_commands.command()
    async def review_submissions(self, ctx):
        # Get the first submission from the database
        ctx = await self.bot.get_context(interaction)
        query = f"""
        SELECT submissions[1] FROM announcements
        WHERE id = 1
        """
        submission = await self.bot.db.fetchval(query)

        if not submission:
            await ctx.send("No submissions to review.")
            return

        self.review_message = await ctx.send(f"Review submission: {submission}")
        await self.review_message.add_reaction("👍")
        await self.review_message.add_reaction("👎")


    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if reaction.message.id != self.review_message.id:
            return
        ctx = await self.bot.get_context(interaction)
        if str(reaction.emoji) == "👍":
            # The submission was approved
            query = f"""
            UPDATE announcements
            SET announcement = announcement || ' ' || submissions[1]
            WHERE id = 1
            """
            await self.bot.db.execute(query)

            await reaction.message.channel.send("Submission approved.")
        elif str(reaction.emoji) == "👎":
            # The submission was denied
            await reaction.message.channel.send("Submission denied.")

        # Remove the first submission from the array
        query = f"""
        UPDATE announcements
        SET submissions = array_remove(submissions, submissions[1])
        WHERE id = 1
        """
        await self.bot.db.execute(query)

        self.review_message = None  # Reset the review message

    @team()
    @app_commands.command()
    async def update_announcement(self, ctx, *, announcement):
        # Update the announcement in the database
        ctx = await self.bot.get_context(interaction)
        query = f"""
        UPDATE announcements
        SET announcement = {announcement}
        WHERE id = 1
        """
        await self.bot.db.execute(query)

        await ctx.send(f"Announcement updated: {announcement}")

    @team()
    @app_commands.command()
    async def send_for_review(self, ctx, member: discord.Member):
        # Get the announcement from the database
        ctx = await self.bot.get_context(interaction)
        query = f"""
        SELECT announcement FROM announcements
        WHERE id = 1
        """
        announcement = await self.bot.db.fetchval(query)

        await member.send(f"Please review the announcement: {announcement}")

async def setup(bot):
    await bot.add_cog(Announcements(bot))
