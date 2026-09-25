import aiosqlite
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class DatabaseLayer:
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS stations (
                    station_code TEXT PRIMARY KEY,
                    station_full_name TEXT,
                    station_zone TEXT,
                    station_address TEXT
                )
            ''')
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS trains (
                    train_no TEXT PRIMARY KEY,
                    train_name TEXT,
                    type_code TEXT
                )
            ''')
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS routes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    train_no TEXT,
                    station_code TEXT,
                    station_no INTEGER,
                    distance_from_origin REAL,
                    arrival_day INTEGER,
                    arrival_time TEXT,
                    departure_day INTEGER,
                    departure_time TEXT,
                    FOREIGN KEY(train_no) REFERENCES trains(train_no),
                    FOREIGN KEY(station_code) REFERENCES stations(station_code)
                )
            ''')
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    train_no TEXT,
                    date TEXT,
                    station_code TEXT,
                    predicted_delay_minutes INTEGER,
                    prediction_time TEXT
                )
            ''')
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS prediction_revisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prediction_id INTEGER,
                    revised_delay_minutes INTEGER,
                    revision_time TEXT,
                    FOREIGN KEY(prediction_id) REFERENCES predictions(id)
                )
            ''')
            
            await db.commit()

    async def get_station(self, station_code: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM stations WHERE station_code = ?", (station_code,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_train(self, train_no: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM trains WHERE train_no = ?", (train_no,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_route(self, train_no: str) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM routes WHERE train_no = ? ORDER BY station_no", (train_no,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
