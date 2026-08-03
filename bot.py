import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import requests
import random
from PIL import Image
import io
import json

# ============== CONFIGURATION ==============
BOT_TOKEN = os.environ.get("MTUzMzgxOTIyMDY5NjEwNDk3MQ.GCuwKd.dnwX6Ub9PmKwnMVr57r6puJee0DhU1HUV3m3E8") # Railway will securely inject this
IMAGES_FOLDER = "images"           
DECALE_NAME = "default"            
# ===========================================

def modify_image(image_path):
    img = Image.open(image_path)
    if img.mode == 'RGBA':
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    width, height = img.size
    pixels = img.load()
    for _ in range(10):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        pixels[x, y] = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    img.close()
    return img_bytes

def upload_decal_sync(api_key, user_id, image_path, display_name):
    modified_image = modify_image(image_path)
    filename = os.path.basename(image_path)
    if not filename.lower().endswith('.png'):
        filename = filename.rsplit('.', 1)[0] + '.png'
    request_payload = {
        "assetType": "Decal",
        "displayName": display_name,
        "description": f"Uploaded: {filename}",
        "creationContext": {"creator": {"userId": user_id}}
    }
    url = "https://apis.roblox.com/assets/v1/assets"
    headers = {"x-api-key": api_key}
    files = {
        "request": (None, json.dumps(request_payload), "application/json"),
        "fileContent": (filename, modified_image, "image/png")
    }
    try:
        response = requests.post(url, headers=headers, files=files, timeout=60)
        if response.status_code == 200:
            data = response.json()
            return True, "Success", data.get('assetId', 'Unknown')
        else:
            try:
                error_msg = response.json().get('message', response.text)
            except:
                error_msg = response.text
            return False, f"Error {response.status_code}: {error_msg}", None
    except Exception as e:
        return False, f"Request Failed: {str(e)}", None

class UploadBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())
    async def setup_hook(self):
        await self.tree.sync()
    async def on_ready(self):
        print(f'Logged in as {self.user}')

bot = UploadBot()

@bot.tree.command(name="t", description="Uploads a specific amount of decals.")
@app_commands.describe(user_id="Your Roblox User ID", api_key="Your Open Cloud API Key", amount="How many to upload")
async def slash_upload(interaction: discord.Interaction, user_id: str, api_key: str, amount: int):
    if amount <= 0 or amount > 500:
        return await interaction.response.send_message("Amount must be between 1 and 500.", ephemeral=True)
    if not os.path.exists(IMAGES_FOLDER):
        return await interaction.response.send_message(f"Error: Missing {IMAGES_FOLDER} folder.", ephemeral=True)
    valid_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')
    images = [f for f in os.listdir(IMAGES_FOLDER) if f.lower().endswith(valid_extensions) and not f.startswith('.')]
    if not images:
        return await interaction.response.send_message(f"Error: No images in {IMAGES_FOLDER}.", ephemeral=True)
    
    await interaction.response.defer(ephemeral=True)
    success_count = 0
    fail_count = 0
    asset_ids = []
    stopped_early = False

    for i in range(amount):
        image_name = images[i % len(images)]
        image_path = os.path.join(IMAGES_FOLDER, image_name)
        success, message, asset_id = await asyncio.to_thread(upload_decal_sync, api_key, user_id, image_path, DECALE_NAME)
        
        if success:
            success_count += 1
            asset_ids.append(asset_id)
        else:
            fail_count += 1
            if "moderat" in message.lower() or "restrict" in message.lower() or "403" in message or "401" in message:
                stopped_early = True
                break
        if i < amount - 1 and success:
            await asyncio.sleep(1.5)

    result_text = f"**Upload Complete!**\nSuccessful: `{success_count}` | Failed: `{fail_count}`\n"
    if stopped_early:
        result_text += "🚨 **Stopped Early:** Moderation/Permission error detected.\n"
    if asset_ids:
        ids_str = ", ".join(map(str, asset_ids))
        if len(ids_str) > 1500: ids_str = ids_str[:1500] + "..."
        result_text += f"\n**Asset IDs:** {ids_str}"
    else:
        result_text += "\nNo assets were successfully uploaded."
    await interaction.followup.send(result_text)

bot.run(BOT_TOKEN)
