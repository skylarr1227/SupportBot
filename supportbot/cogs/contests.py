import discord
from discord.ext import commands
from pytz import timezone
from datetime import datetime
import asyncio
import time

INSPECTION_CHANNEL_ID = 1128673991138222151
PUBLIC_VOTING_CHANNEL_ID = 
CHANNEL_ID = 

class Contests(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.accepting_images = True
        self.bot.loop.create_task(self.check_time())
    

    async def check_time(self):
        while True:
            # Check the current time
            now = datetime.now(timezone('UTC'))
            
            # If it's 9pm UTC (4pm EST), stop accepting images
            if now.hour == 21:
                self.accepting_images = False
            else:
                self.accepting_images = True
            
            # Wait 60 seconds before checking the time again
            await asyncio.sleep(60)
    
    async def inspect_image(self, user_id, image_url):
        # Send the image to a specific channel for manual inspection
        channel = self.bot.get_channel(INSPECTION_CHANNEL_ID)  # Replace INSPECTION_CHANNEL_ID with the ID of your inspection channel
        message = await channel.send(f"New image submission from <@{user_id}> for inspection:", embed=discord.Embed().set_image(url=image_url))
        
        # Add the thumbs up and down emojis as reactions
        await message.add_reaction("👍")
        await message.add_reaction("👎")

    async def post_image(self, user_id, image_url):
        # Post the image to a specific channel for public voting
        channel = self.bot.get_channel(PUBLIC_VOTING_CHANNEL_ID)  # Replace PUBLIC_VOTING_CHANNEL_ID with the ID of your public voting channel
        message = await channel.send(f"Image submission from <@{user_id}>:", embed=discord.Embed().set_image(url=image_url))
        
        # Add the thumbs up emoji as a reaction
        await message.add_reaction("👍")
  
    async def get_theme(self):
        # Query the "contests" table in Supabase to get the theme for the current day
        # You'll need to adjust this query based on the structure of your "contests" table
        result = await self.bot.supabase.table("contests").select().execute()
        return result.data[0]["theme"]

    @commands.Cog.listener()
    async def on_ready(self):
        theme = await self.get_theme()
        # Send the theme to a specific channel
        channel = self.bot.get_channel(CHANNEL_ID)  # Replace CHANNEL_ID with the ID of your channel
        embed = discord.Embed(title="Today's Contest Theme", description=theme)
        await channel.send(embed=embed)
    
    

    @commands.Cog.listener()
    async def on_message(self, message):
        # Check if the message is a DM and contains an image
        if isinstance(message.channel, discord.DMChannel) and message.attachments:
            # Send a confirmation message
            confirm_message = await message.channel.send("Do you want to submit this image for the daily contest? Reply with 'yes' to confirm.")
            
            def check(m):
                # Check that the reply is from the same user and in the same channel
                return m.author == message.author and m.channel == message.channel

            try:
                # Wait for a reply to the confirmation message
                reply = await self.bot.wait_for('message', timeout=60.0, check=check)
            except asyncio.TimeoutError:
                # If the user doesn't reply within 60 seconds, send a timeout message
                await message.channel.send('Sorry, you did not reply in time.')
            else:
                # If the user replies with 'yes', log their ID and the current timestamp in Supabase
                if reply.content.lower() == 'yes' and self.accepting_images:
                    await self.bot.supabase.table("users").upsert({"u_id": message.author.id, "submitted": int(time.time())}).execute()
                    await self.inspect_image(message.author.id, message.attachments[0].url)
                    await message.channel.send('Your image has been submitted for the daily contest.')
                else:
                    await message.channel.send('Your image has not been submitted.')

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        # Check if the reaction is in the inspection channel and was added by a staff member
        if payload.channel_id == INSPECTION_CHANNEL_ID and payload.user_id in self.bot.WOMBO_SUPPORT:
            # Get the message that the reaction was added to
            channel = self.bot.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            
            # Check if the reaction is the thumbs up emoji
            if str(payload.emoji) == "👍":
                # If the image passes manual inspection, post it to the public voting channel
                user_id = message.embeds[0].description.split("<@")[1].split(">")[0]  # Extract the user ID from the message embed
                image_url = message.embeds[0].image.url  # Get the image URL from the message embed
                await self.post_image(user_id, image_url)

async def setup(bot):
    await bot.add_cog(Contests(bot))
