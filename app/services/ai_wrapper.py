"""
EduSync Backend - AI Model Wrapper Service
Unified AI Wrapper that prioritizes local Ollama and falls back to Gemini API.
"""
import os
import logging
import asyncio
import httpx
from google import genai

from app.config import (
    AVAILABLE_MODELS, OLLAMA_BASE_URL, OLLAMA_MODEL,
    HOD_API_KEYS, FACULTY_AI_API_KEYS
)

logger = logging.getLogger("edusync")


class AIModelWrapper:
    """
    Unified AI Wrapper that prioritizes local Ollama and falls back to Gemini API.
    Requested model: gemini-3-flash-preview:cloud
    """
    def __init__(self, gemini_model_obj=None, feature_type="default"):
        self.gemini_model = gemini_model_obj
        self.feature_type = feature_type
        self.ollama_model = OLLAMA_MODEL
        self.base_url = OLLAMA_BASE_URL

    def __bool__(self):
        """Allows 'if gemini_model:' checks to work correctly"""
        return True

    def _format_prompt(self, contents):
        """Helper to convert Gemini-style part list to string"""
        if isinstance(contents, str): return contents
        if isinstance(contents, list):
            parts = []
            for part in contents:
                if isinstance(part, str): parts.append(part)
                elif hasattr(part, 'text'): parts.append(part.text)
                else: parts.append(str(part))
            return "\n".join(parts)
        return str(contents)

    def generate_content(self, contents, **kwargs):
        """Synchronous generation: Ollama first, then Gemini API"""
        prompt = self._format_prompt(contents)
        
        # 1. Try Ollama (Primary)
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "top_p": 0.9
                        }
                    }
                )
                if response.status_code == 200:
                    result = response.json()
                    text = result.get("response", "")
                    if text and text.strip():
                        logger.info(f"✅ AI Response: Ollama ({self.ollama_model})")
                        class MockResponse:
                            def __init__(self, t): self.text = t
                        return MockResponse(text)
                else:
                    logger.warning(f"⚠️ Ollama returned status {response.status_code}. Falling back.")
        except Exception as e:
            logger.debug(f"⚠️ Ollama failed: {e}. Falling back to Gemini API.")

        # 2. Try Gemini API (Fallback)
        if self.gemini_model:
            try:
                logger.info(f"🔄 AI Response: Gemini API ({self.feature_type})")
                if isinstance(self.gemini_model, dict) and "client" in self.gemini_model:
                    client = self.gemini_model["client"]
                    model = self.gemini_model["model"]
                    return client.models.generate_content(
                        model=model,
                        contents=contents,
                        **kwargs
                    )
                else:
                    return self.gemini_model.generate_content(contents, **kwargs)
            except Exception as e:
                logger.error(f"❌ Gemini API error: {e}")
                raise

        raise Exception("AI service unavailable: Both Ollama and Gemini API failed")

    async def generate_content_async(self, contents, **kwargs):
        """Asynchronous generation: Ollama first, then Gemini API"""
        prompt = self._format_prompt(contents)
        
        # 1. Try Ollama (Primary)
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "top_p": 0.9
                        }
                    }
                )
                if response.status_code == 200:
                    result = response.json()
                    text = result.get("response", "")
                    if text and text.strip():
                        logger.info(f"✅ AI Response: Ollama ({self.ollama_model})")
                        class MockResponse:
                            def __init__(self, t): self.text = t
                        return MockResponse(text)
                else:
                    logger.warning(f"⚠️ Ollama returned status {response.status_code}. Falling back.")
        except Exception as e:
            logger.debug(f"⚠️ Ollama Async failed: {e}. Falling back to Gemini API.")

        # 2. Try Gemini API (Fallback)
        if self.gemini_model:
            try:
                logger.info(f"🔄 AI Response (Async): Gemini API ({self.feature_type})")
                if isinstance(self.gemini_model, dict) and "client" in self.gemini_model:
                    client = self.gemini_model["client"]
                    model = self.gemini_model["model"]
                    return await client.aio.models.generate_content(
                        model=model,
                        contents=contents,
                        **kwargs
                    )
                else:
                    if hasattr(self.gemini_model, 'generate_content_async'):
                        return await self.gemini_model.generate_content_async(contents, **kwargs)
                    else:
                        return await asyncio.to_thread(self.gemini_model.generate_content, contents, **kwargs)
            except Exception as e:
                logger.error(f"❌ Gemini API Async error: {e}")
                raise

        raise Exception("AI service unavailable: Both Ollama and Gemini API failed")


# =============== AI MODEL INITIALIZATION ===============

# Initialize HOD Gemini model
hod_gemini_model = None
try:
    hod_api_key = HOD_API_KEYS.get("gemini")
    if hod_api_key:
        hod_genai_client = genai.Client(api_key=hod_api_key)
        if AVAILABLE_MODELS:
            model_name = AVAILABLE_MODELS[0]
            hod_gemini_model = {"client": hod_genai_client, "model": model_name}
            logger.debug(f"✅ HOD Gemini AI configured ({model_name})")
        else:
            logger.warning(f"⚠️ No models configured in AVAILABLE_MODELS")
    else:
        logger.debug(f"⚠️ HOD API key not provided")
except Exception as e:
    logger.warning(f"⚠️ HOD Gemini AI configuration failed: {e}")
    hod_gemini_model = None

# Initialize Faculty Gemini models
faculty_gemini_models = {}
for key_name, api_key in FACULTY_AI_API_KEYS.items():
    try:
        faculty_genai_client = genai.Client(api_key=api_key)
        if AVAILABLE_MODELS:
            model_name = AVAILABLE_MODELS[0]
            logger.debug(f"✅ Faculty Gemini AI configured for '{key_name}' ({model_name})")
            faculty_gemini_models[key_name] = {"client": faculty_genai_client, "model": model_name}
        else:
            logger.warning(f"⚠️ No models configured in AVAILABLE_MODELS for '{key_name}'")
            faculty_gemini_models[key_name] = None
    except Exception as e:
        logger.warning(f"⚠️ Faculty Gemini AI configuration failed for '{key_name}': {e}")
        faculty_gemini_models[key_name] = None

faculty_gemini_model = faculty_gemini_models.get("default")


def get_gemini_model(feature_type="default"):
    """Get AI model (Ollama + Gemini) for specific feature."""
    gemini_obj = faculty_gemini_models.get(feature_type)
    if not gemini_obj:
        gemini_obj = faculty_gemini_model
    return AIModelWrapper(gemini_obj, feature_type)


def get_faculty_gemini_model(feature_type="default"):
    """Get Gemini model for Faculty specific feature. Falls back to default."""
    model = faculty_gemini_models.get(feature_type)
    if model is None:
        model = faculty_gemini_models.get("default")
    return model


# Define global gemini_model for backward compatibility
gemini_model = get_gemini_model("default")
