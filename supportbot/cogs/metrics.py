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
        self.tasks = []
        #self.loop.create_task(self.update_top_words())
        self.tasks.append(self.bot.loop.create_task(self.update_top_words()))
        self.tasks.append(self.bot.loop.create_task(self.log_member_status()))


    async def log_member_status(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            guild_id = 774124295026376755  
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                return

            online, offline, idle, busy = await self.count_member_status(guild)
            await self.insert_status_to_db(online, offline, idle, busy)

            await asyncio.sleep(300)


    async def count_member_status(self, guild):
        online = offline = idle = busy = 0
        for member in guild.members:
            if member.status == discord.Status.online:
                online += 1
            elif member.status == discord.Status.offline:
                offline += 1
            elif member.status == discord.Status.idle:
                idle += 1
            elif member.status == discord.Status.dnd: 
                busy += 1
        return online, offline, idle, busy

    async def insert_status_to_db(self, online, offline, idle, busy):
        query = '''INSERT INTO log (Online, Offline, Busy, Idle) VALUES ($1, $2, $3, $4);'''
        pool = self.bot.pool  
        async with pool.acquire() as conn:
            await conn.execute(query, online, offline, busy, idle)

   

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
    async def on_raw_message_delete(self, message):
        try:
            if not isinstance(message, discord.Message):
                return
            if message.author.bot:
                return
            self.bot.messages_deleted_counter.labels(user=str(message.author.name)).inc()
        except Exception as e:
            print(f"Error in on_message_delete: {e}")


    #@commands.Cog.listener()
    #async def on_member_update(self, before, after):
    #    # Check if the member was timed out
    #    logs = await after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_timed_out).flatten()
    #    if logs:
    #        log_entry = logs[0]
    #        if log_entry.user.id:
    #            self.bot.timeouts_applied_counter.labels(user=str(log_entry.user.name)).inc()
#
#

    async def update_top_words(self):
        while True:
            # Wait for 10 minutes
            await asyncio.sleep(600)
            # Get the top 25 most common words for each user
            for user_id, counter in self.bot.word_counters.items():
                top_25_words = counter.most_common(25)
                # Update the Prometheus gauge
                for word, count in top_25_words:
                    self.bot.top_words_gauge.labels(user=user_id, word=word).set(count)
                # Clear the counter for the next interval
                counter.clear()



    @commands.Cog.listener()
    async def on_message(self, message):
        if isinstance(message.channel, discord.DMChannel):
            return
        # Check for specific server ID and bot messages
        if message.guild.id == 774124295026376755:
            # MOD BANS
            if message.channel.id == 1026904617054916738:  
                if len(message.embeds) != 0:
                    for embed in message.embeds:
                        print(embed.footer)
                        action = "Ban"
                        mod_name = embed.footer.text
                        self.bot.mod_bans_gauge.labels(mod_name=mod_name, action=action).inc()
                        print(f"+1 {action} for {mod_name}")
            # MOD MUTES
            elif message.channel.id == 1026904822286389328:  
                if len(message.embeds) != 0:
                    for embed in message.embeds:
                        print(embed.footer)
                        action = "Mute"
                        mod_name = embed.footer.text
                        self.bot.mod_mutes_gauge.labels(mod_name=mod_name, action=action).inc()
                        print(f"+1 {action} for {mod_name}")
            # MOD WARNS
            elif message.channel.id == 1026904942910378064:
                if len(message.embeds) != 0:
                    for embed in message.embeds:
                        print(embed.footer)
                        action = "Warn"
                        mod_name = embed.footer.text
                        self.bot.mod_warns_gauge.labels(mod_name=mod_name, action=action).inc()
                        print(f"+1 {action} for {mod_name}")
            
            if message.author.bot:
                return
            if message.channel.id == 1156637978815377468:
                self.bot.replies_per_user_counter.labels(user=str(message.author.name)).inc()
           
            #if str(message.author.id) in self.bot.word_counters:
            #    words = message.content.split()
            #    self.bot.word_counters[str(message.author.id)].update(words)
            self.bot.messages_per_channel_counter.labels(channel=message.channel.name).inc()
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


    @team()
    @commands.command()
    async def inv_info(self, ctx, invite_code):
        try:
            # Fetch the invite object
            invite = await self.bot.fetch_invite(f'https://discord.gg/{invite_code}')

            # Extract and display relevant information
            server_name = invite.guild.name
            server_id = invite.guild.id
            inviter_name = invite.inviter.name
            inviter_id = invite.inviter.id
            uses = invite.uses
            max_uses = invite.max_uses
            expires_at = invite.expires_at if invite.expires_at else "Never"

            await ctx.send(f"Invite Link: {invite.url}\n"
                           f"Server Name: {server_name}\n"
                           f"Server ID: {server_id}\n"
                           f"Inviter: {inviter_name} (ID: {inviter_id})\n"
                           f"Uses: {uses}/{max_uses}\n"
                           f"Expires At: {expires_at}")
        except discord.NotFound:
            await ctx.send("Invite link not found or expired.")
        except discord.HTTPException:
            await ctx.send("An error occurred while fetching invite information.")


    @team()
    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def list_invites(self, ctx):
        """
        List all the invite codes for the server.

        This command is only usable by members with the "Manage Server" permission.
        The bot itself also needs the "Manage Server" permission to fetch invite links.
        """
        try:
            # Fetch all invites for the guild
            invites = await ctx.guild.invites()
        except discord.Forbidden:
            # The bot doesn't have the required permissions
            await ctx.send("I don't have the 'Manage Server' permission to fetch invites.")
            return
        except Exception as e:
            # Any other exception
            await ctx.send(f"An error occurred: {e}")
            return

        # Create a list of invite codes
        invite_list = [invite.code for invite in invites]

        # Create the message to send back
        if invite_list:
            message_base = "Here are the invite codes for this server:\n"
            chunk_size = 30  # Number of invite codes per message

            for i in range(0, len(invite_list), chunk_size):
                chunk = invite_list[i:i + chunk_size]
                message = message_base + "\n".join(chunk)
                await ctx.send(message)
        else:
            await ctx.send("There are no invites for this server.")


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
