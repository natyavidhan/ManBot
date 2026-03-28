import asyncio
import os
import sys
import logging
import discord
import aiohttp
from dotenv import load_dotenv
import core.functions as functions
import sqlite3

load_dotenv()
# Database to Store Convo (later we use them to train model)
db_path = os.getenv("SQLITE_DB_PATH", "discord_bot.db")
conn = sqlite3.connect(db_path)
cursor=conn.cursor() #connection done 

INSERT_CHAT_PAIR = """
INSERT INTO chat_pairs (user_message, bot_reply)
VALUES (?, ?)
"""


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# (History is stored in core/functions.py's `history_store`.)


TOKEN = os.getenv("DISCORD_TOKEN")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:4b")
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
OLLAMA_EMPTY_RETRY_NO_THINK = os.getenv("OLLAMA_EMPTY_RETRY_NO_THINK", "1").strip() == "1"


def _env_int(name, default):
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


OLLAMA_NUM_CTX = _env_int("OLLAMA_NUM_CTX", 1536)
OLLAMA_NUM_PREDICT = _env_int("OLLAMA_NUM_PREDICT", 220)
MAX_REPLY_CHAIN_DEPTH = _env_int("MAX_REPLY_CHAIN_DEPTH", 8)
MAX_REPLY_CHAIN_CHARS = _env_int("MAX_REPLY_CHAIN_CHARS", 1200)
OLLAMA_SYSTEM_PROMPT = os.getenv(
    "OLLAMA_SYSTEM_PROMPT",
    "You are a helpful Discord assistant. Be concise, accurate, and practical."
)

http_session = None

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)


async def _get_http_session():
    global http_session
    if http_session is None or http_session.closed:
        timeout = aiohttp.ClientTimeout(total=90, connect=8, sock_read=90)
        connector = aiohttp.TCPConnector(ttl_dns_cache=300, keepalive_timeout=30)
        http_session = aiohttp.ClientSession(timeout=timeout, connector=connector)
    return http_session


async def _close_http_session():
    global http_session
    if http_session is not None and not http_session.closed:
        await http_session.close()
    http_session = None


def _extract_ollama_text(data):
    message = data.get("message")
    if isinstance(message, dict):
        for key in ("content", "response", "output_text", "text"):
            value = message.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    for key in ("response", "output_text", "text"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


async def _chat_ollama(prompt, system_prompt, think=None):
    url = f"{OLLAMA_HOST}/api/chat"
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": {
            "num_ctx": OLLAMA_NUM_CTX,
            "num_predict": OLLAMA_NUM_PREDICT,
        },
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    }
    if think is not None:
        payload["think"] = think

    session = await _get_http_session()
    async with session.post(url, json=payload) as resp:
        if resp.status != 200:
            body = await resp.text()
            raise RuntimeError(f"Ollama error {resp.status}: {body}")
        return await resp.json()


async def ask_ollama(prompt, system_prompt):
    data = await _chat_ollama(prompt, system_prompt)
    text = _extract_ollama_text(data)
    if text:
        return text

    if OLLAMA_EMPTY_RETRY_NO_THINK:
        retry_prompt = (
            prompt
            + "\n\nReturn only a direct final answer. Do not output hidden reasoning."
        )
        data = await _chat_ollama(retry_prompt, system_prompt, think=False)
        text = _extract_ollama_text(data)
        if text:
            return text

    done_reason = data.get("done_reason", "unknown")
    raise RuntimeError(
        f"Ollama returned empty final content (done_reason={done_reason}). "
        "Increase OLLAMA_NUM_PREDICT or disable thinking for this model."
    )


async def _resolve_referenced_message(message):
    if not message.reference:
        return None

    resolved = message.reference.resolved
    if isinstance(resolved, discord.Message):
        return resolved

    if message.reference.message_id:
        try:
            return await message.channel.fetch_message(message.reference.message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None

    return None


async def _build_reply_chain_context(message, max_depth, max_chars):
    lines = []
    seen_ids = set()
    current = await _resolve_referenced_message(message)

    while current and len(lines) < max_depth:
        if current.id in seen_ids:
            break
        seen_ids.add(current.id)

        content = (current.content or "").strip()
        if content:
            author = getattr(current.author, "display_name", current.author.name)
            lines.append(f"{author}: {content}")

        if not current.reference:
            break

        resolved = current.reference.resolved
        if isinstance(resolved, discord.Message):
            current = resolved
            continue

        if current.reference.message_id:
            try:
                current = await current.channel.fetch_message(current.reference.message_id)
                continue
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                break

        break

    if not lines:
        return ""

    chain_text = "\n".join(reversed(lines))
    if len(chain_text) > max_chars:
        chain_text = "..." + chain_text[-(max_chars - 3):]
    return chain_text


def _build_ollama_prompt(memory_key, user_text, reply_chain_context=""):
    history = functions.getHistory(memory_key)
    recent_messages = history[-12:]
    lines = []

    if reply_chain_context:
        lines.append("Reply chain context (oldest to newest):")
        lines.append(reply_chain_context)
        lines.append("")

    for item in recent_messages:
        role = "User" if item.get("role") == "user" else "Assistant"
        content = (item.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")

    if not lines:
        lines.append(f"User: {user_text}")

    lines.append("Assistant:")
    return "\n".join(lines)

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

    referenced_message = await _resolve_referenced_message(message)
    is_reply_to_bot = (
        referenced_message is not None
        and client.user is not None
        and referenced_message.author.id == client.user.id
    )

    # Check if bot should respond (mentioned, replied to, or in private message)
    should_respond = (
            functions.botMentioned(message, client.user) or
            is_reply_to_bot or
            message.guild is None  # Private messages
    )

    if should_respond:
        # Add user message to history
        functions.addUserMessage(memory_key, user_text)

        reply_chain_context = await _build_reply_chain_context(
            message,
            max_depth=MAX_REPLY_CHAIN_DEPTH,
            max_chars=MAX_REPLY_CHAIN_CHARS,
        )

        prompt = _build_ollama_prompt(memory_key, user_text, reply_chain_context)

        try:
            async with message.channel.typing():
                response_text = await ask_ollama(prompt, OLLAMA_SYSTEM_PROMPT)
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.error(f"Ollama connection error: {exc}")
            await message.reply("Sorry, I could not reach the local LLM right now.", mention_author=True)
            return
        except RuntimeError as exc:
            logger.error(f"Ollama response error: {exc}")
            await message.reply("Sorry, the local LLM returned an invalid response.", mention_author=True)
            return
        except Exception as exc:
            logger.error(f"Unexpected LLM error: {exc}")
            await message.reply("Sorry, I encountered an error processing your request.", mention_author=True)
            return

        functions.addBotMessage(memory_key, response_text)

        if user_text and response_text and len(user_text) > 2:
            cursor.execute(INSERT_CHAT_PAIR, (user_text, response_text))
            conn.commit()

        await message.reply(response_text, mention_author=True)

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
    if not TOKEN:
        print("Error: DISCORD_TOKEN not found in environment variables!")
        print("Please check your .env file.")
        return
    try:
        print("Attempting to connect to Discord...")
        success = await connect_with_retry(client, TOKEN, max_retries=5)
        if not success:
            print("Failed to connect after all retries. Check your token and network connection.")
    except KeyboardInterrupt:
        print("Bot shutdown requested by user")
        await client.close()
    except Exception as e:
        print(f"Failed to start bot: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await _close_http_session()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program interrupted by user")
    except Exception as e:
        print(f"Fatal error: {e}")
