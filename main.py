"""
EduSync Backend v4.0 - Main Application Entry Point
====================================================
AI-Powered Learning Platform - Modular Architecture
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.lifespan import lifespan, create_static_dirs
from app.exceptions import register_exception_handlers

# Ensure static directories exist before mounting
create_static_dirs()

# =============== APP INITIALIZATION ===============
app = FastAPI(
    title="EduSync 4.0 - AI-Powered Learning Platform",
    description="Complete backend for EduSync LMS with AI tutoring, coding challenges, career prep, and more.",
    version="4.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# Exception Handlers
register_exception_handlers(app)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static Files
app.mount("/static", StaticFiles(directory="static"), name="static")

# =============== IMPORT ALL ROUTERS ===============

# Core
from app.routes.health import router as health_router
from app.routes.auth import router as auth_router
from app.routes.users import router as users_router

# Features
from app.routes.challenges import router as challenges_router
from app.routes.compiler import router as compiler_router
from app.routes.ai import router as ai_router
from app.routes.ai_grading import router as ai_grading_router
from app.routes.speech import router as speech_router
from app.routes.groups import router as groups_router
from app.routes.projects import router as projects_router
from app.routes.notifications import router as notifications_router
from app.routes.jobs import router as jobs_router
from app.routes.submissions import router as submissions_router
from app.routes.badges import router as badges_router
from app.routes.leaderboard import router as leaderboard_router
from app.routes.learning_paths import router as learning_paths_router
from app.routes.forum import router as forum_router
from app.routes.announcements import router as announcements_router
from app.routes.study_materials import router as study_materials_router
from app.routes.classrooms import router as classrooms_router
from app.routes.repositories import router as repositories_router
from app.routes.pair_programming import router as pair_programming_router
from app.routes.docs import router as docs_router
from app.routes.credits import router as credits_router
from app.routes.language_courses import router as language_courses_router
from app.routes.problem_statements import router as problem_statements_router
from app.routes.files import router as files_router
from app.routes.daily_quiz import router as daily_quiz_router
from app.routes.websockets import router as websockets_router
from app.routes.stage2_arcade import router as stage2_arcade_router

# Faculty
from app.routes.faculty.classrooms import router as faculty_classrooms_router
from app.routes.faculty.announcements import router as faculty_announcements_router
from app.routes.faculty.assignments import router as faculty_assignments_router
from app.routes.faculty.materials import router as faculty_materials_router
from app.routes.faculty.students import router as faculty_students_router
from app.routes.faculty.attendance import router as faculty_attendance_router
from app.routes.faculty.schedule import router as faculty_schedule_router
from app.routes.faculty.communities import router as faculty_communities_router
from app.routes.faculty.profile import router as faculty_profile_router
from app.routes.faculty.ai_assistant import router as faculty_ai_router

# HOD
from app.routes.hod.dashboard import router as hod_dashboard_router
from app.routes.hod.faculty import router as hod_faculty_router
from app.routes.hod.curriculum import router as hod_curriculum_router
from app.routes.hod.approvals import router as hod_approvals_router
from app.routes.hod.resources import router as hod_resources_router
from app.routes.hod.resource_requests import router as hod_resource_requests_router
from app.routes.hod.software_licenses import router as hod_software_licenses_router
from app.routes.hod.maintenance import router as hod_maintenance_router
from app.routes.hod.reports import router as hod_reports_router
from app.routes.hod.analytics import router as hod_analytics_router
from app.routes.hod.ai_assistant import router as hod_ai_router

# Student
from app.routes.student.classrooms import router as student_classrooms_router
from app.routes.student.assignments import router as student_assignments_router
from app.routes.student.materials import router as student_materials_router
from app.routes.student.announcements import router as student_announcements_router

# Admin
from app.routes.admin.users import router as admin_users_router
from app.routes.admin.challenges import router as admin_challenges_router
from app.routes.admin.stage1 import router as admin_stage1_router
from app.routes.admin.stats import router as admin_stats_router
from app.routes.admin.communication import router as admin_comm_router

# Licensing & Subscription
from app.routes.licensing import router as licensing_router

# Career
from app.routes.career.progress import router as career_progress_router
from app.routes.career.interviews import router as career_interviews_router
from app.routes.career.portfolio import router as career_portfolio_router
from app.routes.career.linkedin import router as career_linkedin_router
from app.routes.career.alumni import router as career_alumni_router
from app.routes.career.resume import router as career_resume_router
from app.routes.career.applications import router as career_applications_router
from app.routes.career.jobs import router as career_jobs_router

# Stage 1 Communication
from app.routes.stage1.read_challenge import router as stage1_read_router
from app.routes.stage1.write_challenge import router as stage1_write_router
from app.routes.stage1.speaking import router as stage1_speaking_router
from app.routes.stage1.ai import router as stage1_ai_router
from app.routes.stage1.roleplay import router as stage1_roleplay_router
from app.routes.stage1.listening import router as stage1_listening_router

# Frontend
from app.routes.frontend import router as frontend_router

# =============== REGISTER ALL ROUTERS ===============

# Core
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)

# Features
app.include_router(challenges_router)
app.include_router(compiler_router)
app.include_router(ai_router)
app.include_router(ai_grading_router)
app.include_router(speech_router)
app.include_router(groups_router)
app.include_router(projects_router)
app.include_router(notifications_router)
app.include_router(jobs_router)
app.include_router(submissions_router)
app.include_router(badges_router)
app.include_router(leaderboard_router)
app.include_router(learning_paths_router)
app.include_router(forum_router)
app.include_router(announcements_router)
app.include_router(study_materials_router)
app.include_router(classrooms_router)
app.include_router(repositories_router)
app.include_router(pair_programming_router)
app.include_router(docs_router)
app.include_router(credits_router)
app.include_router(language_courses_router)
app.include_router(problem_statements_router)
app.include_router(files_router)
app.include_router(daily_quiz_router)
app.include_router(websockets_router)
app.include_router(stage2_arcade_router)

# Faculty
app.include_router(faculty_classrooms_router)
app.include_router(faculty_announcements_router)
app.include_router(faculty_assignments_router)
app.include_router(faculty_materials_router)
app.include_router(faculty_students_router)
app.include_router(faculty_attendance_router)
app.include_router(faculty_schedule_router)
app.include_router(faculty_communities_router)
app.include_router(faculty_profile_router)
app.include_router(faculty_ai_router)

# HOD
app.include_router(hod_dashboard_router)
app.include_router(hod_faculty_router)
app.include_router(hod_curriculum_router)
app.include_router(hod_approvals_router)
app.include_router(hod_resources_router)
app.include_router(hod_resource_requests_router)
app.include_router(hod_software_licenses_router)
app.include_router(hod_maintenance_router)
app.include_router(hod_reports_router)
app.include_router(hod_analytics_router)
app.include_router(hod_ai_router)

# Student
app.include_router(student_classrooms_router)
app.include_router(student_assignments_router)
app.include_router(student_materials_router)
app.include_router(student_announcements_router)

# Admin
app.include_router(admin_users_router)
app.include_router(admin_challenges_router)
app.include_router(admin_stage1_router)
app.include_router(admin_stats_router)
app.include_router(admin_comm_router)

# Licensing & Subscription
app.include_router(licensing_router)

# Career
app.include_router(career_progress_router)
app.include_router(career_interviews_router)
app.include_router(career_portfolio_router)
app.include_router(career_linkedin_router)
app.include_router(career_alumni_router)
app.include_router(career_resume_router)
app.include_router(career_applications_router)
app.include_router(career_jobs_router)

# Stage 1 Communication
app.include_router(stage1_read_router)
app.include_router(stage1_write_router)
app.include_router(stage1_speaking_router)
app.include_router(stage1_ai_router)
app.include_router(stage1_roleplay_router)
app.include_router(stage1_listening_router)

# Frontend (Catch-all)
app.include_router(frontend_router)

if __name__ == "__main__":
    import uvicorn
    import sys
    
    # Check if running in a debugger or if reload is explicitly disabled
    is_debugging = 'debugpy' in sys.modules or os.getenv('PYTHON_RELOAD') == 'false'
    
    if is_debugging:
        print("[*] Debugger detected or reload disabled. Starting single-process mode...")
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, reload_dirs=["app"])
