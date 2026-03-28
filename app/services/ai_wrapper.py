"""
═══════════════════════════════════════════════════════════════
EduSync Backend — INIXA AI Engine Service (Python)
5 FREE AI Engines — NO API Key, NO Auth, UNLIMITED!

Fallback Chain: DuckDuckGo → LLM7 → BlackBox → Pollinations → Pollinations Simple
═══════════════════════════════════════════════════════════════
"""
import logging
import asyncio
import re
import json
import random
import httpx

from app.config import (
    POLLINATIONS_API_BASE, POLLINATIONS_MODEL,
    DDG_API_BASE, DDG_MODEL,
    BLACKBOX_API_BASE,
    LLM7_API_BASE, LLM7_MODEL,
    POLLINATIONS_SIMPLE_BASE, POLLINATIONS_SIMPLE_MODEL,
    AI_TIMEOUT, AI_ENGINE_ORDER,
    # Backward compat imports
    OLLAMA_BASE_URL, OLLAMA_MODEL,
    HOD_API_KEYS, FACULTY_AI_API_KEYS, AVAILABLE_MODELS,
)

logger = logging.getLogger("edusync")

# ═══════════════════════════════════════════════════════════════
# Track which engine was last used
# ═══════════════════════════════════════════════════════════════
_last_engine = None


def get_last_engine():
    return _last_engine


def get_last_engine_label():
    labels = {
        "pollinations": "🌸 Pollinations",
        "duckduckgo": "🦆 DuckDuckGo",
        "blackbox": "⬛ BlackBox AI",
        "llm7": "🚀 LLM7",
        "pollinations-simple": "🌸 Pollinations Simple",
    }
    return labels.get(_last_engine, "🤖 AI")


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════
def _is_html(text: str) -> bool:
    """Detect garbage HTML/error responses"""
    t = text.strip()
    return (
        t.startswith("<!DOCTYPE") or
        t.startswith("<html") or
        t.startswith("<div") or
        "<script" in t or
        "window.location" in t or
        "502 Bad Gateway" in t or
        "Queue full" in t or
        "Sorry, AI servers are busy" in t
    )


