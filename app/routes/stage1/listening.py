"""
EduSync Backend - Stage 1 - Listening Routes
Advanced Listening Modules: Fill the Beats, Direction Follower, Tone Recognizer
"""
import logging
import json
import random
import re
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Body, Query
from app.dependencies import get_current_user
from app.database import *
from app.services.ai_service import AIService
from app.models.communication import (
    ListeningEvaluationRequest,
    ListeningMCQEvaluationRequest,
    ListeningGapEvaluationRequest,
    ListeningToneEvaluationRequest,
    ListeningDirectionEvaluationRequest
)
from app.utils.helpers import update_user_credits

logger = logging.getLogger("edusync")

router = APIRouter(prefix="/api", tags=["Stage 1 - Listening"])

# ==================== SENTENCE DICTATION (EXISTING) ====================

@router.post("/communication/evaluate-listening")
async def evaluate_listening(data: ListeningEvaluationRequest, current_user: dict = Depends(get_current_user)):
    """Evaluate a listening challenge answer (Sentence Dictation)."""
    try:
        user_answer = data.user_answer.strip()
        actual_sentence = data.actual_sentence.strip()
        
        if not user_answer:
            raise HTTPException(status_code=400, detail="Answer cannot be empty")
            
        system_prompt = "You are a friendly and professional English teacher evaluating a student's listening comprehension (sentence dictation)."
        prompt = f"""Compare the student's typed answer with the correct sentence they were supposed to hear.
        
        Correct Sentence: "{actual_sentence}"
        Student Answer: "{user_answer}"
        
        Evaluate the accuracy (0-100), identify small typos versus serious misunderstandings, and provide encouraging feedback.
        
        Your response must be a valid JSON object ONLY:
        {{
            "score": integer (0-100),
            "feedback": "Two sentences of professional, constructive feedback in English",
            "tamil_feedback": "A clear professional explanation in Tamil with suggestions for improvement",
            "mistakes": ["specific words misspelled or missed"],
            "praise": "Something positive about their attempt",
            "suggestions": ["how to specifically improve next time"]
        }}"""
        
        json_str = await AIService.call_kimi(prompt, system_prompt, json_mode=True)
        
        if not json_str:
            # Fallback evaluation
            import difflib
            matcher = difflib.SequenceMatcher(None, actual_sentence.lower(), user_answer.lower())
            score = int(matcher.ratio() * 100)
            result = {
                "score": score,
                "feedback": "Good effort! Keep practicing your listening skills.",
                "tamil_feedback": "நல்ல முயற்சி! தொடர்ந்து பயிற்சி செய்யுங்கள்.",
                "mistakes": [],
                "praise": "You're making progress!",
                "suggestions": ["Try listening to the audio multiple times."]
            }
        else:
            result = json.loads(json_str)
        
        # Award credits based on score
        score = result.get("score", 0)
        credits_earned = 0
        if score >= 60:
            credits_earned = max(5, round((score / 100) * 15))
            await update_user_credits(str(current_user["_id"]), credits_earned, "listening_challenge", f"Completed listening challenge with {score}% score")
            
        result["credits_earned"] = credits_earned
        return result
    except Exception as e:
        logger.error(f"Error evaluating listening: {e}")
        return {"score": 50, "feedback": "Evaluation error.", "tamil_feedback": "பிழை ஏற்பட்டது.", "mistakes": [], "credits_earned": 0}

# ==================== LISTEN & RESPOND MCQ (EXISTING) ====================

@router.post("/communication/generate-listening-mcq")
async def generate_listening_mcq(current_user: dict = Depends(get_current_user)):
    """Generate a Listen & Respond MCQ challenge using AI."""
    try:
        system_prompt = "You are an English teacher creating a listening comprehension quiz."
        prompt = """Generate a high-quality listening comprehension multiple choice question.
        Your response must be a valid JSON object ONLY:
        {
            "id": "unique_string",
            "audio_text": "The sentence/question student will HEAR",
            "question": "The written question student will READ",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_index": integer (0-3),
            "explanation": "English explanation",
            "tamil_explanation": "Tamil explanation",
            "difficulty": "easy/medium/hard",
            "category": "conversational"
        }"""
        json_str = await AIService.call_kimi(prompt, system_prompt, json_mode=True)
        return json.loads(json_str)
    except Exception as e:
        logger.error(f"Error generating listening mcq: {e}")
        return {"id": "err", "audio_text": "Error generating.", "question": "Error", "options": ["A","B","C","D"], "correct_index": 0}

