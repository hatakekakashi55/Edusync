"""
EduSync Backend - Stage 1 - Reading Routes
Auto-extracted from main.py via AST parser.
"""
import logging
import os
import re
import json
import uuid
import io
import base64
import random
import asyncio
import hashlib
import tempfile
import subprocess
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List, Dict, Any
from pathlib import Path
from bson import ObjectId

from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form, Query, Body, BackgroundTasks, Request
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse, Response

from app.dependencies import get_current_user, verify_token, convert_objectid_to_str, create_access_token, create_refresh_token
from app.database import *
from app.services.ai_wrapper import gemini_model, get_gemini_model, get_faculty_gemini_model, hod_gemini_model, faculty_gemini_models, AIModelWrapper
from app.lifespan import get_redis_client, get_executor
from app.config import *

# Import all models
from app.models.auth import *
from app.models.challenge import *
from app.models.classroom import *
from app.models.communication import *
from app.models.career import *
from app.models.group import *
from app.models.ai import *
from app.models.hod import *
from app.models.curriculum import *
from app.models.resource import *
from app.models.report import *
from app.models.credit import *
from app.models.compiler import *
from app.models.speech import *
from app.models.faculty import *

# Import helper functions
from app.utils.helpers import *

logger = logging.getLogger("edusync")

