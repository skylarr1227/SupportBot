from discord import app_commands
import asyncio


def team():
    def predicate(interaction):
        return interaction.user.id in interaction.client.WOMBO_TEAM
    return app_commands.check(predicate)

def support():
    def predicate(interaction):
        return interaction.user.id in interaction.client.WOMBO_SUPPORT
    return app_commands.check(predicate)


async def store_in_supabase(bot, old_status, new_status, thread, executor, author, original_message):
    payload = {
        'old_status': old_status,
        'new_status': new_status,
        'thread_jump_url': thread.jump_url,
        'support_rep': int(executor),
        'author_id': int(author),
        'original_message': original_message
    }
    # Insert the data into the Supabase "tickets" table
    response = bot.supabase.table("tickets").insert(payload).execute()
    return response


async def store_prompt(bot, prompt, images, nsfw_triggered):
    data = {
        'prompt': prompt,
        'images': images,
        'nsfw_triggered': nsfw_triggered
    }
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, bot.supabase.table("nsfw_tracking").insert(data).execute)
    return response
