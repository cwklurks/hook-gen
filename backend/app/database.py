import json
import sqlite3
from datetime import datetime
from typing import Any

DB_PATH = "sessions.db"


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at TEXT,
                bpm REAL,
                scale TEXT,
                density INTEGER,
                syncopation REAL,
                register TEXT,
                histogram TEXT,
                seed INTEGER
            )
        ''')
        conn.commit()


def save_session(session_id: str, data: dict[str, Any]) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO sessions
            (id, created_at, bpm, scale, density, syncopation, register, histogram, seed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            session_id,
            datetime.now().isoformat(),
            data['bpm'],
            data['scale'],
            data['density'],
            data['syncopation'],
            data['register'],
            json.dumps(data['histogram']),
            data['seed']
        ))
        conn.commit()


def get_session(session_id: str) -> dict[str, Any] | None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM sessions WHERE id = ?', (session_id,))
        row = c.fetchone()

        if row:
            d = dict(row)
            d['histogram'] = json.loads(d['histogram'])
            return d
        return None
