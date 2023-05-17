import discord
from discord.ext import commands
import traceback
from supportbot.core.utils import team

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
            page = await self.notion_client.pages.create(
            parent={"database_id": "b48e1f0a4f2e4a758992ba1931a35669"},
            properties={
                "Name": {"title": [{"text": {"content": thread.name}}]},
                "First Message": {"rich_text": [{"text": {"content": first_message.content}}]},
                "Template": {"rich_text": [{"text": {"content": response}}]}
            }
        )
        except Exception as e:
            print(f"Error processing thread '{thread.name}': {e}")



    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        global last_error
        last_error = traceback.format_exception(type(error), error, error.__traceback__)
    
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