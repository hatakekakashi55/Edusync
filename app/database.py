"""
EduSync Backend - Database Module
MongoDB connection, collection references, indexes, and sample data.
"""
import logging
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

logger = logging.getLogger("edusync")

# =============== GLOBAL DATABASE VARIABLES ===============
client = None
db = None

# =============== DATABASE CONNECTION ===============
try:
    client = AsyncIOMotorClient("mongodb://localhost:27017", maxPoolSize=100, minPoolSize=10)
    db = client.edusync_v4
    logger.debug("✅ MongoDB connected successfully")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")
    logger.error(f"Make sure MongoDB is running on localhost:27017")
    raise

# =============== COLLECTION REFERENCES ===============
# Core collections
users_collection = db.users
challenges_collection = db.challenges
submissions_collection = db.submissions
groups_collection = db.groups
messages_collection = db.messages
files_collection = db.files
leaderboard_collection = db.leaderboard
badges_collection = db.badges
projects_collection = db.projects
interviews_collection = db.interviews
jobs_collection = db.jobs
notifications_collection = db.notifications
certificates_collection = db.certificates
crew_battles_collection = db.crew_battles
analytics_collection = db.analytics
online_compiler_collection = db.online_compiler
exams_collection = db.exams
announcements_collection = db.announcements
study_materials_collection = db.study_materials
classrooms_collection = db.classrooms
ai_chats_collection = db.ai_chats
coding_challenges_collection = db.coding_challenges
quiz_collection = db.quizzes
assignment_collection = db.assignments
attendance_collection = db.attendance
events_collection = db.events
courses_collection = db.courses
payments_collection = db.payments
feedback_collection = db.feedback
resume_collection = db.resumes

# Code/Repository collections
code_repositories_collection = db.code_repositories
code_commits_collection = db.code_commits
ai_code_assistance_collection = db.ai_code_assistance
code_reviews_collection = db.code_reviews
version_control_collection = db.version_control
pair_programming_collection = db.pair_programming
technical_docs_collection = db.technical_docs
ai_tutor_sessions_collection = db.ai_tutor_sessions
learning_paths_collection = db.learning_paths

# Forum collections
forum_posts_collection = db.forum_posts
forum_comments_collection = db.forum_comments

# Faculty collections
faculty_classrooms_collection = db.faculty_classrooms
faculty_assignments_collection = db.faculty_assignments
faculty_students_collection = db.faculty_students
classroom_requests_collection = db.classroom_requests
faculty_attendance_collection = db.faculty_attendance
faculty_schedule_collection = db.faculty_schedule
faculty_communities_collection = db.faculty_communities
faculty_submissions_collection = db.faculty_submissions

# HOD collections
hod_approvals_collection = db.hod_approvals
hod_reports_collection = db.hod_reports
hod_analytics_collection = db.hod_analytics
department_stats_collection = db.department_stats
faculty_performance_collection = db.faculty_performance

# Curriculum collections
syllabus_collection = db.syllabus
approvals_collection = db.approvals
approval_history_collection = db.approval_history
approval_templates_collection = db.approval_templates
approval_workflows_collection = db.approval_workflows

# Resource collections
resources_collection = db.resources
software_licenses_collection = db.software_licenses
resource_requests_collection = db.resource_requests
maintenance_collection = db.maintenance
resource_history_collection = db.resource_history

# Report collections
reports_collection = db.reports
scheduled_reports_collection = db.scheduled_reports
report_templates_collection = db.report_templates

# Credit/Leaderboard collections
credits_collection = db.credits
credit_transactions_collection = db.credit_transactions
group_requests_collection = db.group_requests

# Language/Communication collections
language_course_progress_collection = db.language_course_progress
problem_statements_collection = db.problem_statements
voice_challenge_sentences_collection = db.voice_challenge_sentences
writing_challenges_collection = db.writing_challenges
communication_submissions_collection = db.communication_submissions
communication_tasks_collection = db.communication_tasks

