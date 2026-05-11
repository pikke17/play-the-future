import sqlite3

DB_NAME = "database.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # ticket table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id TEXT PRIMARY KEY,
            has_voted INTEGER,
            day INTEGER NOT NULL
        )
    """)

    # votes table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT,
            singer_id INTEGER,
            day INTEGER NOT NULL
        )
    """)

    # singers table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS singers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            firstName TEXT NOT NULL,
            lastName TEXT,
            songTitle TEXT NOT NULL,
            songAuthor TEXT NOT NULL,
            day INTEGER NOT NULL
        )
    """)

    # config table 
    cur.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # default --> televoting OFF
    cur.execute("""
        INSERT OR IGNORE INTO config (key, value)
        VALUES ('televoting_active_day_1', '0')
    """)

    cur.execute("""
        INSERT OR IGNORE INTO config (key, value)
        VALUES ('televoting_active_day_2', '0')
    """)

    # default --> current day = 1
    cur.execute("""
        INSERT OR IGNORE INTO config (key, value)
        VALUES ('current_day', '1')
    """)


    conn.commit()
    conn.close()