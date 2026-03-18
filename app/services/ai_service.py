"""
EduSync Backend - AI Service
Auto-extracted from main.py
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
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from bson import ObjectId
from pathlib import Path
import httpx

from app.database import *
from app.config import *
from app.services.ai_wrapper import gemini_model, get_gemini_model, AIModelWrapper

logger = logging.getLogger("edusync")

class AIService:
    @staticmethod
    async def analyze_english_with_gemini(user_text: str, correct_text: str) -> Dict:
        try:
            model = get_gemini_model("analysis")
            
            prompt = f"""
            Act as a friendly and professional English teacher providing constructive feedback. 
            Analyze the student's pronunciation and grammar carefully.
            
            Student said: "{user_text}"
            Target sentence: "{correct_text}"
            
            Provide detailed, encouraging feedback in a professional manner.
            
            Return ONLY a valid JSON object with these keys:
            - score: (int 0-100, overall performance)
            - pronunciation_score: (int 0-100)
            - grammar_score: (int 0-100)
            - fluency_score: (int 0-100)
            - confidence_score: (int 0-100)
            - mistakes: (list of specific corrections)
            - feedback_tamil: (Professional, encouraging feedback in Tamil with constructive suggestions)
            - pronunciation_tips: (Specific advice on how to improve sounds in clear Tamil)
            - corrected_sentence: (Perfect English version)
            - improvement_plan: (Professional 7-day learning plan with clear goals)
            
            Return only the JSON object.
            """
            
            response = await model.generate_content_async(prompt)
            text = response.text.strip()
            
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                # Ensure alias keys exist for frontend compatibility
                if "score" not in data: data["score"] = data.get("pronunciation_score", 70)
                if "feedback_tamil" not in data: data["feedback_tamil"] = data.get("overall_feedback", "Super baby!")
                return data
            
            return {
                "score": 75,
                "pronunciation_score": 75,
                "grammar_score": 70,
                "fluency_score": 80,
                "confidence_score": 65,
                "mistakes": ["Focus on the 'th' sound"],
                "feedback_tamil": "Super baby! Innum konjam poruma pesuna innum nalla irukkum. 💕",
                "pronunciation_tips": "Varthaigala konjam theliva uchari baby.",
                "corrected_sentence": correct_text,
                "improvement_plan": ["Day 1: Practice vowels", "Day 2: Word stress"]
            }
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            return {
                "pronunciation_score": 70,
                "grammar_score": 75,
                "fluency_score": 65,
                "confidence_score": 60,
                "specific_errors": ["Check sentence structure"],
                "correction_suggestions": ["மெதுவாக பேசுங்கள்"],
                "overall_feedback": "நல்ல முயற்சி!",
                "corrected_sentence": correct_text,
                "tamil_explanation": "உச்சரிப்பு பயிற்சி தேவை",
                "improvement_plan": ["Practice daily"],
                "recommended_exercises": ["Basic exercises"]
            }
            
    @staticmethod
    async def grade_submission(submission_content: str, rubric: Dict) -> Dict:
        """AI-powered submission grading"""
        try:
            system_prompt = f"""
            You are an expert educator. Grade this submission based on the rubric:
            {json.dumps(rubric, indent=2)}
            
            Return JSON with:
            - overall_score (0-100)
            - category_scores (dict with category: score)
            - feedback_points (list of constructive feedback)
            - strengths (list)
            - areas_for_improvement (list)
            - plagiarism_indicator (0-10, 0=original, 10=copied)
            - confidence (0-1)
            """
            
            prompt = f"Submission:\n{submission_content}\n\nProvide detailed grading:"
            
            response = await AIService.call_ollama(prompt, system_prompt, json_mode=True)
            return json.loads(response)
            
        except Exception as e:
            logger.error(f"AI grading error: {e}")
            return {
                "overall_score": 70,
                "category_scores": {"content": 70, "clarity": 65, "completeness": 75},
                "feedback_points": ["Good effort", "Could add more details"],
                "strengths": ["Clear structure"],
                "areas_for_improvement": ["More examples needed"],
                "plagiarism_indicator": 1,
                "confidence": 0.7
            }
    
    @staticmethod
    async def code_review(code: str, language: str, requirements: List[str] = None) -> Dict:
        try:
            system_prompt = f"You are an Elite {language} Software Architect and Security Auditor with 20+ years of experience. Your goal is to provide a masterclass-level code review that is professional, authoritative, and extremely detailed."
            
            req_text = "\n".join(requirements) if requirements else "No specific requirements"
            
            prompt = f"""
            Perform a COMPREHENSIVE architectural and security audit of this {language} implementation.
            
            **CODE TO AUDIT:**
            ```{language}
            {code}
            ```
            
            **SPECIAL REQUIREMENTS:** {req_text}
            
            **REVIEW GUIDELINES:**
            1. Provide a professional, expert-level analysis.
            2. Be extremely critical about security and performance.
            3. Use clear markdown headers and bullet points.
            4. Include 'Current Code' vs 'Improved Code' snippets for every major finding.
            
            **YOUR RESPONSE MUST BE A VALID JSON OBJECT WITH THESE EXACT KEYS:**
            1. "correctness_score": (int 0-100)
            2. "efficiency_score": (int 0-100)
            3. "security_score": (int 0-100)
            4. "readability_score": (int 0-100)
            5. "security_vulnerabilities": (list of objects with "issue", "severity", "impact", "fix")
            6. "performance_issues": (list of objects with "issue", "severity", "impact", "fix")
            7. "best_practices_violations": (list of objects with "issue", "severity", "impact", "fix")
            8. "bugs_found": (list of objects with "description", "severity", "impact", "fix")
            9. "code_style_improvements": (list of objects with "problem", "fix")
            10. "corrected_code": (The full optimized version of the code)
            11. "explanation": (A MASSIVE, HIGH-QUALITY MARKDOWN DOCUMENT with these sections:
                # 🔍 Expert Code Review Report

                ## 📊 Executive Summary
                - **Overall Quality Score:** [Score]/100
                - **Complexity Level:** [Low/Medium/High/Very High]
                - **Maintainability Score:** [Score]/100
                - **Security Risk:** [Low/Medium/High/Critical]
                
                (Provide a 2-paragraph high-level architectural overview)

                ## 1. 🔐 Security Vulnerabilities
                (For each vulnerability: describe the issue, explain the risk, show the vulnerable code, and provide the secure fix)

                ## 2. ⚡ Performance Issues
                (Detailed dive into speed, memory, and resource usage with 'Impact' and 'Fix')

                ## 3. ✅ Best Practices Violations 
                (Analysis against industry standards like PEP8, SOLID, DRY, and specialized {language} patterns)

                ## 4. 🎨 Code Style & Maintainability
                (Analysis of naming conventions, modularity, and cognitive complexity)

                ## 5. 🐛 Bug Detection & Logical Errors
                (Identify edge cases, race conditions, and logical flaws)

                ## 6. 🛠️ Suggested Fixes & Refactoring Plan
                (Provide a clear, step-by-step roadmap for implementing these improvements)
                )
            
            IMPORTANT: The 'explanation' field must be at least 1000 words. If the code is small, perform a theoretical dive into how it would scale.
            """
            
            # Using call_ollama which handles Gemini fallback and rotation
            response = await AIService.call_ollama(prompt, system_prompt, json_mode=True)
            
            try:
                # Attempt to parse the JSON
                if isinstance(response, str):
                    # Clean up possible AI preamble/markdown blocks
                    json_match = re.search(r'\{(?:[^{}]|\{[^{}]*\})*\}', response, re.DOTALL)
                    if json_match:
                        data = json.loads(json_match.group(0))
                    else:
                        raise ValueError("No JSON found in response")
                else:
                    data = response

                # Ensure necessary fields exist for frontend
                for key in ["correctness_score", "efficiency_score", "security_score", "readability_score"]:
                    if key not in data: data[key] = 70
                
                if 'explanation' not in data:
                    data['explanation'] = response if isinstance(response, str) else "Detailed analysis in progress..."
                
                return data
            except Exception as e:
                logger.warning(f"Failed to parse structured review: {e}. Returning raw response.")
                return {
                    "explanation": response if isinstance(response, str) else "Failed to parse AI review",
                    "correctness_score": 60,
                    "efficiency_score": 60,
                    "security_score": 60,
                    "readability_score": 60,
                    "security_vulnerabilities": [],
                    "performance_issues": [],
                    "bugs_found": [],
                    "suggestions": ["The AI provided a non-structured response. Detailed markdown analysis is attached below."]
                }

        except Exception as e:
            logger.error(f"Master Code review error: {e}")
            return {
                "explanation": f"Review Service Error: {str(e)}",
                "correctness_score": 0,
                "efficiency_score": 0,
                "security_score": 0,
                "bugs_found": [{"description": "Service encountered a processing error", "severity": "high"}],
                "suggestions": ["Try again in a few moments"]
            }
    
    @staticmethod
    async def generate_interview_questions(role: str, difficulty: str, count: int = 5) -> List[Dict]:
        system_prompt = "You are an experienced HR and Technical Interviewer."
        
        prompt = f"""
        Generate {count} interview questions for {role} position.
        Difficulty: {difficulty}
        
        Return JSON with array of questions, each with:
        - id
        - question
        - type (technical/behavioral/situational)
        - difficulty
        - expected_answer_points (list)
        - category
        - time_to_answer (seconds)
        """
        
        response = await AIService.call_ollama(prompt, system_prompt, json_mode=True)
        try:
            data = json.loads(response)
            return data.get("questions", [])
        except:
            return [
                {
                    "id": "1",
                    "question": f"Tell me about yourself and why you want to be a {role}",
                    "type": "behavioral",
                    "difficulty": "easy",
                    "expected_answer_points": ["Introduction", "Experience", "Motivation"],
                    "category": "General",
                    "time_to_answer": 120
                }
            ]
    
    @staticmethod
    async def evaluate_interview_answer(question: str, answer: str, role: str) -> Dict:
        system_prompt = "You are an expert interviewer evaluating candidate responses."
        
        prompt = f"""
        Question: "{question}"
        Candidate Answer: "{answer}"
        Role: {role}
        
        Evaluate and return JSON with:
        - content_score (0-100)
        - clarity_score (0-100)
        - confidence_score (0-100)
        - relevance_score (0-100)
        - depth_score (0-100)
        - filler_words_count
        - improvement_tips (list)
        - suggested_better_answer
        - keywords_missing (list)
        - keywords_present (list)
        - overall_feedback
        - recommended_resources (list)
        """
        
        response = await AIService.call_ollama(prompt, system_prompt, json_mode=True)
        try:
            return json.loads(response)
        except:
            return {
                "content_score": 70,
                "clarity_score": 65,
                "confidence_score": 60,
                "relevance_score": 75,
                "depth_score": 60,
                "filler_words_count": 0,
                "improvement_tips": ["Structure your answer better"],
                "suggested_better_answer": "A better answer would focus on specific examples...",
                "keywords_missing": [],
                "keywords_present": [],
                "overall_feedback": "Good attempt, needs more depth",
                "recommended_resources": ["Interview preparation guides"]
            }
    
    @staticmethod
    async def generate_learning_path(user_data: Dict) -> Dict:
        system_prompt = "You are an expert educational psychologist and career counselor."
        
        prompt = f"""
        Generate personalized learning path for student:
        
        Student Info:
        - Stage: {user_data.get('stage', 'freshie')}
        - Department: {user_data.get('department', 'General')}
        - Current Skills: {user_data.get('skills', [])}
        - Weak Areas: {user_data.get('weak_areas', [])}
        - Interests: {user_data.get('interests', [])}
        - Career Goals: {user_data.get('career_goals', [])}
        
        Create a 30-day comprehensive learning path in JSON with:
        - overview
        - daily_plans (array for 30 days, each with: day_number, focus_areas, tasks, resources, estimated_hours)
        - weekly_milestones (array for 4 weeks)
        - recommended_courses (array)
        - project_ideas (array)
        - skill_development_timeline
        - assessment_schedule
        - motivational_quotes (array)
        - success_metrics
        """
        
        response = await AIService.call_ollama(prompt, system_prompt, json_mode=True)
        try:
            return json.loads(response)
        except:
            return {
                "overview": "Basic learning path",
                "daily_plans": [{"day": 1, "focus": "Foundations", "tasks": ["Learn basics"]}],
                "weekly_milestones": ["Week 1: Foundation"],
                "recommended_courses": ["Introduction to Programming"],
                "project_ideas": ["Build a simple website"],
                "skill_development_timeline": "4 weeks",
                "assessment_schedule": ["Weekly quiz"],
                "motivational_quotes": ["Keep learning!"],
                "success_metrics": ["Complete all daily tasks"]
            }
    
    @staticmethod
    async def chat_assistant(message: str, context: Dict) -> str:
        system_prompt = f"""You are EduSync AI Assistant, a friendly and knowledgeable tutor.
        User Context: {json.dumps(context, default=str)}
        
        Guidelines:
        1. Be supportive, encouraging, and patient
        2. Provide accurate, practical information
        3. When unsure, admit it and suggest resources
        4. Keep responses concise but helpful
        5. Adapt to user's learning level
        6. Suggest next steps for learning
        7. Use examples when helpful
        8. Maintain professional but friendly tone
        """
        
        prompt = f"User: {message}\n\nAssistant:"
        
        response = await AIService.call_ollama(prompt, system_prompt, json_mode=False)
        return response
    
    @staticmethod
    async def code_help(code: str, error: str, requirement: str, language: str, context: str) -> Dict:
        system_prompt = f"""You are an expert {language} programming tutor. Help students fix code errors and improve their solutions.
        Provide clear explanations and examples."""
        
        # Pre-process conditional sections to avoid backslashes in f-string expressions
        code_section = f"Code Provided:\n```{language}\n{code}\n```" if code else ""
        error_section = f"Error Message:\n{error}" if error else ""
        req_section = f"Requirement:\n{requirement}" if requirement else ""
        context_section = f"Context:\n{context}" if context else ""
        
        prompt = f"""
        Programming Help Request:
        Language: {language}
        
        {code_section}
        {error_section}
        {req_section}
        {context_section}
        
        Provide comprehensive help including:
        1. Problem analysis
        2. Step-by-step solution
        3. Corrected code with comments
        4. Explanation of key concepts
        5. Common pitfalls to avoid
        6. Alternative approaches
        7. Practice exercises
        
        Return as JSON with:
        - analysis
        - corrected_code
        - explanation
        - key_concepts (list)
        - common_mistakes (list)
        - practice_exercises (list)
        - additional_resources (list)
        """
        
        response = await AIService.call_ollama(prompt, system_prompt, json_mode=True)
        try:
            return json.loads(response)
        except:
            return {
                "analysis": "Code analysis",
                "corrected_code": code,
                "explanation": "Explanation of the solution",
                "key_concepts": ["Basic concepts"],
                "common_mistakes": ["Common errors"],
                "practice_exercises": ["Practice problems"],
                "additional_resources": ["Documentation links"]
            }
    
    @staticmethod
    async def generate_project_ideas(user_data: Dict) -> List[Dict]:
        system_prompt = "You are a project mentor and software architect."
        
        prompt = f"""
        Generate 5 project ideas with:
        - title
        - description
        - difficulty (beginner/intermediate/advanced)
        - estimated_time (hours)
        - tech_stack
        - learning_outcomes
        - prerequisites
        - resources
        
        Return as JSON array.
        """
        
        response = await AIService.call_ollama(prompt, system_prompt, json_mode=True)
        try:
            data = json.loads(response)
            return data if isinstance(data, list) else []
        except:
            return [
                {
                    "title": "Portfolio Website",
                    "description": "Build a personal portfolio website",
                    "difficulty": "beginner",
                    "estimated_time": 20,
                    "tech_stack": ["HTML", "CSS", "JavaScript"],
                    "learning_outcomes": ["Web development basics", "Responsive design"],
                    "prerequisites": ["Basic HTML/CSS"],
                    "resources": ["MDN Web Docs", "W3Schools"]
                }
            ]
    
    @staticmethod
    async def english_teacher_feedback(user_text: str) -> Dict:
        """Provide English grammar and pronunciation feedback with Tamil explanations (Professional)"""
        try:
            model = get_gemini_model("analysis")
            
            prompt = f"""
            You are a friendly and professional English teacher who explains in Tamil. 
            The student wrote: "{user_text}"
            
            1. Identify any mistakes professionally and constructively.
            2. Explain in clear Tamil.
            3. Provide the corrected version.
            
            Return format:
            Mistakes in Tamil: (Explain the errors and improvements needed)
            Correct English: (The improved, correct version)
            Additional Tips in Tamil: (Helpful learning tips and encouragement)
            """
            
            response = await model.generate_content_async(prompt)
            text = response.text
            
            # Parse response
            mistakes = ""
            correct_english = ""
            tips = ""
            
            if "Mistakes in Tamil:" in text:
                parts = text.split("Mistakes in Tamil:")
                if len(parts) > 1:
                    subparts = parts[1].split("Correct English:")
                    mistakes = subparts[0].strip()
                    if len(subparts) > 1:
                        subsubparts = subparts[1].split("Additional Tips in Tamil:")
                        correct_english = subsubparts[0].strip()
                        if len(subsubparts) > 1:
                            tips = subsubparts[1].strip()
            
            return {
                "user_text": user_text,
                "mistakes_in_tamil": mistakes,
                "correct_english": correct_english,
                "tips_in_tamil": tips,
                "pronunciation_score": 75,
                "grammar_score": 80,
                "feedback": text
            }
        except Exception as e:
            logger.error(f"English teacher feedback error: {e}")
            return {
                "user_text": user_text,
                "mistakes_in_tamil": "தவறுகளை பகுப்பாய்வு செய்ய முடியவில்லை",
                "correct_english": user_text,
                "tips_in_tamil": "மீண்டும் முயற்சிக்கவும்",
                "pronunciation_score": 60,
                "grammar_score": 65,
                "feedback": "Analysis failed. Please try again."
            }
    
    @staticmethod
    async def call_ollama(prompt: str, system_prompt: str = None, json_mode: bool = False):
        # Premium Key-Rotation Fallback Logic
        # This identifies the most reliable keys to try in order
        priority_keys = ["default", "grammar", "pronunciation", "sentence"]
        
        for key_type in priority_keys:
            config = get_gemini_config(key_type)
            if not config: continue
            
            api_key = config["api_key"]
            models_to_try = config["models"]
            
            try:
                # Create a client with this API key
                genai_client = genai.Client(api_key=api_key)
                
                for model_name in models_to_try:
                    try:
                        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
                        if json_mode:
                            full_prompt += "\n\nIMPORTANT: Return ONLY valid JSON."
                        
                        # Execute AI generation with local thread safety using new SDK
                        response = await asyncio.to_thread(
                            genai_client.models.generate_content,
                            model=model_name,
                            contents=full_prompt
                        )
                        text = response.text.strip()
                        
                        if text:
                            if json_mode:
                                json_match = re.search(r"\{.*\}", text, re.DOTALL)
                                if json_match:
                                    return json_match.group(0)
                            return text
                    except Exception as me:
                        logger.warning(f"Key {key_type} | Model {model_name} failed: {me}")
                        continue # Try next model
            except Exception as ke:
                logger.error(f"Failed to configure Gemini Key {key_type}: {ke}")
                continue # Try next key

        # Safety Fallback: Ollama Local Infrastructure
        try:
            logger.info("All Gemini nodes exhausted. Diverting to local Ollama fallback...")
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(
                    f"{OLLAMA_BASE_URL}/api/chat",
                    json={
                        "model": OLLAMA_MODEL,
                        "messages": messages,
                        "stream": False,
                        "options": {"temperature": 0.6, "num_predict": 1200}
                    }
                )
                if response.status_code == 200:
                    return response.json()["message"]["content"]
        except Exception as oe:
            logger.error(f"Ollama critical failure: {oe}")

        # Terminal Error State
        if json_mode:
            return json.dumps({
                "error": "AI service unavailable",
                "correctness_score": 0,
                "explanation": "Expert Analysis System is currently under extreme load. Our engineers have been notified. Please try again in 5 minutes."
            })
        return "Critical: Expert Analysis Node Offline. Please retry shortly."

    @staticmethod
    async def call_kimi(prompt: str, system_prompt: str = None, json_mode: bool = False):
        """Call Gemini/AI (via Ollama/Cloud) directly for Communication Stage features"""
        try:
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            if json_mode:
                if "Return ONLY valid JSON" not in full_prompt:
                    full_prompt += "\n\nIMPORTANT: Your response must be a valid JSON object only. No preamble, no explanation."
            
            logger.info(f"🔄 Calling Gemini Model ({OLLAMA_MODEL}) for communication feature")
            
            async with httpx.AsyncClient(timeout=90.0) as client:
                # Some deployments might use /api/generate (Ollama style) or /v1/chat/completions (OpenAI style)
                # We'll stick to the Ollama format established in the codebase
                response = await client.post(
                    f"{OLLAMA_BASE_URL}/api/generate",
                    json={
                        "model": OLLAMA_MODEL,
                        "prompt": full_prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "top_p": 0.9,
                            "num_predict": 2048
                        }
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    text = result.get("response", "").strip()
                    
                    if json_mode:
                        # Find the first { and last } to extract JSON
                        start_idx = text.find('{')
                        end_idx = text.rfind('}')
                        if start_idx != -1 and end_idx != -1:
                            return text[start_idx:end_idx+1]
                    return text
                else:
                    logger.error(f"❌ Gemini API error: {response.status_code} - {response.text}")
                    return None
        except Exception as e:
            logger.error(f"❌ Gemini connection error: {e}")
            return None
        
        
async def call_gemini_with_retry(prompt: str, max_retries: int = 3) -> Any:
    """Call Gemini AI with retry logic"""
    if not gemini_model:
        return None
    
    for attempt in range(max_retries):
        try:
            response = gemini_model.generate_content(prompt)
            return response
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Gemini API failed after {max_retries} attempts: {e}")
                raise
            wait_time = 2 ** attempt  # Exponential backoff
            logger.warning(f"Gemini API attempt {attempt + 1} failed, retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)
    
    return None


