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
from app.services.ai_service import AIService
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
        prompt = """Generate a single, clear English sentence for an ESL student to practice pronunciation.
        The sentence should be:
        - 10-15 words long
        - Simple but useful vocabulary
        - Good for practicing English pronunciation
        - About a daily situation or interesting topic
        Just give the sentence, nothing else."""
        
        sentence_text = await AIService.call_kimi(prompt)
        if not sentence_text:
            raise Exception("Gemini model response was empty")
        
        sentence_text = sentence_text.strip().strip('"').strip("'")
        
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
                system_prompt = "You are a friendly and professional English speech coach."
                prompt = f"""Compare the student's spoken text with the correct reference text and provide constructive feedback.
                
                Correct Text: "{original_text}"
                Student Spoken: "{user_text}"
                
                Provide clear, encouraging feedback and identify specific pronunciation improvements needed.
                
                Your response must be a valid JSON object ONLY:
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
                
                json_str = await AIService.call_kimi(prompt, system_prompt, json_mode=True)
                if not json_str:
                    raise Exception("Empty AI response")
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
                raw_ai_response = json_str
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
            "content": "The Great Barrier Reef is the world's largest coral reef system, extending over 2,300 kilometers along Australia's coast. It consists of thousands of individual reefs and hundreds of islands, providing a home for a diverse range of marine life, including colorful fish, sea turtles, and whales. However, the reef faces significant threats from rising ocean temperatures, which cause coral bleaching, and pollution from nearby land development. Conservation efforts are underway to protect this natural wonder, but global action on climate change remains the most critical factor for its long-term survival.",
            "instructions": "Where is the Great Barrier Reef located and why is it currently under threat?",
            "example_answer": "It is located off the coast of Australia. It is threatened by rising ocean temperatures (causing bleaching) and pollution.",
            "multi_questions": [
                {"id": 1, "question": "Where is the Great Barrier Reef located and how long is it?", "example_answer": "It is located off the coast of Australia and is over 2,300 kilometers long."},
                {"id": 2, "question": "Name two types of marine life mentioned that live in the reef.", "example_answer": "Fish, sea turtles, and whales were mentioned."},
                {"id": 3, "question": "What is the most critical factor for the reef's long-term survival?", "example_answer": "Global action on climate change is the most critical factor."}
            ]
        },
        {
            "content": "Marie Curie was a pioneering physicist and chemist, born in Poland in 1867. She is best known for her discovery of radium and polonium, and her extensive research on radioactivity. Curie's work was groundbreaking, as she became the first woman to win a Nobel Prize and the only person to win Nobel Prizes in two different scientific fields: Physics and Chemistry. Despite the challenges she faced as a woman in a male-dominated field, her dedication and brilliance paved the way for future generations of scientists. She also developed mobile X-ray units during World War I to help treat wounded soldiers.",
            "instructions": "What scientific achievements is Marie Curie best known for?",
            "example_answer": "She discovered radium and polonium, researched radioactivity, and won two Nobel Prizes in different fields.",
            "multi_questions": [
                {"id": 1, "question": "What elements did Marie Curie discover?", "example_answer": "She discovered radium and polonium."},
                {"id": 2, "question": "What was unique about Marie Curie's Nobel Prize achievements?", "example_answer": "She was the first woman to win one and the only person to win in two different scientific fields."},
                {"id": 3, "question": "How did she contribute to the war effort during World War I?", "example_answer": "She developed mobile X-ray units to help treat wounded soldiers."}
            ]
        },
        {
            "content": "Sustainable cities are designed to minimize their environmental impact through efficient energy use, reduced waste, and the promotion of public transportation and green spaces. Many modern cities are now integrating vertical gardens on buildings and implementing smart grids to manage electricity more effectively. Furthermore, urban planning that prioritizes walking and cycling over cars helps to reduce air pollution and improve the health of residents. Creating a sustainable urban environment is essential for accommodating the world's growing population while preserving resources for future generations.",
            "instructions": "What are the main goals and features of a sustainable city?",
            "example_answer": "The goals are to minimize environmental impact. Features include efficient energy use, public transport, and green spaces.",
            "multi_questions": [
                {"id": 1, "question": "What are two features of modern sustainable cities mentioned in the text?", "example_answer": "Vertical gardens and smart grids for electricity management."},
                {"id": 2, "question": "How does prioritizing walking and cycling benefit city residents?", "example_answer": "It reduces air pollution and improves the health of residents."},
                {"id": 3, "question": "Why is creating sustainable urban environments considered essential?", "example_answer": "It is necessary to accommodate the growing population while preserving resources."}
            ]
        }
    ]
    
    try:
        difficulty = request_data.get("difficulty", "intermediate")
        topic = request_data.get("topic", "general")
        
        # Use Kimi to generate passage and questions
        prompt = f"""Generate a detailed reading comprehension challenge about {topic} at {difficulty} level for English learners.
        The passage should be substantial (about 150-200 words) and use natural but appropriate vocabulary.
        
        You must provide exactly 3 comprehension questions based on the passage that test different levels of understanding.
        
        Return your response as a valid JSON object ONLY:
        {{
            "passage": "Full passage text...",
            "questions": [
                {{
                    "id": 1,
                    "question": "Question text...",
                    "example_answer": "Brief correct answer for teacher reference..."
                }},
                {{
                    "id": 2,
                    "question": "Question text...",
                    "example_answer": "Brief correct answer for teacher reference..."
                }},
                {{
                    "id": 3,
                    "question": "Question text...",
                    "example_answer": "Brief correct answer for teacher reference..."
                }}
            ]
        }}"""
        
        json_str = await AIService.call_kimi(prompt, json_mode=True)
        if not json_str:
            raise Exception("Gemini model response was empty")
        
        if "```" in json_str:
            import re
            match = re.search(r'\{.*\}', json_str, re.DOTALL)
            if match:
                json_str = match.group(0)
                
        try:
            result_data = json.loads(json_str)
            passage = result_data.get("passage", "")
            questions_list = result_data.get("questions", [])
            
            # Convert to internal format (keeping compatibility)
            # We'll store multiple questions in a field, but keep instructions/example_answer for legacy UI support if needed
            question = questions_list[0].get("question", "") if questions_list else "Question not generated"
            answer = questions_list[0].get("example_answer", "") if questions_list else ""
            
            # Store all questions in a new field
            multi_questions = questions_list
        except Exception as parse_err:
            logger.error(f"Failed to parse generation JSON: {parse_err}")
            # Fallback parsing (very simple)
            passage = json_str[:500] 
            question = "Please analyze the passage above."
            answer = "Understanding"
            multi_questions = [{"id": 1, "question": question, "example_answer": answer}]
        
        challenge = {
            "title": f"{topic.title()} Reading",
            "topic": topic,
            "content": passage,
            "instructions": question,
            "example_answer": answer,
            "multi_questions": multi_questions,
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
        # Support both single answer (legacy) and multiple answers
        answer = request_data.get("answer", "")
        answers_list = request_data.get("answers", []) # Should be list of objects with question and answer
        passage = request_data.get("passage", "")
        question = request_data.get("question", "")
        example_answer = request_data.get("example_answer", "")
        
        if not answer and not answers_list:
            raise HTTPException(status_code=400, detail="Answer is required")
        
        if answers_list:
            # Multi-question evaluation
            answers_str = "\n".join([f"QUESTION {i+1}: {a.get('question')}\nSTUDENT'S ANSWER: {a.get('answer')}\nEXPECTED: {a.get('example_answer')}" for i, a in enumerate(answers_list)])
            
            prompt = f"""You are an English teacher evaluating a student's reading comprehension across multiple questions.
            
            PASSAGE: {passage}
            
            STUDENT'S RESPONSES:
            {answers_str}
            
            Evaluate each answer individually, then provide an overall score (0-100) and combined feedback.
            Consider:
            1. Did the student understand the specific details asked in each question?
            2. Is the overall comprehension of the passage demonstrated?
            3. Are the answers clear and correctly formulated?
            
            Return your response as a valid JSON object ONLY:
            {{
                "score": integer (0-100),
                "feedback": "Two sentences of professional, constructive feedback in English summarizing their performance",
                "tamil_feedback": "A clear professional explanation in Tamil summarizing how well they understood the passage",
                "detailed_analysis": "Briefly mention which questions were handled well or poorly"
            }}"""
            
            # Use JSON mode for multi-eval
            eval_response = await AIService.call_kimi(prompt, json_mode=True)
            if not eval_response:
                raise Exception("Gemini model response was empty")
                
            if "```" in eval_response:
                import re
                match = re.search(r'\{.*\}', eval_response, re.DOTALL)
                if match:
                    eval_response = match.group(0)
            
            result = json.loads(eval_response)
            return {
                "success": True,
                "perfection": result.get("score", 70),
                "accuracy": result.get("score", 70),
                "feedback": result.get("feedback", "Good comprehension!"),
                "tamil_feedback": result.get("tamil_feedback", ""),
                "detailed_analysis": result.get("detailed_analysis", "")
            }

        # Original single question logic fallback
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
        
        eval_response = await AIService.call_kimi(prompt)
        if not eval_response:
            raise Exception("Gemini model response was empty")
        
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


