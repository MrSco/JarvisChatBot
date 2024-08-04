window.addEventListener("visibilitychange", function () {
    console.log("Visibility changed");
    if (document.visibilityState === "visible") {
      console.log("APP resumed");
      window.location.reload();
    }
  });

function openNav() {
    document.getElementById("sideNav").style.width = "250px";
}

function closeNav() {
    document.getElementById("sideNav").style.width = "0";
}

function setActiveLink() {
    var currentPath = window.location.pathname;
    if (currentPath === '/') {
        document.getElementById('homeLink').classList.add('active');
    } else if (currentPath === '/history') {
        document.getElementById('historyLink').classList.add('active');
    }
}

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
        var formHeight = document.getElementById('form')?.offsetHeight || 0;
        var headerHeight = document.getElementById('header')?.offsetHeight || 0; 
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
    var urlRegex = /(https?:\/\/[^\s]+\.(jpg|jpeg|png|gif))/i;
    var urlMatch = messageContent.match(urlRegex);
    var continuingResponse = (urlMatch && messageContent.startsWith(urlMatch[0])) || (!messageContent.startsWith("You") && !messageContent.startsWith(assistant_name));
    if(messageContent.startsWith('You') || urlMatch) {
        messageContent = messageContent.replace('You:', '<span class="you">You:</span>');
        // If the message contains an image URL, create a href with an img element inside
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

    if (continuingResponse) {
        var lastMessage = chatLog.lastChild;
        if (messageContent && lastMessage)
           lastMessage.innerHTML += ' ' + messageContent;
        else if (ahref)
            lastMessage.appendChild(ahref);
    }
    else {
        var newMessage = document.createElement('p');
        if(messageContent.startsWith(assistant_name)) {
            newMessage.className = 'darkBg';
            messageContent = messageContent.replace(`${assistant_name}:`, `<span class="assistant_name">${assistant_name}:</span>`);
        }
        newMessage.innerHTML = messageContent;
        if(ahref) {
            newMessage.appendChild(ahref);
        }
        if (messageContent)
            chatLog.appendChild(newMessage);
    }
    scrollToBottom();
}
function chatbot_ready(data) {
    if(data.status === 'ready') {
        if (images_disabled)
            document.querySelector('label[for="file-upload"]').title = 'Groq does not support image analysis. Image uploads are disabled!';
        document.getElementById('image').disabled = images_disabled;
        document.getElementById('sendButton').disabled = false;
        document.getElementById('imagePreview').style.display = 'none';
        setStatusMsg(`Listening for '${assistant_wake_word}'...`);
    }
}

if (location.toString().includes('/history')) {
    document.addEventListener('DOMContentLoaded', function () {
        setActiveLink();
        populateChatLog(chatLogData);
        adjustChatContainerHeight();
        window.onload = scrollToBottom;
        window.addEventListener('resize', adjustChatContainerHeight);

        var dateSelector = document.getElementById('dateSelector');
        dateSelector.value = (new Date()).toISOString().split('T')[0];
        dateSelector.addEventListener('change', function () {
            var selectedDate = dateSelector.value;
            fetchChatLogForDate(selectedDate);
        });
    });

    function fetchChatLogForDate(date) {
        fetch(`/chatlog/${date}`)
            .then(response => response.json())
            .then(chatLogData => {
                chatLogData.forEach(function(message) {
                    update_chat(message);
                });
            })
            .catch(error => console.error('Error fetching chat log:', error));
    }        
}
else {
    document.addEventListener('DOMContentLoaded', function () {
        setActiveLink();
        populateChatLog(chatLogData);
        adjustChatContainerHeight();
        window.onload = scrollToBottom;
        window.addEventListener('resize', adjustChatContainerHeight);
        var thresholdValue = document.getElementById('thresholdValue');
        var thresholdSlider = document.getElementById('thresholdSlider');
        var vad_threshold = thresholdSlider.value;
        var redDot = document.getElementById('redDot');

        var socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port, {
            reconnection: true,
            reconnectionAttempts: Infinity,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            randomizationFactor: 0.5
        });
        socket.on('connect', function () {
            console.log('Connected to the server.');
            chatbot_ready({ status: 'ready' });
        });
        socket.on('disconnect', function (reason) {
            console.log('Disconnected from the server. Reason:', reason);
            setStatusMsg('Disconnected.');
        });

        function submit_form(e) {
            e.preventDefault();
            var prompt = document.getElementById('prompt').value;
            var file = document.getElementById('image').files[0];
            var dataToSend = {prompt};
        
            if (!prompt && !file) {
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

        socket.on('awake', function(data) {
            if(data.status === 'ready') {
                setStatusMsg('Wake word detected!');
            }
        });

        socket.on('listening_for_prompt', function(data) {
            if(data.status === 'ready') {
                setStatusMsg('Listening for prompt...');
            }
        });

        socket.on('chat_response_ready', function(data) {
            if(data.status === 'ready') {
                redDot.title = '';
                redDot.style.visibility = 'hidden';
                setStatusMsg('Responding...');
                document.getElementById('imagePreview').style.display = 'none';
            }
        });

        // Update the threshold value when the slider is changed
        thresholdSlider.addEventListener('input', function() {
            vad_threshold = this.value;
            thresholdValue.innerText = vad_threshold;
            socket.emit("change_vad_threshold", {vad_threshold: vad_threshold});
        });

        socket.on('processing_audio', function(data) {
            if (data.status === 'done') {
                redDot.innerText = parseInt(data.audio_level);
                redDot.style.visibility = 'visible';
            } else {
                redDot.style.visibility = 'hidden';
            }
        });

        socket.on('chatbot_ready', chatbot_ready);

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

        document.getElementById('assistantSelect').addEventListener('change', function() {
            var selectedAssistant = this.value;
            socket.emit("change_assistant", {assistant: selectedAssistant});
        });

        socket.on('assistant_changed', function(data) {
            if(data.assistant) {
                setStatusMsg('Assistant changed.');
                window.location.reload();
            }
        });
    });
}