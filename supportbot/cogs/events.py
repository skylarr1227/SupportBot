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
        try:
            if thread.parent_id not in CHANNEL_IDS:
                return
            
            if not thread.name.startswith('[NEW]'):
                new_name = f'[NEW] {thread.name}'
                await thread.edit(name=new_name)
            
            # Automatically join the thread
            await thread.join()

            # Fetch the thread's history and get the first message
            messages = await thread.history(limit=1).flatten()
            first_message = messages[0] if messages else ""

            # Use the thread topic and first message as the question
            question = f"{thread.name}\n{first_message.content}"
            response = self.ask_gpt(question)

            # Save the question and response as a new template in Notion
            row = self.collection.collection.add_row()
            row.title = thread.name
            row.first_message = first_message.content
            row.template = response
        except Exception as e:
            print(f"Error processing thread '{thread.name}': {e}")

async def setup(bot):
    await bot.add_cog(Events(bot))