# Stage 1 AI Feature collections
roleplay_sessions_collection = db.roleplay_sessions
speech_analyses_collection = db.speech_analyses

# Subscription & Licensing collections
licenses_collection = db.licenses
edu_credits_collection = db.edu_credits
credit_refill_requests_collection = db.credit_refill_requests
subscription_analytics_collection = db.subscription_analytics
renewal_quotes_collection = db.renewal_quotes


# =============== DATABASE INITIALIZATION FUNCTIONS ===============
async def create_indexes():
    """Create database indexes for performance"""
    try:
        # Core Users collection indexes
        await users_collection.create_index("email", unique=True)
        
        # Robust handling for roll_number index
        try:
            # Drop null values first as they break sparse unique indexes in some MongoDB versions
            await users_collection.update_many({"roll_number": None}, {"$unset": {"roll_number": ""}})
            await users_collection.create_index("roll_number", unique=True, sparse=True)
        except Exception as e:
            # If there's a conflict, it's usually because of changed options (unique/sparse)
            if any(err in str(e) for err in ["IndexKeySpecsConflict", "IndexOptionsConflict", "BSONObj"]):
                logger.warning("Index conflict detected for 'roll_number'. Attempting to drop and recreate...")
                try:
                    # Find the index name for 'roll_number' key
                    async for index in users_collection.list_indexes():
                        if 'roll_number' in index['key']:
                            index_name = index['name']
                            if index_name != "_id_":
                                await users_collection.drop_index(index_name)
                                logger.info(f"Dropped conflicting index: {index_name}")
                    
                    # Recreate with desired options
                    await users_collection.create_index("roll_number", unique=True, sparse=True)
                    logger.info("Successfully recreated roll_number index.")
                except Exception as drop_err:
                    logger.error(f"Failed to resolve index conflict: {drop_err}")
            else:
                logger.error(f"Unexpected error creating roll_number index: {e}")
                
        await users_collection.create_index([("department", 1), ("year", 1)])
        await users_collection.create_index("user_type")
        await users_collection.create_index("created_at")
        
        # Challenges collection indexes
        await challenges_collection.create_index([("stage", 1), ("difficulty", 1)])
        await challenges_collection.create_index([("challenge_type", 1)])
        await challenges_collection.create_index("tags")
        await challenges_collection.create_index("created_at")
        
        # Submissions collection indexes
        await submissions_collection.create_index([("user_id", 1), ("challenge_id", 1)])
        await submissions_collection.create_index([("challenge_id", 1), ("score", -1)])
        await submissions_collection.create_index([("user_id", 1), ("submitted_at", -1)])
        await submissions_collection.create_index("completed")
        
        # Groups collection indexes
        await groups_collection.create_index([("department", 1), ("year", 1)])
        await groups_collection.create_index("privacy")
        await groups_collection.create_index("members")
        
        # Files collection indexes
        await files_collection.create_index("owner_id")
        await files_collection.create_index("project_id")
        await files_collection.create_index("uploaded_at")
        
        # Code repositories indexes
        await code_repositories_collection.create_index("owner_id")
        await code_repositories_collection.create_index([("is_public", 1), ("created_at", -1)])
        
        # Notifications indexes
        await notifications_collection.create_index([("user_id", 1), ("read", 1)])
        await notifications_collection.create_index([("user_id", 1), ("created_at", -1)])
        
        # Leaderboard indexes
        await leaderboard_collection.create_index([("period", 1), ("total_score", -1)])
        await leaderboard_collection.create_index([("user_id", 1), ("period", 1)])
        
        # HOD collections indexes
        await hod_approvals_collection.create_index([("user_id", 1), ("read", 1)])
        await hod_approvals_collection.create_index([("type", 1), ("created_at", -1)])
        
        await hod_reports_collection.create_index([("department", 1), ("generated_at", -1)])
        await hod_analytics_collection.create_index([("department", 1), ("period", 1)])
    
        await department_stats_collection.create_index([("department", 1), ("academic_year", 1)])
        await faculty_performance_collection.create_index([("faculty_id", 1), ("date", -1)])
        
        # Stage 1 AI Feature indexes
        await roleplay_sessions_collection.create_index([("user_id", 1), ("status", 1)])
        await roleplay_sessions_collection.create_index("session_id", unique=True)
        await roleplay_sessions_collection.create_index([("user_id", 1), ("started_at", -1)])
        await speech_analyses_collection.create_index([("user_id", 1), ("created_at", -1)])
        
        # Subscription & Licensing indexes
        await licenses_collection.create_index("license_key_hash", unique=True)
        await licenses_collection.create_index("college_id")
        await licenses_collection.create_index("status")
        await licenses_collection.create_index("expiry_date")
        await edu_credits_collection.create_index("user_id", unique=True)
        await credit_refill_requests_collection.create_index([("user_id", 1), ("status", 1)])
        await credit_refill_requests_collection.create_index([("department", 1), ("created_at", -1)])
        await renewal_quotes_collection.create_index("college_id")
        
        logger.info("✅ Database indexes created successfully")
        
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")


