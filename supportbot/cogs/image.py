from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
import io
import discord
import math
from discord import app_commands
import asyncio
from supportbot.core.utils import team, support

class ImageCollage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # A list to store the submitted images
        self.images = []

    @team()
    @app_commands.command()
    @app_commands.describe(image_file="Drag your image file here", )
    async def submit(self, interaction, image_file: discord.Attachment, image_file2: discord.Attachment=None, image_file3: discord.Attachment=None, image_file4: discord.Attachment=None):
        """
        Submit an image for the collage.
        """
        image_data = await image_file.read(use_cached=True)
        self.images.append(image_data)
        if image_file2:
            image_data = await image_file2.read(use_cached=True)
            self.images.append(image_data)
        if image_file3:
            image_data = await image_file3.read(use_cached=True)
            self.images.append(image_data)
        if image_file4:
            image_data = await image_file4.read(use_cached=True)
            self.images.append(image_data)
        await interaction.response.send_message("Image(s) uploaded successfully!")
    
    @team()
    @app_commands.command()
    async def collage(self, interaction):
        """
        Generate a collage of all submitted images.
        """
        await interaction.response.defer()
        # Convert the list of images bytes to PIL images
        if not self.images:
            await interaction.response.send_message("Submitted Successfully")
        loop = asyncio.get_running_loop()
        pil_images = await loop.run_in_executor(None, self._convert_to_pil, self.images)
        # Create a collage
        collage_img, collage_draw = await loop.run_in_executor(None, self._create_collage, pil_images)


        # Convert the collage image to bytes and send it
        with io.BytesIO() as image_binary:
            collage_img.save(image_binary, 'PNG')
            image_binary.seek(0)
            await interaction.response.followup.send(file=discord.File(fp=image_binary, filename="collage.png"))

    def _create_collage(self, images):
        """
        Create a collage with the provided images and number them.
        """
        num_images = len(images)

        # Determine best grid layout to get close to a 16:9 aspect ratio
        rows = int(math.sqrt(num_images * 9/16))
        cols = int(math.ceil(num_images / rows))

        # Calculate the total width and height of the collage
        collage_width = sum(img.width for img in images[:cols])
        collage_height = sum(images[i::cols][0].height for i in range(rows))


        # Create a blank white collage image
        collage_img = Image.new('RGBA', (collage_width, collage_height), (255, 255, 255, 255))
        collage_draw = ImageDraw.Draw(collage_img)

        # Load a font for numbering
        font = ImageFont.truetype("/home/ubuntu/s/SupportBot/supportbot/futur.ttf", 25)

        x_offset, y_offset = 0, 0
        image_counter = 0
        for i in range(rows):
            for j in range(cols):
                if image_counter < num_images:
                    img = images[image_counter]
                    # Paste the image into the collage
                    collage_img.paste(img, (x_offset, y_offset))
                    # Draw the number on the image
                    collage_draw.text((x_offset + 10, y_offset + 10), str(image_counter + 1), fill=(253, 253, 1, 255), font=font)
                    x_offset += img.width
                    image_counter += 1
            y_offset += img.height
            x_offset = 0

        return collage_img, collage_draw

    def _convert_to_pil(self, images_data):
        """
        Convert bytes images to PIL images.
        """
        return [Image.open(io.BytesIO(img_data)).convert('RGBA') for img_data in images_data]


async def setup(bot):
    await bot.add_cog(ImageCollage(bot))
