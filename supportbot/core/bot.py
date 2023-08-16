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
from supportbot.core.utils import team
load_dotenv()

TOKEN = os.environ.get("TOKEN") # this is the bot token



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
        SUPABASE_API_KEY = os.environ.get("SUPABASE_API_KEY")
        self.SUPABASE_API_KEY = SUPABASE_API_KEY
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
        BITLY_KEY = os.environ.get("BITLY")
        self.BITLY_KEY = BITLY_KEY
        self.closed_tickets = {
            'RESOLVED': 0,
            'ON-GOING': 0,
            'WAITING': 0,
            'HOLD': 0,
            'CLOSED': 0,
            'KNOWN': 0,
        }
        self.remove_command("help")
        self.token = TOKEN
        SUPABASE_URL = os.environ.get("SUPABASE_URL") # this is the supabase url
        self.SUPABASE_URL = SUPABASE_URL
        NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
        OPENAI_KEY = os.environ.get("OPENAI_KEY")
        NOTION_DATABASE_URL = os.environ.get("NOTION_DATABASE_URL")
        FRESHDESK_API_KEY = os.environ.get("FRESHDESK_API_KEY")
        FRESHDESK_DOMAIN = os.environ.get("FRESHDESK_DOMAIN")
        self.logger = logging.Logger("supportbot")
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_API_KEY)
        self.supabase = supabase
        self.NOTION_TOKEN = NOTION_TOKEN
        #self.collection = self.notion_client.databases.retrieve("b48e1f0a4f2e4a758992ba1931a35669")
        self.OPENAI_KEY = OPENAI_KEY
        self.SPECIFIC_POST_CHANNEL_ID = 1102722546232729620
        #self.openai = openai.api_key
        self.api_key = FRESHDESK_API_KEY
        self.domain = FRESHDESK_DOMAIN
        self.api_url = f"https://{self.domain}.freshdesk.com/api/v2/"

    async def create_notion_client(self):
        try:
            self.notion_client = AsyncClient(auth=self.NOTION_TOKEN)
            self.collection = self.notion_client.databases.retrieve("b48e1f0a4f2e4a758992ba1931a35669")
        except Exception as e:
            await self.on_error("create_notion_client", e)
        return self.notion_client



        

    async def analyze_sentiment_and_participation(self, thread_id):
        thread = self.get_channel(thread_id)
        if not isinstance(thread, discord.Thread):
            raise ValueError(f"No thread found with ID {thread_id}")

        sentiments = {}
        participation = {}

        async for message in thread.history():
            sentiment = await self.ask_gpt(f"What is the sentiment of this message: {message.content}")
            sentiments[message.author] = sentiment
            if message.author in participation:
                participation[message.author] += 1
            else:
                participation[message.author] = 1

        return sentiments, participation



    async def ask_gpt(self, question):
        openai.api_key = self.OPENAI_KEY
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo", 
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant."
                },
                {
                    "role": "user",
                    "content": question
                }
            ]
        )
        return response['choices'][0]['message']['content']
    

    async def analyze_sentiment(self, user_messages):
        openai.api_key = self.OPENAI_KEY
        messages = [{"role": "system", "content": "You are a helpful assistant."}]
        for message in user_messages:
            messages.append({"role": "user", "content": f"What is the sentiment of this message: '{message}'?"})
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo", 
            messages=messages
        )
        return response['choices'][0]['message']['content'], response['usage']['total_tokens']

        

    async def on_ready(self):
        self.logger.info(f'{self.user.name} has connected to Discord!')
        specific_post_channel = self.get_channel(1102722546232729620)
        await self.create_notion_client()
        if specific_post_channel is None:
            thread = await specific_post_channel.create_thread(
                name="This is a test",content="Known issues will be listed here with links to each post")   
            print(f'Channel with ID {1102722546232729620} not found.')
            return

        # Create the specific post
        #self.specific_post = await specific_post_channel.send('List of open threads:')


    async def on_error(self, ctx, error):
        if isinstance(error, (commands.NotFound, commands.CheckFailure)):
            return
        await super().on_error(ctx, error)
    
    async def start(self, *args, **kwargs):
        for cogname in ("events", "dev", "tickets"):
            await self.load_extension(f"supportbot.cogs.{cogname}")
        await super().start(*args, **kwargs)
