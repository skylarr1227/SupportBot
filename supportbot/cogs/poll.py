import random
import discord
from discord.ext import commands
from discord import Embed, Colour, app_commands
from supportbot.core.utils import team, support, store_in_supabase, store_prompt


class Polls(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.emoji_numbers = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]


    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        # Ignore the bot's own reactions
        if user == self.bot.user:
            return
        response = await self.bot.supabase.table("polls").select("*").eq('message_id', reaction.message.id).execute()
        if response.error or not response.data:
            return
        poll = response.data[0]
        for embed in reaction.message.embeds:
            for i, option in enumerate(poll['options']):
                if str(reaction.emoji) == self.emoji_numbers[i] and option in str(embed.title):
                    # A vote was added, update the poll
                    poll['votes'][option] += 1
                    await self.bot.supabase.table("polls").update({'votes': poll['votes']}).eq('p_id', poll['p_id']).execute()
                    break


    @team()
    @app_commands.command()
    async def start_poll(self, interaction, channel: discord.TextChannel, poll_name: str, option1: str, option2: str, poll_question: str, option3: str = None, option4: str = None, option5: str = None):
        ctx = await self.bot.get_context(interaction)
        await interaction.response.defer()
        options = {option1: 0, option2: 0}
        if option3:
            options[option3] = 0
        if option4:
            options[option4] = 0
        if option5:
            options[option5] = 0
        embed = Embed(title=poll_name, description=poll_question, color=Colour.blue())
        for i, option in enumerate(options):
            embed.add_field(name=f"{self.emoji_numbers[i]} {option}", value="React accordingly", inline=False)

        Message = await channel.send(embed=embed)
        votes = {option: 0 for option in options}
        data = {
            'name': poll_name,
            'poll': poll_question,
            'started_by': interaction.user.id,
            'options': options,
            'votes': options,
            'message_id': Message.id 
        }

        response = await self.bot.supabase.table("polls").insert(data).returning("p_id").execute()

        if response.error:
            await ctx.send(f"Error starting poll: {response.error}")
        else:
            poll_id = response.data[0]['p_id']
            await ctx.send(f"The poll {poll_name}(`{poll_id}`) started successfully in:\n### <#{channel.id}>.")
        

    @team()
    @app_commands.command()
    async def end_poll(self, interaction, poll_id: int):
        ctx = await self.bot.get_context(interaction)
        await interaction.response.defer()
        response = await self.bot.supabase.table("polls").delete().eq('p_id', poll_id).execute()
        if response.error:
            await ctx.send(f"Error ending poll: {response.error}")
        else:
            await ctx.send(f"Poll {poll_id} ended successfully.")
    
    @team()
    @commands.command()
    async def show_polls(self, ctx):
        response = await self.bot.supabase.table("polls").select("*").execute()

        if response.error:
            await ctx.send(f"Error fetching polls: {response.error}")
        else:
            for poll in response.data:
                embed = Embed(title=f"{poll['name']} (ID: {poll['p_id']})", description=poll['poll'], color=Colour.blue())
                for option, votes in poll['votes'].items():
                    total_votes = sum(poll['votes'].values())
                    percent = (votes / total_votes) * 100 if total_votes else 0
                    bar = "".join(["▰" if i < round(percent / 10) else "▱" for i in range(10)])
                    embed.add_field(name=option, value=f"{bar} {percent}%", inline=False)
                await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Polls(bot))
