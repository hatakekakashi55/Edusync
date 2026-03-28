/**
 * ============================================================
 * EduSync AI Engine - LLM7.io Primary + Pollinations Fallback
 * ============================================================
 * Drop-in replacement for Puter.js AI chat functionality.
 * Usage: const response = await window.eduSyncAI.chat(prompt, options);
 * 
 * Configuration:
 *   PRIMARY:  LLM7.io (Free Anonymous, 100 req/hr per IP)
 *   FALLBACK: Pollinations.ai (Premium API Key)
 *   IMAGES:   Pollinations Image API (Always Free via GET)
 */

(function() {
    'use strict';

    const PRIMARY_API_BASE = 'https://api.llm7.io/v1/chat/completions';
    const FALLBACK_API_BASE = 'https://gen.pollinations.ai/v1/chat/completions';
    const FALLBACK_API_KEY = 'sk_58XnY00x4Z8IcaapKp9VuELQEu54HZ69';
    const IMAGE_BASE = 'https://image.pollinations.ai/prompt';

    // ✅ TEXT CHAT — Non-streaming with Automatic Intelligent Fallback
    async function aiChat(promptOrMessages, options = {}) {
        const { model, stream = false, systemPrompt } = options;
        
        // Build messages array
        let messages;
        if (typeof promptOrMessages === 'string') {
            messages = [{ role: 'user', content: promptOrMessages }];
        } else if (Array.isArray(promptOrMessages)) {
            messages = promptOrMessages;
        } else {
            messages = [{ role: 'user', content: String(promptOrMessages) }];
        }

        let res;
        
        try {
            const primaryModel = model || 'gpt-3.5-turbo';
            console.log(`%c🚀 [EduSync AI] Provider: LLM7.io (Free Anonymous Tier) | Model: ${primaryModel}`, 'color: #4F46E5; font-weight: bold;');
            
            // Attempt 1: Try the free anonymous LLM7.io API first!
            res = await fetch(PRIMARY_API_BASE, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    messages,
                    model: primaryModel,
                    stream: false,
                }),
            });
            
            // If rate limited or unavailable, manually throw to trigger the fallback!
            if (!res.ok) throw new Error(`Primary API Error: ${res.status}`);
        } catch (err) {
            const fallbackModel = 'openai';
            console.log(`%c⚠️ [EduSync AI] Primary Offline/Limit Reached. Fallback: Pollinations.ai (Premium Key) | Model: ${fallbackModel}`, 'color: #ff9900; font-weight: bold;');
            
            // Attempt 2: Seamlessly fall back to Pollinations!
            res = await fetch(FALLBACK_API_BASE, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${FALLBACK_API_KEY}`
                },
                body: JSON.stringify({
                    messages,
                    model: fallbackModel,
                    stream: false,
                }),
            });
            
            if (!res.ok) throw new Error(`Both Primary & Fallback APIs Failed! status: ${res.status}`);
        }

        // Parse the OpenAI-compatible response
        const data = await res.json();
        const content = data.choices?.[0]?.message?.content || '';
        
        // Return in a format compatible with Puter.js response structure
        return content.trim();
    }

    // ✅ STREAMING TEXT CHAT — With Automatic Intelligent Fallback
    async function aiChatStream(messages, onChunk) {
        let res;
        
        try {
            const primaryModel = 'gpt-3.5-turbo';
            console.log(`%c🚀 [EduSync AI] Streaming: LLM7.io | Model: ${primaryModel}`, 'color: #4F46E5; font-weight: bold;');
            
            res = await fetch(PRIMARY_API_BASE, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    messages,
                    model: primaryModel,
                    stream: true,
                }),
            });
            
            if (!res.ok) throw new Error(`Primary API Error: ${res.status}`);
        } catch (err) {
            const fallbackModel = 'openai';
            console.log(`%c⚠️ [EduSync AI] Streaming Fallback: Pollinations.ai | Model: ${fallbackModel}`, 'color: #ff9900; font-weight: bold;');
            
            res = await fetch(FALLBACK_API_BASE, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${FALLBACK_API_KEY}`
                },
                body: JSON.stringify({
                    messages,
                    model: fallbackModel,
                    stream: true,
                }),
            });
            
            if (!res.ok) throw new Error(`Both Primary & Fallback APIs Failed! status: ${res.status}`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let fullText = '';
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            let lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (let line of lines) {
                line = line.trim();
                if (!line.startsWith('data: ')) continue;
                if (line.includes('[DONE]')) continue;
                try {
                    const json = JSON.parse(line.slice(6));
                    const content = json.choices?.[0]?.delta?.content;
                    if (content != null && content !== '') {
                        fullText += content;
                        onChunk?.(content, fullText);
                    }
                } catch (_) {}
            }
        }

        return fullText.trim();
    }

    // ✅ IMAGE GENERATE — Pollinations Standard Output (Always Free & Unlimited via GET)
    function aiGenerateImage(prompt, options = {}) {
        const {
            width = 1024,
            height = 1024,
            model = 'flux',
            seed = null,
            enhance = false,
            nologo = true,
        } = options;

        const params = new URLSearchParams({
            width,
            height,
            model,
            enhance,
            nologo,
            ...(seed !== null && { seed }),
        });

        return `${IMAGE_BASE}/${encodeURIComponent(prompt)}?${params.toString()}`;
    }

    // ✅ STATUS CHECK
    async function checkAiStatus() {
        try {
            const res = await fetch(PRIMARY_API_BASE, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    messages: [{ role: 'user', content: 'test' }],
                    model: 'gpt-3.5-turbo',
                    max_tokens: 1,
                    stream: false,
                }),
                signal: AbortSignal.timeout(5000),
            });
            if (res.ok) {
                return { online: true, hasModel: true, models: ['gpt-3.5-turbo'], activeModel: 'gpt-3.5-turbo', provider: 'llm7.io' };
            }
            return { online: false, provider: 'llm7.io' };
        } catch {
            return { online: false, provider: 'llm7.io' };
        }
    }

    // ✅ Expose globally as window.eduSyncAI (and backward-compat shim for puter.ai.chat)
    window.eduSyncAI = {
        chat: aiChat,
        chatStream: aiChatStream,
        generateImage: aiGenerateImage,
        checkStatus: checkAiStatus,
        PRIMARY_API_BASE,
        FALLBACK_API_BASE,
        IMAGE_BASE,
    };

    // ✅ Backward compatibility: shimming window.puter.ai.chat to use LLM7.io
    if (!window.puter) window.puter = {};
    if (!window.puter.ai) window.puter.ai = {};
    
    window.puter.ai.chat = async function(prompt, options = {}) {
        const result = await aiChat(prompt, options);
        return result;
    };

    console.log('%c🎓 EduSync AI Engine Loaded | Primary: LLM7.io | Fallback: Pollinations.ai', 
        'color: #4F46E5; font-weight: bold; font-size: 14px; background: #0a0a0a; padding: 5px 10px; border-radius: 5px;');
})();
