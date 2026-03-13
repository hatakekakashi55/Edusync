"""
EduSync Backend - Speech Service (Enhanced)
Features: TTS, STT (Whisper + Deepgram + Fallback), Filler Word Detection,
WPM Calculation, Shadowing/Phoneme Correction with Levenshtein Distance.
"""
import logging
import os
import json
import asyncio
import uuid
import hashlib
import subprocess
import tempfile
import re
import difflib
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from bson import ObjectId
from pathlib import Path

from app.database import *
from app.config import *
from app.services.ai_wrapper import gemini_model, get_gemini_model, AIModelWrapper
from app.services.ai_service import AIService
from app.services.prompts import FILLER_WORDS, HESITATION_PHRASES

logger = logging.getLogger("edusync")


class SpeechService:
    # ==================== TEXT-TO-SPEECH ====================

    @staticmethod
    async def text_to_speech(text: str, language: str = 'ta', speed: float = 1.0) -> bytes:
        """Convert text to speech using gTTS (Google Akka Voice) as requested by user"""
        try:
            from gtts import gTTS
            import io
            
            # Map languages for gTTS
            lang_map = {
                'ta': 'ta',
                'tamil': 'ta',
                'en': 'en',
                'english': 'en'
            }
            lang = lang_map.get(language, 'ta') # Default to Tamil for that Akka feel
            
            # Create gTTS object with Indian TLD for better accent
            tts = gTTS(text=text, lang=lang, slow=False, tld='co.in')
            
            audio_bytes_io = io.BytesIO()
            tts.write_to_fp(audio_bytes_io)
            audio_bytes_io.seek(0)
            return audio_bytes_io.read()
            
        except Exception as e:
            logger.error(f"gTTS error: {e}")
            # Fallback to Edge TTS if gTTS fails
            try:
                import edge_tts
                voice = 'ta-IN-PallaviNeural' if language in ['ta', 'tamil'] else 'en-US-JennyNeural'
                communicate = edge_tts.Communicate(text, voice)
                
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_file:
                    output_file = tmp_file.name
                
                await communicate.save(output_file)
                with open(output_file, 'rb') as f:
                    audio_bytes = f.read()
                os.unlink(output_file)
                return audio_bytes
            except Exception as fallback_error:
                logger.error(f"Edge TTS Fallback error: {fallback_error}")
                return b""

    # ==================== SPEECH-TO-TEXT (WHISPER) ====================

    @staticmethod
    async def speech_to_text_whisper(audio_bytes: bytes, language: str = 'en') -> Dict:
        """
        Convert speech to text using OpenAI Whisper (self-hosted).
        Returns transcript with word-level timestamps for filler detection.
        Falls back to other STT engines if Whisper is unavailable.
        """
        try:
            import whisper
            import numpy as np
            import io
            
            # Save audio to temp file for Whisper
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
                tmp_file.write(audio_bytes)
                tmp_path = tmp_file.name
            
            try:
                # Load Whisper model (cached after first load)
                model = whisper.load_model("base")  # Options: tiny, base, small, medium, large
                
                result = model.transcribe(
                    tmp_path,
                    language=language if language != 'en' else 'en',
                    word_timestamps=True,
                    fp16=False  # CPU compatibility
                )
                
                transcript = result.get("text", "").strip()
                segments = result.get("segments", [])
                
                # Extract word-level data for analysis
                words_data = []
                total_duration = 0
                for segment in segments:
                    for word_info in segment.get("words", []):
                        words_data.append({
                            "word": word_info.get("word", "").strip(),
                            "start": word_info.get("start", 0),
                            "end": word_info.get("end", 0),
                            "probability": word_info.get("probability", 0)
                        })
                    segment_end = segment.get("end", 0)
                    if segment_end > total_duration:
                        total_duration = segment_end
                
                logger.info(f"✅ Whisper transcription successful: {len(transcript)} chars")
                return {
                    "transcript": transcript,
                    "words": words_data,
                    "duration_seconds": total_duration,
                    "language": result.get("language", language),
                    "source": "whisper"
                }
                
            finally:
                try:
                    os.unlink(tmp_path)
                except:
                    pass
                    
        except ImportError:
            logger.warning("⚠️ Whisper not installed. Falling back to alternative STT.")
            return await SpeechService._stt_with_duration_fallback(audio_bytes, language)
        except Exception as e:
            logger.error(f"Whisper STT error: {e}")
            return await SpeechService._stt_with_duration_fallback(audio_bytes, language)

    @staticmethod
    async def _stt_with_duration_fallback(audio_bytes: bytes, language: str = 'en') -> Dict:
        """Fallback STT that also extracts audio duration."""
        transcript = ""
        duration_seconds = 0.0
        
        # Try to get duration from audio file
        try:
            import io
            from pydub import AudioSegment
            audio_segment = AudioSegment.from_file(io.BytesIO(audio_bytes))
            duration_seconds = len(audio_segment) / 1000.0  # pydub returns ms
        except Exception as e:
            logger.warning(f"Could not extract audio duration: {e}")
            duration_seconds = 30.0  # Default fallback
        
        # Try Deepgram first
        transcript = await SpeechService.speech_to_text_deepgram(audio_bytes, language)
        
        if not transcript or transcript in ["Could not understand audio", "Speech recognition service error", "Audio processing failed", ""]:
            transcript = await SpeechService.speech_to_text_fallback(audio_bytes, language)
        
        return {
            "transcript": transcript,
            "words": [],  # No word-level data from fallback
            "duration_seconds": duration_seconds,
            "language": language,
            "source": "fallback"
        }

    @staticmethod
    async def speech_to_text_deepgram(audio_bytes: bytes, language: str = 'en') -> str:
        """Convert speech to text using Deepgram (More accurate)"""
        try:
            
            # Deepgram API Key (Get from environment)
            DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
            
            if not DEEPGRAM_API_KEY:
                # Fallback to speech_recognition
                return await SpeechService.speech_to_text_fallback(audio_bytes, language)
            
            # Language mapping
            lang_map = {
                'en': 'en-US',
                'ta': 'ta',
                'hi': 'hi-IN'
            }
            
            deepgram_lang = lang_map.get(language, 'en-US')
            
            # Initialize Deepgram
            dg_client = Deepgram(DEEPGRAM_API_KEY)
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_file.write(audio_bytes)
                tmp_path = tmp_file.name
            
            try:
                with open(tmp_path, 'rb') as audio:
                    source = {'buffer': audio, 'mimetype': 'audio/wav'}
                    
                    # Call Deepgram API
                    response = await dg_client.transcription.prerecorded(
                        source,
                        {
                            'smart_format': True,
                            'model': 'nova-2',
                            'language': deepgram_lang,
                            'punctuate': True
                        }
                    )
                    
                    # Extract transcript
                    if 'results' in response:
                        transcript = response['results']['channels'][0]['alternatives'][0]['transcript']
                        return transcript.strip()
                    else:
                        return ""
                        
            finally:
                # Clean up temporary file
                try:
                    os.unlink(tmp_path)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Deepgram STT error: {e}")
            # Fallback to speech_recognition
            return await SpeechService.speech_to_text_fallback(audio_bytes, language)
    
    @staticmethod
    async def speech_to_text_fallback(audio_bytes: bytes, language: str = 'en-US') -> str:
        """Fallback speech to text using speech_recognition"""
        try:
            import speech_recognition as sr
            
            recognizer = sr.Recognizer()
            
            # Save audio to temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            
            try:
                with sr.AudioFile(tmp_path) as source:
                    audio = recognizer.record(source)
                    text = recognizer.recognize_google(audio, language=language)
                return text
            except sr.UnknownValueError:
                return "Could not understand audio"
            except sr.RequestError as e:
                logger.error(f"STT request error: {e}")
                return "Speech recognition service error"
            except Exception as e:
                logger.error(f"STT error: {e}")
                return "Audio processing failed"
            finally:
                os.unlink(tmp_path)
                
        except Exception as e:
            logger.error(f"Fallback STT error: {e}")
            return ""

    # ==================== FILLER WORD DETECTION ====================

    @staticmethod
    def detect_filler_words(transcript: str) -> Dict:
        """
        Detect filler words and hesitation phrases in a transcript.
        Returns detailed analysis with counts and positions.
        """
        if not transcript:
            return {
                "filler_words_found": [],
                "total_filler_count": 0,
                "total_words": 0,
                "filler_percentage": 0.0,
                "filler_feedback": "No transcript to analyze."
            }
        
        text_lower = transcript.lower().strip()
        words = text_lower.split()
        total_words = len(words)
        
        filler_counts = {}
        
        # Check for single-word fillers
        for word in words:
            # Clean the word of punctuation
            clean_word = re.sub(r'[^\w\s]', '', word).strip()
            if clean_word in FILLER_WORDS:
                filler_counts[clean_word] = filler_counts.get(clean_word, 0) + 1
        
        # Check for multi-word filler phrases
        for phrase in HESITATION_PHRASES:
            count = text_lower.count(phrase)
            if count > 0:
                filler_counts[phrase] = count
        
        # Check for multi-word fillers from FILLER_WORDS list
        for filler in FILLER_WORDS:
            if ' ' in filler:
                count = text_lower.count(filler)
                if count > 0:
                    filler_counts[filler] = filler_counts.get(filler, 0) + count
        
        total_filler_count = sum(filler_counts.values())
        filler_percentage = (total_filler_count / total_words * 100) if total_words > 0 else 0
        
        # Generate feedback
        if filler_percentage == 0:
            filler_feedback = "🎯 Excellent! No filler words detected. Very clean speech!"
        elif filler_percentage < 3:
            filler_feedback = "✅ Great job! Very few filler words. Your speech is clear and professional."
        elif filler_percentage < 7:
            filler_feedback = "👍 Good effort! Some filler words detected. Try to pause instead of using fillers."
        elif filler_percentage < 15:
            filler_feedback = "⚠️ Noticeable filler words. Practice pausing and taking a breath instead of saying 'um' or 'like'."
        else:
            filler_feedback = "🔄 High filler word usage detected. Focus on: 1) Slow down 2) Embrace silence 3) Practice with a mirror."
        
        filler_list = [
            {"word": word, "count": count}
            for word, count in sorted(filler_counts.items(), key=lambda x: x[1], reverse=True)
        ]
        
        return {
            "filler_words_found": filler_list,
            "total_filler_count": total_filler_count,
            "total_words": total_words,
            "filler_percentage": round(filler_percentage, 2),
            "filler_feedback": filler_feedback
        }

    # ==================== WPM / PACE CALCULATION ====================

    @staticmethod
    def calculate_wpm(total_words: int, duration_seconds: float) -> Dict:
        """
        Calculate Words Per Minute and provide pace feedback.
        Optimal speaking pace: 120-150 WPM for presentations.
        Conversational: 150-180 WPM.
        """
        if duration_seconds <= 0:
            return {
                "wpm": 0,
                "pace_rating": "unknown",
                "pace_feedback": "Could not calculate pace — audio duration is zero."
            }
        
        wpm = (total_words / duration_seconds) * 60
        wpm = round(wpm, 1)
        
        # Classify pace
        if wpm < 80:
            pace_rating = "too_slow"
            pace_feedback = (
                f"🐢 Your pace is {wpm} WPM, which is very slow. "
                "This might cause your audience to lose interest. "
                "Try to maintain a natural rhythm — aim for 120-150 WPM."
            )
        elif wpm < 120:
            pace_rating = "slow"
            pace_feedback = (
                f"🚶 Your pace is {wpm} WPM — a bit slow but deliberate. "
                "This works well for explaining complex topics. "
                "For conversations, try to pick up the pace to ~140 WPM."
            )
        elif wpm < 160:
            pace_rating = "good"
            pace_feedback = (
                f"✅ Excellent pace! {wpm} WPM is ideal for professional communication. "
                "Your speech is clear and easy to follow. Keep it up!"
            )
        elif wpm < 200:
            pace_rating = "fast"
            pace_feedback = (
                f"🏃 Your pace is {wpm} WPM — a bit fast. "
                "Your audience might miss key points. "
                "Try to slow down at important moments and add strategic pauses."
            )
        else:
            pace_rating = "too_fast"
            pace_feedback = (
                f"⚡ Your pace is {wpm} WPM — very fast! "
                "Listeners will struggle to keep up. "
                "Practice pausing after each key point. Take a breath between sentences."
            )
        
        return {
            "wpm": wpm,
            "pace_rating": pace_rating,
            "pace_feedback": pace_feedback
        }

    # ==================== SHADOWING / PHONEME CORRECTION ====================

    @staticmethod
    def levenshtein_distance(s1: str, s2: str) -> int:
        """Calculate the Levenshtein distance between two strings."""
        if len(s1) < len(s2):
            return SpeechService.levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]

    @staticmethod
    def word_similarity(word1: str, word2: str) -> float:
        """Calculate similarity between two words (0-100)."""
        if not word1 or not word2:
            return 0.0
        w1, w2 = word1.lower().strip(), word2.lower().strip()
        if w1 == w2:
            return 100.0
        max_len = max(len(w1), len(w2))
        if max_len == 0:
            return 100.0
        distance = SpeechService.levenshtein_distance(w1, w2)
        return round((1 - distance / max_len) * 100, 1)

    @staticmethod
    def analyze_shadowing(reference_text: str, user_text: str) -> Dict:
        """
        Compare user's speech with reference text using Levenshtein distance.
        ELSA-style phoneme comparison at word level.
        """
        if not reference_text or not user_text:
            return {
                "similarity_score": 0,
                "word_accuracy": 0,
                "matching_words": [],
                "missing_words": [],
                "extra_words": [],
                "mispronounced_words": [],
                "phoneme_feedback": "No text provided for comparison.",
                "overall_score": 0,
                "tips": ["Please provide both reference and spoken text."]
            }
        
        # Normalize texts
        ref_clean = re.sub(r'[^\w\s]', '', reference_text.lower()).strip()
        user_clean = re.sub(r'[^\w\s]', '', user_text.lower()).strip()
        
        ref_words = ref_clean.split()
        user_words = user_clean.split()
        
        # Overall text similarity using Levenshtein
        text_distance = SpeechService.levenshtein_distance(ref_clean, user_clean)
        max_text_len = max(len(ref_clean), len(user_clean))
        text_similarity = round((1 - text_distance / max_text_len) * 100, 1) if max_text_len > 0 else 100
        
        # Word-level comparison using SequenceMatcher
        matcher = difflib.SequenceMatcher(None, ref_words, user_words)
        
        matching_words = []
        missing_words = []
        extra_words = []
        mispronounced = []
        
        # Track matched reference words
        ref_matched = set()
        user_matched = set()
        
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op == 'equal':
                for k in range(i1, i2):
                    matching_words.append(ref_words[k])
                    ref_matched.add(k)
                for k in range(j1, j2):
                    user_matched.add(k)
            elif op == 'replace':
                for k in range(i1, i2):
                    # Find the closest user word in the replacement range
                    if j1 + (k - i1) < j2:
                        user_word = user_words[j1 + (k - i1)]
                        sim = SpeechService.word_similarity(ref_words[k], user_word)
                        if sim >= 60:  # Close enough to be a mispronunciation
                            mispronounced.append({
                                "expected": ref_words[k],
                                "actual": user_word,
                                "similarity": sim
                            })
                        else:
                            missing_words.append(ref_words[k])
                    else:
                        missing_words.append(ref_words[k])
                    ref_matched.add(k)
                for k in range(j1, j2):
                    if k not in user_matched and (k - j1) >= (i2 - i1):
                        extra_words.append(user_words[k])
                    user_matched.add(k)
            elif op == 'delete':
                for k in range(i1, i2):
                    missing_words.append(ref_words[k])
                    ref_matched.add(k)
            elif op == 'insert':
                for k in range(j1, j2):
                    extra_words.append(user_words[k])
                    user_matched.add(k)
        
        # Calculate word accuracy
        correct_count = len(matching_words)
        total_ref_words = len(ref_words)
        word_accuracy = round((correct_count / total_ref_words) * 100, 1) if total_ref_words > 0 else 0
        
        # Overall score (weighted: 60% text similarity + 40% word accuracy)
        overall_score = int(round(text_similarity * 0.6 + word_accuracy * 0.4))
        overall_score = max(0, min(100, overall_score))
        
        # Generate feedback
        tips = []
        if missing_words:
            tips.append(f"Practice these missed words: {', '.join(missing_words[:5])}")
        if mispronounced:
            for mp in mispronounced[:3]:
                tips.append(f"'{mp['expected']}' → you said '{mp['actual']}' ({mp['similarity']}% match)")
        if extra_words:
            tips.append(f"You added extra words: {', '.join(extra_words[:3])}. Try to match the original exactly.")
        if not tips:
            tips.append("Perfect shadowing! Try a harder passage next time.")
        
        # Phoneme feedback summary
        if overall_score >= 90:
            phoneme_feedback = "🎯 Excellent! Your pronunciation almost perfectly matches the reference. Outstanding work!"
        elif overall_score >= 75:
            phoneme_feedback = "✅ Good shadowing! Most words are correctly pronounced. Focus on the highlighted words."
        elif overall_score >= 50:
            phoneme_feedback = "👍 Decent attempt. About half the words match. Practice speaking slowly and clearly."
        else:
            phoneme_feedback = "🔄 Needs more practice. Listen to the reference audio carefully and try word by word."
        
        return {
            "similarity_score": text_similarity,
            "word_accuracy": word_accuracy,
            "matching_words": matching_words,
            "missing_words": missing_words,
            "extra_words": extra_words,
            "mispronounced_words": mispronounced,
            "phoneme_feedback": phoneme_feedback,
            "overall_score": overall_score,
            "tips": tips
        }

    # ==================== FULL SPEECH ANALYSIS ====================

    @staticmethod
    async def full_speech_analysis(audio_bytes: bytes, language: str = 'en', audio_duration: float = None) -> Dict:
        """
        Complete speech analysis pipeline:
        1. Transcribe audio (Whisper → Deepgram → Fallback)
        2. Detect filler words
        3. Calculate WPM & pace
        4. Return comprehensive analysis
        """
        # Step 1: Transcribe
        stt_result = await SpeechService.speech_to_text_whisper(audio_bytes, language)
        transcript = stt_result.get("transcript", "")
        duration = audio_duration or stt_result.get("duration_seconds", 0)
        
        if not transcript or transcript in ["Could not understand audio", "Audio processing failed", ""]:
            return {
                "transcript": "Could not transcribe audio",
                "total_words": 0,
                "audio_duration_seconds": duration,
                "wpm": 0,
                "pace_rating": "unknown",
                "pace_feedback": "Audio could not be processed. Please try again.",
                "filler_words_found": [],
                "filler_word_count": 0,
                "filler_word_percentage": 0.0,
                "filler_feedback": "No transcript available.",
                "clarity_score": 0,
                "overall_fluency_score": 0,
                "stt_source": stt_result.get("source", "unknown"),
                "error": "Audio transcription failed"
            }
        
        total_words = len(transcript.split())
        
        # Step 2: Filler word detection
        filler_analysis = SpeechService.detect_filler_words(transcript)
        
        # Step 3: WPM calculation
        pace_analysis = SpeechService.calculate_wpm(total_words, duration)
        
        # Step 4: Calculate clarity score (based on word confidence if available)
        words_data = stt_result.get("words", [])
        if words_data:
            avg_confidence = sum(w.get("probability", 0.7) for w in words_data) / len(words_data)
            clarity_score = int(round(avg_confidence * 100))
        else:
            # Estimate based on filler percentage
            clarity_score = max(30, 100 - int(filler_analysis["filler_percentage"] * 3))
        
        # Step 5: Overall fluency score
        pace_score = 100 if pace_analysis["pace_rating"] == "good" else (
            80 if pace_analysis["pace_rating"] in ["slow", "fast"] else 50
        )
        filler_score = max(0, 100 - int(filler_analysis["filler_percentage"] * 5))
        overall_fluency = int(round(clarity_score * 0.4 + pace_score * 0.3 + filler_score * 0.3))
        
        return {
            "transcript": transcript,
            "total_words": total_words,
            "audio_duration_seconds": round(duration, 2),
            "wpm": pace_analysis["wpm"],
            "pace_rating": pace_analysis["pace_rating"],
            "pace_feedback": pace_analysis["pace_feedback"],
            "filler_words_found": filler_analysis["filler_words_found"],
            "filler_word_count": filler_analysis["total_filler_count"],
            "filler_word_percentage": filler_analysis["filler_percentage"],
            "filler_feedback": filler_analysis["filler_feedback"],
            "clarity_score": clarity_score,
            "overall_fluency_score": overall_fluency,
            "stt_source": stt_result.get("source", "unknown")
        }

    # ==================== PRONUNCIATION ANALYSIS (EXISTING - ENHANCED) ====================

    @staticmethod
    async def analyze_pronunciation(audio_bytes: bytes, reference_text: str) -> Dict:
        """Analyze pronunciation with improved AI"""
        try:
            # Convert audio to text using Whisper/Deepgram
            stt_result = await SpeechService.speech_to_text_whisper(audio_bytes)
            spoken_text = stt_result.get("transcript", "")
            
            if not spoken_text or spoken_text == "Could not understand audio":
                return {
                    "pronunciation_score": 50,
                    "grammar_score": 50,
                    "fluency_score": 50,
                    "spoken_text": "Could not process audio",
                    "error": "Audio not clear"
                }
            
            # Get AI analysis
            analysis = await AIService.analyze_english_with_gemini(spoken_text, reference_text)
            
            # Add audio metrics
            analysis["spoken_text"] = spoken_text
            analysis["word_count"] = len(spoken_text.split())
            
            # Add shadowing comparison
            shadowing = SpeechService.analyze_shadowing(reference_text, spoken_text)
            analysis["shadowing_analysis"] = shadowing
            
            return analysis
        except Exception as e:
            logger.error(f"Pronunciation analysis error: {e}")
            return {
                "pronunciation_score": 50,
                "grammar_score": 50,
                "fluency_score": 50,
                "spoken_text": "Analysis failed",
                "error": str(e)
            }
