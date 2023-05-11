import discord
from discord.ext import commands



class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    




clicked_users = set()

@commands.Cog.listener()
async def on_button_click(self, res):
    if res.component.label == "Send User ID":
        if res.user.id not in clicked_users:
            await res.respond(
                type=InteractionType.ChannelMessageWithSource,
                content=f"{res.user.name}'s User ID: {res.user.id}"
            )
            clicked_users.add(res.user.id)
        else:
            return



@commands.Cog.listener()
async def on_thread_update(self, before, after):
    CHANNEL_IDS = [1053048696343896084, 1053787533139521637]
    if after.parent_id in CHANNEL_IDS:
        if before.applied_tags != after.applied_tags:
            last_applied_tag = after.applied_tags[-1] if after.applied_tags else None
            if last_applied_tag:
                new_name = f"{last_applied_tag} - {after.name}"
                if new_name != after.name:
                    await after.edit(name=new_name)

@commands.Cog.listener()
async def on_thread_create(self, thread):
    if thread.parent_id == 1053787533139521637:
        if not thread.name.startswith('[NEW]'):
            new_name = f'[NEW] {thread.name}'
            await thread.edit(name=new_name)
            print(f"Thread name updated to: {new_name}")
        # Automatically join the thread
        await thread.join()

@commands.Cog.listener()
async def on_command_error(self, ctx, error):
    if isinstance(error, MissingRequiredArgument):
        await ctx.send(f"Missing required argument: {error.param.name}")
    elif isinstance(error, CommandError):
        await ctx.send(f"An error occurred while processing the command: {error}")
    else:
        print(f"Unhandled error: {error}")