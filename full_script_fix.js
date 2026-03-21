        function insertAIChatExample(text) {
            const input = document.getElementById('aiChatInput');
            input.value = text;
            input.focus();
        }

        function clearAIChat() {
            document.getElementById('aiChatMessages').innerHTML = `
                <div class="message ai">
                    Chat cleared! Ready to help you with English learning.
                    <div class="message-time">Just now</div>
                </div>
            `;
        }

        function handleAIChatInput(event) {
            if (event.key === 'Enter' && event.ctrlKey) {
                sendAIChat();
            }
        }

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
                    systemConfig + "\n\nUser text: " + message,
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
                else text = 'Help mode active. How can I assist you further?';

                let formatted = escapeHtml(text).replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                aiMsg.innerHTML = `<div style="line-height: 1.6;">${formatted}</div><div class="message-time">Just now</div>`;
                messagesDiv.appendChild(aiMsg);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;

            } catch (error) {
                console.error('Puter Error:', error);
                const loading = document.getElementById('loadingMsg');
                if (loading) loading.remove();
                
                const messagesDiv = document.getElementById('aiChatMessages');
                const errorMsg = document.createElement('div');
                errorMsg.className = 'message ai';
                errorMsg.innerHTML = `Service unavailable at the moment. Please try again. <div class="message-time">Just now</div>`;
                messagesDiv.appendChild(errorMsg);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }
        }

        // ==========================================================
        // 17. CONVERSATION PRACTICE (RESTORED)
        // ==========================================================

        function openConversationPractice() {
            showSection('ai-chat');
            setAIChatMode('conversation');
        }

        async function sendConversationResponse() {
            const input = document.getElementById('conversationInput');
            if (!input) return;
            const message = input.value.trim();
            if (!message) return;
            const messagesContainer = document.getElementById('conversationMessages');
            if (!messagesContainer) return;

            const userMsg = document.createElement('div');
            userMsg.className = 'message-bubble user';
            userMsg.textContent = message;
            messagesContainer.appendChild(userMsg);
            input.value = '';
            messagesContainer.scrollTop = messagesContainer.scrollHeight;

            const typingIndicator = document.createElement('div');
            typingIndicator.className = 'message-bubble ai typing';
            typingIndicator.innerHTML = '<div class="typing-dots"><span>.</span><span>.</span><span>.</span></div>';
            messagesContainer.appendChild(typingIndicator);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;

            try {
                const response = await window.puter.ai.chat(
                    "You are a helpful conversation partner. Respond to: " + message,
                    { model: 'gpt-4o', stream: false }
                );
                typingIndicator.remove();

                const aiMsg = document.createElement('div');
                aiMsg.className = 'message-bubble ai';
                aiMsg.textContent = (typeof response === 'string') ? response : (response.message?.content?.[0]?.text || response.text || '...');
                messagesContainer.appendChild(aiMsg);
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            } catch (err) {
                typingIndicator.remove();
                console.error(err);
            }
        }
