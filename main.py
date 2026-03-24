import asyncio
import os
import sys
import logging
from collections import defaultdict, deque
import discord
from dotenv import load_dotenv
import core.functions as functions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Message history storage
history = defaultdict(lambda: deque(maxlen=50))

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
SERVER_API = os.getenv("SERVER_API")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'{client.user} has logged in!')
    print('Bot is ready to use!')
    print(f'Currently in {len(client.guilds)} guilds')


@client.event
async def on_disconnect():
    print("Bot disconnected from Discord. Attempting to reconnect...")


@client.event
async def on_resumed():
    print("Bot connection resumed!")


@client.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == client.user:
        return

    # Ignore empty messages
    if not message.content.strip():
        return

    # Generate memory key for conversation history
    memory_key = functions.getMemoryKey(message)

    # Clean bot mentions from message
    user_text = functions.cleanMention(message.content, client.user.id)

    # Check if bot should respond (mentioned, replied to, or in private message)
    should_respond = (
            functions.botMentioned(message, client.user) or
            functions.replyToBot(message, client.user) or
            message.guild is None  # Private messages
    )

    if should_respond and SERVER_API:
        # Add user message to history
        functions.addUserMessage(memory_key, user_text)

        # Build context for API request
        context = functions.buildContext(message, user_text, memory_key)

        # Make API request to LLM
        response_data = await functions.manbotAPIRequest(SERVER_API, context)

        if response_data and isinstance(response_data, dict) and "response" in response_data:
            response_text = response_data["response"]

            # Add bot response to history
            functions.addBotMessage(memory_key, response_text)

            # Send response to Discord
            await message.channel.send(response_text)
        elif isinstance(response_data, str):
            # Handle string responses
            functions.addBotMessage(memory_key, response_data)
            await message.channel.send(response_data)
        else:
            # Handle API errors
            error_msg = "Sorry, I encountered an error processing your request."
            await message.channel.send(error_msg)

@client.event
async def on_error(event):
    print(f"Bot error in {event}: {sys.exc_info()}")

async def connect_with_retry(client_, token, max_retries=5):
    """Attempt to connect with retry logic and better error handling"""
    for attempt in range(max_retries):
        try:
            print(f"Connection attempt {attempt + 1}/{max_retries}")
            await client_.start(token)
            return True
        except discord.errors.DiscordServerError as e:
            if "503" in str(e) or "overflow" in str(e).lower():
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"503/Overflow error on attempt {attempt + 1}, waiting {wait_time} seconds before retry...")
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait_time)
                continue
            else:
                print(f"Discord server error: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(5)
                continue
        except Exception as e:
            print(f"Other error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(5)
            continue
    return False

async def main():
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("Error: DISCORD_TOKEN not found in environment variables!")
        print("Please check your .env file.")
        return
    try:
        print("Attempting to connect to Discord...")
        success = await connect_with_retry(client, token, max_retries=5)
        if not success:
            print("Failed to connect after all retries. Check your token and network connection.")
    except KeyboardInterrupt:
        print("Bot shutdown requested by user")
        await client.close()
    except Exception as e:
        print(f"Failed to start bot: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program interrupted by user")
    except Exception as e:
        print(f"Fatal error: {e}")