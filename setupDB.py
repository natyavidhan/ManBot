import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()


# just run it for First time setup to create the Database and Table

db_path = os.getenv("SQLITE_DB_PATH", "discord_bot.db")
conn = sqlite3.connect(db_path)

cursor = conn.cursor()

# Create table
cursor.execute("""
CREATE TABLE IF NOT EXISTS chat_pairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_message TEXT,
    bot_reply TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()
conn.close()

print(f"SQLite database and table ready at: {db_path}")
