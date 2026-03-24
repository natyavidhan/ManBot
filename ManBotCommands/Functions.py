import aiohttp
import discord
import json
from collections import defaultdict, deque

def GetMemoryKey(message):
    return f"{message.channel.id}:{message.author.id}"


def CleanMention(content, bot_id):
    content = content.replace(f"<@{bot_id}>", "")
    content = content.replace(f"<@!{bot_id}>", "")
    return content.strip()


def ReplyToBot(message, bot_user):
    return (
        message.refrence is not None
        and message.refrence.resolved is not None
        and getattr(message.refrence.resolved, "author", None) == bot_user
    )


def BotMentioned(message, bot_user):
    return bot_user in message.mentions


HistoryStore = defaultdict(lambda: deque(maxlen=50))
def AddUserMessage(memory_key,content):    #adding to hstry user msg
    HistoryStore[memory_key].append({
        "role": "user",
        "content": content
    })

def AddBotMessage(memory_key,content):    #adding to hstry bot msg
    HistoryStore[memory_key].append({
        "role": "ManBot",
        "content": content
    })


def GetHistory(memory_key):
    return list(HistoryStore[memory_key])

def BuildContex(message, user_text, memory_key):
    return {
        "message": user_text,
        "history": GetHistory(memory_key),
        "user":{
            "id": str(message.author.id),
            "name": message.author.name,
            "display_name": message.author.display_name
        },
        "channel":{
            "id": str(message.channel.id),
            "name": getattr(message.channel, "name", "DM")
        },
        "guild":{
            "id": str(message.guild.id) if message.guild else None,
            "name": message.guild.name if message.guild else None
        }
    }

async def ManBotAPIRequest(api_url, context):
    timeout = aiohttp.ClientTimeout(total=30)
    try: 
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(api_url, json=context) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"API Error: {response.status}")
                    return None
                
    except aiohttp.ClientError as e:
        print(f"HTTP Error: {e}")
        return "ManBot Request Failed!"
    except Exception as e:
        print(f"Unexpected Error: {e}")