router = APIRouter(tags=["Stage 1 - Reading"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/stage1/read-challenge/admin", tags=["Stage 1", "Student"])
async def get_admin_read_challenge(current_user: dict = Depends(get_current_user)):
    """Get a random admin-created sentence for read challenge"""
    try:
        # Get random active admin sentence
        pipeline = [
            {"$match": {"is_active": True, "source": "admin"}},
            {"$sample": {"size": 1}}
        ]
        
        cursor = voice_challenge_sentences_collection.aggregate(pipeline)
        sentences = await cursor.to_list(length=1)
        
        if not sentences:
            raise HTTPException(status_code=404, detail="No admin sentences available")
        
        sentence = sentences[0]
        sentence["_id"] = str(sentence["_id"])
        
        return {"success": True, "challenge": sentence}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching admin sentence: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/stage1/read-challenge/ai", tags=["Stage 1", "Student"])
async def get_ai_read_challenge(current_user: dict = Depends(get_current_user)):
    """Generate an AI sentence for read challenge"""
    # Pre-generated fallback sentences to use when API quota is exceeded
    fallback_sentences = [
        "The weather is beautiful today with clear skies and gentle breeze.",
        "I enjoy reading books in my favorite café on weekend afternoons.",
        "Learning new languages opens doors to different cultures and opportunities.",
        "Fresh fruits and vegetables are essential for maintaining good health.",
        "Regular exercise and proper sleep improve our overall well-being significantly.",
        "Technology continues to change how we work and communicate daily.",
        "Making friends from different backgrounds enriches our life experiences.",
        "Cooking is both a practical skill and a creative form of expression.",
        "Traveling to new places helps us understand diverse customs and traditions.",
        "Reading fiction develops imagination and improves our critical thinking skills."
    ]
    
    try:
        model = get_gemini_model("sentence")
        if not model:
            raise Exception("AI model not configured for sentences")
        
        prompt = """Generate a single, clear English sentence for an ESL student to practice pronunciation.
        The sentence should be:
        - 10-15 words long
        - Simple but useful vocabulary
        - Good for practicing English pronunciation
        - About a daily situation or interesting topic
        Just give the sentence, nothing else."""
        
        response = model.generate_content(prompt)
        sentence_text = response.text.strip().strip('"').strip("'")
        
        # Create temporary AI sentence
        sentence_data = {
            "sentence": sentence_text,
            "difficulty": "medium",
            "credits": 15,
            "time_limit": 90,
            "source": "ai",
            "is_active": True,
            "created_at": datetime.now(timezone.utc)
        }
        
        # Store AI-generated sentence
        result = await voice_challenge_sentences_collection.insert_one(sentence_data)
        sentence_data["_id"] = str(result.inserted_id)
        
        return {"success": True, "challenge": sentence_data}
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Error generating AI sentence: {error_msg}")
        
        # Check if it's a quota exceeded error (429)
        is_quota_exceeded = "429" in error_msg or "quota" in error_msg.lower() or "exhausted" in error_msg.lower()
        
        # Use random fallback sentence
        fallback_sentence = random.choice(fallback_sentences)
        sentence_data = {
            "sentence": fallback_sentence,
            "difficulty": "medium",
            "credits": 10,
            "time_limit": 60,
            "source": "fallback",
            "is_active": True,
            "created_at": datetime.now(timezone.utc)
        }
        
        # Store fallback sentence
        result = await voice_challenge_sentences_collection.insert_one(sentence_data)
        sentence_data["_id"] = str(result.inserted_id)
        
        warning_msg = "API quota exceeded - using fallback sentence" if is_quota_exceeded else "AI service error - using fallback sentence"
        return {"success": True, "challenge": sentence_data, "warning": warning_msg}


@router.post("/api/stage1/read-challenge/submit", tags=["Stage 1", "Student"])
async def submit_read_challenge(
    challenge_id: str = Body(...),
    transcribed_text: str = Body(...),
    time_taken: int = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Submit a read challenge and get AI feedback with voice"""
    try:
        # Validate challenge_id is a valid ObjectId
        try:
            challenge_oid = ObjectId(challenge_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid challenge ID format")
        
        # Get challenge
        challenge = await voice_challenge_sentences_collection.find_one({"_id": challenge_oid})
        if not challenge:
            raise HTTPException(status_code=404, detail="Challenge not found")
        
        original_text = challenge.get("sentence", "").strip()
        user_text = transcribed_text.strip()
        
        # AI Analysis with Advanced Error Handling and Retry Logic
        ai_success = False
        max_retries = 3
        retry_count = 0
        
        # Initialize evaluation variables to avoid UnboundLocalError
        passed = False
        score = 0
        feedback = "Submission evaluated by system."
        tamil_feedback = "நல்ல முயற்சி! உங்கள் பதில் கிடைத்துள்ளது."
        mistakes = []
        praise = "Keep practicing!"
        suggestions = ["Focus on clarity."]
        word_analysis = [] # New: Detailed word analysis
        raw_ai_response = "AI Evaluation Failed"
        
        while not ai_success and retry_count < max_retries:
            try:
                model = get_gemini_model("pronunciation")
                if not model:
                    logger.warning(f"⚠️ AI model unavailable (attempt {retry_count + 1}/{max_retries})")
                    raise Exception("AI model unavailable")
                
                prompt = f"""You are a friendly and professional English speech coach.
                Compare the student's spoken text with the correct reference text and provide constructive feedback.
                
                Correct Text: "{original_text}"
                Student Spoken: "{user_text}"
                
                Provide clear, encouraging feedback and identify specific pronunciation improvements needed.
                
                Output valid JSON only:
                {{
                    "score": integer (0-100),
                    "passed": boolean,
                    "feedback": "Two sentences of professional, constructive feedback in English",
                    "tamil_feedback": "A clear professional explanation in Tamil with suggestions for improvement",
                    "mistakes": ["specific words mispronounced"],
                    "word_analysis": [
                        {{"word": "word1", "status": "Correct" or "Needs Practice", "feedback": "tip"}},
                        ...
                    ],
                    "praise": "Something positive about their attempt",
                    "suggestions": ["how to specifically improve next time"]
                }}"""
                
                response = model.generate_content(prompt)
                if not response or not response.text:
                    raise Exception("Empty AI response")
                    
                json_str = response.text
                if "```" in json_str:
                    import re
                    match = re.search(r'\{.*\}', json_str, re.DOTALL)
                    if not match:
                        raise Exception("No JSON found in response")
                    json_str = match.group(0)
                
                result = json.loads(json_str)
                
                # Validate required fields
                if "score" not in result:
                    raise Exception("Missing score in AI response")
                    
                passed = result.get("passed", False)
                score = result.get("score", 0)
                feedback = result.get("feedback", "Good effort!")
                tamil_feedback = result.get("tamil_feedback", "நல்ல முயற்சி செல்லம்! இன்னும் கொஞ்சம் முயற்சி பண்ணுங்க.")
                mistakes = result.get("mistakes", [])
                word_analysis = result.get("word_analysis", [])
                praise = result.get("praise", "Keep practicing!")
                suggestions = result.get("suggestions", ["Try to relax while speaking."])
                
                ai_success = True
                raw_ai_response = response.text
                logger.info(f"✅ AI evaluation successful on attempt {retry_count + 1}")
                
            except json.JSONDecodeError as e:
                retry_count += 1
                logger.error(f"❌ JSON parsing failed (attempt {retry_count}/{max_retries}): {e}")
                if retry_count < max_retries:
                    await asyncio.sleep(0.5)  # Brief delay before retry
                    
            except Exception as e:
                retry_count += 1
                logger.error(f"❌ AI evaluation failed (attempt {retry_count}/{max_retries}): {e}")
                if retry_count < max_retries:
                    await asyncio.sleep(0.5)  # Brief delay before retry
        
        # Fallback if AI failed after all retries
        if not ai_success:
            logger.warning("⚠️ Using fallback evaluation after AI failures")
            import difflib
            matcher = difflib.SequenceMatcher(None, original_text.lower(), user_text.lower())
            score = int(matcher.ratio() * 100)
            passed = score >= 80
            feedback = "Great job! You did well!" if passed else "Good try! Keep practicing to improve."
            tamil_feedback = "அருமை செல்லம்! இன்னும் நன்றாக பயிற்சி செய்யுங்கள். 💕"
            mistakes = []
            praise = "You're making progress!"
        
        # Generate voice feedback using gTTS
        audio_filename = None
        try:
            # Use Tamil feedback for "Google Akka" voice if available
            voice_text = tamil_feedback or feedback
            tts_lang = 'ta' if tamil_feedback else 'en'
            tts = gTTS(text=voice_text, lang=tts_lang, slow=False)
            
            # Save audio file
            audio_filename = f"feedback_{current_user['_id']}_{int(datetime.now().timestamp())}.mp3"
            audio_path = f"static/uploads/{audio_filename}"
            tts.save(audio_path)
            
            logger.info(f"✅ Voice feedback generated: {audio_filename}")
        except Exception as e:
            logger.error(f"❌ Voice generation failed: {e}")
        
        # Calculate credits
        credits_earned = 0
        if passed:
            # Check if already completed this sentence
            already_completed = await communication_submissions_collection.find_one({
                "user_id": str(current_user["_id"]),
                "challenge_id": challenge_id,
                "challenge_type": "read",
                "score": {"$gte": 80}
            })
            
            if not already_completed:
                credits_earned = challenge.get("credits", 10)
                await update_user_credits(
                    str(current_user["_id"]),
                    credits_earned,
                    "read_challenge",
                    f"Completed read challenge"
                )
        
        # Save submission
        submission_data = {
            "user_id": str(current_user["_id"]),
            "challenge_type": "read",
            "challenge_id": challenge_id,
            "submission_text": user_text,
            "time_taken": time_taken,
            "score": score,
            "passed": passed,
            "feedback": feedback,
            "tamil_feedback": tamil_feedback,
            "mistakes": mistakes,
            "word_analysis": word_analysis,
            "praise": praise,
            "suggestions": suggestions,
            "credits_earned": credits_earned,
            "submitted_at": datetime.now(timezone.utc)
        }
        
        await communication_submissions_collection.insert_one(submission_data)
        
        return {
            "success": True,
            "passed": passed,
            "score": score,
            "feedback": feedback,
            "tamil_feedback": tamil_feedback,
            "mistakes": mistakes,
            "word_analysis": word_analysis,
            "praise": praise,
            "suggestions": suggestions,
            "credits_earned": credits_earned,
            "audio_url": f"/static/uploads/{audio_filename}" if audio_filename else None,
            "raw_ai_response": raw_ai_response if ai_success else "AI Evaluation Failed"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error submitting read challenge: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/stage1/generate-reading-challenge")
async def generate_reading_challenge(
    request_data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Generate a reading challenge passage using Ollama"""
    
    # Fallback reading passages when Ollama fails
    fallback_passages = [
        {
            "content": "The Great Barrier Reef is the world's largest coral reef system. Located off the coast of Australia, it stretches over 2,300 kilometers. The reef is home to thousands of species of fish and coral. However, climate change and pollution are threatening its survival.",
            "instructions": "What is the Great Barrier Reef and where is it located?",
            "example_answer": "The Great Barrier Reef is the world's largest coral reef system located off the coast of Australia, stretching over 2,300 kilometers."
        },
        {
            "content": "Marie Curie was a Polish-born physicist and chemist who conducted pioneering research on radioactivity. She was the first woman to win a Nobel Prize and the first person to win Nobel Prizes in two scientific fields. Despite facing discrimination as a woman in science, she made groundbreaking discoveries that changed our understanding of atoms.",
            "instructions": "Why was Marie Curie important in the history of science?",
            "example_answer": "Marie Curie was important because she conducted pioneering research on radioactivity and was the first woman and first person to win Nobel Prizes in two scientific fields."
        },
        {
            "content": "Renewable energy sources like solar and wind power are becoming increasingly important. Unlike fossil fuels, they don't produce greenhouse gases. Countries around the world are investing in renewable energy to combat climate change and reduce pollution. By using renewable energy, we can create a more sustainable future for our planet.",
            "instructions": "What are the advantages of renewable energy?",
            "example_answer": "Renewable energy sources don't produce greenhouse gases and help combat climate change and pollution, creating a more sustainable future."
        },
        {
            "content": "The Amazon Rainforest is often called the 'lungs of the Earth' because it produces about 20% of the world's oxygen. It is home to millions of plant and animal species. However, deforestation is destroying this vital ecosystem at an alarming rate. Protecting the Amazon is crucial for fighting climate change.",
            "instructions": "Why is the Amazon Rainforest important to the world?",
            "example_answer": "The Amazon Rainforest is important because it produces about 20% of the world's oxygen, is home to millions of species, and is crucial for fighting climate change."
        }
    ]
    
    try:
        difficulty = request_data.get("difficulty", "intermediate")
        topic = request_data.get("topic", "general")
        
        # Use Ollama directly to generate passage
        prompt = f"""Generate a short reading passage about {topic} at {difficulty} level for English learners.
The passage should be 2-3 sentences long and easy to understand.

Format your response as:
PASSAGE: [the passage text]
QUESTION: [a comprehension question about the passage]
ANSWER: [a brief example answer]

Make it appropriate for {difficulty} level English learners."""
        
        # Direct Ollama call
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.8,
                        "top_p": 0.9
                    }
                }
            )
            
            if response.status_code != 200:
                raise Exception(f"Ollama API error: {response.status_code}")
            
            result = response.json()
            generated_text = result.get("response", "").strip()
        
        # Robust Parsing
        passage = ""
        question = ""
        answer = ""
        
        # Try to extract using regex
        import re
        p_match = re.search(r'(?i)(?:PASSAGE|Passage):\s*([\s\S]*?)(?=(?:QUESTION|Question|ANSWER|Answer|$))', generated_text)
        q_match = re.search(r'(?i)(?:QUESTION|Question):\s*([\s\S]*?)(?=(?:PASSAGE|Passage|ANSWER|Answer|$))', generated_text)
        a_match = re.search(r'(?i)(?:ANSWER|Answer):\s*([\s\S]*?)(?=(?:PASSAGE|Passage|QUESTION|Question|$))', generated_text)
        
        if p_match:
            passage = p_match.group(1).strip().strip('*').strip('"')
        if q_match:
            question = q_match.group(1).strip().strip('*').strip('"')
        if a_match:
            answer = a_match.group(1).strip().strip('*').strip('"')
        
        # Fallback to line splitting if regex fails or looks weird
        if not passage or not question:
            for line in generated_text.split('\n'):
                if line.upper().startswith("PASSAGE:"):
                    passage = line.split(":", 1)[1].strip()
                elif line.upper().startswith("QUESTION:"):
                    question = line.split(":", 1)[1].strip()
                elif line.upper().startswith("ANSWER:"):
                    answer = line.split(":", 1)[1].strip()
        
        # Validate parsed content
        if not passage:
            passage = generated_text.split('\n')[0]
        if not question:
            question = "What is the main idea of this passage?"
        if not answer:
            answer = "Provide your understanding based on the passage"
        
        challenge = {
            "title": f"{topic.title()} Reading",
            "topic": topic,
            "content": passage,
            "instructions": question,
            "example_answer": answer,
            "difficulty": difficulty,
            "duration": 5,
            "credits": 10,
            "skill": "reading",
            "is_active": True,
            "source": "ollama",
            "generated_at": datetime.now(timezone.utc)
        }
        
        # Store the generated challenge in the database
        result = await challenges_collection.insert_one(challenge)
        challenge["_id"] = str(result.inserted_id)
        
        logger.info(f"✅ Reading challenge generated and saved via Ollama: {difficulty}")
        return {"success": True, "challenge": challenge}
    except Exception as e:
        error_msg = str(e)
        logger.warning(f"⚠️ Ollama reading generation failed: {error_msg}. Using fallback.")
        
        # Use random fallback passage
        fallback = random.choice(fallback_passages)
        challenge = {
            "title": f"{topic.title()} Reading (Fallback)", # Added title for fallback
            "topic": topic, # Added topic for fallback
            "content": fallback["content"],
            "instructions": fallback["instructions"],
            "example_answer": fallback["example_answer"],
            "difficulty": "intermediate",
            "duration": 5,
            "credits": 10,
            "skill": "reading",
            "is_active": True,
            "source": "fallback",
            "generated_at": datetime.now(timezone.utc)
        }
        
        logger.info("✅ Using fallback reading passage")
        return {"success": True, "challenge": challenge}


