"""
EduSync Backend - Report Generator
Auto-extracted from main.py
"""
import logging
import random
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from bson import ObjectId

from app.database import *
from app.config import *
from app.models.auth import UserType
from app.services.ai_wrapper import gemini_model, get_gemini_model
from app.utils.report_helpers import (
    get_faculty_by_designation, analyze_faculty_workload,
    calculate_academic_improvement, analyze_weak_areas,
    analyze_student_attendance_patterns, calculate_resource_age_days,
    get_placement_support_activities, analyze_research_collaborations,
    get_student_research_participation, calculate_research_impact,
    generate_pdf_report, generate_excel_report, generate_csv_report
)

logger = logging.getLogger("edusync")

# =============== REPORT GENERATOR FUNCTIONS ===============

async def generate_summary_data(department: str):
    """Generate summary data for department"""
    try:
        # Get department stats
        stats = await calculate_department_stats(department, f"{datetime.now().year}-{datetime.now().year + 1}")
        
        if not stats:
            return None
        
        # Get faculty count
        faculty_count = await users_collection.count_documents({
            "department": department,
            "user_type": {"$in": [UserType.FACULTY.value, UserType.HOD.value]}
        })
        
        # Get student count
        student_count = await users_collection.count_documents({
            "department": department,
            "user_type": UserType.STUDENT.value
        })
        
        # Get active classes
        active_classes = await classrooms_collection.count_documents({
            "department": department,
            "status": "active"
        })
        
        # Get ongoing projects
        ongoing_projects = await projects_collection.count_documents({
            "department": department,
            "status": {"$in": ["in_progress", "planning"]}
        })
        
        # Get recent achievements
        recent_achievements = await notifications_collection.find({
            "notification_type": "achievement",
            "department": department,
            "created_at": {"$gte": datetime.now(timezone.utc) - timedelta(days=30)}
        }).sort("created_at", -1).limit(5).to_list(5)
        
        return {
            "faculty_count": faculty_count,
            "student_count": student_count,
            "active_classes": active_classes,
            "ongoing_projects": ongoing_projects,
            "pass_percentage": stats.get("stats", {}).get("pass_percentage", {}).get("value", 0),
            "placement_rate": stats.get("stats", {}).get("placement", {}).get("value", 0),
            "attendance_rate": stats.get("stats", {}).get("attendance_rate", 0),
            "student_faculty_ratio": stats.get("stats", {}).get("student_faculty_ratio", 0),
            "research_output": stats.get("stats", {}).get("research_output", 0),
            "recent_achievements": recent_achievements,
            "overall_performance": "Excellent" if stats.get("stats", {}).get("pass_percentage", {}).get("value", 0) > 85 else "Good"
        }
    except Exception as e:
        logger.error(f"Generate summary data error: {e}")
        return None

async def generate_faculty_performance_data(department: str):
    """Generate faculty performance data"""
    try:
        # Get all faculty in department
        faculty_list = await users_collection.find({
            "user_type": {"$in": [UserType.FACULTY.value, UserType.HOD.value]},
            "department": department
        }).to_list(50)
        
        faculty_performance = []
        for faculty in faculty_list:
            performance = await get_faculty_stats(str(faculty["_id"]))
            if performance:
                faculty_performance.append(performance)
        
        # Calculate department averages
        if faculty_performance:
            avg_rating = sum(f["avg_rating"] for f in faculty_performance) / len(faculty_performance)
            avg_workload = sum(f["workload_percentage"] for f in faculty_performance) / len(faculty_performance)
            total_research = sum(f["research_papers"] for f in faculty_performance)
        else:
            avg_rating = 0
            avg_workload = 0
            total_research = 0
        
        # Get faculty by performance tier
        high_performers = [f for f in faculty_performance if f["avg_rating"] >= 4.5]
        medium_performers = [f for f in faculty_performance if 3.5 <= f["avg_rating"] < 4.5]
        low_performers = [f for f in faculty_performance if f["avg_rating"] < 3.5]
        
        # Get top 3 performing faculty
        top_faculty = sorted(faculty_performance, key=lambda x: x["avg_rating"], reverse=True)[:3]
        
        return {
            "total_faculty": len(faculty_performance),
            "average_rating": round(avg_rating, 1),
            "average_workload": round(avg_workload, 1),
            "total_research_papers": total_research,
            "performance_distribution": {
                "high_performers": len(high_performers),
                "medium_performers": len(medium_performers),
                "low_performers": len(low_performers)
            },
            "top_performers": top_faculty,
            "faculty_details": faculty_performance[:10],  # Limit for report
            "by_designation": await get_faculty_by_designation(department),
            "workload_analysis": await analyze_faculty_workload(department)
        }
    except Exception as e:
        logger.error(f"Generate faculty performance data error: {e}")
        return None

