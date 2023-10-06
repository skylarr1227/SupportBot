from supportbot.core.utils import team, vip
from discord import app_commands, Embed
from discord.ext import commands
import discord
import json
import aiohttp
from enum import Enum
from datetime import datetime, timedelta
import pytz
import asyncio 

class Options(Enum):
    Critical = 1
    Normal = 2 
    Backlog = 3

BATCH_SIZE = 1000  
DELAY = 5
TODOIST='f8ecdbb2d7c78936b63fc9a1882e74a4ffb19ed9'

class Todo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @team()
    @app_commands.command()
    @app_commands.describe(title="Title of Task to be added")
    @app_commands.describe(priority="1 is 'urgent', 4 is 'normal'")
    async def task(self, interaction, title: str, priority: int = 4):
        """Add a new task to the to-do list"""
        task_info = {
            'content': title,
            'project_id': 2320689199, 
            'priority': priority,  
        }
        token = TODOIST
        result = await self.add_todoist_task(token, task_info)
        if result == 1:
            await interaction.response.send_message("Task added successfully.", ephemeral=True)
        else:
            await interaction.response.send_message("Failed to add task.", ephemeral=True)


    @commands.command()
    @commands.is_owner()
    async def populate_long_term_members(self, ctx):
        three_months_ago = datetime.utcnow().replace(tzinfo=pytz.utc) - timedelta(days=180)

        long_term_member_ids = [
            member.id for member in ctx.guild.members
            if member.joined_at is not None and member.joined_at < three_months_ago
        ]
        async with self.bot.pool.acquire() as connection:
        # Inserting into the database
            await connection.executemany(
                "INSERT INTO long_term_members (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING",
                [(user_id,) for user_id in long_term_member_ids]
            )
            await ctx.send(f"{len(long_term_member_ids)} members have been added to the long_term_members table.")
    
    @commands.command()
    @commands.is_owner()
    async def populate_90(self, ctx):
        three_months_ago = datetime.utcnow().replace(tzinfo=pytz.utc) - timedelta(days=90)
        
        long_term_member_ids = [
            member.id for member in ctx.guild.members
            if member.joined_at is not None and member.joined_at < three_months_ago
        ]

        await ctx.send(f"Found {len(long_term_member_ids)} members who joined more than 3 months ago. Beginning to add them to the database in batches...")
        
        async with self.bot.pool.acquire() as connection:
            for i in range(0, len(long_term_member_ids), BATCH_SIZE):
                batch_ids = [(user_id,) for user_id in long_term_member_ids[i:i+BATCH_SIZE]]
                
                # Inserting into the database
                await connection.executemany(
                    "INSERT INTO long_term_members2 (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING",
                    batch_ids
                )
                
                await ctx.send(f"Added {len(batch_ids)} members to the database (Batch {i//BATCH_SIZE + 1}).")
                await asyncio.sleep(DELAY)  # Pause to reduce rate of API calls
            
        await ctx.send("Finished adding members to the database.")

    @commands.command()
    @commands.is_owner()
    async def check(self, ctx, days: int):
        three_months_ago = datetime.utcnow().replace(tzinfo=pytz.utc) - timedelta(days=days)
        
        long_term_member_ids = [
            member.id for member in ctx.guild.members
            if member.joined_at is not None and member.joined_at < three_months_ago
        ]

        await ctx.send(f"Found {len(long_term_member_ids)} members who joined more than {days} days ago. Beginning to add them to the database in batches...")
        

    @vip()
    @app_commands.command()
    @app_commands.describe(title="Short title of bug being added")
    @app_commands.describe(desc="Important details about the bug")
    async def addbug(self, interaction, title: str, desc: str, priority: Options = 2):
        """Add a new bug to the list"""
        task_info = {
            'content': title,
            'description': desc,
            'project_id': 2320689619, 
            'priority': priority,  
        }
        token = TODOIST
        result = await self.add_todoist_task(token, task_info)
        if result == 1:
            await interaction.response.send_message("Bug added successfully.", ephemeral=True)
        else:
            await interaction.response.send_message("Failed to add bug.", ephemeral=True)


    
    @app_commands.command()
    async def bugs(self, interaction):
        """View bugs."""
        if interaction.guild.id != 914705867855773746:
            await interaction.response.send_message("This cannot be used in this server, sorry.", ephemeral=True)
            return
        else:
            token = TODOIST
            tasks = await self.get_todoist_tasks(token, 2320689619) 
            embed = Embed(title="Bugs", description="Here are the Bugs reported so far (cleaned up weekly).", color=0x03f8fc)
            task_list = "\n".join([f"- {task['content']}" for task in tasks])
            embed.description += f"\n\n{task_list}"
            await interaction.response.send_message(embed=embed)

    @team()
    @app_commands.command()
    async def view_tasks(self, interaction):
        """View tasks."""
        token = TODOIST
        tasks = await self.get_todoist_tasks(token, 2320689199)  # Replace with your actual project ID
        embed = Embed(title="Tasks", description="Here are the tasks from your todo list.", color=0x03f8fc)
        task_list = "\n".join([f"- {task['content']}" for task in tasks])
        embed.description += f"\n\n{task_list}"
        await interaction.response.send_message(embed=embed)


    async def add_todoist_task(self,token,task_info):
        """
        Adds a task to Todoist using aiohttp for asynchronous HTTP requests.

        Parameters:
            token (str): Your Todoist API token.
            task_name (str): The name of the task to add.
            project_id (int): The ID of the project to which the task will be added.
        """
        url = 'https://api.todoist.com/rest/v2/tasks'
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=task_info) as resp:
                response_data = await resp.json()

                if resp.status == 200:
                    return 1
                else:
                    return 2


    
    async def get_todoist_tasks(self, token, project_id):
        """
        Fetches tasks from a Todoist project using aiohttp for asynchronous HTTP requests.

        Parameters:
            token (str): Your Todoist API token.
            project_id (int): The ID of the project from which tasks will be fetched.
        
        Returns:
            list: A list of tasks.
        """
        # API endpoint for fetching tasks
        url = f'https://api.todoist.com/rest/v2/tasks?project_id={project_id}'

        # Headers for the HTTP request
        headers = {
            'Authorization': f'Bearer {token}'
        }

        # Asynchronous HTTP GET request to fetch tasks
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    return []

async def setup(bot):
    await bot.add_cog(Todo(bot))