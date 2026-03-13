"""
EduSync Backend - Syllabus Processor
Handles PDF syllabus processing and AI-based analysis.
"""
import io
import json
import logging
import re
from datetime import datetime, timezone
from typing import Dict

from bson import ObjectId
from fastapi import HTTPException

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

from app.database import courses_collection
from app.services.ai_wrapper import gemini_model

logger = logging.getLogger("edusync")


class SyllabusProcessor:
    """Process and analyze PDF syllabi using AI."""

    @staticmethod
    async def extract_text_from_pdf(pdf_bytes: bytes) -> str:
        """Extract text from PDF"""
        try:
            if not PyPDF2:
                raise ImportError("PyPDF2 is not installed")
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
            text = ""
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text()
            return text
        except Exception as e:
            logger.error(f"PDF text extraction error: {e}")
            return ""
    
    @staticmethod
    async def analyze_syllabus_with_ai(pdf_text: str, course_code: str, unit_count: int = 5) -> Dict:
        """Use AI to analyze syllabus and extract units"""
        try:
            if not gemini_model:
                raise Exception("Gemini AI not configured")
            
            prompt = f"""
            You are an expert academic syllabus analyzer. Analyze this university syllabus and extract {unit_count} main units.
            
            COURSE: {course_code}
            SYLLABUS TEXT:
            {pdf_text[:3000]}
            
            Extract exactly {unit_count} units with the following structure for EACH unit:
            1. unit_number (1-{unit_count})
            2. title (meaningful unit title)
            3. description (2-3 sentence description)
            4. topics (list of 3-5 main topics covered)
            5. learning_outcomes (list of 2-3 learning outcomes)
            6. references (list of 1-2 recommended references)
            
            Return ONLY valid JSON in this exact format:
            {{
                "units": [
                    {{
                        "unit_number": 1,
                        "title": "Introduction to ...",
                        "description": "...",
                        "topics": ["topic1", "topic2", ...],
                        "learning_outcomes": ["outcome1", "outcome2", ...],
                        "references": ["ref1", "ref2"]
                    }},
                    ...more units
                ]
            }}
            
            If Tamil language content is present in syllabus, keep titles/topics in Tamil.
            """
            
            response = gemini_model.generate_content(prompt)
            text = response.text.strip()
            
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            
            return {
                "units": [
                    {
                        "unit_number": i+1,
                        "title": f"Unit {i+1}",
                        "description": f"Topics covered in Unit {i+1}",
                        "topics": [f"Topic {j+1}" for j in range(3)],
                        "learning_outcomes": [f"Understand basic concepts {i+1}"],
                        "references": ["Textbook references"]
                    }
                    for i in range(unit_count)
                ]
            }
            
        except Exception as e:
            logger.error(f"AI syllabus analysis error: {e}")
            return {
                "units": [
                    {
                        "unit_number": i+1,
                        "title": f"Unit {i+1}",
                        "description": f"Unit {i+1} content from syllabus",
                        "topics": [f"Main topic {i+1}.{j+1}" for j in range(3)],
                        "learning_outcomes": [f"Learning outcome {i+1}"],
                        "references": ["Course textbook"]
                    }
                    for i in range(unit_count)
                ]
            }
    
    @staticmethod
    async def process_pdf_syllabus(pdf_bytes: bytes, course_id: str, unit_count: int = 5) -> Dict:
        """Main function to process PDF syllabus"""
        try:
            course = await courses_collection.find_one({"_id": ObjectId(course_id)})
            if not course:
                raise HTTPException(status_code=404, detail="Course not found")
            
            pdf_text = await SyllabusProcessor.extract_text_from_pdf(pdf_bytes)
            
            if not pdf_text or len(pdf_text.strip()) < 100:
                raise HTTPException(status_code=400, detail="PDF text extraction failed or document is not readable")
            
            analysis = await SyllabusProcessor.analyze_syllabus_with_ai(
                pdf_text, 
                course.get("course_code", "Course"),
                unit_count
            )
            
            return {
                "course_id": course_id,
                "course_code": course.get("course_code"),
                "course_title": course.get("title"),
                "pdf_text_preview": pdf_text[:500] + "..." if len(pdf_text) > 500 else pdf_text,
                "total_pages": len(PyPDF2.PdfReader(io.BytesIO(pdf_bytes)).pages) if PyPDF2 else 0,
                "processed_units": analysis.get("units", []),
                "total_units": len(analysis.get("units", [])),
                "processing_time": datetime.now(timezone.utc)
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"PDF syllabus processing error: {e}")
            raise HTTPException(status_code=500, detail=f"Syllabus processing failed: {str(e)}")