async def generate_student_performance_data(department: str):
    """Generate student performance data"""
    try:
        # Get all students in department
        students = await users_collection.find({
            "user_type": UserType.STUDENT.value,
            "department": department
        }).to_list(1000)
        
        # This would normally come from exam/assignment submissions
        # For demo, generate simulated data
        
        # Simulate student performance by year
        performance_by_year = {}
        for year in range(1, 6):
            year_students = [s for s in students if s.get("year") == year]
            if year_students:
                # Simulate average scores
                avg_score = random.uniform(65, 90)
                pass_rate = random.uniform(80, 98)
                
                performance_by_year[year] = {
                    "student_count": len(year_students),
                    "average_score": round(avg_score, 1),
                    "pass_percentage": round(pass_rate, 1),
                    "top_performers": random.randint(1, 5),
                    "needs_improvement": random.randint(0, 3)
                }
        
        # Get recent exam results (simulated)
        recent_exams = []
        exam_titles = ["Mid-Term Exam", "Final Exam", "Internal Assessment 1", "Internal Assessment 2"]
        
        for i in range(4):
            recent_exams.append({
                "exam_title": exam_titles[i],
                "subject": f"Subject {i+1}",
                "average_score": random.uniform(65, 85),
                "pass_percentage": random.uniform(75, 95),
                "top_scorer": random.randint(85, 100),
                "date": (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))).isoformat()
            })
        
        # Get student achievements
        student_achievements = await notifications_collection.find({
            "notification_type": "student_achievement",
            "department": department,
            "created_at": {"$gte": datetime.now(timezone.utc) - timedelta(days=90)}
        }).sort("created_at", -1).limit(10).to_list(10)
        
        # Calculate overall statistics
        total_students = len(students)
        overall_avg_score = sum(p["average_score"] for p in performance_by_year.values()) / len(performance_by_year) if performance_by_year else 0
        overall_pass_rate = sum(p["pass_percentage"] for p in performance_by_year.values()) / len(performance_by_year) if performance_by_year else 0
        
        return {
            "total_students": total_students,
            "overall_average_score": round(overall_avg_score, 1),
            "overall_pass_percentage": round(overall_pass_rate, 1),
            "performance_by_year": performance_by_year,
            "recent_exam_results": recent_exams,
            "student_achievements": student_achievements,
            "academic_improvement": await calculate_academic_improvement(department),
            "weak_areas_analysis": await analyze_weak_areas(department)
        }
    except Exception as e:
        logger.error(f"Generate student performance data error: {e}")
        return None

