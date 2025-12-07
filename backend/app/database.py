import sqlite3
import json
from datetime import datetime

DB_PATH = "sessions.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
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
    conn.close()

def save_session(session_id, data):
    conn = sqlite3.connect(DB_PATH)
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
    conn.close()

def get_session(session_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM sessions WHERE id = ?', (session_id,))
    row = c.fetchone()
    conn.close()
    
    if row:
        d = dict(row)
        d['histogram'] = json.loads(d['histogram'])
        return d
    return None
