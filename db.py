import mysql.connector

DB_CONFIG = {
    "host": "192.168.1.138",
    "user": "user1",
    "port":"3306",
    "password": "myroot",   
    "database": "audio_studio",
}

_connection = None   # module-level connection reused by all functions


def get_connection():
    """Return a live connection, creating or reconnecting if needed."""
    global _connection
    if _connection is None or not _connection.is_connected():
        _connection = mysql.connector.connect(**DB_CONFIG)
    return _connection


def execute(query, params=None):
    """Run INSERT / UPDATE / DELETE. Returns lastrowid (useful after INSERT)."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(query, params or ())
        conn.commit()
        return cur.lastrowid
    except mysql.connector.Error:
        conn.rollback()
        raise
    finally:
        cur.close()


def fetch_one(query, params=None):
    """Run a SELECT and return one row as a dict (or None)."""
    cur = get_connection().cursor(dictionary=True)
    try:
        cur.execute(query, params or ())
        return cur.fetchone()
    finally:
        cur.close()


def fetch_all(query, params=None):
    """Run a SELECT and return all rows as a list of dicts."""
    cur = get_connection().cursor(dictionary=True)
    try:
        cur.execute(query, params or ())
        return cur.fetchall()
    finally:
        cur.close()


def close_connection():
    global _connection
    if _connection is not None and _connection.is_connected():
        _connection.close()
    _connection = None