async def generate_attendance_data(department: str):
    """Generate attendance data"""
    try:
        # Get all classes in department
        classes = await classrooms_collection.find({
            "department": department,
            "status": "active"
        }).to_list(100)
        
        total_classes = len(classes)
        attendance_summary = []
        total_present = 0
        total_expected = 0
        
        # Process each class
        for cls in classes:
            class_id = str(cls["_id"])
            
            # Get attendance records for this class (simulated for demo)
            attendance_records = await faculty_attendance_collection.find({
                "classroom_id": class_id
            }).sort("date", -1).limit(10).to_list(10)
            
            class_present = 0
            class_expected = 0
            
            for record in attendance_records:
                stats = record.get("stats", {})
                class_present += stats.get("present", 0)
                class_expected += stats.get("total", 0)
            
            attendance_rate = (class_present / class_expected * 100) if class_expected > 0 else 0
            
            attendance_summary.append({
                "classroom_code": cls.get("code"),
                "classroom_name": cls.get("name"),
                "total_sessions": len(attendance_records),
                "average_attendance": round(attendance_rate, 1),
                "present_count": class_present,
                "expected_count": class_expected
            })
            
            total_present += class_present
            total_expected += class_expected
        
        # Calculate overall attendance
        overall_attendance = (total_present / total_expected * 100) if total_expected > 0 else 0
        
        # Get attendance trends (last 30 days)
        attendance_trend = []
        for i in range(30):
            date = datetime.now(timezone.utc) - timedelta(days=30-i)
            # Simulate daily attendance
            daily_attendance = random.uniform(70, 95)
            attendance_trend.append({
                "date": date.strftime("%Y-%m-%d"),
                "attendance_rate": round(daily_attendance, 1)
            })
        
        # Get classes with low attendance
        low_attendance_classes = [c for c in attendance_summary if c["average_attendance"] < 75]
        
        # Get student attendance patterns
        student_attendance_patterns = await analyze_student_attendance_patterns(department)
        
        return {
            "overall_attendance_rate": round(overall_attendance, 1),
            "total_sessions_tracked": total_classes * 10,  # Approximate
            "attendance_by_class": attendance_summary[:10],  # Top 10 for report
            "attendance_trend": attendance_trend,
            "low_attendance_classes": low_attendance_classes[:5],
            "best_attendance_classes": sorted(attendance_summary, key=lambda x: x["average_attendance"], reverse=True)[:3],
            "student_attendance_patterns": student_attendance_patterns,
            "recommendations": [
                "Implement automated attendance tracking",
                "Address low attendance in specific classes",
                "Introduce attendance incentives"
            ]
        }
    except Exception as e:
        logger.error(f"Generate attendance data error: {e}")
        return None

async def generate_resource_utilization_data(department: str):
    """Generate resource utilization data"""
    try:
        # Get all resources in department
        resources = await resources_collection.find({
            "department": department,
            "status": {"$ne": "archived"}
        }).to_list(100)
        
        resource_summary = []
        total_resources = len(resources)
        in_use_count = 0
        available_count = 0
        maintenance_count = 0
        total_cost = 0
        
        # Process each resource
        for resource in resources:
            status = resource.get("status", "available")
            
            if status == "in-use":
                in_use_count += 1
            elif status == "available":
                available_count += 1
            elif status == "maintenance":
                maintenance_count += 1
            
            if resource.get("purchase_cost"):
                total_cost += resource["purchase_cost"]
            
            # Calculate utilization if available
            usage_count = resource.get("usage_count", 0)
            age_days = calculate_resource_age_days(resource.get("purchase_date"))
            utilization_rate = (usage_count / max(age_days, 1)) * 100 if age_days > 0 else 0
            
            resource_summary.append({
                "name": resource["name"],
                "category": resource.get("category"),
                "status": status,
                "location": resource.get("location"),
                "purchase_cost": resource.get("purchase_cost", 0),
                "usage_count": usage_count,
                "last_used": resource.get("last_used"),
                "utilization_rate": round(min(utilization_rate, 100), 1)
            })
        
        # Calculate overall utilization
        utilization_rate = (in_use_count / total_resources * 100) if total_resources > 0 else 0
        
        # Get resources by category
        resources_by_category = {}
        for resource in resources:
            category = resource.get("category", "other")
            if category not in resources_by_category:
                resources_by_category[category] = 0
            resources_by_category[category] += 1
        
        # Get maintenance status
        maintenance_records = await maintenance_collection.find({
            "department": department,
            "status": {"$in": ["pending", "in_progress"]}
        }).sort("scheduled_date", 1).limit(10).to_list(10)
        
        # Get resource requests
        pending_requests = await resource_requests_collection.count_documents({
            "department": department,
            "status": "pending"
        })
        
        # Calculate cost efficiency
        avg_cost_per_resource = total_cost / total_resources if total_resources > 0 else 0
        
        return {
            "total_resources": total_resources,
            "in_use_count": in_use_count,
            "available_count": available_count,
            "maintenance_count": maintenance_count,
            "overall_utilization_rate": round(utilization_rate, 1),
            "total_investment": total_cost,
            "average_cost_per_resource": round(avg_cost_per_resource, 2),
            "resources_by_category": resources_by_category,
            "top_utilized_resources": sorted(resource_summary, key=lambda x: x["utilization_rate"], reverse=True)[:5],
            "underutilized_resources": [r for r in resource_summary if r["utilization_rate"] < 30][:5],
            "pending_maintenance": len(maintenance_records),
            "pending_resource_requests": pending_requests,
            "recommendations": [
                "Optimize utilization of underutilized resources",
                "Plan maintenance schedules better",
                "Consider resource sharing between departments"
            ]
        }
    except Exception as e:
        logger.error(f"Generate resource utilization data error: {e}")
        return None

