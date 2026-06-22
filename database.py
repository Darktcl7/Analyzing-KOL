import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

DB_FILE = 'kol_scout.db'

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
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
    
    conn.commit()
    conn.close()

def create_user(username, password):
    username = username.strip()
    if not username or not password:
        return None
        
    password_hash = generate_password_hash(password)
    conn = get_db()
    cursor = conn.cursor()
    try:
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
    finally:
        conn.close()

def verify_user(username, password):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username.strip(),))
    user = cursor.fetchone()
    conn.close()
    
    if user and check_password_hash(user['password_hash'], password):
        return {
            'id': user['id'],
            'username': user['username']
        }
    return None

def get_user_lists(user_id):
    conn = get_db()
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
        
    conn.close()
    return [dict(l) for l in lists]

def create_list(user_id, name):
    name = name.strip()
    if not name:
        return None
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO saved_lists (user_id, name) VALUES (?, ?)",
        (user_id, name)
    )
    list_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return list_id

def delete_list(user_id, list_id):
    conn = get_db()
    cursor = conn.cursor()
    # Security check: ensure list belongs to the user
    cursor.execute("SELECT id FROM saved_lists WHERE id = ? AND user_id = ?", (list_id, user_id))
    list_found = cursor.fetchone()
    if list_found:
        cursor.execute("DELETE FROM saved_lists WHERE id = ?", (list_id,))
        conn.commit()
        success = True
    else:
        success = False
    conn.close()
    return success

def rename_list(user_id, list_id, new_name):
    new_name = new_name.strip()
    if not new_name:
        return False
    conn = get_db()
    cursor = conn.cursor()
    # Security check: ensure list belongs to user
    cursor.execute("SELECT id FROM saved_lists WHERE id = ? AND user_id = ?", (list_id, user_id))
    if cursor.fetchone():
        cursor.execute("UPDATE saved_lists SET name = ? WHERE id = ?", (new_name, list_id))
        conn.commit()
        success = True
    else:
        success = False
    conn.close()
    return success

def get_list_items(list_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM list_items WHERE list_id = ? ORDER BY created_at DESC", (list_id,))
    items = cursor.fetchall()
    conn.close()
    return [dict(item) for item in items]

def add_to_list(list_id, username):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO list_items (list_id, username) VALUES (?, ?)",
            (list_id, username.strip())
        )
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False # Already in list
    finally:
        conn.close()
    return success

def remove_from_list(list_id, username):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM list_items WHERE list_id = ? AND username = ?",
        (list_id, username.strip())
    )
    conn.commit()
    rows = cursor.rowcount
    conn.close()
    return rows > 0

def update_item_crm(list_id, username, status=None, notes=None):
    conn = get_db()
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
        conn.close()
        return False
        
    params.append(list_id)
    params.append(username.strip())
    
    query = f"UPDATE list_items SET {', '.join(updates)} WHERE list_id = ? AND username = ?"
    cursor.execute(query, tuple(params))
    conn.commit()
    rows = cursor.rowcount
    conn.close()
    return rows > 0

def is_username_saved_by_user(user_id, username):
    conn = get_db()
    cursor = conn.cursor()
    # Check across all lists of this user
    cursor.execute("""
        SELECT li.username 
        FROM list_items li
        JOIN saved_lists sl ON li.list_id = sl.id
        WHERE sl.user_id = ? AND li.username = ?
    """, (user_id, username.strip()))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def get_all_saved_usernames_by_user(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT li.username 
        FROM list_items li
        JOIN saved_lists sl ON li.list_id = sl.id
        WHERE sl.user_id = ?
    """, (user_id,))
    results = cursor.fetchall()
    conn.close()
    return {r['username'] for r in results}