@router.post("/communication/evaluate-listening-mcq")
async def evaluate_listening_mcq(data: ListeningMCQEvaluationRequest, current_user: dict = Depends(get_current_user)):
    """Evaluate a Listening MCQ answer."""
    is_correct = (data.selected_index == data.correct_index)
    credits_earned = 10 if is_correct else 0
    if is_correct:
        await update_user_credits(str(current_user["_id"]), credits_earned, "listening_mcq", "Completed Listen & Respond challenge correctly")
    return {"success": True, "is_correct": is_correct, "credits_earned": credits_earned, "feedback": "Perfect!" if is_correct else "Try again!"}

# ==================== 1. FILL THE BEATS (UPDATED) ====================

@router.post("/communication/generate-listening-gap")
async def generate_listening_gap(current_user: dict = Depends(get_current_user)):
    """Generate a 'Fill the Beats' challenge using Gemini."""
    try:
        system_prompt = "You are an English teacher creating a 'Fill the Beats' listening exercise."
        prompt = """Generate an engaging English passage (4-6 sentences) that could be from a song or a natural conversation.
        Pick 3-5 specific words to be hidden as gaps. Ensure they are important keywords.
        
        Return ONLY valid JSON:
        {
            "id": "gap_task_" + uuid,
            "full_text": "The complete text with all words (audio source)",
            "text_with_gaps": "The text with [___] placeholders (e.g., 'I [___] to the store.')",
            "correct_answers": ["went", ...],
            "difficulty": "medium",
            "topic": "Daily Life/Song Verse"
        }"""
        
        # Using a UUID placeholder logic or just random
        import uuid
        task_id = f"gap-{uuid.uuid4().hex[:8]}"
        
        json_str = await AIService.call_kimi(prompt.replace("uuid", task_id), system_prompt, json_mode=True)
        data = json.loads(json_str)
        data["id"] = task_id
        return data
    except Exception as e:
        logger.error(f"Error generating Fill the Beats: {e}")
        return {
            "id": "err",
            "full_text": "I really enjoy learning English every day because it helps me communicate.",
            "text_with_gaps": "I really [___] learning English every [___] because it helps me [___].",
            "correct_answers": ["enjoy", "day", "communicate"],
            "difficulty": "medium"
        }

@router.post("/communication/evaluate-listening-gap")
async def evaluate_listening_gap(data: ListeningGapEvaluationRequest, current_user: dict = Depends(get_current_user)):
    """Evaluate 'Fill the Beats' answers with AI feedback."""
    try:
        user_answers = [a.strip().lower() for a in data.user_answers]
        correct_answers = [a.strip().lower() for a in data.correct_answers]
        
        correct_count = 0
        for u, c in zip(user_answers, correct_answers):
            if u == c: correct_count += 1
            
        score = int((correct_count / len(correct_answers)) * 100) if correct_answers else 0
        
        # Get AI feedback
        system_prompt = "You are an English tutor."
        feedback_prompt = f"""Student filled gaps in a listening task.
        Correct: {correct_answers}
        Student: {user_answers}
        Accuracy: {score}%
        
        Provide professional feedback in English and Tamil.
        Return ONLY JSON:
        {{
            "feedback": "Short encouraging English feedback",
            "tamil_feedback": "Short Tamil feedback"
        }}"""
        
        feedback_json = await AIService.call_kimi(feedback_prompt, system_prompt, json_mode=True)
        feedback_data = json.loads(feedback_json) if feedback_json else {"feedback": "Good job!", "tamil_feedback": "நல்ல முயற்சி!"}
        
        credits_earned = 20 if score >= 80 else (10 if score >= 50 else 0)
        if credits_earned > 0:
            await update_user_credits(str(current_user["_id"]), credits_earned, "listening_gap", f"Completed Fill the Beats with {score}%")
            
        return {
            "score": score,
            "credits_earned": credits_earned,
            "feedback": feedback_data.get("feedback"),
            "tamil_feedback": feedback_data.get("tamil_feedback")
        }
    except Exception as e:
        logger.error(e)
        return {"score": 0, "credits_earned": 0, "feedback": "Error evaluating", "tamil_feedback": "பிழை"}

