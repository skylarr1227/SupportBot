import discord
from discord.ext import commands
import traceback
from supportbot.core.utils import team
from collections import defaultdict
import re
from discord.errors import NotFound
KNOWN_ISSUES = [1102722546232729620]
CHANNEL_IDS = [1109324122833567744, 1109323625439445012]
STAFF_CHANNEL_ID = 1111054788487032863
CHANNEL_IDS2 = [1102722546232729620]
class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        channel = self.bot.get_channel(payload.channel_id)
        if isinstance(channel, discord.Thread):
            # Get the first message in the thread
            first_message_id = None
            async for m in channel.history(oldest_first=True, limit=1):
                first_message_id = m.id
                break
            
            # If the first message is the one that got deleted, archive and lock the thread
            if first_message_id is None or first_message_id == payload.message_id:
                await channel.edit(archived=True, locked=True, reason="Original post deleted.")



    @commands.Cog.listener()
    async def on_thread_update(self, before, after):
        if after.parent_id not in CHANNEL_IDS:
            #if after.parent_id in KNOWN_ISSUES:
            #    # Edit the specific post
            #    specific_post_channel = self.bot.get_channel(1114313493450072084)  
            #    self.specific_post = await specific_post_channel.fetch_message(1114313493450072084)
            #    new_content = self.specific_post.content + f'\n {after.name}'
            #    await self.specific_post.edit(content=new_content)
            return
        
        old = set([tag.name for tag in before.applied_tags if isinstance(tag, discord.ForumTag)])
        new = set([tag.name for tag in after.applied_tags if isinstance(tag, discord.ForumTag)])
        added = new - old
        added = [tag for tag in added if tag.isupper()]  # Only include tags in ALL CAPS
        if not added:
            return
        if "RESOLVED" in added:
            new_name = re.sub(r'^\[[^\]]*\]', '[RESOLVED]', after.name)
                # Ensure the name does not exceed the Discord limit of 100 characters
            if len(new_name) > 100:
                new_name = new_name[:100]
            await after.edit(name=new_name, archived=True, locked=True, reason="Thread resolved or closed.")
            return
        if "KNOWN" in added:
            new_name = re.sub(r'^\[[^\]]*\]', '[KNOWN]', after.name)
                # Ensure the name does not exceed the Discord limit of 100 characters
            if len(new_name) > 100:
                new_name = new_name[:100]
            await after.edit(name=new_name, reason="Thread marked as a known issue")
            return
        if "CLOSED" in added:
            new_name = re.sub(r'^\[[^\]]*\]', '[CLOSED]', after.name)
                # Ensure the name does not exceed the Discord limit of 100 characters
            if len(new_name) > 100:
                new_name = new_name[:100]
            await after.edit(name=new_name, archived=True, locked=True, reason="Thread resolved or closed.")
            return
    
        if 'LOG' in added:
            # Copy relevant information from the original post/message
            original_post = None
            async for message in after.history(oldest_first=True, limit=1):
                original_post = message
    
            if original_post is None:
                print(f"Could not find the original post in the thread {after.name}.")
                return
    
            # Set thread to locked and closed
            await after.edit(archived=True, locked=True)
    
            # Repost this in a designated staff only forum channel nice and neatly
            staff_channel = self.bot.get_channel(STAFF_CHANNEL_ID)  # Replace STAFF_CHANNEL_ID with the actual ID
            if staff_channel is not None:
                await staff_channel.send(
                    f"Thread **{after.name}** locked and closed automatically due to LOG tag:\n\n"
                    f"**Original Post by {original_post.author.name}**: {original_post.content}"
                )
            else:
                print("Could not find the staff channel.")
    
            # Delete the original post from 1
            try:
                await original_post.delete()
            except NotFound:
                print(f"Original post in thread {after.name} was not found or already deleted.")
        else:
            new_name = f"{' '.join(added)} - {after.name}"
            # Ensure the name does not exceed the Discord limit of 100 characters
            if len(new_name) > 100:
                new_name = new_name[:100]
            await after.edit(name=new_name)
    

    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        try:
            if thread.parent_id not in CHANNEL_IDS:
                #if thread.parent_id in KNOWN_ISSUES:
                #    # Get the specific post
                #    specific_post_channel = self.bot.get_channel(1114313493450072084)  
                #    try:
                #        self.specific_post = await specific_post_channel.fetch_message(1114313493450072084)
                #    except discord.NotFound:
                #        print(f"Post with ID {1114313493450072084} not found.")
                #        return
                #    except discord.Forbidden:
                #        print(f"Do not have permission to access post with ID {1114313493450072084}.")
                #        return
