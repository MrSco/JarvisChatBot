window.addEventListener("visibilitychange", function () {
    console.log("Visibility changed");
    if (document.visibilityState === "visible") {
      console.log("APP resumed");
      window.location.reload();
    }
  });

function adjustChatContainerHeight() {
    var chatContainer = document.querySelector('.chat-container');
    if (chatContainer) {
        // Set the height of the chat container to the window's inner height
        // This accounts for mobile browsers where the vh unit does not always account for the address bar
        chatContainer.style.height = window.innerHeight + 'px';
    }
    var chatLog = document.getElementById('chat-log');
    if (chatLog) {
        var viewportHeight = window.innerHeight;
        var formHeight = document.getElementById('form').offsetHeight;
        var headerHeight = document.getElementById('header').offsetHeight; 
        var padding = 30;
        var availableHeight = viewportHeight - formHeight - headerHeight - padding;

        chatLog.style.height = availableHeight + 'px';
    }
}
function populateChatLog(chatLogData) {
    chatLogData.forEach(function(message) {
        update_chat(message); 
    });
}
function scrollToBottom() {
    var chatLog = document.getElementById('chat-log');
    var images = chatLog.getElementsByTagName('img');
    var imageLoadPromises = [];

    for (let img of images) {
        if (!img.complete) {
            let promise = new Promise((resolve) => {
                img.onload = resolve;
                img.onerror = resolve; // Also resolve on error to not block scrolling
            });
            imageLoadPromises.push(promise);
        }
    }

    // Wait for all images to load or a maximum of 5 seconds (as a fallback)
    Promise.all(imageLoadPromises).then(() => {
        chatLog.scrollTop = chatLog.scrollHeight;
    }).catch(() => {
        chatLog.scrollTop = chatLog.scrollHeight;
    });

    setTimeout(() => {
        chatLog.scrollTop = chatLog.scrollHeight;
    }, 5000); // Fallback timeout
}
function setStatusMsg(msg, error) {
    var statusMsg = document.getElementById('statusMsg');
    statusMsg.textContent = msg;
    if (error) {
        statusMsg.classList.add('error');
    } else {
        statusMsg.classList.remove('error');
    }
}
function update_chat(data) {
    if (!data) {
        return;
    }
    var chatLog = document.getElementById('chat-log');
    var messageContent = data.message;
    if (!messageContent) {
        return;
    }
    var ahref = null;
    if(messageContent.startsWith('You')) {
        messageContent = messageContent.replace('You:', '<span class="you">You:</span>');
        // If the message contains an image URL, create an a href with an img element inside
        var urlRegex = /(https?:\/\/[^\s]+\.(jpg|jpeg|png|gif))/i;
        var urlMatch = messageContent.match(urlRegex);
        if (urlMatch) {
            messageContent = messageContent.replace(urlRegex, '');
            var imageElement = document.createElement('img');
            imageElement.src = urlMatch[0];
            imageElement.className = 'inline-image';
            ahref = document.createElement('a');
            ahref.href = urlMatch[0];
            ahref.target = '_blank';
            ahref.appendChild(imageElement);
        }
    }

    var newMessage = document.createElement('p');
    if(messageContent.startsWith('Jarvis')) {
        newMessage.className = 'darkBg';
        messageContent = messageContent.replace('Jarvis:', '<span class="jarvis">Jarvis:</span>');
    }
    newMessage.innerHTML = messageContent;
    if(ahref) {
        newMessage.appendChild(ahref);
    }
    if (messageContent)
        chatLog.appendChild(newMessage);
    scrollToBottom();
}
function jarvis_ready(data) {
    if(data.status === 'ready') {
        document.getElementById('image').disabled = false;
        document.getElementById('sendButton').disabled = false;
        document.getElementById('imagePreview').style.display = 'none';
        setStatusMsg('Listening for wake word...');
    }
}
document.addEventListener('DOMContentLoaded', function () {
    populateChatLog(chatLogData);
    adjustChatContainerHeight();
    window.onload = scrollToBottom;
    window.addEventListener('resize', adjustChatContainerHeight);
    var socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port, {
        reconnection: true,
        reconnectionAttempts: Infinity,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        randomizationFactor: 0.5
    });
    socket.on('connect', function () {
        console.log('Connected to the server.');
        jarvis_ready({ status: 'ready' });
    });
    socket.on('disconnect', function (reason) {
        console.log('Disconnected from the server. Reason:', reason);
        setStatusMsg('Disconnected.');
    });
    socket.on('reconnect', function (attemptNumber) {
        console.log('Reconnected to the server after', attemptNumber, 'attempts.');
        setStatusMsg('Reconnected.');
    });
    socket.on('reconnect_attempt', function () {
        console.log('Attempting to reconnect to the server...');
        setStatusMsg('Reconnecting...');
    });

    function submit_form(e) {
        e.preventDefault();
        var prompt = document.getElementById('prompt').value;
        var file = document.getElementById('image').files[0];
        var dataToSend = {prompt};
    
        if (!prompt && !image) {
            return setStatusMsg('Please enter a prompt or upload an image!', true);
        }
        
        if (!file)
            return socket.emit("file_chunk", {
                fileId: null,
                ...dataToSend,
            });
        // if CHUNK_SIZE >= 1MB then the socket header gets overwritten and throws errors
        const CHUNK_SIZE = 1024 * 512; // 0.5MB
        const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
        const fileId = `${file.name}-${Date.now()}`; // Unique ID for the file upload
    
        for (let i = 0; i < totalChunks; i++) {
            const blob = file.slice(i * CHUNK_SIZE, (i + 1) * CHUNK_SIZE);
            const reader = new FileReader();
            reader.onload = (e) => {
                const base64Content = e.target.result.split(",")[1];
                socket.emit("file_chunk", {
                    fileId: fileId,
                    chunkIndex: i,
                    totalChunks: totalChunks,
                    chunkData: base64Content,
                    fileName: file.name, // Consider sanitizing on the server
                    ...dataToSend,
                });
            };
            reader.readAsDataURL(blob);
        }
    }
    
    socket.on('update_chat', update_chat);

    socket.on('prompt_received', function(data) {
        if(data.status === 'ready') {
            document.getElementById('prompt').value = '';
            var image = document.getElementById('image');
            image.value = '';
            image.disabled = true;
            document.getElementById('sendButton').disabled = true;
            setStatusMsg('Generating response...');
        }
    });

    socket.on('chat_response_ready', function(data) {
        if(data.status === 'ready') {
            setStatusMsg('Responding...');
            document.getElementById('imagePreview').style.display = 'none';
        }
    });

    socket.on('jarvis_ready', jarvis_ready);

    document.getElementById('form').addEventListener('submit', submit_form);

    document.getElementById('image').addEventListener('change', function(e) {
        var image = e.target.files[0];
        if (image) {
            var reader = new FileReader();
            reader.onload = function(e) {
                var preview = document.getElementById('imagePreview');
                preview.src = e.target.result;
                preview.style.display = 'inline-block';
            };
            reader.readAsDataURL(image);
        }
    });

    document.querySelector('label[for="file-upload"]').addEventListener('click', function(e) {
        e.preventDefault();
        document.getElementById('image').click();
    });
});