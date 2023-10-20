from discord.ext import commands, tasks
import discord
import asyncio
import asyncpg
import random
import string
import time
import re
from supportbot.core.utils import team
import json
from decimal import Decimal

def generate_progress_bar(self, percentage):
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

class ArtContest(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.submission_count = 0
        self.approved_count = 0
        self.denied_count = 0
        self.is_submission_phase = False 
        self.is_voting_phase = False
        self.user_votes = {}
        self.current_contest_id = None
        self.ANNOUNCEMENT_CHANNEL_ID =  None 
        self.STAFF_CHANNEL_ID = None
        self.VOTING_CHANNEL_ID = None
        self.UPDATES_CHANNEL = None
        self.load_channels()
        self.staff_channel_id = self.STAFF_CHANNEL_ID
        self.voting_channel_id = self.VOTING_CHANNEL_ID

    async def load_channels(self):
        async with self.bot.pool.acquire() as connection:
            config_data_str = await connection.fetchval('SELECT contests FROM settings WHERE id = 1')

        config_data = json.loads(config_data_str)

        self.ANNOUNCEMENT_CHANNEL_ID = config_data.get('ANNOUNCEMENT_CHANNEL_ID', '0')
        self.STAFF_CHANNEL_ID = config_data.get('STAFF_CHANNEL_ID', '0')
        self.VOTING_CHANNEL_ID = config_data.get('VOTING_CHANNEL_ID', '0')
        self.UPDATES_CHANNEL = config_data.get('UPDATES_CHANNEL', '0')

    async def generate_contest_id(self):
        """Generate a unique contest ID and check its uniqueness in the database."""
        unique = False
        while not unique:
            letters = ''.join(random.choice(string.ascii_uppercase) for i in range(4))
            numbers = ''.join(random.choice(string.digits) for i in range(4))
            contest_id = f"{letters}-{numbers}"
            async with self.bot.pool.acquire() as connection:
                exists = await connection.fetchval('SELECT COUNT(*) FROM contests WHERE contest_id = $1', contest_id)
            if exists == 0:
                unique = True
        return contest_id
    
    @team()
    @commands.command()
    async def config(self, ctx, config_name: str, channel_id: int):
        """
        Update a channel ID in the configuration.
        """
        # Convert the config_name to uppercase
        config_name = config_name.upper()

        # Validate the config_name
        valid_configs = ['ANNOUNCEMENT_CHANNEL_ID', 'STAFF_CHANNEL_ID', 'VOTING_CHANNEL_ID', 'UPDATES_CHANNEL']
        if config_name not in valid_configs:
            await ctx.send(f"Invalid configuration name. Choose from {', '.join(valid_configs)}")
            return

        async with self.bot.pool.acquire() as connection:
            # Fetch existing data
            config_data_str = await connection.fetchval('SELECT contests FROM settings WHERE id = 1')

            # Deserialize the JSON string into a Python dictionary
            config_data = json.loads(config_data_str)

            # Update the specific field
            config_data[config_name] = str(channel_id)

            # Serialize the updated Python dictionary back into a JSON string
            updated_config_data_str = json.dumps(config_data)

            # Update the database
            await connection.execute('UPDATE settings SET contests = $1 WHERE id = 1', updated_config_data_str)

        # Reload the configuration
        await self.load_channels() 
        await ctx.send(f"Configuration {config_name} updated successfully.")


    @team()
    @commands.command()
    async def start_contest(self, ctx):
        """Start a new art contest."""
        # Generate a unique contest ID
        self.current_contest_id = self.generate_contest_id()
        # Ask questions about the contest
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        questions = [
            "Is this a 24h contest or 48 hour contest? (12h phases vs. 24hour phases)",
            "What is the theme of this contest?",
            "Any specific rules/regulations?",
            "Would you like to submit a cover image for this contest? (provide link to image)"
        ]

        answers = {}
        for question in questions:
            await ctx.send(question)
            try:
                message = await self.bot.wait_for('message', timeout=60.0, check=check)
            except asyncio.TimeoutError:
                await ctx.send("You took too long to respond. Try again.")
                return

            answers[question] = message.content
        
        self.is_submission_phase = True
        # Calculate phase timings based on the contest duration
        duration = 12 if answers[questions[0]] == "24h" else 24
        submission_end_time = int(time.time()) + (duration * 3600)
        voting_end_time = submission_end_time + (duration * 3600)

        asyncio.create_task(self.end_submission_phase(submission_end_time))
        asyncio.create_task(self.end_voting_phase(voting_end_time))

        # Create an announcement embed
        embed = discord.Embed(title="New Art Contest Started!")
        embed.add_field(name="Theme", value=answers[questions[1]], inline=False)
        embed.add_field(name="Requirements", value=answers[questions[2]], inline=False)
        embed.add_field(name="Schedule", value=f"- Submission phase ends: {submission_end_time}\n- Voting Phase begins: {submission_end_time}\n- Voting Phase ends: {voting_end_time}", inline=False)
        
        cover_image_url = answers[questions[3]]
        if re.match(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', cover_image_url):
            embed.set_image(url=cover_image_url)

        preview_message = await ctx.send("Here's a preview of the announcement:", embed=embed)
        await ctx.send("Do you want to send this announcement? (yes/no)")
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ['yes', 'no']

        try:
            message = await self.bot.wait_for('message', timeout=60.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("You took too long to respond. Try again.")
            self.is_submission_phase = False
            return
        if message.content.lower() == 'yes':
            announcement_channel = self.bot.get_channel(self.ANNOUNCEMENT_CHANNEL_ID) 
            await announcement_channel.send(embed=embed)
            await ctx.send("Announcement sent and contest started!")
        else:
            await ctx.send("Announcement canceled.")
            self.is_submission_phase = False

    async def end_submission_phase(self, submission_end_time):
        """End the submission phase and start the voting phase."""
        await asyncio.sleep(submission_end_time - int(time.time()))
        self.is_submission_phase = False
        self.is_voting_phase = True
        await self.start_voting_phase()

    async def end_voting_phase(self, voting_end_time):
        """End the voting phase."""
        await asyncio.sleep(voting_end_time - int(time.time()))
        self.is_voting_phase = False
        voting_channel = self.bot.get_channel(self.voting_channel_id)
        await voting_channel.set_permissions(self.bot.get_guild(774124295026376755).default_role, read_messages=False)

    async def start_voting_phase(self):
        """Start the voting phase."""
        self.is_voting_phase = True
        voting_channel = self.bot.get_channel(self.voting_channel_id)
        await voting_channel.set_permissions(self.bot.get_guild(774124295026376755).default_role, read_messages=True)
        # Fetch approved artworks from the database
        async with self.bot.pool.acquire() as connection:
            records = await connection.fetch("""
                SELECT id, link FROM artwork WHERE inspected_by IS NOT NULL AND contest_id = $1
            """, self.current_contest_id)

        # Post approved artworks in the voting channel and add reactions for voting
        #for record in records:
        #    embed = discord.Embed(title="Artwork", description=f"Submitted for contest {self.current_contest_id}")
        #    embed.set_image(url=record['link'])
        #    message = await voting_channel.send(embed=embed)
        #    await message.add_reaction("🗳")
#

    async def create_artwork(self, link, submitted_by, message_id):
        """Insert a new artwork submission into the database."""
        async with self.bot.pool.acquire() as connection:
            await connection.execute("""
                INSERT INTO artwork (link, submitted_by, message_id) VALUES ($1, $2, $3)
            """, link, submitted_by, message_id)


    @commands.Cog.listener()
    async def on_message(self, message):
        """Listen for DMs to accept artwork submissions."""
        if message.guild is None and message.author != self.bot.user:
            if not self.is_submission_phase:
                await message.channel.send("The submission phase is not currently active.")
                return
            if message.attachments:
                submitted_by = message.author.id
                async with self.bot.pool.acquire() as connection:
                    existing_submission = await connection.fetchrow("""
                        SELECT * FROM artwork WHERE submitted_by = $1 AND contest_id = $2
                    """, submitted_by, self.current_contest_id)

                if existing_submission:
                    await message.channel.send("You have already submitted an artwork for this contest.")
                    return
                link = message.attachments[0].url
                
                # Post the artwork in the staff channel for review
                staff_channel = self.bot.get_channel(self.staff_channel_id)
                review_message = await staff_channel.send(f"New artwork submission by {message.author.mention}", file=discord.File(link))
                
                # Add thumbs-up and thumbs-down reactions for approval and denial
                await review_message.add_reaction("👍")
                await review_message.add_reaction("👎")

                # Save the submission in the database
                await self.create_artwork(link, submitted_by, review_message.id)

                self.submission_count += 1
                await message.channel.send("Your artwork has been submitted for review!")
    
    
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle artwork approval or denial based on staff reaction."""
        if reaction.message.channel.id == self.staff_channel_id and user != self.bot.user:
            async with self.bot.pool.acquire() as connection:
                if reaction.emoji == "👍":
                    await connection.execute("""
                        UPDATE artwork SET inspected_by = $1 WHERE message_id = $2
                    """, user.id, reaction.message.id)
                    self.approved_count += 1

                    # Get the approved artwork link
                    record = await connection.fetchrow("""
                        SELECT link FROM artwork WHERE message_id = $1
                    """, reaction.message.id)

                    # Post the approved artwork in an embed in the voting channel
                    voting_channel = self.bot.get_channel(self.voting_channel_id)
                    embed = discord.Embed(title="Submitted Artwork", description=f"Approved by <@{user.id}>")
                    embed.set_image(url=record['link'])
                    await voting_channel.send(embed=embed)
                elif reaction.emoji == "👎":
                    await connection.execute("""
                        DELETE FROM artwork WHERE message_id = $1
                    """, reaction.message.id)
                    self.denied_count += 1
                    
        if reaction.message.channel.id == self.voting_channel_id and reaction.emoji == "🗳" and self.is_voting_phase:
            if user.id not in self.user_votes:
                self.user_votes[user.id] = {}
            
            if self.current_contest_id not in self.user_votes[user.id]:
                self.user_votes[user.id][self.current_contest_id] = 0

            if self.user_votes[user.id][self.current_contest_id] >= 3:
                await user.send("You've already cast 3 votes for this contest.")
                return

            # Confirm the vote via DM
            await user.send("Do you wish to vote for this artwork? (yes/no)")

            def check(m):
                return m.author == user and m.channel.type == discord.ChannelType.private and m.content.lower() in ['yes', 'no']

            try:
                message = await self.bot.wait_for('message', timeout=60.0, check=check)
            except asyncio.TimeoutError:
                await user.send("You took too long to respond. Vote not counted.")
                return

            if message.content.lower() == 'yes':
                self.user_votes[user.id][self.current_contest_id] += 1
                await user.send("Your vote has been counted.")
            else:
                await user.send("Vote cancelled.")

    @tasks.loop(hours=4)
    async def send_periodic_updates(self):
        """Send updates every 4 hours."""
        channel = self.bot.get_channel(self.ANNOUNCEMENT_CHANNEL_ID)  
        await channel.send(f"Total Submissions: {self.submission_count}, Approved: {self.approved_count}, Denied: {self.denied_count}")



# Initialize the cog
async def setup(bot):
    await bot.add_cog(ArtContest(bot))