# ==================== 2. DIRECTION FOLLOWER (GRID PATH TRACING) ====================

@router.post("/communication/generate-listening-direction")
async def generate_listening_direction(current_user: dict = Depends(get_current_user)):
    """Generate a grid-based path tracing listening challenge."""
    try:
        GRID_SIZE = 7  # 7x7 grid

        all_landmarks = [
            {"name": "Library", "icon": "fa-book"},
            {"name": "Bakery", "icon": "fa-bread-slice"},
            {"name": "Park", "icon": "fa-tree"},
            {"name": "Hospital", "icon": "fa-hospital"},
            {"name": "Bank", "icon": "fa-university"},
            {"name": "Gym", "icon": "fa-dumbbell"},
            {"name": "Pharmacy", "icon": "fa-pills"},
            {"name": "School", "icon": "fa-school"},
            {"name": "Cafe", "icon": "fa-coffee"},
            {"name": "Theater", "icon": "fa-film"},
            {"name": "Market", "icon": "fa-shopping-basket"},
            {"name": "Museum", "icon": "fa-landmark"},
            {"name": "Hotel", "icon": "fa-hotel"},
            {"name": "Office", "icon": "fa-briefcase"},
            {"name": "Garage", "icon": "fa-car"},
            {"name": "Bus Stop", "icon": "fa-bus"},
            {"name": "Train Station", "icon": "fa-train"},
        ]

        random.shuffle(all_landmarks)
        num_landmarks = random.randint(8, 12)
        selected_landmarks = all_landmarks[:num_landmarks]

        # Place landmarks on random grid positions (no overlaps)
        all_positions = [(r, c) for r in range(GRID_SIZE) for c in range(GRID_SIZE)]
        random.shuffle(all_positions)

        placed_landmarks = []
        for i, lm in enumerate(selected_landmarks):
            pos = all_positions[i]
            placed_landmarks.append({
                "name": lm["name"],
                "icon": lm["icon"],
                "row": pos[0],
                "col": pos[1]
            })

        # Build a lookup for quick access
        pos_to_landmark = {(lm["row"], lm["col"]): lm for lm in placed_landmarks}

        # Pick start and end landmarks (ensure they are different)
        start_lm = placed_landmarks[0]
        end_lm = placed_landmarks[-1]

        # Generate a simple path from start to end using L-shape or staircase
        path = []
        sr, sc = start_lm["row"], start_lm["col"]
        er, ec = end_lm["row"], end_lm["col"]

        # Walk rows first, then columns (simple L-path)
        r, c = sr, sc
        path.append({"row": r, "col": c})

        # Add 1-2 intermediate waypoints for more interesting paths
        mid_row = (sr + er) // 2
        mid_col = (sc + ec) // 2

        # Path: start -> (sr, mid_col) -> (er, mid_col) -> end
        # Or: start -> (mid_row, sc) -> (mid_row, ec) -> end
        strategy = random.choice(["col_first", "row_first"])

        if strategy == "col_first":
            # Move along columns first to mid_col, then rows to er, then cols to ec
            while c != mid_col:
                c += 1 if mid_col > c else -1
                path.append({"row": r, "col": c})
            while r != er:
                r += 1 if er > r else -1
                path.append({"row": r, "col": c})
            while c != ec:
                c += 1 if ec > c else -1
                path.append({"row": r, "col": c})
        else:
            # Move along rows first
            while r != mid_row:
                r += 1 if mid_row > r else -1
                path.append({"row": r, "col": c})
            while c != ec:
                c += 1 if ec > c else -1
                path.append({"row": r, "col": c})
            while r != er:
                r += 1 if er > r else -1
                path.append({"row": r, "col": c})

        # Find landmarks that are on/near the path for direction references
        path_positions = set((p["row"], p["col"]) for p in path)
        landmarks_on_path = [lm["name"] for lm in placed_landmarks if (lm["row"], lm["col"]) in path_positions]

        # Generate directions text via AI
        path_description = []
        for i in range(1, len(path)):
            prev = path[i - 1]
            curr = path[i]
            if curr["row"] > prev["row"]:
                path_description.append("down")
            elif curr["row"] < prev["row"]:
                path_description.append("up")
            elif curr["col"] > prev["col"]:
                path_description.append("right")
            elif curr["col"] < prev["col"]:
                path_description.append("left")

        # Compress consecutive same directions
        compressed = []
        if path_description:
            current_dir = path_description[0]
            count = 1
            for d in path_description[1:]:
                if d == current_dir:
                    count += 1
                else:
                    compressed.append(f"{count} block{'s' if count > 1 else ''} {current_dir}")
                    current_dir = d
                    count = 1
            compressed.append(f"{count} block{'s' if count > 1 else ''} {current_dir}")

        simple_directions = f"Start from {start_lm['name']}. Go " + ", then ".join(compressed) + f". Your destination is {end_lm['name']}."

        # Try AI for more natural directions
        try:
            system_prompt = "You are an English teacher giving clear walking directions on a grid map."
            prompt = f"""Given these step-by-step grid movements: {', '.join(compressed)},
            starting from '{start_lm['name']}' and ending at '{end_lm['name']}',
            with these landmarks nearby: {', '.join(landmarks_on_path)},
            
            Rewrite these as natural-sounding walking directions (3-4 sentences).
            Use phrases like 'Go straight', 'Turn left/right', 'Walk X blocks', 'Pass by the...'
            
            Return ONLY valid JSON:
            {{
                "directions_text": "Natural walking directions here"
            }}"""

            json_str = await AIService.call_kimi(prompt, system_prompt, json_mode=True)
            ai_data = json.loads(json_str)
            directions_text = ai_data.get("directions_text", simple_directions)
        except Exception:
            directions_text = simple_directions

        return {
            "id": f"dir-{random.randint(1000, 9999)}",
            "grid_size": GRID_SIZE,
            "landmarks": placed_landmarks,
            "start": {"row": start_lm["row"], "col": start_lm["col"], "name": start_lm["name"]},
            "end": {"row": end_lm["row"], "col": end_lm["col"], "name": end_lm["name"]},
            "correct_path": path,
            "directions_text": directions_text,
            "difficulty": "Hard"
        }
    except Exception as e:
        logger.error(f"Direction generation error: {e}")
        raise HTTPException(status_code=500, detail="Generation failed")