async def initialize_sample_data():
    """Initialize sample data for demonstration"""
    try:
        logger.info("Initializing sample data with real users...")
        
        # Sample users data
        from app.utils.auth import hash_password
        sample_users = [
            {
                "full_name": "Naruto Uzumaki",
                "email": "naruto@edusync.com",
                "password": hash_password("password123"),
                "user_type": "student",
                "department": "Computer Science",
                "year": 3,
                "roll_number": "CS001",
                "credits": 500,
                "created_at": datetime.now(timezone.utc)
            },
            {
                "full_name": "Sasuke Uchiha",
                "email": "sasuke@edusync.com",
                "password": hash_password("password123"),
                "user_type": "student",
                "department": "Computer Science",
                "year": 3,
                "roll_number": "CS002",
                "credits": 450,
                "created_at": datetime.now(timezone.utc)
            },
            {
                "full_name": "Kakashi Hatake",
                "email": "hatakekakashi@edusync.com",
                "password": hash_password("password123"),
                "user_type": "faculty",
                "department": "Computer Science",
                "created_at": datetime.now(timezone.utc)
            },
            {
                "full_name": "Admin User",
                "email": "admin@edusync.com",
                "password": hash_password("admin123"),
                "user_type": "admin",
                "created_at": datetime.now(timezone.utc)
            }
        ]
        
        # Only insert sample users if they don't already exist
        emails = [u["email"] for u in sample_users]
        existing_emails = await users_collection.distinct("email", {"email": {"$in": emails}})
        
        users_to_insert = [u for u in sample_users if u["email"] not in existing_emails]
        
        if users_to_insert:
            await users_collection.insert_many(users_to_insert)
            logger.info(f"✅ Created {len(users_to_insert)} new sample users")
        else:
            logger.info("ℹ️ Sample users already exist, skipping insertion")
        
        # Create sample challenges if none exist
        existing_challenges = await challenges_collection.count_documents({})
        if existing_challenges == 0:
            sample_challenges = [
                {
                    "title": "Hello World in Python",
                    "description": "Write a program that prints 'Hello, World!' to the console.",
                    "stage": "freshie",
                    "challenge_type": "coding",
                    "difficulty": "easy",
                    "credits_reward": 50,
                    "time_limit": 10,
                    "language": "python",
                    "code_template": "print('Hello, World!')",
                    "test_cases": [
                        {"input": "", "output": "Hello, World!"}
                    ],
                    "requirements": ["Must print exactly 'Hello, World!'"],
                    "tags": ["python", "beginner", "hello-world"],
                    "created_at": datetime.now(timezone.utc),
                    "created_by": "system",
                    "created_by_name": "System"
                }
            ]
            await challenges_collection.insert_many(sample_challenges)
            logger.info(f"✅ Created {len(sample_challenges)} sample challenges")
        
        # Create sample jobs if none exist
        existing_jobs = await jobs_collection.count_documents({})
        if existing_jobs == 0:
            sample_jobs = [
                {
                    "title": "Junior Full Stack Developer",
                    "company": "EduSync Tech",
                    "location": "Chennai, Tamil Nadu",
                    "description": "Looking for a passionate junior developer to join our core team.",
                    "requirements": ["React", "Python", "MongoDB", "FastAPI"],
                    "salary_range": "₹6,00,000 - ₹8,00,000 PA",
                    "job_type": "Full-time",
                    "experience_required": "Fresher",
                    "experience_level": "Entry Level",
                    "status": "active",
                    "posted_at": datetime.now(timezone.utc),
                    "is_featured": True
                },
                {
                    "title": "Data Analyst Intern",
                    "company": "Data Insights Corp",
                    "location": "Bangalore, Karnataka",
                    "description": "Join our data team to help analyze user behavior and platform performance.",
                    "requirements": ["Python", "SQL", "Pandas", "Matplotlib"],
                    "salary_range": "₹25,000 - ₹40,000 / month",
                    "job_type": "Internship",
                    "experience_required": "0-1 years",
                    "experience_level": "Internship",
                    "status": "active",
                    "posted_at": datetime.now(timezone.utc),
                    "is_featured": True
                },
                {
                    "title": "Frontend Developer",
                    "company": "Creative UI Labs",
                    "location": "Remote",
                    "description": "Build stunning user interfaces for our global clients.",
                    "requirements": ["JavaScript", "React", "CSS3", "HTML5"],
                    "salary_range": "₹4,00,000 - ₹12,00,000 PA",
                    "job_type": "Full-time",
                    "experience_required": "0-2 years",
                    "experience_level": "Junior",
                    "status": "active",
                    "posted_at": datetime.now(timezone.utc),
                    "is_featured": False
                }
            ]
            await jobs_collection.insert_many(sample_jobs)
            logger.info(f"✅ Created {len(sample_jobs)} sample jobs")
            
        # Create real sample jobs for stage 4
        sample_jobs = [
            {
                "title": "Junior Full Stack Developer",
                "company": "EduSync Tech",
                "location": "Chennai, Tamil Nadu",
                "description": "Looking for a passionate junior developer to join our core team.",
                "requirements": ["React", "Python", "MongoDB", "FastAPI"],
                "salary_range": "₹6,00,000 - ₹8,00,000 PA",
                "job_type": "Full-time",
                "experience_required": "Fresher",
                "experience_level": "Entry Level",
                "status": "active",
                "posted_at": datetime.now(timezone.utc),
                "is_featured": True
            },
            {
                "title": "Data Analyst Intern",
                "company": "Data Insights Corp",
                "location": "Bangalore, Karnataka",
                "description": "Join our data team to help analyze user behavior and platform performance.",
                "requirements": ["Python", "SQL", "Pandas", "Matplotlib"],
                "salary_range": "₹25,000 - ₹40,000 / month",
                "job_type": "Internship",
                "experience_required": "0-1 years",
                "experience_level": "Internship",
                "status": "active",
                "posted_at": datetime.now(timezone.utc),
                "is_featured": True
            },
            {
                "title": "Frontend Developer",
                "company": "Creative UI Labs",
                "location": "Remote",
                "description": "Build stunning user interfaces for our global clients.",
                "requirements": ["JavaScript", "React", "CSS3", "HTML5"],
                "salary_range": "₹4,00,000 - ₹12,00,000 PA",
                "job_type": "Full-time",
                "experience_required": "0-2 years",
                "experience_level": "Junior",
                "status": "active",
                "posted_at": datetime.now(timezone.utc),
                "is_featured": False
            }
        ]
        
        existing_jobs = await jobs_collection.count_documents({})
        if existing_jobs == 0:
            await jobs_collection.insert_many(sample_jobs)
            logger.info(f"✅ Created {len(sample_jobs)} sample jobs")
            
        logger.info("✅ Sample data initialization complete")
        
    except Exception as e:
        logger.error(f"Error initializing sample data: {e}")
