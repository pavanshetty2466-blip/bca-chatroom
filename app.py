from flask import Flask, render_template, request
import os
import sqlite3
from flask_socketio import SocketIO, join_room, leave_room, emit
import re


# PostgreSQL
import psycopg
from psycopg.rows import dict_row


# =========================================================
# APP
# =========================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = "bca1_batch_secret"

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading"
)


# =========================================================
# ROOM SETTINGS
# =========================================================

ROOM_NAME = "BCA 1st Batch"

# Change this whenever you want.
# Treat this like a password.

ROOM_PASSWORD = "BCA2026"

ROOM_ID = "bca_1st_batch_private"


# =========================================================
# DATABASE
# =========================================================

DATABASE_URL = os.environ.get("DATABASE_URL")

SQLITE_DATABASE = "chat.db"


def get_sqlite_connection():
    connection = sqlite3.connect(
        SQLITE_DATABASE,
        check_same_thread=False
    )

    connection.row_factory = sqlite3.Row

    return connection


def init_database():

    if DATABASE_URL:

        print("Using PostgreSQL database.")

        with psycopg.connect(DATABASE_URL) as connection:

            with connection.cursor() as cursor:

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS messages (
                        id BIGSERIAL PRIMARY KEY,
                        username VARCHAR(20) NOT NULL,
                        message TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

            connection.commit()

    else:

        print("DATABASE_URL not found.")
        print("Using local SQLite database.")

        connection = get_sqlite_connection()

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        connection.commit()
        connection.close()


def save_message(username, message):

    if DATABASE_URL:

        with psycopg.connect(DATABASE_URL) as connection:

            with connection.cursor() as cursor:

                cursor.execute(
                    """
                    INSERT INTO messages
                    (username, message)
                    VALUES (%s, %s)
                    """,
                    (username, message)
                )

            connection.commit()

    else:

        connection = get_sqlite_connection()

        connection.execute(
            """
            INSERT INTO messages
            (username, message)
            VALUES (?, ?)
            """,
            (username, message)
        )

        connection.commit()
        connection.close()


def get_all_messages():

    if DATABASE_URL:

        with psycopg.connect(
            DATABASE_URL,
            row_factory=dict_row
        ) as connection:

            with connection.cursor() as cursor:

                cursor.execute(
                    """
                    SELECT username, message, created_at
                    FROM messages
                    ORDER BY id ASC
                    """
                )

                return cursor.fetchall()

    else:

        connection = get_sqlite_connection()

        rows = connection.execute(
            """
            SELECT username, message, created_at
            FROM messages
            ORDER BY id ASC
            """
        ).fetchall()

        connection.close()

        return [
            {
                "username": row["username"],
                "message": row["message"],
                "created_at": row["created_at"]
            }
            for row in rows
        ]


# Initialize database when application starts
init_database()


# =========================================================
# BANNED WORDS
# =========================================================

BANNED_WORDS = {
    "fuck",
    "shit",
    "bitch",
    "asshole",
    "bastard",
    "dick",
    "piss",
    "cunt",
    "slut",
    "whore"
}


# =========================================================
# ACTIVE USERS
# =========================================================

users = {}


# =========================================================
# USERNAME VALIDATION
# =========================================================

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

    cleaned = re.sub(
        r"[^a-z0-9]",
        "",
        username.lower()
    )

    for word in BANNED_WORDS:

        if word in cleaned:

            return False, (
                "This username contains inappropriate language."
            )

    return True, username


# =========================================================
# LOGIN PAGE
# =========================================================

@app.route("/")
def login():

    return render_template(
        "login.html",
        room_name=ROOM_NAME
    )


# =========================================================
# CHAT PAGE
# =========================================================

@app.route("/chat")
def chat():

    return render_template(
        "chat.html",
        room_name=ROOM_NAME
    )


# =========================================================
# CONNECT
# =========================================================

@socketio.on("connect")
def handle_connect():

    print(
        "Client connected:",
        request.sid
    )


# =========================================================
# JOIN ROOM
# =========================================================

@socketio.on("join_room")
def handle_join(data):

    username = str(
        data.get("username", "")
    ).strip()

    password = str(
        data.get("password", "")
    )


    # -----------------------------------------
    # Validate username
    # -----------------------------------------

    valid, result = validate_username(username)

    if not valid:

        emit(
            "join_error",
            {
                "message": result
            }
        )

        return


    # -----------------------------------------
    # Check room password
    # -----------------------------------------

    if password != ROOM_PASSWORD:

        emit(
            "join_error",
            {
                "message": "Incorrect room password."
            }
        )

        return


    # -----------------------------------------
    # Join room
    # -----------------------------------------

    join_room(ROOM_ID)


    users[request.sid] = {
        "username": username,
        "room": ROOM_ID
    }


    # -----------------------------------------
    # Tell user they successfully joined
    # -----------------------------------------

    emit(
        "join_success",
        {
            "username": username
        }
    )


    # -----------------------------------------
    # Send previous messages
    # -----------------------------------------

    try:

        previous_messages = get_all_messages()

        history = []

        for item in previous_messages:

            history.append(
                {
                    "username": item["username"],
                    "message": item["message"],
                    "created_at": str(
                        item["created_at"]
                    )
                }
            )


        emit(
            "message_history",
            {
                "messages": history
            }
        )

    except Exception as error:

        print(
            "Error loading message history:",
            error
        )

        emit(
            "message_history",
            {
                "messages": []
            }
        )


    # -----------------------------------------
    # Notify everyone else
    # -----------------------------------------

    emit(
        "user_joined",
        {
            "username": username
        },
        to=ROOM_ID,
        include_self=False
    )


    print(
        f"{username} joined {ROOM_NAME}"
    )


# =========================================================
# SEND MESSAGE
# =========================================================

@socketio.on("send_message")
def handle_message(data):

    message = str(
        data.get("message", "")
    ).strip()


    if not message:

        return


    if len(message) > 2000:

        emit(
            "message_error",
            {
                "message":
                "Message cannot exceed 2000 characters."
            }
        )

        return


    # -----------------------------------------
    # Verify connected user
    # -----------------------------------------

    user = users.get(request.sid)

    if not user:

        return


    username = user["username"]

    room_id = user["room"]


    # -----------------------------------------
    # Save message
    # -----------------------------------------

    try:

        save_message(
            username,
            message
        )

    except Exception as error:

        print(
            "Database error:",
            error
        )

        emit(
            "message_error",
            {
                "message":
                "Message could not be saved."
            }
        )

        return


    # -----------------------------------------
    # Send message to room
    # -----------------------------------------

    emit(
        "new_message",
        {
            "username": username,
            "message": message
        },
        to=room_id
    )


# =========================================================
# TYPING
# =========================================================

@socketio.on("typing")
def handle_typing(data=None):

    user = users.get(request.sid)

    if not user:

        return


    room_id = user["room"]

    username = user["username"]


    emit(
        "user_typing",
        {
            "username": username
        },
        to=room_id,
        include_self=False
    )


# =========================================================
# STOP TYPING
# =========================================================

@socketio.on("stop_typing")
def handle_stop_typing(data=None):

    user = users.get(request.sid)

    if not user:

        return


    room_id = user["room"]

    username = user["username"]


    emit(
        "user_stop_typing",
        {
            "username": username
        },
        to=room_id,
        include_self=False
    )


# =========================================================
# LEAVE ROOM
# =========================================================

@socketio.on("leave_room")
def handle_leave():

    user = users.get(request.sid)

    if not user:

        return


    room_id = user["room"]

    username = user["username"]


    leave_room(room_id)


    emit(
        "user_left",
        {
            "username": username
        },
        to=room_id
    )


    users.pop(
        request.sid,
        None
    )


# =========================================================
# DISCONNECT
# =========================================================

@socketio.on("disconnect")
def handle_disconnect():

    user = users.get(request.sid)

    if user:

        room_id = user["room"]

        username = user["username"]


        emit(
            "user_left",
            {
                "username": username
            },
            to=room_id
        )


        users.pop(
            request.sid,
            None
        )


    print(
        "Client disconnected"
    )


# =========================================================
# RUN SERVER
# =========================================================

if __name__ == "__main__":

    print()
    print("========================================")
    print("       BCA 1st Batch Chatroom")
    print("========================================")
    print()

    socketio.run(
        app,
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=False
    )