#
                #    # Edit the specific post
                #    new_content = self.specific_post.content + f"\n- {thread.name}"
                #    await self.specific_post.edit(content=new_content)
                return
    
            if not thread.name.startswith('[NEW]'):
                new_name = '[NEW] ' + thread.name
                # Ensure the name does not exceed the Discord limit of 100 characters
                if len(new_name) > 100:
                    new_name = new_name[:100]
                await thread.edit(name=new_name)
    
            # Automatically join the thread
            await thread.join()
    
            # Log the thread creation in Supabase
            original_message = None  # Initialize to None, will be updated later
            author = None  # Initialize to None, will be updated later
    
            # Fetch the first message in the thread to get the original author and message
            async for message in thread.history(oldest_first=True, limit=1):
                author = message.author
                original_message = message.content
    
            # Determine the platform based on tags in the original_message
            platform = 0  # Default platform
            if "dream" in original_message:
                platform = 1
            elif "wombot" in original_message:
                platform = 2
    
            # Prepare the data for insertion
            payload = {
                'old_status': 'NEW',  # Since the thread is new, the old_status is 'NEW'
                'new_status': 'NEW',  # The new_status is also 'NEW' at the time of creation
                'thread_jump_url': thread.jump_url,
                'support_rep': None,  # No support representative assigned at the time of creation
                'author_id': int(author.id) if author else None,
                'original_message': original_message,
                # New fields
                'platform': platform,
                't_id': int(thread.id),
                'msg_count': thread.message_count  # Or use 'thread.total_message_sent' depending on your requirement
            }
            # Insert the data into the Supabase "tickets" table
            response = self.bot.supabase.table("tickets").insert(payload).execute()
            return response
    
        except Exception as e:
            print(f"Error processing thread '{thread.name}': {e}")



    #@commands.Cog.listener()
    #async def on_command_error(self, ctx, error):
    #    global last_error
    #    last_error = traceback.format_exception(type(error), error, error.__traceback__)
    

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        ignored_errors = (
            commands.errors.CommandNotFound,
            commands.errors.MissingPermissions,
            commands.CheckFailure,
            commands.DisabledCommand,
            commands.MaxConcurrencyReached,
        )
        if isinstance(error, ignored_errors):
            return
        if isinstance(error, discord.errors.Forbidden):
            await ctx.author.send(
                    f"I do not have Permissions to use in {ctx.channel}")
            return
        help_errors = (
            commands.errors.MissingRequiredArgument,
            commands.errors.BadArgument,
        )
        if isinstance(error, help_errors):
            command = ctx.command
            try:
                await ctx.send(
                    f"That command doesn't look quite right...\n"
                    f"Syntax: `{ctx.prefix}{command.qualified_name} {command.signature}`\n\n"
                )
            except:
                pass
            return
        if isinstance(error, commands.errors.CommandInvokeError):
            # This should get the actual error behind the CommandInvokeError
            error = error.__cause__ or error
            if "TimeoutError" in str(error) or "Forbidden" in str(error):
                return
            ctx.bot.traceback = (
                f"Exception in command '{ctx.command.qualified_name}'\n"
                + "".join(
                    traceback.format_exception(type(error), error, error.__traceback__)
                )
            )
        ctx.bot.logger.exception(type(error).__name__, exc_info=error)
        

    @team()
    @commands.command(name='analyze_sentiment')
    async def analyze_sentiment_command(self, interaction, thread_id: discord.TextChannel):
        
        try:
            thread = self.bot.get_channel(thread_id)
            if thread is None:
                await interaction.response.send_message(f"No thread found with ID {thread_id}")
                return

            users = {}
            async for message in thread.history(oldest_first=True):
                if message.author.bot:
                    continue
                user_messages = users.get(message.author.id, [])
                user_messages.append(message.content)
                users[message.author.id] = user_messages

            if not users:
                await interaction.response.send_message(f"No messages found in the thread {thread_id}")
                return

            report_parts = []
            total_tokens_used = 0
            for user_id, messages in users.items():
                sentiment, tokens_used = await self.bot.analyze_sentiment(messages)
                total_tokens_used += tokens_used
                user = await self.bot.fetch_user(user_id)
                report_parts.append(f"# {user.name}\n### Sentiment: \n- {sentiment}\n- Number of messages: `{len(messages)}`\n----------------------------")

            sentiment_report = '\n'.join(report_parts)
            sentiment_report += f"\n\n**Total tokens used:** `{total_tokens_used}` (`cost: {total_tokens_used * .002}`)"
            # Split the report into chunks of <= 2000 characters
            chunks = [sentiment_report[i:i+2000] for i in range(0, len(sentiment_report), 2000)]
            for chunk in chunks:
                await interaction.response.send_message(chunk)

        except Exception as e:
            self.bot.logger.error(f"Error in analyze_sentiment command: {e}")
            await interaction.response.send_message(f"An error occurred while analyzing sentiment: {str(e)}")


    @team()
    @commands.command(name='scan')
    async def scan(self, ctx):
        prefix_counts = defaultdict(int)

        for channel_id in CHANNEL_IDS:
            channel = self.bot.get_channel(channel_id)
            for thread in channel.threads:
                match = re.match(r'\[(.*?)\]', thread.name)  # regex to find a string enclosed in square brackets
                if match:
                    prefix = match.group(1)  # get the prefix of the thread name
                    prefix_counts[prefix] += 1
            async for thread in channel.archived_threads(limit=100):  # specify your limit here
                match = re.match(r'\[(.*?)\]', thread.name)
                if match:
                    prefix = match.group(1)
                    prefix_counts[prefix] += 1

        # format the counts into a string
        count_strs = [f'{prefix}: {count}' for prefix, count in prefix_counts.items()]
        count_report = '\n'.join(count_strs)

        await ctx.send(f'Here are the counts of each prefix:\n{count_report}')

    @team()
    @commands.command(name='summarize')
    async def summarize(self, ctx):
        try:
            summaries = []
            for channel_id in CHANNEL_IDS2:
                channel = self.bot.get_channel(channel_id)
                for thread in channel.threads:
                    first_message = None
                    async for message in thread.history(oldest_first=True, limit=1):
                        first_message = message.content
                        break
                    if first_message:
                        summary = await self.bot.ask_gpt(f"Summarize: {thread.name} - {first_message}")
                        summaries.append(f"## {thread.name}\n- {summary}")
            summary_report = '\n'.join(summaries)

            # Split summary report into chunks of 2000 characters or less
            for i in range(0, len(summary_report), 2000):
                await ctx.send(summary_report[i:i+2000])
        except Exception as e:
            self.bot.logger.error(f"Error in summarize command: {e}")

    @team()
    @commands.command(name='summarize2')
    async def summarize2(self, ctx):
        summaries = []
        for channel_id in CHANNEL_IDS2:
            channel = self.bot.get_channel(channel_id)
            for thread in channel.threads:
                first_message = None
                async for message in thread.history(oldest_first=True, limit=1):
                    first_message = message.content
                    break
                if first_message:
                    summaries.append(f"## {thread.name}\n- {first_message}")
        summary_report = '\n'.join(summaries)
        await ctx.send(f'Here are the summaries of each thread:\n{summary_report}')


    @team()
    @commands.command(name='lasterror')
    async def last_error(self, ctx):
        global last_error
        if last_error is None:
            await ctx.send("No errors have occurred yet.")
        else:
            # Send the traceback in a code block for formatting
            await ctx.send(f"```python\n{''.join(last_error)}\n```")

            
async def setup(bot):
    await bot.add_cog(Events(bot))
