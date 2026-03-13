"""
EduSync Backend - Report Helpers
Helper functions for report generation and analytics.
"""
import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from bson import ObjectId

from app.database import *
from app.config import *
from app.models.auth import UserType
from app.utils.common import convert_objectid_to_str

logger = logging.getLogger("edusync")


async def get_faculty_by_designation(department: str):
    """Get faculty count by designation"""
    pipeline = [
        {"$match": {
            "department": department,
            "user_type": {"$in": [UserType.FACULTY.value, UserType.HOD.value]}
        }},
        {"$group": {
            "_id": "$designation",
            "count": {"$sum": 1},
            "avg_experience": {"$avg": "$experience_years"}
        }}
    ]
    
    result = list(await users_collection.aggregate(pipeline).to_list(10))
    return {item["_id"]: {"count": item["count"], "avg_experience": item["avg_experience"]} for item in result}

async def analyze_faculty_workload(department: str):
    """Analyze faculty workload distribution"""
    # This would analyze classes, assignments, research, etc.
    # For demo, return simulated data
    return {
        "teaching_load": random.randint(60, 90),
        "research_load": random.randint(10, 30),
        "administrative_load": random.randint(5, 20),
        "balanced_workload_faculty": random.randint(60, 80),
        "overloaded_faculty": random.randint(10, 25),
        "recommendations": "Consider redistributing teaching assignments"
    }

async def calculate_academic_improvement(department: str):
    """Calculate academic improvement trends"""
    # Simulated improvement data
    return {
        "overall_improvement": random.uniform(2.0, 10.0),
        "improvement_by_year": {
            1: random.uniform(3.0, 12.0),
            2: random.uniform(2.5, 10.0),
            3: random.uniform(2.0, 8.0),
            4: random.uniform(1.5, 6.0)
        },
        "most_improved_subjects": ["Mathematics", "Programming", "Database Systems"],
        "areas_needing_attention": ["Communication Skills", "Advanced Algorithms"]
    }

async def analyze_weak_areas(department: str):
    """Analyze weak areas in student performance"""
    # Simulated weak areas analysis
    return {
        "common_weak_areas": [
            {"subject": "Advanced Mathematics", "students_affected": random.randint(20, 40)},
            {"subject": "Data Structures", "students_affected": random.randint(15, 30)},
            {"subject": "Software Engineering", "students_affected": random.randint(10, 25)}
        ],
        "remediation_effectiveness": random.randint(60, 85),
        "suggested_interventions": [
            "Additional tutorial sessions",
            "Peer mentoring programs",
            "Online learning resources"
        ]
    }

async def analyze_student_attendance_patterns(department: str):
    """Analyze student attendance patterns"""
    # Simulated attendance patterns
    return {
        "regular_attenders": random.randint(60, 85),
        "irregular_attenders": random.randint(10, 25),
        "chronic_absentees": random.randint(2, 8),
        "peak_absent_days": ["Monday", "Friday"],
        "common_reasons_for_absence": ["Health issues", "Transport problems", "Personal reasons"],
        "attendance_correlation_with_performance": random.uniform(0.6, 0.9)
    }

