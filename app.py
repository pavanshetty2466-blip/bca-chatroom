from flask import Flask, render_template, request
import os
import sqlite3
import re
from flask_socketio import SocketIO, join_room, leave_room, emit

# PostgreSQL
import psycopg
from psycopg.rows import dict_row

app = Flask(__name__)
app.config["SECRET_KEY"] = "bca1_batch_secret"

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading"
)

ROOM_NAME = "BCA 1st Batch"
ROOM_PASSWORD = "BCA2026"
ROOM_ID = "bca_1st_batch_private"
ADMIN_USERNAME = "jon snow"
MAX_IMAGE_CHARS = 750_000

DATABASE_URL = os.environ.get("DATABASE_URL")
SQLITE_DATABASE = "chat.db"


def get_sqlite_connection():
    connection = sqlite3.connect(SQLITE_DATABASE, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def init_database():
    if DATABASE_URL:
        print("Using PostgreSQL database.")
        with psycopg.connect(DATABASE_URL) as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id BIGSERIAL PRIMARY KEY,
                        username VARCHAR(20) NOT NULL,
                        message TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    ALTER TABLE messages
                    ADD COLUMN IF NOT EXISTS message_type VARCHAR(10) NOT NULL DEFAULT 'text'
                """)
            connection.commit()
    else:
        print("DATABASE_URL not found.")
        print("Using local SQLite database.")
        connection = get_sqlite_connection()
        connection.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(messages)").fetchall()
        }
        if "message_type" not in columns:
            connection.execute(
                "ALTER TABLE messages ADD COLUMN message_type TEXT NOT NULL DEFAULT 'text'"
            )
        connection.commit()
        connection.close()


def save_message(username, message, message_type="text"):
    if DATABASE_URL:
        with psycopg.connect(DATABASE_URL) as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO messages (username, message, message_type)
                    VALUES (%s, %s, %s)
                    RETURNING id, created_at
                """, (username, message, message_type))
                row = cursor.fetchone()
            connection.commit()
            return row[0], row[1]

    connection = get_sqlite_connection()
    cursor = connection.execute("""
        INSERT INTO messages (username, message, message_type)
        VALUES (?, ?, ?)
    """, (username, message, message_type))
    message_id = cursor.lastrowid
    row = connection.execute(
        "SELECT created_at FROM messages WHERE id = ?", (message_id,)
    ).fetchone()
    connection.commit()
    connection.close()
    return message_id, row["created_at"]


