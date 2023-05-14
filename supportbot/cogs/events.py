import discord
from discord.ext import commands


CHANNEL_IDS = [1053048696343896084, 1053787533139521637]

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
        if not added:
            return
        
        new_name = f"{' '.join(added)} - {after.name}"
        await after.edit(name=new_name)

    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        if thread.parent_id not in CHANNEL_IDS:
            return
        
        if not thread.name.startswith('[NEW]'):
            new_name = f'[NEW] {thread.name}'
            await thread.edit(name=new_name)
        
        # Automatically join the thread
        await thread.join()

async def setup(bot):
    await bot.add_cog(Events(bot))