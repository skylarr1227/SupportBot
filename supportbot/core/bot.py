import discord
from discord import app_commands
from discord.ext import commands
from supabase import create_client, Client
import os
import asyncio
from dotenv import load_dotenv
import logging
import openai
#from notion_client import AsyncClient
from supportbot.core.utils import team
import asyncpg
import discord.ext.prometheus
from prometheus_client import Counter, Gauge, Summary, Enum, Info
from discord.ext.prometheus import PrometheusCog, PrometheusLoggingHandler

logging.getLogger().addHandler(PrometheusLoggingHandler())

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
        self.pool = None 
        pool = self.pool
        self.counters = {}
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
        #NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
        OPENAI_KEY = os.environ.get("OPENAI_KEY")
        #NOTION_DATABASE_URL = os.environ.get("NOTION_DATABASE_URL")
        #FRESHDESK_DOMAIN = os.environ.get("FRESHDESK_DOMAIN")
        self.logger = logging.Logger("supportbot")
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_API_KEY)
        self.supabase = supabase
        #self.NOTION_TOKEN = NOTION_TOKEN
        #self.collection = self.notion_client.databases.retrieve("b48e1f0a4f2e4a758992ba1931a35669")
        self.OPENAI_KEY = OPENAI_KEY
        self.SPECIFIC_POST_CHANNEL_ID = 1102722546232729620
        #self.openai = openai.api_key
        
        self.SUBMITTED_TRACK = Gauge('image_submissions', 'Number of image submissions for the daily contest')
        self.TOTAL_CONTESTS = Counter('contest_total', 'Total number of contests held')
        self.TOTAL_SPECIAL_CONTESTS = Counter('contest_total_special', 'Total number of special contests held')
        self.TOTAL_VOTES_CAST = Counter('contest_total_votes_cast', 'Total number of votes cast during contests')
        self.TOTAL_SUBMISSIONS = Counter('contest_total_submissions', 'Total number of submissions for each contest')
        self.ACTIVE_USERS = Gauge('contest_active_users', 'Number of users active during a contest')
        self.ALERTS_SENT = Counter('contest_alerts_sent', 'Number of alerts sent by the bot')
        
        ## support metrics for grafana
        self.messages_per_category_counter = Counter('discord_messages_per_category', 'Number of messages per category', ['category'])
        self.new_forum_posts_counter = Counter('discord_new_forum_posts', 'Number of new posts in the forum channel', ['channel_name'])


        # new mods watch
        self.specific_users_counter = Counter('discord_specific_users_activity', 'Activity count for specific users', ['user'])

        self.messages_per_user_counter = Counter('discord_messages_per_user', 'Number of messages per user', ['user'])
        self.messages_per_channel_counter = Counter('discord_messages_per_channel', 'Number of messages per channel', ['channel'])
        self.active_users_gauge = Gauge('discord_active_users', 'Number of active users')
        self.new_users_counter = Counter('discord_new_users', 'Number of new users')
        self.users_leaving_counter = Counter('discord_users_leaving', 'Number of users leaving')
        self.messages_per_channel_per_day_counter = Counter('discord_messages_per_channel_per_day', 'Number of messages per day per channel', ['channel', 'date'])
        self.unique_users_per_channel_counter = Counter('discord_unique_users_per_channel', 'Number of unique users per channel', ['channel'])
        self.replies_per_user_counter = Counter('discord_replies_per_user', 'Number of replies per user', ['user'])
        #self.prometheus_counters = {
        #    'image_submissions': self.SUBMITTED_TRACK,
        #    'contest_total': self.TOTAL_CONTESTS,
        #    'contest_total_special': self.TOTAL_SPECIAL_CONTESTS,
        #    'contest_total_votes_cast': self.TOTAL_VOTES_CAST,
        #    'contest_total_submissions': self.TOTAL_SUBMISSIONS,
        #    'contest_active_users': self.ACTIVE_USERS,
        #    'contest_alerts_sent': self.ALERTS_SENT,
        #    'discord_messages_per_user': self.messages_per_user_counter,
        #    'discord_messages_per_channel': self.messages_per_channel_counter,
        #    'discord_active_users': self.active_users_gauge,
        #    'discord_new_users': self.new_users_counter,
        #    'discord_users_leaving': self.users_leaving_counter,
        #    'discord_messages_per_channel_per_day': self.messages_per_channel_per_day_counter,
        #    'discord_unique_users_per_channel': self.unique_users_per_channel_counter,
        #    'discord_replies_per_user': self.replies_per_user_counter,
        #    'discord_messages_per_category': self.messages_per_category_counter,
        #    'discord_new_forum_posts': self.new_forum_posts_counter,
        #    'discord_specific_users_activity': self.specific_users_counter
        #}   




  


    async def create_pool(self):
            return await asyncpg.create_pool(
                user=os.environ.get("PGUSER"),
                password=os.environ.get("PGPASS"),
                database=os.environ.get("PGDB"),
                host=os.environ.get("PGHOST")
                #port=os.environ.get("PGPORT")
            )

    async def _setup_hook(self):
        self.db = await self.create_pool()
        try:
            await self.add_cog(PrometheusCog(self, port=9999))
        except Exception as e:
            print(e)
    
        

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
        if specific_post_channel is None:
            thread = await specific_post_channel.create_thread(
                name="This is a test", content="Known issues will be listed here with links to each post")
            print(f'Channel with ID {1102722546232729620} not found.')
            return
        # Create the specific post
        #self.specific_post = await specific_post_channel.send('List of open threads:')


    async def on_error(self, ctx, error):
        if isinstance(error, (commands.CommandNotFound, commands.CheckFailure)):
            return
        await super().on_error(ctx, error)
    
    async def start(self, *args, **kwargs):
        try:
            self.pool = await self.create_pool()
            self.logger.info(f'Postgres Database has been Initialized.')
            print(f'Postgres Database has been Initialized.')
        except:
            print(f'Postgres Database has FAILED to Initialize.')
            self.logger.info("Postgres Database has FAILED to Initialize.")
        for cogname in ("events", "dev", "tickets", "metrics", "zendesk"):
            await self.load_extension(f"supportbot.cogs.{cogname}")
        try:
            await self.add_cog(PrometheusCog(self, port=9999))
        except Exception as e:
            print(e)
        await super().start(*args, **kwargs)