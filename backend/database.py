import os
import mysql.connector
import numpy as np
from backend.config import DB_CONFIG
def get_connection():
    return mysql.connector.connect(**DB_CONFIG)
def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                avatar_url TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS face_embeddings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                embedding LONGBLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                name VARCHAR(255) NOT NULL,
                timestamp DATETIME NOT NULL,
                log_date DATE NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        conn.commit()
    finally:
        cursor.close()
        conn.close()
# =========================================================
# USER CRUD
# =========================================================
def create_user(name, avatar_url=None):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (name, avatar_url) VALUES (%s, %s)",
            (name, avatar_url)
        )
        user_id = cursor.lastrowid
        conn.commit()
        return user_id
    finally:
        cursor.close()
        conn.close()
def get_user(user_id):
    conn = get_connection()
    cursor = conn.cursor(buffered=True, dictionary=True)
    try:
        cursor.execute("SELECT id, name, created_at FROM users WHERE id = %s", (user_id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()
def get_all_users():
    conn = get_connection()
    cursor = conn.cursor(buffered=True, dictionary=True)
    try:
        cursor.execute("SELECT id, name, avatar_url, created_at FROM users ORDER BY id DESC")
        rows = cursor.fetchall()
        # Ép kiểu datetime về string chuẩn ISO để FastAPI trả JSON dễ hơn
        for row in rows:
            if row.get("created_at"):
                row["created_at"] = str(row["created_at"])
        return rows
    finally:
        cursor.close()
        conn.close()
def get_user(user_id):
    conn = get_connection()
    cursor = conn.cursor(buffered=True, dictionary=True)
    try:
        cursor.execute("SELECT id, name, avatar_url, created_at FROM users WHERE id = %s", (user_id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()
def update_user(user_id, new_name):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET name = %s WHERE id = %s", (new_name, user_id))
        cursor.execute("UPDATE attendance_logs SET name = %s WHERE user_id = %s", (new_name, user_id))
        affected_rows = cursor.rowcount
        conn.commit()
        return affected_rows > 0
    finally:
        cursor.close()
        conn.close()
def update_user_avatar(user_id, avatar_url):
    """
    UPDATE: Cập nhật đường dẫn avatar_url mới cho người dùng
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE users SET avatar_url = %s WHERE id = %s",
            (avatar_url, user_id)
        )
        affected_rows = cursor.rowcount
        conn.commit()
        return affected_rows > 0
    finally:
        cursor.close()
        conn.close()
def delete_user(user_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT avatar_url FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            return False, None
        avatar_url = user.get("avatar_url")
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        return True, avatar_url
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()
# =========================================================
# EMBEDDING CRUD
# =========================================================
def save_embedding(user_id, embedding):
    embedding = np.asarray(embedding, dtype=np.float32)
    embedding_blob = embedding.tobytes()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO face_embeddings (user_id, embedding) VALUES (%s, %s)",
            (user_id, embedding_blob)
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()
def load_embeddings():
    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    try:
        cursor.execute("""
            SELECT face_embeddings.user_id, users.name, face_embeddings.embedding
            FROM face_embeddings
            JOIN users ON users.id = face_embeddings.user_id
        """)
        rows = cursor.fetchall()
        embeddings, names, user_ids = [], [], []
        for user_id, name, blob in rows:
            embedding = np.frombuffer(memoryview(blob), dtype=np.float32)
            embeddings.append(embedding)
            names.append(name)
            user_ids.append(user_id)
        return embeddings, names, user_ids
    finally:
        cursor.close()
        conn.close()
def update_user_embedding(user_id, new_embedding):
    new_embedding = np.asarray(new_embedding, dtype=np.float32)
    embedding_blob = new_embedding.tobytes()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM face_embeddings WHERE user_id = %s", (user_id,))
        cursor.execute(
            "INSERT INTO face_embeddings (user_id, embedding) VALUES (%s, %s)",
            (user_id, embedding_blob)
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()
def delete_embeddings_by_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM face_embeddings WHERE user_id = %s", (user_id,))
        affected_rows = cursor.rowcount
        conn.commit()
        return affected_rows > 0
    finally:
        cursor.close()
        conn.close()
# =========================================================
# ATTENDANCE CRUD
# =========================================================
def log_attendance(user_id, name, timestamp, log_date):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO attendance_logs (user_id, name, timestamp, log_date) VALUES (%s, %s, %s, %s)",
            (user_id, name, timestamp, log_date)
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()
def get_attendance_history():
    conn = get_connection()
    cursor = conn.cursor(buffered=True, dictionary=True)
    try:
        cursor.execute("""
            SELECT id, user_id, name, timestamp, log_date
            FROM attendance_logs
            ORDER BY timestamp DESC
        """)
        rows = cursor.fetchall()
        for row in rows:
            if row.get("timestamp"):
                row["timestamp"] = str(row["timestamp"])
            if row.get("log_date"):
                row["log_date"] = str(row["log_date"])
        return rows
    finally:
        cursor.close()
        conn.close()
def delete_attendance_log(log_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM attendance_logs WHERE id = %s", (log_id,))
        affected_rows = cursor.rowcount
        conn.commit()
        return affected_rows > 0
    finally:
        cursor.close()
        conn.close()