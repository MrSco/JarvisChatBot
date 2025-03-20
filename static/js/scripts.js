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
        if (ahref && lastMessage)
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
        if (messageContent || ahref)
            chatLog.appendChild(newMessage);
    }
    scrollToBottom();
}
function enable_prompting() {
    if (images_disabled)
        document.querySelector('label[for="file-upload"]').title = 'AI Model does not support image analysis. Image uploads are disabled!';
    document.getElementById('image').disabled = images_disabled;
    document.getElementById('sendButton').disabled = false;
    document.getElementById('imagePreview').style.display = 'none';
    document.getElementById("assistantSelect").disabled = false;
}

function disable_prompting() {
    document.getElementById('prompt').value = '';
    var image = document.getElementById('image');
    image.value = '';
    image.disabled = true;
    document.getElementById('sendButton').disabled = true;
    document.getElementById("assistantSelect").disabled = true;
}

function chatbot_ready(data) {
    if(data.status === 'ready') {
        enable_prompting();
        setStatusMsg(`Listening for '${assistant_wake_word}'...`);
        var radioControlButton = document.getElementById("radioControlButton");
        var kidRadioControlButton = document.getElementById("kidRadioControlButton");
        radioControlButton.disabled = kidRadioControlButton.disabled = false;
        if (radio_playing) {
            setStatusMsg('Music active...');
            radioControlButton.textContent = kidRadioControlButton.textContent = "Stop Radio";
            disable_prompting();
        }
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
        const today = new Date();
        const year = today.getFullYear();
        const month = String(today.getMonth() + 1).padStart(2, '0'); // Months are zero-based
        const day = String(today.getDate()).padStart(2, '0');
        const localDate = `${year}-${month}-${day}`;
        dateSelector.value = localDate;
        dateSelector.addEventListener('change', function () {
            var selectedDate = dateSelector.value;
            fetchChatLogForDate(selectedDate);
        });
    });

    function fetchChatLogForDate(date) {
        fetch(`/chatlog/${date}`)
            .then(response => response.json())
            .then(chatLogData => {
                var chatLog = document.getElementById('chat-log');
                chatLog.innerHTML = '';
                chatLogData.forEach(function(message) {
                    update_chat(message);
                });
            })
            .catch(error => console.error('Error fetching chat log:', error));
    }        
}
else if (location.toString().includes('/settings')) {
    document.addEventListener('DOMContentLoaded', function () {
        setActiveLink();

        // Get the model selection dropdowns
        var openai_modelSelect = document.getElementById('openai_modelSelect');
        var groq_modelSelect = document.getElementById('groq_modelSelect');
        var google_modelSelect = document.getElementById('google_modelSelect');
        var ai_serviceSelect = document.getElementById('ai_service');
        var tts_engineSelect = document.getElementById('tts_engine');
        var image_storageSelect = document.getElementById('image_storage');
        
        // Set the initial values
        openai_modelSelect.value = openai_model;
        groq_modelSelect.value = groq_model;
        google_modelSelect.value = google_model;
        ai_serviceSelect.value = ai_service;
        tts_engineSelect.value = tts_engine;
        image_storageSelect.value = image_storage;
        // Function to show/hide model dropdowns based on selected service
        function updateModelVisibility() {
            var selectedService = ai_serviceSelect.value;

            var openai_modelLabel = document.querySelector('label[for="openai_modelSelect"]');
            var openai_keyLabel = document.querySelector('label[for="openai_key"]');
            var groq_modelLabel = document.querySelector('label[for="groq_modelSelect"]');
            var groq_keyLabel = document.querySelector('label[for="groq_key"]');
            var google_modelLabel = document.querySelector('label[for="google_modelSelect"]');
            var google_keyLabel = document.querySelector('label[for="google_key"]');
            
            // Hide all model dropdowns first
            openai_modelLabel.parentNode.style.display = 'none';
            openai_keyLabel.parentNode.style.display = 'none';
            groq_modelLabel.parentNode.style.display = 'none';
            groq_keyLabel.parentNode.style.display = 'none';
            google_modelLabel.parentNode.style.display = 'none';
            google_keyLabel.parentNode.style.display = 'none';
            
            // Show only the relevant model dropdown
            if (selectedService === 'openai') {
                openai_modelLabel.parentNode.style.display = 'block';
                openai_keyLabel.parentNode.style.display = 'block';
            } else if (selectedService === 'groq') {
                groq_modelLabel.parentNode.style.display = 'block';
                groq_keyLabel.parentNode.style.display = 'block';
            } else if (selectedService === 'google') {
                google_modelLabel.parentNode.style.display = 'block';
                google_keyLabel.parentNode.style.display = 'block';
            }
            updateImageStorageDisabled(selectedService);
        }

        // Function to show/hide TTS related fields based on selected engine
        function updateTTSVisibility() {
            var selectedEngine = tts_engineSelect.value;
            
            // Hide ElevenLabs key by default
            document.querySelector('label[for="elevenlabs_key"]').parentNode.style.display = 'none';
            
            // Show ElevenLabs key only when ElevenLabs is selected
            if (selectedEngine === 'elevenlabs') {
                document.querySelector('label[for="elevenlabs_key"]').parentNode.style.display = 'block';
            }
        }

        // Function to show/hide freeimage key based on selected storage
        function updateImageStorageVisibility() {            
            var selectedStorage = image_storageSelect.value;
            // Hide freeimage key by default
            document.querySelector('label[for="freeimage_key"]').parentNode.style.display = 'none';
            // Show freeimage key only when freeimage is selected
            if (selectedStorage === 'freeimage') {
                document.querySelector('label[for="freeimage_key"]').parentNode.style.display = 'block';
            }
        }

        // Function to disable image storage if ai_service is google
        function updateImageStorageDisabled(selectedService) {
            // Disable image storage if ai_service is google
            if (selectedService === 'google') {
                image_storageSelect.value = 'local';
                image_storageSelect.disabled = true;
                updateImageStorageVisibility();
            }
            else {
                image_storageSelect.disabled = false;
            }
        }

        // Set initial visibility
        updateModelVisibility();
        updateTTSVisibility();
        updateImageStorageVisibility();

        // Update visibility when service selection changes
        ai_serviceSelect.addEventListener('change', updateModelVisibility);
        tts_engineSelect.addEventListener('change', updateTTSVisibility);
        image_storageSelect.addEventListener('change', updateImageStorageVisibility);

        // Set initial TTS engine value
        if (tts_engine == 'elevenlabs') {
            tts_engineSelect.value = 'elevenlabs';
        } else if (tts_engine == 'gtts') {
            tts_engineSelect.value = 'gtts';
        } else {
            tts_engineSelect.value = 'pyttsx3';
        }

        // Update the threshold value when the slider is changed
        thresholdSlider.addEventListener('input', function() {
            vad_threshold = this.value;
            thresholdValue.innerText = vad_threshold;
        });

        document.getElementById('settingsForm').addEventListener('submit', function(event) {
            event.preventDefault();
            var formData = new FormData(this);
            console.log('Submitting settings form', formData);
            fetch('/settings', {
                method: 'POST',
                body: formData
            }).then(response => {
                if (response.ok) {
                    alert('Settings saved successfully!');
                } else {
                    alert('Failed to save settings.');
                }
            });
        });
    });
}
else {
    document.addEventListener('DOMContentLoaded', function () {
        setActiveLink();
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

            // Validate that the file is an image
            const acceptedImageTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/webp', 'image/tiff'];
            if (!acceptedImageTypes.includes(file.type)) {
                return setStatusMsg('Please upload only image files (JPEG, PNG, GIF, BMP, WebP, TIFF)', true);
            }
            // Check file size (limit to 20MB)
            const maxSize = 20 * 1024 * 1024; // 20MB
            if (file.size > maxSize) {
                return setStatusMsg('Image file size must be less than 20MB', true);
            }

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
            var radioControlButton = document.getElementById("radioControlButton");
            var kidRadioControlButton = document.getElementById("kidRadioControlButton");
            if(data.status === 'ready') {
                radioControlButton.disabled = kidRadioControlButton.disabled = true;
                disable_prompting();
                setStatusMsg('Generating response...');
            }
        });

        socket.on('awake', function(data) {
            var radioControlButton = document.getElementById("radioControlButton");
            var kidRadioControlButton = document.getElementById("kidRadioControlButton");
            if(data.status === 'ready') {
                setStatusMsg('Wake word detected!');
                radioControlButton.disabled = kidRadioControlButton.disabled = true;
            }
        });

        socket.on('listening_for_prompt', function(data) {
            var radioControlButton = document.getElementById("radioControlButton");
            var kidRadioControlButton = document.getElementById("kidRadioControlButton");
            if(data.status === 'ready') {
                radioControlButton.disabled = kidRadioControlButton.disabled = true;
                setStatusMsg('Listening for prompt...');
                disable_prompting();
            }
        });

        socket.on('music_active', function(data) {
            var radioControlButton = document.getElementById("radioControlButton");
            var kidRadioControlButton = document.getElementById("kidRadioControlButton");
            if(data.status === 'ready') {
                setStatusMsg('Music active...');
                radioControlButton.textContent = kidRadioControlButton.textContent = "Stop Radio";
                disable_prompting();
                radio_playing = !radio_playing;
            }
            else {
                setStatusMsg('Music stopped...');
                radioControlButton.textContent = "Play Radio";
                kidRadioControlButton.textContent = "Play Kid Radio";
                enable_prompting();
                radio_playing = !radio_playing;
            }
        });                

        window.toggleRadio = function() {
            var radioControlButton = document.getElementById("radioControlButton");
            var kidRadioControlButton = document.getElementById("kidRadioControlButton");
            if (radio_playing) {
                stopRadio(radioControlButton, "Play Radio");
                kidRadioControlButton.textContent = "Play Kid Radio";
            } else {
                playRadio(radioControlButton, "Stop Radio");
                kidRadioControlButton.textContent = "Stop Radio";
            }
        };

        window.toggleKidRadio = function() {
            var radioControlButton = document.getElementById("radioControlButton");
            var kidRadioControlButton = document.getElementById("kidRadioControlButton");
            if (radio_playing) {
                stopRadio(kidRadioControlButton, "Play Kid Radio");
                radioControlButton.textContent = "Play Radio";
            } else {
                playRadio(kidRadioControlButton, "Stop Radio");
                radioControlButton.textContent = "Stop Radio";
            }
        };
        
        function playRadio(btn, text) {
            var radio = btn.id === 'radioControlButton' ? '' : 'kid';
            fetch('/play_radio', { 
                method: 'POST', 
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({radio: radio})
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'error') {
                    console.error("Error stopping radio");
                    return;
                }
                setStatusMsg('Music active...');
                btn.textContent = text;
                disable_prompting();
                radio_playing = !radio_playing;
            })
            .catch(error => {
                console.error("Error starting radio:", error);
            });
        }
        
        function stopRadio(btn, text) {
            fetch('/stop_radio', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'error') {
                        console.error("Error stopping radio");
                        return;
                    }
                    setStatusMsg('Music stopped...');
                    btn.textContent = text;
                    enable_prompting();
                    radio_playing = !radio_playing;
                })
                .catch(error => {
                    console.error("Error stopping radio:", error);
                });
        }

        socket.on('chat_response_ready', function(data) {
            if(data.status === 'ready') {
                setStatusMsg('Responding...');
                document.getElementById('imagePreview').style.display = 'none';
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