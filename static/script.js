const socket = io();

const username = sessionStorage.getItem("username");
const roomPassword = sessionStorage.getItem("roomPassword");

if (!username || !roomPassword) window.location.href = "/";

const messages = document.getElementById("messages");
const messageInput = document.getElementById("messageInput");
const sendButton = document.getElementById("sendButton");
const typingIndicator = document.getElementById("typingIndicator");
const leaveButton = document.getElementById("leaveButton");
const imageButton = document.getElementById("imageButton");
const imageInput = document.getElementById("imageInput");
const imagePreview = document.getElementById("imagePreview");
const previewImage = document.getElementById("previewImage");
const cancelImage = document.getElementById("cancelImage");
const onlineCount = document.getElementById("onlineCount");

let selectedImage = null;
let typingTimer = null;
let isAdmin = false;

socket.on("connect", () => {
    socket.emit("join_room", { username, password: roomPassword });
});

socket.on("join_success", (data) => {
    isAdmin = Boolean(data.is_admin);
    document.body.classList.toggle("admin-mode", isAdmin);
});

socket.on("join_error", (data) => {
    alert(data.message);
    sessionStorage.removeItem("username");
    sessionStorage.removeItem("roomPassword");
    window.location.href = "/";
});

socket.on("message_history", (data) => {
    messages.innerHTML = "";
    data.messages.forEach(addMessage);
    scrollToBottom();
});

socket.on("new_message", addMessage);

socket.on("message_deleted", (data) => {
    const element = document.querySelector(`[data-message-id="${data.id}"]`);
    if (element) {
        element.classList.add("message-removing");
        setTimeout(() => element.remove(), 180);
    }
});

socket.on("delete_error", (data) => alert(data.message));

socket.on("message_error", (data) => alert(data.message));

socket.on("room_user_count", (data) => {
    onlineCount.textContent = `${data.count} online`;
});

socket.on("user_typing", (data) => {
    typingIndicator.textContent = `${data.username} is typing…`;
});

socket.on("user_stop_typing", () => {
    typingIndicator.textContent = "";
});

function addMessage(item) {
    const sender = item.username;
    const type = item.message_type || "text";
    const wrapper = document.createElement("div");
    wrapper.className = "message-wrapper";
    wrapper.dataset.messageId = item.id;

    const message = document.createElement("div");
    message.className = `message ${sender === username ? "my-message" : "other-message"}`;

    const top = document.createElement("div");
    top.className = "message-top";

    const senderName = document.createElement("div");
    senderName.className = "sender-name";
    senderName.textContent = sender;
    top.appendChild(senderName);

    if (isAdmin) {
        const deleteButton = document.createElement("button");
        deleteButton.className = "delete-button";
        deleteButton.type = "button";
        deleteButton.title = "Delete message";
        deleteButton.textContent = "🗑️";
        deleteButton.addEventListener("click", () => {
            if (confirm("Delete this message for everyone?")) {
                socket.emit("delete_message", { id: item.id });
            }
        });
        top.appendChild(deleteButton);
    }

    message.appendChild(top);

    if (type === "image") {
        const img = document.createElement("img");
        img.className = "chat-image";
        img.src = item.message;
        img.alt = `Image sent by ${sender}`;
        img.loading = "lazy";
        img.addEventListener("click", () => openImage(item.message));
        message.appendChild(img);
    } else {
        const text = document.createElement("div");
        text.className = "message-text";
        text.textContent = item.message;
        message.appendChild(text);
    }

    const time = document.createElement("div");
    time.className = "message-time";
    time.textContent = formatTime(item.created_at);
    message.appendChild(time);

    wrapper.appendChild(message);
    messages.appendChild(wrapper);
    scrollToBottom();
}

function formatTime(value) {
    if (!value) return "";
    const date = new Date(value.replace(" ", "T") + (value.includes("Z") ? "" : "Z"));
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function sendMessage() {
    if (selectedImage) {
        socket.emit("send_message", { message: selectedImage, message_type: "image" });
        clearSelectedImage();
        return;
    }

    const text = messageInput.value.trim();
    if (!text) return;

    socket.emit("send_message", { message: text, message_type: "text" });
    messageInput.value = "";
    socket.emit("stop_typing");
}

sendButton.addEventListener("click", sendMessage);

messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
        event.preventDefault();
        sendMessage();
    }
});

messageInput.addEventListener("input", () => {
    socket.emit("typing");
    clearTimeout(typingTimer);
    typingTimer = setTimeout(() => socket.emit("stop_typing"), 900);
});

imageButton.addEventListener("click", () => imageInput.click());

imageInput.addEventListener("change", async () => {
    const file = imageInput.files[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
        alert("Please select an image file.");
        imageInput.value = "";
        return;
    }

    try {
        selectedImage = await compressImage(file);
        previewImage.src = selectedImage;
        imagePreview.hidden = false;
        messageInput.placeholder = "Image selected — tap ➤ to send";
    } catch (error) {
        console.error(error);
        alert("Could not prepare that image. Please try another one.");
        clearSelectedImage();
    }
});

cancelImage.addEventListener("click", clearSelectedImage);

function clearSelectedImage() {
    selectedImage = null;
    imageInput.value = "";
    previewImage.removeAttribute("src");
    imagePreview.hidden = true;
    messageInput.placeholder = "Write a message...";
}

function compressImage(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onerror = reject;
        reader.onload = () => {
            const img = new Image();
            img.onerror = reject;
            img.onload = () => {
                const maxSide = 1280;
                const scale = Math.min(1, maxSide / Math.max(img.width, img.height));
                const canvas = document.createElement("canvas");
                canvas.width = Math.max(1, Math.round(img.width * scale));
                canvas.height = Math.max(1, Math.round(img.height * scale));
                const ctx = canvas.getContext("2d");
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                resolve(canvas.toDataURL("image/jpeg", 0.76));
            };
            img.src = reader.result;
        };
        reader.readAsDataURL(file);
    });
}

function openImage(src) {
    const overlay = document.createElement("div");
    overlay.className = "image-lightbox";
    overlay.innerHTML = `<button class="lightbox-close" aria-label="Close">×</button><img alt="Full size image">`;
    overlay.querySelector("img").src = src;
    const close = () => overlay.remove();
    overlay.addEventListener("click", (event) => {
        if (event.target === overlay || event.target.classList.contains("lightbox-close")) close();
    });
    document.body.appendChild(overlay);
}

leaveButton.addEventListener("click", () => {
    socket.emit("leave_room");
    sessionStorage.removeItem("username");
    sessionStorage.removeItem("roomPassword");
    window.location.href = "/";
});

function scrollToBottom() {
    requestAnimationFrame(() => {
        messages.scrollTop = messages.scrollHeight;
    });
}
