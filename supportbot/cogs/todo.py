from supportbot.core.utils import team
from discord import app_commands, Embed
from discord.ext import commands
import discord
import json
import aiohttp



TODOIST='f8ecdbb2d7c78936b63fc9a1882e74a4ffb19ed9'

class Contests(commands.Cog):
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
            await interaction.response.send_message("Task added successfully.")
        else:
            await interaction.response.send_message("Failed to add task.")


    @team()
    @app_commands.command()
    async def view_tasks(self, interaction):
        """View tasks."""
        token = TODOIST
        tasks = await self.get_todoist_tasks(token, 2320689199)  # Replace with your actual project ID
        embed = Embed(title="Todoist Tasks", description="Here are the tasks from your Todoist project.", color=0x03f8fc)
        task_list = "\n".join([f"- {task['content']}" for task in tasks])
        embed.description += f"\n\n{task_list}"
        await interaction.response.send_message(embed=embed)


    async def add_todoist_task(token,task_info):
        """
        Adds a task to Todoist using aiohttp for asynchronous HTTP requests.

        Parameters:
            token (str): Your Todoist API token.
            task_name (str): The name of the task to add.
            project_id (int): The ID of the project to which the task will be added.
        """
        url = 'https://api.todoist.com/rest/v1/tasks'
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
        url = f'https://api.todoist.com/rest/v1/tasks?project_id={project_id}'

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

