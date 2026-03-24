from collections import defaultdict, deque
import ManBotCommands.Functions as Functions
from discord import message
import discord
from dotenv import load_dotenv
import aiohttp
import json
import os

history = defaultdict(lambda: deque(maxlen=50))

key = str(message.author.id)
key = str(message.channel.id)

load_dotenv()
TOKEN = os.getenv("dihcord_token")
ServerApi = os.getenv("ServerApi")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# CHANGE IT ACCORDINGLY I HAVENT COMPLETED IT