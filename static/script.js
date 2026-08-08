const socket = io();


// =====================================================
// GET LOGIN INFORMATION
// =====================================================

const username = sessionStorage.getItem("username");
const roomPassword = sessionStorage.getItem("roomPassword");


// =====================================================
// CHECK LOGIN
// =====================================================

if (!username || !roomPassword) {

    window.location.href = "/";

}


// =====================================================
// GET ELEMENTS
// =====================================================

const messages =
    document.getElementById("messages");

const messageInput =
    document.getElementById("messageInput");

const sendButton =
    document.getElementById("sendButton");

const typingIndicator =
    document.getElementById("typingIndicator");

const leaveButton =
    document.getElementById("leaveButton");


// =====================================================
// CONNECT TO SERVER
// =====================================================

socket.on("connect", function () {

    console.log("Connected to server");

    // IMPORTANT:
    // The new socket connection must join the room again.

    socket.emit("join_room", {

        username: username,

        password: roomPassword

    });

});


// =====================================================
// JOIN SUCCESS
// =====================================================

socket.on("join_success", function (data) {

    console.log("Successfully joined chatroom");

});


// =====================================================
// JOIN ERROR
// =====================================================

socket.on("join_error", function (data) {

    alert(data.message);

    sessionStorage.removeItem("username");
    sessionStorage.removeItem("roomPassword");

    window.location.href = "/";

});


// =====================================================
// RECEIVE MESSAGE
// =====================================================

socket.on("new_message", function (data) {

    addMessage(
        data.username,
        data.message
    );

});


// =====================================================
// ADD MESSAGE
// =====================================================

function addMessage(sender, text) {

    const wrapper =
        document.createElement("div");

    wrapper.classList.add(
        "message-wrapper"
    );


    const message =
        document.createElement("div");

    message.classList.add(
        "message"
    );


    // YOUR MESSAGE

    if (sender === username) {

        message.classList.add(
            "my-message"
        );

    }

    // OTHER USER

    else {

        message.classList.add(
            "other-message"
        );

    }


    // USERNAME

    const senderName =
        document.createElement("div");

    senderName.classList.add(
        "sender-name"
    );

    senderName.textContent =
        sender;


    // MESSAGE TEXT

    const messageText =
        document.createElement("div");

    messageText.classList.add(
        "message-text"
    );

    messageText.textContent =
        text;


    message.appendChild(
        senderName
    );

    message.appendChild(
        messageText
    );

    wrapper.appendChild(
        message
    );

    messages.appendChild(
        wrapper
    );


    scrollToBottom();

}


// =====================================================
// SEND MESSAGE
// =====================================================

function sendMessage() {

    const text =
        messageInput.value.trim();


    if (!text) {

        return;

    }


    console.log(
        "Sending message:",
        text
    );


    socket.emit(
        "send_message",
        {
            username: username,
            message: text
        }
    );


    messageInput.value = "";


    socket.emit(
        "stop_typing"
    );

}


// =====================================================
// SEND BUTTON
// =====================================================

sendButton.addEventListener(
    "click",
    function () {

        sendMessage();

    }
);


// =====================================================
// ENTER KEY
// =====================================================

messageInput.addEventListener(
    "keydown",
    function (event) {

        if (event.key === "Enter") {

            event.preventDefault();

            sendMessage();

        }

    }
);


// =====================================================
// TYPING
// =====================================================

let typingTimer = null;


messageInput.addEventListener(
    "input",
    function () {

        socket.emit(
            "typing"
        );


        clearTimeout(
            typingTimer
        );


        typingTimer =
            setTimeout(
                function () {

                    socket.emit(
                        "stop_typing"
                    );

                },
                1000
            );

    }
);


// =====================================================
// SOMEONE IS TYPING
// =====================================================

socket.on(
    "user_typing",
    function (data) {

        typingIndicator.textContent =
            data.username +
            " is typing...";

    }
);


// =====================================================
// STOP TYPING
// =====================================================

socket.on(
    "user_stop_typing",
    function () {

        typingIndicator.textContent =
            "";

    }
);


// =====================================================
// USER JOINED
// =====================================================

socket.on(
    "user_joined",
    function (data) {

        addSystemMessage(
            data.username +
            " joined the chat."
        );

    }
);


// =====================================================
// USER LEFT
// =====================================================

socket.on(
    "user_left",
    function (data) {

        addSystemMessage(
            data.username +
            " left the chat."
        );

    }
);


// =====================================================
// SYSTEM MESSAGE
// =====================================================

function addSystemMessage(text) {

    const system =
        document.createElement("div");

    system.classList.add(
        "system-message"
    );

    system.textContent =
        text;

    messages.appendChild(
        system
    );

    scrollToBottom();

}


// =====================================================
// SCROLL
// =====================================================

function scrollToBottom() {

    messages.scrollTop =
        messages.scrollHeight;

}


// =====================================================
// LEAVE CHAT
// =====================================================

leaveButton.addEventListener(
    "click",
    function () {

        socket.emit(
            "leave_room"
        );


        sessionStorage.removeItem(
            "username"
        );

        sessionStorage.removeItem(
            "roomPassword"
        );


        socket.disconnect();


        window.location.href =
            "/";

    }
);