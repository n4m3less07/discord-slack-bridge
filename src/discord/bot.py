import discord
from discord.ext import commands
import redis
import json
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("DISCORD_GUILD_ID")

if GUILD_ID:
    GUILD_ID = int(GUILD_ID)
else:
    print("DISCORD_GUILD_ID not found in .env file")
    exit(1)

redis_host = os.getenv("REDIS_HOST")
redis_port = int(os.getenv("REDIS_PORT"))
redis_db   = int(os.getenv("REDIS_DB"))

redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db)


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

class ChannelManager:
    def __init__(self, guild):
        self.guild = guild
        self.channel_cache = {}
    
    async def get_or_create_channel(self, channel_name):

        channel_name = channel_name.lower().replace(' ', '-').replace('_', '-')
        
        if channel_name in self.channel_cache:
            return self.channel_cache[channel_name]
        
        for channel in self.guild.text_channels:
            if channel.name == channel_name:
                self.channel_cache[channel_name] = channel
                return channel
        
        try:
            new_channel = await self.guild.create_text_channel(
                channel_name,
                topic=f"Bridged from Slack #{channel_name}"
            )
            self.channel_cache[channel_name] = new_channel
            print(f"Created Discord channel: #{channel_name}")
            return new_channel
        except Exception as e:
            print(f"Error creating channel {channel_name}: {e}")
            return discord.utils.get(self.guild.text_channels, name='general')

channel_manager = None

@bot.event
async def on_ready():
    global channel_manager
    print(f'{bot.user} has connected to discord!')
    
    guild = bot.get_guild(GUILD_ID)
    if guild:
        channel_manager = ChannelManager(guild)
        print(f'connected to guild: {guild.name}')
        
        general_channel = discord.utils.get(guild.text_channels, name='general')
        if general_channel:
            await general_channel.send("SldsBot is now online ")
            print("connection announcement ")
        else:
            print("could not find #general channel")
        
        asyncio.create_task(listen_for_slack_messages())
    else:
        print(f'Could not find guild with ID: {GUILD_ID}')

@bot.event
async def on_message(message):
    if message.author.bot:
        print(f"ignoring bot message from {message.author.name}")
        return
    
    if not message.guild:
        print("ignoring DM message")
        return
    
    message_data = {
        "platform": "discord",
        "username": message.author.display_name,
        "text": message.content,
        "channel": message.channel.name,
        "user_id": str(message.author.id),
        "channel_id": str(message.channel.id),
        "timestamp": str(message.created_at)
    }
    
    try:
        result = redis_client.publish("discord_to_slack", json.dumps(message_data))
        print(f"published to redis (subscribers: {result})")
        if result == 0:
            print("no slack listeners found")
    except Exception as e:
        print(f"redis publish error: {e}")
    
    await bot.process_commands(message)

async def send_message_to_discord(channel_name, username, text):
    if not channel_manager:
        print("channel manager not initialized")
        return
    
    try:
        target_channel = await channel_manager.get_or_create_channel(channel_name)
        if target_channel:
            await target_channel.send(f"{username} : {text}")
            print(f"sent message to discord #{target_channel.name}")
    except Exception as e:
        print(f"eror sending message to discord: {e}")

async def listen_for_slack_messages():
    pubsub = redis_client.pubsub()
    pubsub.subscribe("slack_to_discord")
    
    while True:
        try:
            message = pubsub.get_message(timeout=1)
            if message and message["type"] == "message":
                data = json.loads(message["data"])
                await send_message_to_discord(
                    data["channel"],
                    data["username"],
                    data["text"]
                )
        except Exception as e:
            print(f"error processin slack message: {e}")
        
        await asyncio.sleep(0.1)

@bot.command(name='status')
async def status(ctx):
    await ctx.send(f"bot is running  {len(bot.guilds)} ")

@bot.command(name='channels')
async def list_channels(ctx):
    channels = [channel.name for channel in ctx.guild.text_channels]
    await ctx.send(f"available channels: {', '.join(channels)}")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)