import aiosqlite
import logging
from datetime import datetime
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "data/trixbot.db"):
        self.db_path = db_path
        self.conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        try:
            self.conn = await aiosqlite.connect(self.db_path)
            self.conn.row_factory = aiosqlite.Row
            await self.init_tables()
            logger.info("Database connected successfully")
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise

    async def init_tables(self):
        try:
            await self.conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await self.conn.execute("""
                CREATE TABLE IF NOT EXISTS user_activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)

            await self.conn.execute("""
                CREATE TABLE IF NOT EXISTS command_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    command TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)

            await self.conn.execute("""
                CREATE TABLE IF NOT EXISTS channel_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER,
                    member_count INTEGER,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await self.conn.execute("""
                CREATE TABLE IF NOT EXISTS publications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    message_id INTEGER,
                    text TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    moderated_at TIMESTAMP,
                    published_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)

            await self.conn.commit()
            logger.info("Database tables initialized")
        except Exception as e:
            logger.error(f"Error initializing tables: {e}")
            raise

    async def execute_query(self, query: str, params: tuple = ()) -> List[Tuple]:
        try:
            cursor = await self.conn.execute(query, params)
            await self.conn.commit()
            return await cursor.fetchall()
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            return []

    async def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
        try:
            await self.conn.execute("""
                INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            """, (user_id, username, first_name, last_name))
            await self.conn.commit()
        except Exception as e:
            logger.error(f"Error adding user: {e}")

    async def update_user_activity(self, user_id: int):
        try:
            now = datetime.now().isoformat()
            await self.conn.execute("""
                UPDATE users SET last_activity = ? WHERE user_id = ?
            """, (now, user_id))
            await self.conn.execute("""
                INSERT INTO user_activity (user_id, last_activity) VALUES (?, ?)
            """, (user_id, now))
            await self.conn.commit()
        except Exception as e:
            logger.error(f"Error updating user activity: {e}")

    async def log_command(self, user_id: int, command: str):
        try:
            await self.conn.execute("""
                INSERT INTO command_usage (user_id, command) VALUES (?, ?)
            """, (user_id, command))
            await self.conn.commit()
        except Exception as e:
            logger.error(f"Error logging command: {e}")

    async def add_channel_stat(self, channel_id: int, member_count: int):
        try:
            await self.conn.execute("""
                INSERT INTO channel_stats (channel_id, member_count) VALUES (?, ?)
            """, (channel_id, member_count))
            await self.conn.commit()
        except Exception as e:
            logger.error(f"Error adding channel stat: {e}")

    async def close(self):
        if self.conn:
            await self.conn.close()
            logger.info("Database connection closed")

db = Database()
