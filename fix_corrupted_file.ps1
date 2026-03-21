$filePath = "c:\Users\wayne\Documents\edusync-babu\communication_stage.html"
$content = Get-Content $filePath -Raw
$startMark = "        function cleanMarkdownFormatting(text) {"
$endMark = "        // ==========================================================\n        // 17. CONVERSATION PRACTICE (DEPRECATED - NOW IN UNIFIED AI CHAT)"

# This is the correct block to insert
$newBlock = @"
        function cleanMarkdownFormatting(text) {
            if (!text) return '';
            text = text.replace(/\*\*([^*]+)\*\*/g, '$1');
            text = text.replace(/\*([^*]+)\*/g, '$1');
            text = text.replace(/#+\s+/gm, '');
            text = text.replace(/^\s*[-*+•]\s+/gm, '');
            text = text.replace(/`([^`]+)`/g, '$1');
            return text.trim();
        }

        async function sendAIChat() {
            const inputElement = document.getElementById('aiChatInput');
            const message = inputElement.value.trim();

            if (!message) {
                showToast('warning', 'Empty Message', 'Please type something to send.');
                return;
            }

            try {
                const messagesDiv = document.getElementById('aiChatMessages');
                const userMsg = document.createElement('div');
                userMsg.className = 'message user';
                userMsg.innerHTML = `${escapeHtml(message)} <div class="message-time">Just now</div>`;
                messagesDiv.appendChild(userMsg);
                inputElement.value = '';
                messagesDiv.scrollTop = messagesDiv.scrollHeight;

                const loadingMsg = document.createElement('div');
                loadingMsg.className = 'message ai';
                loadingMsg.id = 'loadingMsg';
                loadingMsg.innerHTML = `<span style="opacity: 0.6;">Thinking...</span>`;
                messagesDiv.appendChild(loadingMsg);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;

                const systemConfig = "You are a helpful english teacher and grammar expert. Give short corrections and encouraging feedback.";
                const response = await window.puter.ai.chat(
                    systemConfig + "\n\nUser: " + message,
                    { model: 'gpt-4o', stream: false }
                );

                const loading = document.getElementById('loadingMsg');
                if (loading) loading.remove();

                const aiMsg = document.createElement('div');
                aiMsg.className = 'message ai';
                
                let text = '';
                if (typeof response === 'string') text = response;
                else if (response?.message?.content?.[0]?.text) text = response.message.content[0].text;
                else if (response?.text) text = response.text;
                else text = 'I am here to help you improve your English.';

                let formatted = escapeHtml(text).replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                aiMsg.innerHTML = `<div style="line-height: 1.6;">` + formatted + `</div><div class="message-time">Just now</div>`;
                messagesDiv.appendChild(aiMsg);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;

            } catch (error) {
                console.error('Puter Error:', error);
                const messagesDiv = document.getElementById('aiChatMessages');
                const errorMsg = document.createElement('div');
                errorMsg.className = 'message ai';
                errorMsg.innerHTML = 'Service currently unavailable. <div class="message-time">Just now</div>';
                messagesDiv.appendChild(errorMsg);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
                const loading = document.getElementById('loadingMsg');
                if (loading) loading.remove();
            }
        }
"@

# Since the file is corrupted, markers might not exist. 
# We'll replace lines from 11500 to 11800 roughly.
$lines = Get-Content $filePath
$before = $lines[0..11540]
$after = $lines[11800..($lines.Count-1)]

# Join them
$finalContent = @($before; $newBlock; $after) | Out-String
# Write back with UTF8 to preserve characters
[IO.File]::WriteAllText($filePath, $finalContent, [System.Text.Encoding]::UTF8)