def calculate_resource_age_days(purchase_date: Optional[str]):
    """Calculate age of resource in days"""
    if not purchase_date:
        return 365  # Default 1 year
    
    try:
        purchase = datetime.fromisoformat(purchase_date.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        return (now - purchase).days
    except:
        return 365

async def get_placement_support_activities(department: str):
    """Get placement support activities"""
    # Simulated placement activities
    activities = [
        {"activity": "Resume Building Workshop", "participants": random.randint(50, 150), "effectiveness": "High"},
        {"activity": "Mock Interviews", "participants": random.randint(30, 100), "effectiveness": "Very High"},
        {"activity": "Soft Skills Training", "participants": random.randint(40, 120), "effectiveness": "Medium"},
        {"activity": "Technical Aptitude Tests", "participants": random.randint(60, 180), "effectiveness": "High"},
        {"activity": "Industry Expert Sessions", "participants": random.randint(20, 80), "effectiveness": "Medium"}
    ]
    return activities

async def analyze_research_collaborations(department: str):
    """Analyze research collaborations"""
    # Simulated collaboration data
    return {
        "industry_collaborations": random.randint(3, 10),
        "international_collaborations": random.randint(1, 5),
        "interdisciplinary_collaborations": random.randint(5, 15),
        "collaboration_types": {
            "joint_research": random.randint(2, 8),
            "student_exchange": random.randint(1, 4),
            "conference_organization": random.randint(1, 3),
            "publication_collaboration": random.randint(3, 12)
        }
    }

async def get_student_research_participation(department: str):
    """Get student research participation data"""
    # Simulated student research data
    return {
        "ug_students_in_research": random.randint(10, 30),
        "pg_students_in_research": random.randint(5, 15),
        "phd_students": random.randint(3, 8),
        "student_publications": random.randint(5, 20),
        "student_conference_presentations": random.randint(10, 25),
        "student_research_awards": random.randint(1, 5)
    }

async def calculate_research_impact(department: str):
    """Calculate research impact metrics"""
    # Simulated research impact
    return {
        "average_citations_per_paper": random.randint(5, 25),
        "h_index_department": random.randint(10, 30),
        "patents_filed": random.randint(1, 8),
        "technology_transfers": random.randint(0, 3),
        "societal_impact_projects": random.randint(2, 7)
    }

async def generate_pdf_report(content: Dict[str, Any], file_path: str):
    """Generate PDF report"""
    # Implement PDF generation using reportlab or other library
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    
    c = canvas.Canvas(file_path, pagesize=letter)
    c.setFont("Helvetica", 12)
    
    # Add title
    c.drawString(100, 750, content["title"])
    c.drawString(100, 730, f"Department: {content['department']}")
    c.drawString(100, 710, f"Generated: {content['generated_at']}")
    
    # Add sections
    y_position = 680
    for section_name, section_data in content["sections"].items():
        c.drawString(100, y_position, f"{section_name.replace('_', ' ').title()}:")
        y_position -= 20
        
        if isinstance(section_data, dict):
            for key, value in section_data.items():
                c.drawString(120, y_position, f"{key}: {value}")
                y_position -= 20
        elif isinstance(section_data, list):
            for item in section_data:
                c.drawString(120, y_position, f"- {item}")
                y_position -= 20
        
        y_position -= 10
    
    c.save()

async def generate_excel_report(content: Dict[str, Any], file_path: str):
    """Generate Excel report"""
    # Implement Excel generation using openpyxl or pandas
    import pandas as pd
    
    # Create DataFrame from content
    data = []
    for section_name, section_data in content["sections"].items():
        if isinstance(section_data, dict):
            for key, value in section_data.items():
                data.append({
                    "Section": section_name,
                    "Metric": key,
                    "Value": value
                })
    
    df = pd.DataFrame(data)
    df.to_excel(file_path, index=False)

async def generate_csv_report(content: Dict[str, Any], file_path: str):
    """Generate CSV report"""
    import pandas as pd
    
    # Create DataFrame from content
    data = []
    for section_name, section_data in content["sections"].items():
        if isinstance(section_data, dict):
            for key, value in section_data.items():
                data.append({
                    "Section": section_name,
                    "Metric": key,
                    "Value": value
                })
    
    df = pd.DataFrame(data)
    df.to_csv(file_path, index=False)


def calculate_utilization_rate(total_reports: int, period: str) -> float:
    """
    Calculate report utilization rate based on period.
    Returns a percentage value (0-100).
    """
    try:
        # Define expected report counts per period
        expected_counts = {
            "week": 5,      # ~5 reports per week expected
            "month": 20,    # ~20 reports per month expected
            "quarter": 60,  # ~60 reports per quarter expected
            "year": 240     # ~240 reports per year expected
        }
        
        # Get expected count for the period
        expected = expected_counts.get(period, 20)  # Default to month if not found
        
        if expected == 0:
            return 0.0
        
        # Calculate utilization rate (capped at 100%)
        utilization = (total_reports / expected) * 100
        
        # Cap at 100%
        return min(100.0, round(utilization, 1))
        
    except Exception as e:
        logger.error(f"Calculate utilization rate error: {e}")
        return 0.0


async def get_report_templates_stats(department: str):
    """Get report templates statistics"""
    pipeline = [
        {"$match": {"department": department}},
        {"$group": {
            "_id": "$type",
            "count": {"$sum": 1},
            "active": {"$sum": {"$cond": [{"$eq": ["$is_active", True]}, 1, 0]}}
        }}
    ]
    
    result = list(await report_templates_collection.aggregate(pipeline).to_list(10))
    return result

async def get_scheduled_reports_stats(department: str):
    """Get scheduled reports statistics"""
    pipeline = [
        {"$match": {"department": department}},
        {"$group": {
            "_id": "$frequency",
            "count": {"$sum": 1},
            "active": {"$sum": {"$cond": [{"$eq": ["$is_active", True]}, 1, 0]}}
        }}
    ]
    
    result = list(await scheduled_reports_collection.aggregate(pipeline).to_list(10))
    return result


async def get_reports_by_type(department: str):
    """Get reports count by type"""
    pipeline = [
        {"$match": {"department": department}},
        {"$group": {
            "_id": "$type",
            "count": {"$sum": 1},
            "last_generated": {"$max": "$generated_at"}
        }}
    ]
    
    result = list(await reports_collection.aggregate(pipeline).to_list(10))
    return result

async def get_reports_by_status(department: str):
    """Get reports count by status"""
    pipeline = [
        {"$match": {"department": department}},
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1}
        }}
    ]
    
    result = list(await reports_collection.aggregate(pipeline).to_list(10))
    return {item["_id"]: item["count"] for item in result}

async def get_recently_generated(department: str, limit: int = 5):
    """Get recently generated reports"""
    from app.models.report import ReportStatus
    reports = await reports_collection.find({
        "department": department,
        "status": ReportStatus.GENERATED.value
    }).sort("generated_at", -1).limit(limit).to_list(limit)
    
    return convert_objectid_to_str(reports)


async def get_reports_trend(department: str, period: str):
    """Get reports generation trend"""
    now = datetime.now(timezone.utc)
    
    if period == "week":
        days = 7
        format_str = "%Y-%m-%d"
    elif period == "month":
        days = 30
        format_str = "%Y-%m-%d"
    elif period == "quarter":
        days = 90
        format_str = "%Y-%m-%d"
    elif period == "year":
        days = 365
        format_str = "%Y-%m"
    else:
        days = 30
        format_str = "%Y-%m-%d"
    
    pipeline = [
        {"$match": {
            "department": department,
            "generated_at": {"$gte": now - timedelta(days=days)}
        }},
        {"$group": {
            "_id": {"$dateToString": {"format": format_str, "date": "$generated_at"}},
            "count": {"$sum": 1},
            "successful": {"$sum": {"$cond": [{"$eq": ["$status", "generated"]}, 1, 0]}}
        }},
        {"$sort": {"_id": 1}}
    ]
    
    result = list(await reports_collection.aggregate(pipeline).to_list(100))
    return result
