import aiohttp
import logging
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

def getMemoryKey(message):
    """Generate a unique key for storing message history"""
    return f"{message.channel.id}:{message.author.id}"


def cleanMention(content, bot_id):
    """Remove bot mentions from message content"""
    content = content.replace(f"<@{bot_id}>", "").replace(f"<@!{bot_id}>", "")
    return content.strip()


def replyToBot(message, bot_user):
    """Check if message is a reply to the bot"""
    return (
            message.reference is not None
            and message.reference.resolved is not None
            and getattr(message.reference.resolved, "author", None) == bot_user
    )


def botMentioned(message, bot_user):
    """Check if bot is mentioned in the message"""
    return bot_user in message.mentions


# History storage
history_store = defaultdict(lambda: deque(maxlen=50))


def addUserMessage(memory_key, content):
    """Add user message to history"""
    history_store[memory_key].append({
        "role": "user",
        "content": content
    })


def addBotMessage(memory_key, content):
    """Add bot message to history"""
    history_store[memory_key].append({
        "role": "assistant",  # Changed from "ManBot" to standard "assistant"
        "content": content
    })


def getHistory(memory_key):
    """Retrieve message history"""
    return list(history_store[memory_key])


def buildContext(message, user_text, memory_key):
    """Build context object for API request"""
    return {
        "message": user_text,
        "history": getHistory(memory_key),
        "user": {
            "id": str(message.author.id),
            "name": message.author.name,
            "display_name": message.author.display_name
        },
        "channel": {
            "id": str(message.channel.id),
            "name": getattr(message.channel, "name", "DM")
        },
        "guild": {
            "id": str(getattr(message.guild, "id", None)),
            "name": getattr(message.guild, "name", None) if message.guild else None
        }
    }


async def manbotAPIRequest(api_url, context):
    """Make API request to ManBot backend"""
    timeout = aiohttp.ClientTimeout(total=30)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(api_url, json=context) as response:
                response.raise_for_status()  # This will raise for bad status codes
                return await response.json()

    except aiohttp.ClientError as e:
        logger.error(f"HTTP Error in ManBot API request: {e}")
        return {"error": "ManBot Request Failed!"}
    except Exception as e:
        logger.error(f"Unexpected error in ManBot API request: {e}")
        return {"error": "Unexpected error occurred"}