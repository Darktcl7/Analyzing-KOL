import sqlite3
import os
import time
import functools
from contextlib import contextmanager
from werkzeug.security import generate_password_hash, check_password_hash

DB_FILE = 'kol_scout.db'

@contextmanager
def get_db():
    """Context manager for database connections. Always closes properly."""
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE, timeout=60.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 60000")  # 60 second busy timeout
        yield conn
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def with_retry(max_retries=5, base_delay=0.2):
    """Decorator that retries database operations on lock errors."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e) or "locked" in str(e).lower():
                        last_error = e
                        delay = base_delay * (2 ** attempt)
                        print(f"[DB RETRY] {func.__name__} attempt {attempt+1}/{max_retries}, waiting {delay:.1f}s...")
                        time.sleep(delay)
                    else:
                        raise
            raise last_error
        return wrapper
    return decorator


def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Create Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create Saved Lists table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS saved_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # Create List Items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS list_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                status TEXT DEFAULT 'Scouted',
                notes TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (list_id) REFERENCES saved_lists(id) ON DELETE CASCADE,
                UNIQUE(list_id, username)
            )
        """)
        
        # Ensure admin user exists with ID 9999 to satisfy FOREIGN KEY checks
        cursor.execute("SELECT id FROM users WHERE id = 9999")
        if not cursor.fetchone():
            admin_hash = generate_password_hash("admin123")
            cursor.execute(
                "INSERT INTO users (id, username, password_hash) VALUES (9999, 'admin', ?)",
                (admin_hash,)
            )
            # Also create default list for admin
            cursor.execute(
                "INSERT OR IGNORE INTO saved_lists (id, user_id, name) VALUES (9999, 9999, 'Daftar Utama')"
            )
            
        conn.commit()


@with_retry()
def create_user(username, password):
    username = username.strip()
    if not username or not password:
        return None
        
    password_hash = generate_password_hash(password)
    with get_db() as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash)
            )
            user_id = cursor.lastrowid
            # Automatically create a default list for the new user
            cursor.execute(
                "INSERT INTO saved_lists (user_id, name) VALUES (?, ?)",
                (user_id, "Daftar Utama")
            )
            conn.commit()
            return user_id
        except sqlite3.IntegrityError:
            return None  # Username already exists


@with_retry()
def verify_user(username, password):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username.strip(),))
        user = cursor.fetchone()
        if user and check_password_hash(user['password_hash'], password):
            return {
                'id': user['id'],
                'username': user['username']
            }
        return None


@with_retry()
def get_user_lists(user_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM saved_lists WHERE user_id = ? ORDER BY id ASC", (user_id,))
        lists = cursor.fetchall()
        
        # If no lists exist, create a default one
        if not lists:
            cursor.execute(
                "INSERT INTO saved_lists (user_id, name) VALUES (?, ?)",
                (user_id, "Daftar Utama")
            )
            conn.commit()
            cursor.execute("SELECT * FROM saved_lists WHERE user_id = ? ORDER BY id ASC", (user_id,))
            lists = cursor.fetchall()
            
        return [dict(l) for l in lists]


@with_retry()
def create_list(user_id, name):
    name = name.strip()
    if not name:
        return None
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO saved_lists (user_id, name) VALUES (?, ?)",
            (user_id, name)
        )
        list_id = cursor.lastrowid
        conn.commit()
        return list_id


@with_retry()
def delete_list(user_id, list_id):
    with get_db() as conn:
        cursor = conn.cursor()
        # Security check: ensure list belongs to the user
        cursor.execute("SELECT id FROM saved_lists WHERE id = ? AND user_id = ?", (list_id, user_id))
        list_found = cursor.fetchone()
        if list_found:
            cursor.execute("DELETE FROM saved_lists WHERE id = ?", (list_id,))
            conn.commit()
            return True
        return False


@with_retry()
def rename_list(user_id, list_id, new_name):
    new_name = new_name.strip()
    if not new_name:
        return False
    with get_db() as conn:
        cursor = conn.cursor()
        # Security check: ensure list belongs to user
        cursor.execute("SELECT id FROM saved_lists WHERE id = ? AND user_id = ?", (list_id, user_id))
        if cursor.fetchone():
            cursor.execute("UPDATE saved_lists SET name = ? WHERE id = ?", (new_name, list_id))
            conn.commit()
            return True
        return False


@with_retry()
def get_list_items(list_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM list_items WHERE list_id = ? ORDER BY created_at DESC", (list_id,))
        items = cursor.fetchall()
        return [dict(item) for item in items]


@with_retry()
def add_to_list(list_id, username):
    with get_db() as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO list_items (list_id, username) VALUES (?, ?)",
                (list_id, username.strip())
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # Already in list


@with_retry()
def remove_from_list(list_id, username):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM list_items WHERE list_id = ? AND username = ?",
            (list_id, username.strip())
        )
        conn.commit()
        return cursor.rowcount > 0


@with_retry()
def update_item_crm(list_id, username, status=None, notes=None):
    with get_db() as conn:
        cursor = conn.cursor()
        updates = []
        params = []
        if status is not None:
            updates.append("status = ?")
            params.append(status.strip())
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes.strip())
            
        if not updates:
            return False
            
        params.append(list_id)
        params.append(username.strip())
        
        query = f"UPDATE list_items SET {', '.join(updates)} WHERE list_id = ? AND username = ?"
        cursor.execute(query, tuple(params))
        conn.commit()
        return cursor.rowcount > 0


@with_retry()
def is_username_saved_by_user(user_id, username):
    with get_db() as conn:
        cursor = conn.cursor()
        # Check across all lists of this user
        cursor.execute("""
            SELECT li.username 
            FROM list_items li
            JOIN saved_lists sl ON li.list_id = sl.id
            WHERE sl.user_id = ? AND li.username = ?
        """, (user_id, username.strip()))
        result = cursor.fetchone()
        return result is not None


@with_retry()
def get_all_saved_usernames_by_user(user_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT li.username 
            FROM list_items li
            JOIN saved_lists sl ON li.list_id = sl.id
            WHERE sl.user_id = ?
        """, (user_id,))
        results = cursor.fetchall()
        return {r['username'] for r in results}
