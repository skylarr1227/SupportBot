import discord
from discord.ext import commands
import traceback
from supportbot.core.utils import team
from collections import defaultdict
import re

CHANNEL_IDS = [1019642044878159965, 1025458916441723021,1026654225045913621]

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_thread_update(self, before, after):
        if after.parent_id not in CHANNEL_IDS:
            return
        
        old = set([tag.name for tag in before.applied_tags if isinstance(tag, discord.ForumTag)])
        new = set([tag.name for tag in after.applied_tags if isinstance(tag, discord.ForumTag)])
        added = new - old
        added = [tag for tag in added if tag.isupper()]  # Only include tags in ALL CAPS
        if not added:
            return
        
        new_name = f"{' '.join(added)} - {after.name}"
        # Ensure the name does not exceed the Discord limit of 100 characters
        if len(new_name) > 100:
            new_name = new_name[:100]
        await after.edit(name=new_name)

    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        try:
            if thread.parent_id not in CHANNEL_IDS:
                return

            if not thread.name.startswith('[NEW]'):
                new_name = '[NEW] ' + thread.name
                # Ensure the name does not exceed the Discord limit of 100 characters
                if len(new_name) > 100:
                    new_name = new_name[:100]
                await thread.edit(name=new_name)

            # Automatically join the thread
            await thread.join()

        except Exception as e:
            print(f"Error processing thread '{thread.name}': {e}")



    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        global last_error
        last_error = traceback.format_exception(type(error), error, error.__traceback__)
    
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

        # format the counts into a string
        count_strs = [f'{prefix}: {count}' for prefix, count in prefix_counts.items()]
        count_report = '\n'.join(count_strs)

        await ctx.send(f'Here are the counts of each prefix:\n{count_report}')

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