@router.post("/communication/evaluate-listening-direction")
async def evaluate_listening_direction(data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Evaluate direction follower path tracing results."""
    try:
        user_path = data.get("user_path", [])
        correct_path = data.get("correct_path", [])
        start_name = data.get("start_name", "Start")
        end_name = data.get("end_name", "End")
        time_taken = data.get("time_taken", 0)

        if not user_path or not correct_path:
            return {"score": 0, "is_correct": False, "feedback": "No path data.", "credits_earned": 0}

        # Convert to tuples for comparison
        user_tuples = [(p.get("row"), p.get("col")) for p in user_path]
        correct_tuples = [(p.get("row"), p.get("col")) for p in correct_path]

        # Check if user reached the correct destination
        reached_destination = user_tuples[-1] == correct_tuples[-1] if user_tuples and correct_tuples else False

        # Calculate path accuracy (how many correct nodes were hit in order)
        correct_count = 0
        user_set = set(user_tuples)
        for node in correct_tuples:
            if node in user_set:
                correct_count += 1

        path_accuracy = int((correct_count / len(correct_tuples)) * 100) if correct_tuples else 0

        # Bonus for reaching the destination
        score = path_accuracy
        if reached_destination:
            score = min(100, score + 20)

        # Speed bonus
        speed_bonus = 0
        if time_taken > 0 and time_taken < 60 and score >= 70:
            speed_bonus = 5

        score = min(100, score + speed_bonus)
        is_correct = reached_destination and path_accuracy >= 60

        # AI feedback
        try:
            system_prompt = "You are a professional English tutor."
            prompt = f"""Student traced a path on a map from '{start_name}' to '{end_name}'.
            Path accuracy: {path_accuracy}%, Reached destination: {reached_destination}, Score: {score}%.
            Time taken: {time_taken} seconds.
            Give feedback in 1-2 sentences and a Tamil translation.
            Return ONLY JSON:
            {{
                "feedback": "English feedback",
                "tamil_feedback": "Tamil feedback"
            }}"""

            ai_json = await AIService.call_kimi(prompt, system_prompt, json_mode=True)
            ai_feedback = json.loads(ai_json) if ai_json else {"feedback": "Good attempt!", "tamil_feedback": "நல்ல முயற்சி!"}
        except Exception:
            ai_feedback = {"feedback": "Good attempt at following directions!", "tamil_feedback": "திசையைப் பின்பற்றும் உங்கள் முயற்சி நல்லது!"}

        credits = 0
        if is_correct:
            credits = 15 + speed_bonus
            await update_user_credits(str(current_user["_id"]), credits, "listening_direction", f"Direction path tracing - {score}%")

        return {
            "score": score,
            "path_accuracy": path_accuracy,
            "reached_destination": reached_destination,
            "is_correct": is_correct,
            "credits_earned": credits,
            "speed_bonus": speed_bonus,
            "feedback": ai_feedback.get("feedback"),
            "tamil_feedback": ai_feedback.get("tamil_feedback")
        }
    except Exception as e:
        logger.error(f"Direction eval error: {e}")
        return {"score": 0, "is_correct": False, "feedback": "Evaluation error", "credits_earned": 0}

# ==================== 3. TONE RECOGNIZER (UPDATED) ====================

@router.post("/communication/generate-listening-tone")
async def generate_listening_tone(current_user: dict = Depends(get_current_user)):
    """Generate a tone recognition challenge."""
    try:
        tones = ["Happy", "Angry", "Sarcastic", "Sad", "Worried", "Excited", "Bored", "Formal", "Surprised"]
        correct_tone = random.choice(tones)
        
        system_prompt = "You are an English teacher focus on emotional intelligence and tone."
        prompt = f"""Generate a short sentence (10-15 words) that a speaker would say with a '{correct_tone}' tone.
        The words should reflect the emotion without explicitly naming it.
        
        Return ONLY valid JSON:
        {{
            "voice_text": "The sentence here",
            "correct_tone": "{correct_tone}",
            "options": {json.dumps(random.sample(tones, 4) if correct_tone in random.sample(tones, 4) else random.sample(tones, 3) + [correct_tone])},
            "difficulty": "medium"
        }}"""
        
        json_str = await AIService.call_kimi(prompt, system_prompt, json_mode=True)
        data = json.loads(json_str)
        # Ensure options are unique and shuffled
        opts = list(set(data["options"]))
        if data["correct_tone"] not in opts: opts[0] = data["correct_tone"]
        random.shuffle(opts)
        data["options"] = opts
        data["id"] = f"tone-{random.randint(100,999)}"
        return data
    except Exception as e:
        logger.error(e)
        return {
            "id": "t1",
            "voice_text": "Oh, another wonderful day of doing chores. I am so thrilled.",
            "correct_tone": "Sarcastic",
            "options": ["Sarcastic", "Happy", "Angry", "Sad"]
        }

@router.post("/communication/evaluate-listening-tone")
async def evaluate_listening_tone(data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Evaluate tone recognition selection."""
    try:
        selected = data.get("selected_tone")
        correct = data.get("correct_tone")
        is_correct = (selected == correct)
        
        system_prompt = "You are a professional English tutor."
        prompt = f"""Student identified the tone as '{selected}'. It was actually '{correct}'.
        Explain briefly why it was '{correct}' and its Tamil translation.
        Return ONLY JSON:
        {{
            "feedback": "English explanation",
            "tamil_feedback": "Tamil explanation"
        }}"""
        
        ai_json = await AIService.call_kimi(prompt, system_prompt, json_mode=True)
        ai_feedback = json.loads(ai_json) if ai_json else {"feedback": "Good attempt.", "tamil_feedback": "நல்ல முயற்சி."}
        
        credits = 10 if is_correct else 0
        if is_correct:
            await update_user_credits(str(current_user["_id"]), credits, "listening_tone", "Correctly identified tone")
            
        return {
            "is_correct": is_correct,
            "credits_earned": credits,
            "feedback": ai_feedback.get("feedback"),
            "tamil_feedback": ai_feedback.get("tamil_feedback")
        }
    except Exception as e:
        return {"is_correct": False, "feedback": "Evaluation error"}