def get_all_messages():
    if DATABASE_URL:
        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT id, username, message, message_type, created_at
                    FROM messages
                    ORDER BY id ASC
                """)
                return cursor.fetchall()

    connection = get_sqlite_connection()
    rows = connection.execute("""
        SELECT id, username, message, message_type, created_at
        FROM messages
        ORDER BY id ASC
    """).fetchall()
    connection.close()
    return [dict(row) for row in rows]


def delete_message(message_id):
    if DATABASE_URL:
        with psycopg.connect(DATABASE_URL) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM messages WHERE id = %s RETURNING id",
                    (message_id,)
                )
                deleted = cursor.fetchone()
            connection.commit()
            return deleted is not None

    connection = get_sqlite_connection()
    cursor = connection.execute("DELETE FROM messages WHERE id = ?", (message_id,))
    deleted = cursor.rowcount > 0
    connection.commit()
    connection.close()
    return deleted


init_database()

BANNED_WORDS = {
    "fuck", "shit", "bitch", "asshole", "bastard",
    "dick", "piss", "cunt", "slut", "whore"
}

users = {}


def validate_username(username):
    username = username.strip()
    if not username:
        return False, "Please enter your username."
    if len(username) < 2:
        return False, "Username must contain at least 2 characters."
    if len(username) > 20:
        return False, "Username cannot exceed 20 characters."
    if not re.fullmatch(r"[A-Za-z0-9_ ]+", username):
        return False, "Username contains invalid characters."

    cleaned = re.sub(r"[^a-z0-9]", "", username.lower())
    for word in BANNED_WORDS:
        if word in cleaned:
            return False, "This username contains inappropriate language."
    return True, username


def is_admin(username):
    return username.strip().lower() == ADMIN_USERNAME


@app.route("/")
def login():
    return render_template("login.html", room_name=ROOM_NAME)


@app.route("/chat")
def chat():
    return render_template("chat.html", room_name=ROOM_NAME)


@socketio.on("connect")
def handle_connect():
    print("Client connected:", request.sid)


@socketio.on("join_room")
def handle_join(data):
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    valid, result = validate_username(username)
    if not valid:
        emit("join_error", {"message": result})
        return

    if password != ROOM_PASSWORD:
        emit("join_error", {"message": "Incorrect room password."})
        return

    join_room(ROOM_ID)
    users[request.sid] = {
        "username": username,
        "room": ROOM_ID,
        "is_admin": is_admin(username)
    }

    emit("join_success", {
        "username": username,
        "is_admin": is_admin(username)
    })

    try:
        history = []
        for item in get_all_messages():
            history.append({
                "id": item["id"],
                "username": item["username"],
                "message": item["message"],
                "message_type": item.get("message_type", "text"),
                "created_at": str(item["created_at"])
            })
        emit("message_history", {"messages": history})
    except Exception as error:
        print("Error loading message history:", error)
        emit("message_history", {"messages": []})

    emit("user_joined", {"username": username}, to=ROOM_ID, include_self=False)
    emit("room_user_count", {"count": sum(1 for u in users.values() if u["room"] == ROOM_ID)}, to=ROOM_ID)
    print(f"{username} joined {ROOM_NAME}")


@socketio.on("send_message")
def handle_message(data):
    message = str(data.get("message", "")).strip()
    message_type = str(data.get("message_type", "text")).lower()

    user = users.get(request.sid)
    if not user:
        return

    if message_type not in {"text", "image"}:
        emit("message_error", {"message": "Invalid message type."})
        return

    if not message:
        return

    if message_type == "text" and len(message) > 2000:
        emit("message_error", {"message": "Message cannot exceed 2000 characters."})
        return

    if message_type == "image":
        if not message.startswith("data:image/") or ";base64," not in message:
            emit("message_error", {"message": "Invalid image data."})
            return
        if len(message) > MAX_IMAGE_CHARS:
            emit("message_error", {"message": "Image is too large. Please choose a smaller image."})
            return

    username = user["username"]
    room_id = user["room"]

    try:
        message_id, created_at = save_message(username, message, message_type)
    except Exception as error:
        print("Database error:", error)
        emit("message_error", {"message": "Message could not be saved."})
        return

    emit("new_message", {
        "id": message_id,
        "username": username,
        "message": message,
        "message_type": message_type,
        "created_at": str(created_at)
    }, to=room_id)


@socketio.on("delete_message")
def handle_delete_message(data):
    user = users.get(request.sid)
    if not user:
        return

    if not user.get("is_admin"):
        emit("delete_error", {"message": "Only Jon Snow can delete messages."})
        return

    try:
        message_id = int(data.get("id"))
    except (TypeError, ValueError):
        emit("delete_error", {"message": "Invalid message ID."})
        return

    try:
        deleted = delete_message(message_id)
    except Exception as error:
        print("Delete error:", error)
        emit("delete_error", {"message": "Message could not be deleted."})
        return

    if not deleted:
        emit("delete_error", {"message": "Message was already deleted or does not exist."})
        return

    emit("message_deleted", {"id": message_id}, to=user["room"])


@socketio.on("typing")
def handle_typing(data=None):
    user = users.get(request.sid)
    if not user:
        return
    emit("user_typing", {"username": user["username"]}, to=user["room"], include_self=False)


@socketio.on("stop_typing")
def handle_stop_typing(data=None):
    user = users.get(request.sid)
    if not user:
        return
    emit("user_stop_typing", {"username": user["username"]}, to=user["room"], include_self=False)


@socketio.on("leave_room")
def handle_leave():
    user = users.get(request.sid)
    if not user:
        return
    room_id = user["room"]
    username = user["username"]
    leave_room(room_id)
    emit("user_left", {"username": username}, to=room_id)
    users.pop(request.sid, None)
    emit("room_user_count", {"count": sum(1 for u in users.values() if u["room"] == ROOM_ID)}, to=ROOM_ID)


@socketio.on("disconnect")
def handle_disconnect():
    user = users.get(request.sid)
    if user:
        room_id = user["room"]
        username = user["username"]
        emit("user_left", {"username": username}, to=room_id)
        users.pop(request.sid, None)
        emit("room_user_count", {"count": sum(1 for u in users.values() if u["room"] == ROOM_ID)}, to=ROOM_ID)
    print("Client disconnected")


if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
