import discord
from discord import app_commands
from discord.ext import commands
from supabase import create_client, Client
import os
import asyncio
from dotenv import load_dotenv
import logging
import openai
from notion_client import AsyncClient

load_dotenv()

TOKEN = os.environ.get("TOKEN") # this is the bot token
SUPABASE_URL = os.environ.get("SUPABASE_URL") # this is the supabase url
SUPABASE_API_KEY = os.environ.get("SUPABASE_API_KEY") # this is the supabase api key for the database
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
OPENAI_KEY = os.environ.get("GPT_KEY")
NOTION_DATABASE_URL = os.environ.get("NOTION_DATABASE_URL")



intents = discord.Intents.default()
intents.messages = True
intents.reactions = True
intents.guilds = True
intents.message_content = True

async def get_prefix(bot, message):
    if not message.guild:
        return "dev."
    prefixes = ['<@1000125868938633297>']
    if message.author.id == 790722073248661525:
        prefixes.append('.')
    return commands.when_mentioned_or(*prefixes)(bot, message)

class ErrorHandlingTree(app_commands.CommandTree):
    async def on_error(self, interaction, error):
        if isinstance(error, app_commands.CheckFailure):
            return
        await super().on_error(interaction, error)

class SupportBot(commands.AutoShardedBot):
    def __init__(self, *args, **kwargs):
        super().__init__(
            command_prefix=get_prefix,
            max_messages=None,
            intents=intents,
            heartbeat_timeout=120,
            guild_ready_timeout=10,
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True),
            tree_cls=ErrorHandlingTree,
            *args,
            **kwargs,
        )
        self.WOMBO_TEAM = [
            790722073248661525,
            381887137362083841,
            149706927868215297,
            291970766419787788,
        ]
        self.WOMBO_SUPPORT = [
            790722073248661525, 
            381887137362083841, 
            149706927868215297, 
            291970766419787788,
            275092045671038986,
            986262236479750174,
            702554894032175246,
            395788963475881985,
            988106635874533467,
        ]

        self.closed_tickets = {
            'RESOLVED': 0,
            'ON-GOING': 0,
            'WAITING': 0,
            'HOLD': 0,
            'CLOSED': 0,
            'KNOWN': 0,
        }
        self.token = TOKEN
        self.logger = logging.Logger("supportbot")
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_API_KEY)
        self.notion_client = AsyncClient(auth=NOTION_TOKEN)
        self.collection = self.notion_client.databases.retrieve("b48e1f0a4f2e4a758992ba1931a35669")
        openai.api_key = os.environ.get(OPENAI_KEY)
        self.openai = openai.api_key


    async def ask_gpt(self, question):
        response = openai.Completion.create(
            engine="gpt3.5-turbo", 
            prompt=question, 
            temperature=0.5,
            max_tokens=100
        )
        return response.choices[0].text.strip()

    async def on_ready(self):
        self.logger.info(f'{self.user.name} has connected to Discord!')
    
    async def on_error(self, ctx, error):
        if isinstance(error, (commands.NotFound, commands.CheckFailure)):
            return
        await super().on_error(ctx, error)
    
    async def start(self, *args, **kwargs):
        for cogname in ("events", "dev", "tickets"):
            await self.load_extension(f"supportbot.cogs.{cogname}")
        await super().start(*args, **kwargs)