# ═══════════════════════════════════════════════════════════════
# ENGINE 1: POLLINATIONS (OpenAI-compatible)
# ═══════════════════════════════════════════════════════════════
async def _try_pollinations(messages: list) -> str | None:
    logger.info("🌸 [INIXA] Trying Pollinations...")
    try:
        async with httpx.AsyncClient(timeout=AI_TIMEOUT) as client:
            res = await client.post(
                POLLINATIONS_API_BASE,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "model": POLLINATIONS_MODEL,
                    "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
                    "stream": False,
                },
            )
            if res.status_code != 200:
                logger.warning(f"[Pollinations] HTTP {res.status_code}")
                return None

            data = res.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            if not content or _is_html(content):
                logger.warning("[Pollinations] Invalid response")
                return None

            logger.info("✅ Pollinations response received")
            return content.strip()
    except Exception as e:
        logger.warning(f"[Pollinations] Error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# ENGINE 2: DUCKDUCKGO (via Cloudflare Worker)
# ═══════════════════════════════════════════════════════════════
async def _try_duckduckgo(messages: list) -> str | None:
    logger.info("🦆 [INIXA] Trying DuckDuckGo...")
    try:
        async with httpx.AsyncClient(timeout=AI_TIMEOUT) as client:
            res = await client.post(
                DDG_API_BASE,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "model": DDG_MODEL,
                    "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
                },
            )
            if res.status_code != 200:
                logger.warning(f"[DDG] HTTP {res.status_code}")
                return None

            # Try to parse as JSON first
            try:
                data = res.json()
                content = (
                    data.get("choices", [{}])[0].get("message", {}).get("content", "") or
                    data.get("response", "") or
                    data.get("message", {}).get("content", "") if isinstance(data.get("message"), dict) else data.get("message", "")
                )
                if content and not _is_html(content):
                    logger.info("✅ DuckDuckGo response received")
                    return content.strip()
            except Exception:
                pass

            # Fallback: read as streaming text
            text = res.text
            full_text = ""
            for line in text.split("\n"):
                line = line.strip()
                if not line.startswith("data: ") or "[DONE]" in line:
                    continue
                try:
                    chunk = json.loads(line[6:])
                    if chunk.get("message"):
                        full_text += chunk["message"]
                except Exception:
                    pass

            if full_text.strip():
                logger.info("✅ DuckDuckGo streaming response received")
                return full_text.strip()
            return None
    except Exception as e:
        logger.warning(f"[DDG] Error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# ENGINE 3: BLACKBOX AI
# ═══════════════════════════════════════════════════════════════
async def _try_blackbox(messages: list) -> str | None:
    logger.info("⬛ [INIXA] Trying BlackBox AI...")
    try:
        async with httpx.AsyncClient(timeout=AI_TIMEOUT) as client:
            res = await client.post(
                BLACKBOX_API_BASE,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
                    "maxTokens": 4096,
                    "mobileClient": True,
                    "agentMode": {"ImageGenerationMode": False},
                },
            )
            if res.status_code != 200:
                logger.warning(f"[BlackBox] HTTP {res.status_code}")
                return None

            text = res.text
            # Clean BlackBox source links
            text = re.sub(r'\$~~~\$[\s\S]*?\$~~~\$', '', text)
            text = re.sub(r'\[\^\d+\^\]', '', text).strip()

            if not text or len(text) < 5 or _is_html(text):
                logger.warning("[BlackBox] Invalid response")
                return None

            logger.info("✅ BlackBox response received")
            return text.strip()
    except Exception as e:
        logger.warning(f"[BlackBox] Error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# ENGINE 4: LLM7
# ═══════════════════════════════════════════════════════════════
async def _try_llm7(messages: list) -> str | None:
    logger.info("🚀 [INIXA] Trying LLM7...")
    try:
        async with httpx.AsyncClient(timeout=AI_TIMEOUT) as client:
            res = await client.post(
                LLM7_API_BASE,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
                    "model": LLM7_MODEL,
                    "stream": False,
                },
            )
            if res.status_code != 200:
                logger.warning(f"[LLM7] HTTP {res.status_code}")
                return None

            data = res.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            if not content or _is_html(content):
                logger.warning("[LLM7] Invalid response")
                return None

            logger.info("✅ LLM7 response received")
            return content.strip()
    except Exception as e:
        logger.warning(f"[LLM7] Error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# ENGINE 5: POLLINATIONS SIMPLE (Last resort)
# ═══════════════════════════════════════════════════════════════
async def _try_pollinations_simple(messages: list) -> str | None:
    logger.info("🌸 [INIXA] Trying Pollinations Simple...")
    try:
        async with httpx.AsyncClient(timeout=AI_TIMEOUT) as client:
            res = await client.post(
                POLLINATIONS_SIMPLE_BASE,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "text/plain,application/json",
                },
                json={
                    "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
                    "model": POLLINATIONS_SIMPLE_MODEL,
                    "seed": random.randint(0, 10000),
                },
            )
            if res.status_code != 200:
                logger.warning(f"[PollinationsSimple] HTTP {res.status_code}")
                return None

            text = res.text
            if not text or len(text) < 5 or _is_html(text):
                logger.warning("[PollinationsSimple] Invalid response")
                return None

            logger.info("✅ Pollinations Simple response received")
            return text.strip()
    except Exception as e:
        logger.warning(f"[PollinationsSimple] Error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# ENGINE REGISTRY
# ═══════════════════════════════════════════════════════════════
_ENGINE_MAP = {
    "duckduckgo": _try_duckduckgo,
    "llm7": _try_llm7,
    "blackbox": _try_blackbox,
    "pollinations": _try_pollinations,
    "pollinations-simple": _try_pollinations_simple,
}


# ═══════════════════════════════════════════════════════════════
# MAIN AI CHAT — Smart Fallback Chain
# ═══════════════════════════════════════════════════════════════
async def ai_chat(messages: list) -> str:
    """
    Main AI function — tries all 5 FREE engines in fallback order.
    Returns the first successful response.
    """
    global _last_engine
    logger.info("🧠 [INIXA] Starting AI chat with 5-engine fallback...")

    for engine_name in AI_ENGINE_ORDER:
        engine_fn = _ENGINE_MAP.get(engine_name.strip())
        if not engine_fn:
            logger.warning(f"[INIXA] Unknown engine: {engine_name}")
            continue

        _last_engine = engine_name.strip()
        try:
            result = await engine_fn(messages)
            if result:
                logger.info(f"🎉 [INIXA] ✓ Success with {engine_name}")
                return result
        except Exception as e:
            logger.warning(f"[INIXA] {engine_name} failed: {e}")

    _last_engine = None
    logger.error("💀 [INIXA] All 5 engines failed!")
    return "⚠️ AI service temporarily unavailable. All engines are busy. Please try again in a moment."


async def ai_generate(prompt: str) -> str:
    """Simple single-prompt AI call"""
    return await ai_chat([{"role": "user", "content": prompt}])


# ═══════════════════════════════════════════════════════════════
# AI Chat with Retry (Exponential Backoff)
# ═══════════════════════════════════════════════════════════════
async def ai_chat_with_retry(messages: list, max_retries: int = 3) -> str:
    """Retry AI chat with exponential backoff"""
    last_error = ""

    for i in range(max_retries):
        try:
            result = await ai_chat(messages)
            if "⚠️" not in result:
                return result
            last_error = result
        except Exception as e:
            last_error = str(e)

        if i < max_retries - 1:
            delay = (2 ** i) * 1
            logger.info(f"🔄 [INIXA] Retrying in {delay}s...")
            await asyncio.sleep(delay)

    return last_error


# ═══════════════════════════════════════════════════════════════
# AI Status Check
# ═══════════════════════════════════════════════════════════════
async def check_ai_status() -> dict:
    """Check if any AI engine is available"""
    logger.info("🔍 [INIXA] Checking AI status...")
    try:
        test_messages = [{"role": "user", "content": "hi"}]

        # Quick check with DDG (usually fastest)
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(
                    DDG_API_BASE,
                    headers={"Content-Type": "application/json"},
                    json={"messages": test_messages, "model": DDG_MODEL},
                )
                if res.status_code == 200:
                    return {"online": True, "engine": "DuckDuckGo (Active)"}
        except Exception:
            pass

        # Try BlackBox
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(
                    BLACKBOX_API_BASE,
                    headers={"Content-Type": "application/json"},
                    json={"messages": test_messages},
                )
                if res.status_code == 200:
                    return {"online": True, "engine": "BlackBox AI (Active)"}
        except Exception:
            pass

        # Try Pollinations
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(
                    POLLINATIONS_API_BASE,
                    headers={"Content-Type": "application/json"},
                    json={"messages": test_messages, "model": POLLINATIONS_MODEL, "stream": False},
                )
                if res.status_code == 200:
                    return {"online": True, "engine": "Pollinations (Active)"}
        except Exception:
            pass

        return {"online": False, "engine": "All Engines Offline"}
    except Exception as e:
        logger.warning(f"[INIXA] Status check failed: {e}")
        return {"online": False, "engine": "Connection Error"}


# ═══════════════════════════════════════════════════════════════
# AIModelWrapper — BACKWARD COMPATIBLE WRAPPER
# Keeps the same interface so old code (get_gemini_model, etc.) still works
# ═══════════════════════════════════════════════════════════════
class AIModelWrapper:
    """
    Drop-in replacement for the old Gemini/Ollama wrapper.
    All calls are routed through the 5 FREE AI engines.
    """
    def __init__(self, gemini_model_obj=None, feature_type="default"):
        self.feature_type = feature_type
        # These are kept for backward compat but NOT used
        self.gemini_model = gemini_model_obj
        self.ollama_model = OLLAMA_MODEL
        self.base_url = OLLAMA_BASE_URL

    def __bool__(self):
        """Always return True — AI is always available"""
        return True

    def _format_prompt(self, contents):
        """Convert Gemini-style content to string"""
        if isinstance(contents, str):
            return contents
        if isinstance(contents, list):
            parts = []
            for part in contents:
                if isinstance(part, str):
                    parts.append(part)
                elif hasattr(part, 'text'):
                    parts.append(part.text)
                else:
                    parts.append(str(part))
            return "\n".join(parts)
        return str(contents)

    def generate_content(self, contents, **kwargs):
        """Synchronous generation — runs async in thread"""
        prompt = self._format_prompt(contents)
        messages = [{"role": "user", "content": prompt}]

        # Run async in sync context
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're in an async context — create a future
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(asyncio.run, ai_chat(messages)).result()
        else:
            result = asyncio.run(ai_chat(messages))

        class MockResponse:
            def __init__(self, t):
                self.text = t
        return MockResponse(result)

    async def generate_content_async(self, contents, **kwargs):
        """Asynchronous generation — uses 5-engine fallback"""
        prompt = self._format_prompt(contents)
        messages = [{"role": "user", "content": prompt}]
        result = await ai_chat(messages)

        class MockResponse:
            def __init__(self, t):
                self.text = t
        return MockResponse(result)


# ═══════════════════════════════════════════════════════════════
# BACKWARD COMPATIBLE EXPORTS
# All old imports still work — no code changes needed elsewhere!
# ═══════════════════════════════════════════════════════════════

# These used to be Gemini models — now they're all AIModelWrapper instances
hod_gemini_model = None
faculty_gemini_models = {
    "default": None,
    "voice": None,
    "analysis": None,
    "content": None,
}
faculty_gemini_model = None


def get_gemini_model(feature_type="default"):
    """Returns AIModelWrapper (routes to 5 FREE engines)"""
    return AIModelWrapper(None, feature_type)


def get_faculty_gemini_model(feature_type="default"):
    """Returns AIModelWrapper (routes to 5 FREE engines)"""
    return AIModelWrapper(None, feature_type)


# Global gemini_model for backward compatibility
gemini_model = get_gemini_model("default")

logger.info("🚀 [INIXA] AI Engine Initialized: 5 FREE Engines Active!")
logger.info(f"   Fallback Order: {' → '.join(AI_ENGINE_ORDER)}")
logger.info("   🦆 DuckDuckGo | 🚀 LLM7 | ⬛ BlackBox | 🌸 Pollinations | 🌸 Pollinations Simple")
