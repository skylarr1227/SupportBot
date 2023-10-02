from discord.ext import commands
from discord import Embed, ui, ButtonStyle, Interaction

class RoleSelect(ui.Select):
    def __init__(self):
        options = [
            ui.SelectOption(label="Role 1", value="role_1_id"),
            ui.SelectOption(label="Role 2", value="role_2_id")
        ]
        super().__init__(placeholder="Choose a role", options=options, custom_id="role_select_menu")

    async def callback(self, interaction):
        role_value = self.values[0]
        if role_value == "role_1_id":
            role = interaction.guild.get_role(774125342809391154)  # Replace ROLE_1_ID with the actual ID
        elif role_value == "role_2_id":
            role = interaction.guild.get_role(1134273992883187762)  # Replace ROLE_2_ID with the actual ID
        else:
            await interaction.response.send_message("Invalid role selected.", ephemeral=True)
            return

        await interaction.user.add_roles(role)
        await interaction.response.send_message(f"You have been given the {role.name} role!", ephemeral=True)

class RoleView(ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(RoleSelect())

class RoleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def choose_role(self, ctx):
        """Allows a user to choose between two roles."""
        embed = Embed(title="Choose your role", description="Select a role from the dropdown menu below.")
        view = RoleView()
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(RoleCog(bot))
