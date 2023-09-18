from discord.ext import commands
from collections import defaultdict
from collections import Counter as Counter
from datetime import datetime
from supportbot.core.utils import team, support
import discord
import asyncio
import postgrest.exceptions
import logging
import re

categories = [980877639675949166,1030538756081590402,1077936033863323708,1026663023273844786]
support_categories = [1109323625439445012,1109324122833567744,1043533890414968842,1088531848264683581]

IGNORED_WORDS = {
    'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', "you're", "you've", "you'll", 
    "you'd", 'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she', "she's", 
    'her', 'hers', 'herself', 'it', "it's", 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves', 
    'what', 'which', 'who', 'whom', 'this', 'that', "that'll", 'these', 'those', 'am', 'is', 'are', 'was', 
    'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing', 'a', 'an', 
    'the', 'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for', 'with', 
    'about', 'against', 'between', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'to', 
    'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 'again', 'further', 'then', 'once'
}

class UserMetricsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.SPECIFIC_USERS_LIST = [894035560623128576, 1085865858183737384, 273621738657415169]  
        self.word_freqs = defaultdict(Counter)

    async def update_metrics(self, user_id, metrics):
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: self.bot.supabase.table('user_metrics').upsert({'user_id': user_id, 'metrics': metrics}).execute())
        return response

    def calculate_rank(self, points):
        milestones = [
            (0, "Novice"),
            (51, "Apprentice"),
            (201, "Journeyman"),
            (501, "Craftsman"),
            (1001, "Artisan"),
            (2001, "Expert"),
            (4001, "Master"),
            (8001, "WOMBO Wizard"),
        ]
        for milestone, rank in reversed(milestones):
            if points >= milestone:
                return rank
        return "Novice"  # Default rank if points are somehow negative



    @commands.Cog.listener()
    async def on_message_delete(self, message):
        try:
            if not isinstance(message, discord.Message):
                return
            if message.author.bot:
                return
            self.bot.messages_deleted_counter.labels(user=str(message.author.name)).inc()
        except Exception as e:
            print(f"Error in on_message_delete: {e}")


    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        # Check if the member was timed out
        logs = await after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_timed_out).flatten()
        if logs:
            log_entry = logs[0]
            if log_entry.user.id:
                self.bot.timeouts_applied_counter.labels(user=str(log_entry.user.name)).inc()



    @commands.Cog.listener()
    async def on_message(self, message):
        if isinstance(message.channel, discord.DMChannel):
            return
        if message.channel.category in categories:
            self.bot.messages_per_category_counter.labels(category=message.channel.category.name).inc()
        # Check for specific server ID and bot messages
        if message.guild.id == 774124295026376755:
            
            if message.author.bot:
                return
            if message.author.id in self.SPECIFIC_USERS_LIST:
                words = [word.lower() for word in re.findall(r'\w+', message.content) if word.lower() not in IGNORED_WORDS]
                for word in words:
                    self.bot.word_frequency_counter.labels(user=message.author.name, word=word).inc()
                    self.bot.messages_per_user_counter.labels(user=str(message.author.name)).inc()
                    self.bot.messages_per_channel_per_day_counter.labels(channel=message.channel.name, date=datetime.today().strftime('%Y-%m-%d')).inc()
            if message.channel.id in support_categories and isinstance(message.channel, discord.Thread):
                parent_channel_name = message.channel.parent.name
                self.bot.new_forum_posts_counter.labels(channel_name=parent_channel_name).inc()
            
            self.bot.messages_per_channel_counter.labels(channel=message.channel.name).inc()

            # Channel Activity Metrics
            
            self.bot.unique_users_per_channel_counter.labels(channel=message.channel.name).inc()

            # User Engagement Metrics
            if message.reference:
                self.bot.replies_per_user_counter.labels(user=str(message.author.name)).inc()
        if message.guild.id != 914705867855773746:
            return
        # Retrieve existing metrics or initialize
        loop = asyncio.get_event_loop()

        try:
            user_metrics_query = lambda: self.bot.supabase.table('user_metrics').select('metrics').eq('user_id', message.author.id).single().execute()
            user_metrics_response = await loop.run_in_executor(None, user_metrics_query)
            metrics = user_metrics_response.data['metrics']  # Accessing the metrics
        except postgrest.exceptions.APIError:
            # No existing metrics found for the user; initialize as needed
            metrics = {
                'activity_rating': 0,
                'daily_metrics': defaultdict(lambda: {'posts': 0, 'replies': 0, 'messages': 0})
            }
            # Insert new row for the user
            payload = {
                'user_id': message.author.id,
                'metrics': metrics,
                'name': message.author.name
            }
            insert_query = lambda: self.bot.supabase.table('user_metrics').insert(payload).execute()
            await loop.run_in_executor(None, insert_query)

        # Specific channel ID to exclude from normal messages count
        exclude_channel_id = 1132716536478568568

        # Current date as a string
        current_date = datetime.today().strftime('%Y-%m-%d')
        if current_date not in metrics['daily_metrics']:
            metrics['daily_metrics'][current_date] = {'posts': 0, 'messages': 0, 'replies': 0}
        # Check if it's a new post in a forum channel
        if isinstance(message.channel, discord.Thread) and message.type == discord.MessageType.default and not message.reference:
            points = 10 if message.attachments else 5
            metrics['daily_metrics'][current_date]['posts'] += 1
            metrics['activity_rating'] += points
        elif isinstance(message.channel, discord.Thread):
            # Reply in a thread
            metrics['daily_metrics'][current_date]['replies'] += 1
            metrics['activity_rating'] += 2
        elif message.channel.id != exclude_channel_id:
            # Normal message outside the specific channel
            metrics['daily_metrics'][current_date]['messages'] += 1
            metrics['activity_rating'] += 1

        # Update the metrics in Supabase
        await self.update_metrics(message.author.id, metrics)

    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        try:
            if member.guild.id == 774124295026376755:
                self.bot.active_users_gauge.set(len(member.guild.members))
                self.bot.new_users_counter.inc()
        except Exception as e:
            print(f"Error in on_member_join: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        try:
            if member.guild.id == 774124295026376755:
                self.bot.active_users_gauge.set(len(member.guild.members))
                self.bot.users_leaving_counter.inc()
        except Exception as e:
            print(f"Error in on_member_remove: {e}")
       


    async def get_or_create_metrics(self, user_id):
        loop = asyncio.get_event_loop()
        try:
            user_metrics_query = lambda: self.bot.supabase.table('user_metrics').select('metrics').eq('user_id', user_id).single().execute()
            user_metrics_response = await loop.run_in_executor(None, user_metrics_query)
            return user_metrics_response.data
        except postgrest.exceptions.APIError:
            # No existing metrics found for the user; initialize as needed
            metrics = {
                'activity_rating': 0,
                'daily_metrics': defaultdict(lambda: {'posts': 0, 'messages': 0})
            }
            # Insert new row for the user
            payload = {
                'user_id': user_id,
                'metrics': metrics
            }
            insert_query = lambda: self.bot.supabase.table('user_metrics').insert(payload).execute()
            await loop.run_in_executor(None, insert_query)
            return {'metrics': metrics}

    @team()
    @commands.command(name='mod-metrics')
    async def update_word_metrics_command(self, ctx):
        await self.update_prometheus_metrics()
        await ctx.send("Updated word metrics.")

    @commands.command(name='viprank')
    async def my_rank(self, ctx):
        user_metrics_response = await self.get_or_create_metrics(ctx.author.id)
        points = user_metrics_response['metrics']['activity_rating']
        rank = self.calculate_rank(points)
        await ctx.send(f"{ctx.author.mention}, your tester rank is **{rank}**.") # with **{points}** points.

    @commands.command(name='toptesters')
    async def leaderboard(self, ctx):
        # Retrieve all user metrics
        user_metrics_query = self.bot.supabase.table('user_metrics').select('user_id, metrics', 'name').execute()
        user_metrics = user_metrics_query.data

        # Sort by activity points and take top 10
        leaderboard = sorted(user_metrics, key=lambda x: x['metrics']['activity_rating'], reverse=True)[:10]

        # Build the leaderboard message
        leaderboard_text = ""
        for position, entry in enumerate(leaderboard, 1):
            user = entry['name']
            rank = self.calculate_rank(entry['metrics']['activity_rating'])

            # Check if the user is None, and handle accordingly
            if user is None:
                username = "Unknown User"
            else:
                username = user

            leaderboard_text += f"{position}. {username} - ({entry['metrics']['activity_rating']} points) **{rank}**\n"

        await ctx.send(f"🏆 Top Testers 🏆\n{leaderboard_text}")

    @commands.command(name='get_summary_metrics')
    async def get_summary_metrics(self, ctx):
        try:
            # Retrieve all metrics
            loop = asyncio.get_event_loop()
            all_metrics_query = lambda: self.bot.supabase.table('user_metrics').select('*').execute()
            all_metrics_response = await loop.run_in_executor(None, all_metrics_query)
            all_metrics = all_metrics_response.data
            
            # Top 10 active users
            top_10_active_users = sorted(all_metrics, key=lambda x: x['metrics']['activity_rating'], reverse=True)[:10]
            top_10_active_users_text = "\n".join([f"`{user['name']}`: **{user['metrics']['activity_rating']}** points" for user in top_10_active_users])

            # Initialize counters for posts and messages per day
            posts_per_day = defaultdict(int)
            messages_per_day = defaultdict(int)
            # Role-based metrics
            role_metrics = defaultdict(lambda: {'activity_rating': 0, 'posts': 0, 'messages': 0})
            specific_roles = [1132750157591617699, 1132750327142158497, 1132750619631964320]

            # Calculate daily metrics and role-based metrics
            for user in all_metrics:
                daily_metrics = user['metrics']['daily_metrics']
                for date, counts in daily_metrics.items():
                    posts_per_day[date] += counts['posts']
                    messages_per_day[date] += counts['messages']
                # Role-based metrics logic ...
                user_roles = user['metrics'].get('roles', {})
                if user_roles:
                    # Role-based metrics logic ...
                    for role_id in specific_roles:
                        if str(role_id) in user_roles:
                            role_metrics[role_id]['activity_rating'] += user['metrics']['activity_rating']
                            role_metrics[role_id]['posts'] += user['metrics']['posts']
                            role_metrics[role_id]['messages'] += user['metrics']['messages']


            # Format summary text
            summary_text = f"Top 10 Active Users:\n{top_10_active_users_text}\n\n"
            summary_text += "Posts per Day:\n" + "\n".join([f"{date}: {count} posts" for date, count in posts_per_day.items()])
            summary_text += "\n\nMessages per Day:\n" + "\n".join([f"{date}: {count} messages" for date, count in messages_per_day.items()])
            summary_text += "\n\nRole-based Metrics:\n" + "\n".join([f"Role {role_id}: {metrics}" for role_id, metrics in role_metrics.items()])

            await ctx.send(summary_text)
        except Exception as e:
            await ctx.send(f"Error retrieving summary metrics: {e}")

async def setup(bot):
    await bot.add_cog(UserMetricsCog(bot))
