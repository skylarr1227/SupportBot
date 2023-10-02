from discord.ext import commands
from discord import Embed, SelectMenu, SelectOption, Interaction

class RoleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def choose_role(self, ctx):
        """Allows a user to choose between two roles."""
        
        # Create a select menu with the two roles
        select_menu = SelectMenu(custom_id='role_select_menu', placeholder='Role Choice Testing',
                                 options=[
                                     SelectOption(label='VIP TESTER', value='1134273992883187762'),
                                     SelectOption(label='ART SHARING', value='1006994577279942656')
                                 ])
        
        # Create an embed and add the select menu
        embed = Embed(title='Choose your role', description='Select a role from the dropdown menu below.')
        await ctx.send(embed=embed, components=[select_menu])

    @commands.Cog.listener()
    async def on_select_option(self, interaction: Interaction):
        """Handles the select option interaction."""
        if interaction.custom_id == 'role_select_menu':
            selected_role_value = interaction.data['values'][0]
            
            # Find the role based on the selected value
            if selected_role_value == '1134273992883187762':
                role = interaction.guild.get_role(1134273992883187762)  # Replace ROLE_1_ID with the actual ID
            elif selected_role_value == '1006994577279942656':
                role = interaction.guild.get_role(1006994577279942656)  # Replace ROLE_2_ID with the actual ID
            else:
                await interaction.response.send_message("Invalid role selected.", ephemeral=True)
                return
            
            # Add the role to the user
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"You have been given the {role.name} role!", ephemeral=True)

# Replace "bot" with the name of your bot instance
async def setup(bot):
    await bot.add_cog(RoleCog(bot))
