import asyncio
import aiosqlite
import os
from datetime import datetime
import time


class DatabaseHandler:
    async def _create_table(self):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """CREATE TABLE IF NOT EXISTS essence_data (
                time INTEGER,
                group_id INTEGER,
                sender_id INTEGER,
                operator_id INTEGER,
                message_type TEXT,
                message_data TEXT
                )"""
            )
            await conn.execute(
                """CREATE TABLE IF NOT EXISTS user_mapping (
                    nickname TEXT,
                    group_id INTEGER,
                    user_id INTEGER,
                    time INTEGER
                )"""
            )
            await conn.commit()

    def __init__(self, db_path: str):
        self.db_path = db_path
        asyncio.run(self._create_table())

    async def insert_data(self, data):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """INSERT INTO essence_data (time, group_id, sender_id, operator_id, message_type, message_data) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    data["time"],
                    data["group_id"],
                    data["sender_id"],
                    data["operator_id"],
                    data["message_type"],
                    data["message_data"],
                ),
            )
            await conn.commit()
        return True

    async def delete_data(self, data):
        data["message_data"] = data["message_data"][:100]
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                """SELECT rowid 
                       FROM essence_data 
                       WHERE group_id = ? 
                       AND sender_id = ? 
                       AND operator_id = ? 
                       AND message_type = ? 
                       AND message_data LIKE ? 
                       LIMIT 1""",
                (
                    data["group_id"],
                    data["sender_id"],
                    data["operator_id"],
                    data["message_type"],
                    data["message_data"],
                ),
            )
            row = await cursor.fetchone()

            if row:
                rowid = row[0]
                await conn.execute("DELETE FROM essence_data WHERE rowid = ?", (rowid,))
                await conn.commit()
                return True
            return False

    async def fetch_all(self):
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute("SELECT * FROM essence_data")
            return await cursor.fetchall()

    async def summary_by_date(self, date, group_id):
        start_time = int(datetime.strptime(date, "%Y-%m-%d").timestamp())
        end_time = start_time + 86400  # Add one day in seconds

        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT * FROM essence_data WHERE time BETWEEN ? AND ? AND group_id = ?",
                (start_time, end_time, group_id),
            )
            return await cursor.fetchall()

    async def random_essence(self, group_id):
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                """SELECT * FROM essence_data 
                   WHERE group_id = ? 
                   ORDER BY RANDOM() LIMIT 1""",
                (group_id,),
            )
            return await cursor.fetchone()

    async def sender_rank(self, group_id, sender_id):
        async with aiosqlite.connect(self.db_path) as conn:
            # 获取所有排名的查询以便计算指定用户的排名
            rank_query = """
                WITH RankedData AS (
                    SELECT 
                        sender_id,
                        COUNT(*) as count,
                        RANK() OVER (ORDER BY COUNT(*) DESC) as rank
                    FROM essence_data
                    WHERE group_id = ?
                    GROUP BY sender_id
                )
                SELECT sender_id, count, rank
                FROM RankedData
                WHERE rank <= 5 OR sender_id = ?
                ORDER BY rank
            """
            
            cursor = await conn.execute(rank_query, (group_id, sender_id))
            results = await cursor.fetchall()
            
            return results

    async def operator_rank(self, group_id, sender_id):
        async with aiosqlite.connect(self.db_path) as conn:
            # 获取所有排名的查询以便计算指定用户的排名
            rank_query = """
                WITH RankedData AS (
                    SELECT 
                        operator_id,
                        COUNT(*) as count,
                        RANK() OVER (ORDER BY COUNT(*) DESC) as rank
                    FROM essence_data
                    WHERE group_id = ?
                    GROUP BY operator_id
                )
                SELECT operator_id, count, rank
                FROM RankedData
                WHERE rank <= 5 OR operator_id = ?
                ORDER BY rank
            """
            
            cursor = await conn.execute(rank_query, (group_id, sender_id))
            results = await cursor.fetchall()
            
            return results

    async def search_entries(self, group_id, keyword):
        keyword_escaped = keyword.replace("%", r"\%").replace("_", r"\_")
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                """SELECT * FROM essence_data 
                WHERE group_id = ? 
                AND message_type = 'text' 
                AND LENGTH(message_data) <= 100 
                AND message_data LIKE ? ESCAPE '\\' 
                ORDER BY RANDOM() 
                LIMIT 5""",
                (group_id, f"%{keyword_escaped}%"),
            )
            return await cursor.fetchall()

    async def export_group_data(self, group_id):
        export_db_path = os.path.join(
            os.path.dirname(self.db_path), f"group_{group_id}_{int(time.time())}.db"
        )

        async with aiosqlite.connect(self.db_path) as conn:
            async with aiosqlite.connect(export_db_path) as export_conn:
                await export_conn.execute(
                    """CREATE TABLE IF NOT EXISTS essence_data (
                       time INTEGER,
                       group_id INTEGER,
                       sender_id INTEGER,
                       operator_id INTEGER,
                       message_type TEXT,
                       message_data TEXT
                    )"""
                )
                cursor = await conn.execute(
                    "SELECT * FROM essence_data WHERE group_id = ?", (group_id,)
                )
                rows = await cursor.fetchall()
                await export_conn.executemany(
                    """INSERT INTO essence_data 
                       (time, group_id, sender_id, operator_id, message_type, message_data) 
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    rows,
                )
                await export_conn.commit()
        return export_db_path

    async def get_latest_nickname(self, group_id, user_id):
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                """SELECT nickname, time 
                   FROM user_mapping 
                   WHERE group_id = ? AND user_id = ? 
                   ORDER BY time DESC 
                   LIMIT 1""",
                (group_id, user_id),
            )
            result = await cursor.fetchone()
            return result

    async def insert_user_mapping(self, nickname, group_id, user_id, time):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """INSERT INTO user_mapping (nickname, group_id, user_id, time) 
                   VALUES (?, ?, ?, ?)""",
                (nickname, group_id, user_id, time),
            )
            await conn.commit()

    async def entry_exists(self, data):
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                """SELECT COUNT(*) 
                   FROM essence_data 
                   WHERE group_id = ? 
                   AND sender_id = ? 
                   AND message_type = ? 
                   AND message_data LIKE ? """,
                (
                    data["group_id"],
                    data["sender_id"],
                    data["message_type"],
                    data["message_data"][:100],
                ),
            )
            one = await cursor.fetchone()
            return one != None and one[0] != 0