@router.post("/api/stage1/evaluate-reading-answer")
async def evaluate_reading_answer(
    request_data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Evaluate reading comprehension answer using Ollama"""
    try:
        answer = request_data.get("answer", "")
        passage = request_data.get("passage", "")
        question = request_data.get("question", "")
        example_answer = request_data.get("example_answer", "")
        
        if not answer:
            raise HTTPException(status_code=400, detail="Answer is required")
        
        # Create evaluation prompt
        prompt = f"""You are an English teacher evaluating a student's reading comprehension.

PASSAGE: {passage}

QUESTION: {question}

EXPECTED/EXAMPLE ANSWER: {example_answer}

STUDENT'S ANSWER: {answer}

Evaluate the answer on a scale of 0-100 based on:
1. Does the student understand the passage?
2. Does the answer address the question?
3. Is the answer clear and well-written?

Provide ONLY these two lines:
SCORE: [0-100]
FEEDBACK: [1-2 sentences of feedback]"""
        
        # Direct Ollama call for evaluation
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.5,
                        "top_p": 0.9
                    }
                }
            )
            
            if response.status_code != 200:
                raise Exception(f"Ollama API error: {response.status_code}")
            
            result = response.json()
            eval_response = result.get("response", "").strip()
        
        # Robust Parsing
        score = 70
        feedback = "Good comprehension. Keep practicing!"
        
        # Use regex to find SCORE: and FEEDBACK:
        import re
        score_match = re.search(r'(?i)SCORE:\s*(\d+)', eval_response)
        feedback_match = re.search(r'(?i)FEEDBACK:\s*([\s\S]*)', eval_response)
        
        if score_match:
            try:
                score = int(score_match.group(1))
                score = max(0, min(100, score))
            except:
                pass
        
        if feedback_match:
            feedback = feedback_match.group(1).strip().strip('*').strip('"')
            if "SCORE" in feedback.upper() and feedback.upper().find("SCORE") > 0:
                feedback = feedback[:feedback.upper().find("SCORE")].strip()
                
        # Fallback to line splitting
        if not score_match or not feedback_match:
            for line in eval_response.split('\n'):
                if line.upper().startswith("SCORE:"):
                    try:
                        score_str = line.split(":", 1)[1].strip()
                        score = int(''.join(filter(str.isdigit, score_str)))
                        score = max(0, min(100, score))
                    except:
                        pass
                elif line.upper().startswith("FEEDBACK:"):
                    feedback = line.split(":", 1)[1].strip()
        
        logger.info(f"✅ Reading answer evaluated: score={score}")
        return {
            "success": True,
            "perfection": score,
            "accuracy": score,
            "feedback": feedback
        }
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.warning(f"⚠️ Ollama evaluation failed: {error_msg}. Using default scoring.")
        
        # Fallback evaluation - count key words from example answer
        try:
            answer_lower = answer.lower()
            expected_lower = example_answer.lower()
            
            # Simple keyword matching
            words = expected_lower.split()
            matched = sum(1 for word in words if len(word) > 3 and word in answer_lower)
            score = min(100, max(30, (matched / max(len(words), 1)) * 100))
            
            feedback = "Your answer shows understanding. Good effort!"
            if score >= 80:
                feedback = "Excellent comprehension! Well done."
            elif score >= 60:
                feedback = "Good understanding. You could add more details."
            elif score >= 40:
                feedback = "You understood some points. Review the passage again."
            
            return {
                "success": True,
                "perfection": int(score),
                "accuracy": int(score),
                "feedback": feedback
            }
        except Exception as fallback_error:
            logger.error(f"Fallback evaluation failed: {fallback_error}")
            return {
                "success": True,
                "perfection": 50,
                "accuracy": 50,
                "feedback": "Your answer was evaluated. Keep improving your comprehension!"
            }


