from discord.ext import commands

import discord
import json

class Prometheus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def save_metrics(self, ctx):
        """
        Save current Prometheus metrics to a file.
        """
        try:
            metrics_data = {
                "new_users_counter": self.bot.new_users_counter._value.get(),
                "users_leaving_counter": self.bot.users_leaving_counter._value.get(),
                "specific_users_counter": self.bot.specific_users_counter._value._metrics,
                "mod_bans_gauge": self.bot.mod_bans_gauge._value._metrics,
                "mod_mutes_gauge": self.bot.mod_mutes_gauge._value._metrics,
                "mod_warns_gauge": self.bot.mod_warns_gauge._value._metrics,
                "word_counters": {k: v._value.get() for k, v in self.bot.word_counters.items()},
                "top_words_gauge": self.bot.top_words_gauge._value._metrics,
                "messages_deleted_counter": self.bot.messages_deleted_counter._value._metrics,
                "active_users_gauge": self.bot.active_users_gauge._value.get(),
                "messages_per_user_counter": self.bot.messages_per_user_counter._value._metrics,
                "messages_per_channel_counter": self.bot.messages_per_channel_counter._value._metrics,
                "messages_per_channel_counter2": self.bot.messages_per_channel_counter2._value._metrics,
                "messages_per_channel_per_day_counter": self.bot.messages_per_channel_per_day_counter._value._metrics,
                "unique_users_per_channel_counter": self.bot.unique_users_per_channel_counter._value._metrics,
                "replies_per_user_counter": self.bot.replies_per_user_counter._value._metrics,
                "TOTAL_CONTESTS": self.bot.TOTAL_CONTESTS._value.get(),
                "SUBMITTED_TRACK": self.bot.SUBMITTED_TRACK._value.get(),
            }
            with open("/home/ubuntu/metrics.json", "w") as f:
                json.dump(metrics_data, f)
            await ctx.send("Successfully saved metrics to file.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @commands.command()
    async def load_metrics(self, ctx):
        """
        Load Prometheus metrics from a file.
        """
        try:
            with open("/home/ubuntu/metrics.json", "r") as f:
                metrics_data = json.load(f)

            self.bot.new_users_counter._value.set(metrics_data.get("new_users_counter", 0))
            self.bot.users_leaving_counter._value.set(metrics_data.get("users_leaving_counter", 0))
            self.bot.specific_users_counter._value._metrics = metrics_data.get("specific_users_counter", {})
            self.bot.mod_bans_gauge._value._metrics = metrics_data.get("mod_bans_gauge", {})
            self.bot.mod_mutes_gauge._value._metrics = metrics_data.get("mod_mutes_gauge", {})
            self.bot.mod_warns_gauge._value._metrics = metrics_data.get("mod_warns_gauge", {})
            for k, v in metrics_data.get("word_counters", {}).items():
                self.bot.word_counters[k]._value.set(v)
            self.bot.top_words_gauge._value._metrics = metrics_data.get("top_words_gauge", {})
            self.bot.messages_deleted_counter._value._metrics = metrics_data.get("messages_deleted_counter", {})
            self.bot.active_users_gauge._value.set(metrics_data.get("active_users_gauge", 0))
            self.bot.messages_per_user_counter._value._metrics = metrics_data.get("messages_per_user_counter", {})
            self.bot.messages_per_channel_counter._value._metrics = metrics_data.get("messages_per_channel_counter", {})
            self.bot.messages_per_channel_counter2._value._metrics = metrics_data.get("messages_per_channel_counter2", {})
            self.bot.messages_per_channel_per_day_counter._value._metrics = metrics_data.get("messages_per_channel_per_day_counter", {})
            self.bot.unique_users_per_channel_counter._value._metrics = metrics_data.get("unique_users_per_channel_counter", {})
            self.bot.replies_per_user_counter._value._metrics = metrics_data.get("replies_per_user_counter", {})
            self.bot.TOTAL_CONTESTS._value.set(metrics_data.get("TOTAL_CONTESTS", 0))
            self.bot.SUBMITTED_TRACK._value.set(metrics_data.get("SUBMITTED_TRACK", 0))

            await ctx.send("Successfully loaded metrics from file.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")


async def setup(bot):
    await bot.add_cog(Prometheus(bot))