async def generate_financial_data(department: str):
    """Generate financial data"""
    try:
        # This would normally come from financial systems
        # For demo, generate simulated data
        
        # Simulate budget allocation
        budget_categories = {
            "Salaries": random.randint(500000, 1000000),
            "Infrastructure": random.randint(200000, 500000),
            "Research": random.randint(100000, 300000),
            "Training": random.randint(50000, 150000),
            "Equipment": random.randint(150000, 400000),
            "Events": random.randint(50000, 100000),
            "Miscellaneous": random.randint(50000, 100000)
        }
        
        total_budget = sum(budget_categories.values())
        
        # Simulate expenses
        expenses_by_category = {}
        for category, budget in budget_categories.items():
            # Expenses are typically 70-95% of budget
            expenses = budget * random.uniform(0.7, 0.95)
            expenses_by_category[category] = round(expenses, 2)
        
        total_expenses = sum(expenses_by_category.values())
        
        # Simulate grants and funding
        grants = [
            {"name": "Research Grant 2024", "amount": random.randint(50000, 200000), "status": "active"},
            {"name": "Infrastructure Grant", "amount": random.randint(100000, 300000), "status": "active"},
            {"name": "Student Scholarship Fund", "amount": random.randint(50000, 150000), "status": "active"}
        ]
        
        total_grants = sum(g["amount"] for g in grants)
        
        # Calculate utilization percentages
        budget_utilization = {}
        for category in budget_categories:
            utilization = (expenses_by_category.get(category, 0) / budget_categories[category]) * 100
            budget_utilization[category] = round(utilization, 1)
        
        overall_utilization = (total_expenses / total_budget) * 100
        
        # Get recent financial transactions (simulated)
        recent_transactions = []
        transaction_types = ["Salary Payment", "Equipment Purchase", "Software License", "Maintenance", "Training", "Event Sponsorship"]
        
        for i in range(10):
            recent_transactions.append({
                "date": (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d"),
                "description": f"{random.choice(transaction_types)} - {i+1}",
                "amount": random.randint(1000, 50000),
                "type": "expense",
                "category": random.choice(list(budget_categories.keys()))
            })
        
        # Get pending approvals with financial impact
        financial_approvals = await approvals_collection.find({
            "department": department,
            "approval_type": {"$in": ["budget_allocation", "resource_request"]},
            "status": "pending"
        }).sort("created_at", -1).limit(5).to_list(5)
        
        # Calculate financial health indicators
        budget_variance = total_expenses - total_budget
        burn_rate = total_expenses / 12  # Monthly burn rate
        
        return {
            "total_budget": total_budget,
            "total_expenses": total_expenses,
            "budget_variance": budget_variance,
            "overall_utilization": round(overall_utilization, 1),
            "budget_by_category": budget_categories,
            "expenses_by_category": expenses_by_category,
            "utilization_by_category": budget_utilization,
            "grants_and_funding": grants,
            "total_grants": total_grants,
            "recent_transactions": recent_transactions,
            "pending_financial_approvals": len(financial_approvals),
            "financial_health": "Good" if overall_utilization < 90 else "Needs Attention",
            "burn_rate": round(burn_rate, 2),
            "recommendations": [
                "Review high-utilization categories",
                "Optimize resource allocation",
                "Explore additional funding opportunities"
            ]
        }
    except Exception as e:
        logger.error(f"Generate financial data error: {e}")
        return None

async def generate_placement_data(department: str):
    """Generate placement data"""
    try:
        # This would normally come from placement records
        # For demo, generate simulated data
        
        # Simulate placement statistics
        placement_stats = {
            "total_students_eligible": random.randint(100, 300),
            "placed_students": random.randint(80, 250),
            "placement_percentage": 0,  # Will be calculated
            "average_salary": random.randint(400000, 800000),
            "highest_salary": random.randint(800000, 1500000),
            "companies_visited": random.randint(20, 50),
            "offers_made": random.randint(100, 300)
        }
        
        placement_stats["placement_percentage"] = round(
            (placement_stats["placed_students"] / placement_stats["total_students_eligible"]) * 100, 
            1
        )
        
        # Simulate placement by company
        companies = ["Infosys", "TCS", "Wipro", "Accenture", "Amazon", "Google", "Microsoft", "IBM", "Cognizant", "Capgemini"]
        placement_by_company = []
        
        for company in companies[:6]:  # Top 6 companies
            placements = random.randint(5, 30)
            avg_salary = random.randint(400000, 700000)
            placement_by_company.append({
                "company": company,
                "placements": placements,
                "average_salary": avg_salary,
                "highest_salary": random.randint(avg_salary + 100000, avg_salary + 500000)
            })
        
        # Simulate placement trend (last 5 years)
        placement_trend = []
        current_year = datetime.now().year
        
        for year in range(current_year - 4, current_year + 1):
            placements = random.randint(60, 120)
            eligible = random.randint(80, 150)
            percentage = round((placements / eligible) * 100, 1)
            avg_salary = random.randint(300000 + (year - (current_year - 4)) * 50000, 
                                       500000 + (year - (current_year - 4)) * 50000)
            
            placement_trend.append({
                "year": year,
                "eligible_students": eligible,
                "placed_students": placements,
                "placement_percentage": percentage,
                "average_salary": avg_salary
            })
        
        # Simulate upcoming placement drives
        upcoming_drives = []
        drive_companies = ["Amazon", "Microsoft", "Google", "Adobe", "Intel"]
        
        for i in range(3):
            drive_date = datetime.now(timezone.utc) + timedelta(days=random.randint(7, 60))
            upcoming_drives.append({
                "company": drive_companies[i],
                "date": drive_date.strftime("%Y-%m-%d"),
                "positions": random.randint(5, 20),
                "eligibility_criteria": "CGPA > 7.5, No backlogs",
                "status": "scheduled"
            })
        
        # Get student achievements in placements
        placement_achievements = await notifications_collection.find({
            "notification_type": "placement",
            "department": department,
            "created_at": {"$gte": datetime.now(timezone.utc) - timedelta(days=180)}
        }).sort("created_at", -1).limit(5).to_list(5)
        
        # Calculate growth metrics
        if len(placement_trend) >= 2:
            growth_rate = ((placement_trend[-1]["placement_percentage"] - placement_trend[-2]["placement_percentage"]) / 
                          placement_trend[-2]["placement_percentage"]) * 100
        else:
            growth_rate = 0
        
        return {
            **placement_stats,
            "placement_by_company": placement_by_company,
            "placement_trend": placement_trend,
            "top_recruiters": sorted(placement_by_company, key=lambda x: x["placements"], reverse=True)[:3],
            "upcoming_drives": upcoming_drives,
            "placement_achievements": placement_achievements,
            "year_over_year_growth": round(growth_rate, 1),
            "placement_support_activities": await get_placement_support_activities(department),
            "recommendations": [
                "Increase industry collaboration",
                "Enhance placement training programs",
                "Diversify recruiter portfolio"
            ]
        }
    except Exception as e:
        logger.error(f"Generate placement data error: {e}")
        return None

async def generate_research_data(department: str):
    """Generate research data"""
    try:
        # Get all faculty in department
        faculty_list = await users_collection.find({
            "user_type": {"$in": [UserType.FACULTY.value, UserType.HOD.value]},
            "department": department
        }).to_list(50)
        
        # Calculate research metrics
        total_publications = 0
        total_grants = 0
        total_projects = 0
        faculty_research = []
        
        for faculty in faculty_list:
            publications = faculty.get("publications", [])
            grants = faculty.get("grants", [])
            projects = faculty.get("research_projects", [])
            
            total_publications += len(publications)
            total_grants += len(grants)
            total_projects += len(projects)
            
            faculty_research.append({
                "faculty_name": faculty["full_name"],
                "publications": len(publications),
                "grants": len(grants),
                "projects": len(projects),
                "h_index": random.randint(5, 20),  # Simulated
                "citations": random.randint(100, 1000)  # Simulated
            })
        
        # Get research publications (simulated details)
        recent_publications = []
        publication_types = ["Journal", "Conference", "Book Chapter", "Patent"]
        
        for i in range(10):
            recent_publications.append({
                "title": f"Research Publication {i+1}",
                "authors": ["Faculty Member 1", "Faculty Member 2", "Student 1"],
                "type": random.choice(publication_types),
                "year": random.randint(2020, 2024),
                "citations": random.randint(0, 50),
                "journal": f"Journal of {department} Sciences",
                "impact_factor": round(random.uniform(2.0, 5.0), 2)
            })
        
        # Get research grants
        research_grants = []
        grant_agencies = ["DST", "UGC", "AICTE", "CSIR", "ICMR", "Industry Collaboration"]
        
        for i in range(6):
            amount = random.randint(500000, 3000000)
            start_date = datetime.now(timezone.utc) - timedelta(days=random.randint(100, 1000))
            end_date = start_date + timedelta(days=random.randint(365, 1095))
            
            research_grants.append({
                "title": f"Research Grant {i+1}",
                "agency": random.choice(grant_agencies),
                "amount": amount,
                "principal_investigator": random.choice([f["full_name"] for f in faculty_list]),
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "status": "ongoing" if end_date > datetime.now(timezone.utc) else "completed"
            })
        
        # Calculate total grant amount
        total_grant_amount = sum(g["amount"] for g in research_grants)
        
        # Get ongoing research projects
        ongoing_projects = await projects_collection.find({
            "department": department,
            "project_type": "research",
            "status": {"$in": ["planning", "in_progress"]}
        }).sort("created_at", -1).limit(5).to_list(5)
        
        # Calculate research productivity
        faculty_count = len(faculty_list)
        publications_per_faculty = total_publications / faculty_count if faculty_count > 0 else 0
        grants_per_faculty = total_grants / faculty_count if faculty_count > 0 else 0
        
        # Get research collaborations
        collaborations = await analyze_research_collaborations(department)
        
        # Get student research participation
        student_research = await get_student_research_participation(department)
        
        return {
            "faculty_count": faculty_count,
            "total_publications": total_publications,
            "total_grants": total_grants,
            "total_grant_amount": total_grant_amount,
            "total_research_projects": total_projects,
            "publications_per_faculty": round(publications_per_faculty, 1),
            "grants_per_faculty": round(grants_per_faculty, 1),
            "faculty_research_performance": sorted(faculty_research, key=lambda x: x["publications"], reverse=True)[:5],
            "recent_publications": recent_publications[:5],
            "research_grants": research_grants,
            "ongoing_research_projects": ongoing_projects,
            "research_collaborations": collaborations,
            "student_research_participation": student_research,
            "research_impact": await calculate_research_impact(department),
            "recommendations": [
                "Increase interdisciplinary research",
                "Enhance industry-academia collaboration",
                "Improve research publication quality"
            ]
        }
    except Exception as e:
        logger.error(f"Generate research data error: {e}")
        return None

