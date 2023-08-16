from discord.ext import commands
from collections import defaultdict
from datetime import datetime
import discord
import asyncio

class UserMetricsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def update_metrics(self, user_id, metrics):
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: self.bot.supabase.table('user_metrics').upsert({'user_id': user_id, 'metrics': metrics}).execute())
        return response

    

    @commands.Cog.listener()
    async def on_message(self, message):
        # Check for specific server ID and bot messages
        if message.guild.id != 914705867855773746 or message.author.bot:
            return

        # Retrieve existing metrics or initialize
        loop = asyncio.get_event_loop()
        user_metrics = await loop.run_in_executor(None, lambda: self.bot.supabase.table('user_metrics').select('metrics').eq('user_id', message.author.id).single().execute())
        metrics = user_metrics.get('metrics', {
            'activity_rating': 0,
            'daily_metrics': defaultdict(lambda: {'posts': 0, 'messages': 0})
        })

        # Specific channel ID to exclude from normal messages count
        exclude_channel_id = 1132716536478568568

        # Current date as a string
        current_date = datetime.today().strftime('%Y-%m-%d')

        # Check if it's a new post in a forum channel
        if isinstance(message.channel, discord.Thread):
            points = 10 if message.attachments else 5
            metrics['daily_metrics'][current_date]['posts'] += 1
            metrics['activity_rating'] += points
        elif message.channel.id != exclude_channel_id:
            # Normal message outside the specific channel
            metrics['daily_metrics'][current_date]['messages'] += 1
            metrics['activity_rating'] += 1

        # Update the metrics in Supabase
        await self.update_metrics(message.author.id, metrics)

    @commands.command(name='get_summary_metrics')
    async def get_summary_metrics(self, ctx):
        try:
            # Retrieve all metrics
            all_metrics = await self.bot.supabase.table('user_metrics').select('*')
            
            # Top 10 active users
            top_10_active_users = sorted(all_metrics, key=lambda x: x['metrics']['activity_rating'], reverse=True)[:10]
            top_10_active_users_text = "\n".join([f"User {user['user_id']}: {user['metrics']['activity_rating']} points" for user in top_10_active_users])

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
                user_roles = user['metrics']['roles']
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
