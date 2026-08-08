from flask import Flask, render_template
import os
from flask_socketio import SocketIO, join_room, leave_room, emit
import re

app = Flask(__name__)
app.config["SECRET_KEY"] = "bca1_batch_secret"

socketio = SocketIO(
    app,
    cors_allowed_origins="*"
)
# =========================================================
# ROOM SETTINGS
# =========================================================

ROOM_NAME = "BCA 1st Batch"

# Change this whenever you want.
# Treat this like a password.
ROOM_PASSWORD = "BCA2026"


# =========================================================
# BANNED WORDS FOR USERNAMES
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

    # Only letters, numbers, spaces and underscore
    if not re.fullmatch(r"[A-Za-z0-9_ ]+", username):
        return False, "Username contains invalid characters."

    # Check bad words
    cleaned = re.sub(r"[^a-z0-9]", "", username.lower())

    for word in BANNED_WORDS:
        if word in cleaned:
            return False, "This username contains inappropriate language."

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

    print("Client connected:", request_id())


def request_id():
    from flask import request
    return request.sid


# =========================================================
# JOIN ROOM
# =========================================================

@socketio.on("join_room")
def handle_join(data):

    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    # -----------------------------------------
    # Check username
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

    ROOM_ID = "bca_1st_batch_private"

    join_room(ROOM_ID)


    from flask import request

    users[request.sid] = {
        "username": username,
        "room": ROOM_ID
    }


    # -----------------------------------------
    # Tell this user they successfully joined
    # -----------------------------------------

    emit(
        "join_success",
        {
            "username": username
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

    username = str(data.get("username", "")).strip()
    message = str(data.get("message", "")).strip()


    if not username or not message:
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


    from flask import request

    user = users.get(request.sid)

    if not user:
        return


    ROOM_ID = user["room"]


    emit(
        "new_message",
        {
            "username": username,
            "message": message
        },
        to=ROOM_ID
    )


# =========================================================
# TYPING
# =========================================================

@socketio.on("typing")
def handle_typing(data):

    from flask import request

    user = users.get(request.sid)

    if not user:
        return


    ROOM_ID = user["room"]

    username = user["username"]


    emit(
        "user_typing",
        {
            "username": username
        },
        to=ROOM_ID,
        include_self=False
    )


# =========================================================
# STOP TYPING
# =========================================================

@socketio.on("stop_typing")
def handle_stop_typing(data):

    from flask import request

    user = users.get(request.sid)

    if not user:
        return


    ROOM_ID = user["room"]

    username = user["username"]


    emit(
        "user_stop_typing",
        {
            "username": username
        },
        to=ROOM_ID,
        include_self=False
    )


# =========================================================
# LEAVE ROOM
# =========================================================

@socketio.on("leave_room")
def handle_leave():

    from flask import request

    user = users.get(request.sid)

    if not user:
        return


    ROOM_ID = user["room"]
    username = user["username"]


    leave_room(ROOM_ID)


    emit(
        "user_left",
        {
            "username": username
        },
        to=ROOM_ID
    )


    users.pop(request.sid, None)


# =========================================================
# DISCONNECT
# =========================================================

@socketio.on("disconnect")
def handle_disconnect():

    from flask import request

    user = users.get(request.sid)

    if user:

        ROOM_ID = user["room"]
        username = user["username"]


        emit(
            "user_left",
            {
                "username": username
            },
            to=ROOM_ID
        )


        users.pop(request.sid, None)


    print("Client disconnected")


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
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )