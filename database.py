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
            has_voted INTEGER
        )
    """)

    # votes table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS votes (
            ticket_id TEXT,
            singer TEXT
        )
    """)

    conn.commit()
    conn.close()