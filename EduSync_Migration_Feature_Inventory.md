# EduSync 4.0 — Full Feature & Technical Inventory
### Exhaustive Source-Code Verified Checklist for Spring Boot + React TypeScript Migration

> Every item below was extracted directly from the source files (`app/routes/`, `app/services/`, `app/models/`, `app/database.py`).  
> Nothing is assumed. Everything is real.
>
> **⚠️ AUDIT CORRECTED — June 2, 2026:** Cross-verified against source code. Errors removed, stubs flagged, missing modules added.

---

## SECTION 1 — Authentication & Session System

### 1.1 Registration (`POST /api/auth/register`)
- [ ] Duplicate email check before insert
- [ ] Duplicate roll number check (students only), with sparse unique index handling
- [ ] BCrypt password hashing on creation
- [ ] Auto-generate `campus_email` from full name (`name@campus.com`)
- [ ] Auto-assign student fields on creation:
  - `stage = "freshie"`, `credits = 0`, `xp = 0`, `level = 1`
  - `daily_login_streak = 0`, `weekly_login_streak = 0`
  - `current_stage_progress = 0`, `completed_challenges = 0`
  - `weak_areas = []`, `strengths = []`, `skills = []`, `interests = []`
  - `badges = []`, `achievements = []`, `mood_history = []`
  - `notification_preferences` object (email, push, sms, challenge reminders, deadline alerts)
- [ ] Auto-create "Welcome Aboard! 🎉" badge document on signup
- [ ] Auto-create analytics entry on signup
- [ ] Welcome email via background task (async email dispatch)
- [ ] In-app welcome notification on signup

### 1.2 Login (`POST /api/auth/login`)
- [ ] Email + BCrypt password verification
- [ ] Account active status check (403 if deactivated)
- [ ] **Daily Login Streak Calculator:** Compare today with `last_login` date
  - Streak continues if gap = 1 day; resets if gap > 1 day
- [ ] **Weekly Login Streak Calculator:** Continues if gap ≤ 7 days
- [ ] **Login Credit Reward Formula:** `10 + (daily_streak × 2)` credits per login
- [ ] **Device History Tracking:** Append device info to last-10 history list
- [ ] Update analytics `total_sessions` counter
- [ ] Issue both `access_token` (24h) and `refresh_token` (30d) as JWT HS256
- [ ] Store refresh token in **Redis** with TTL `= REFRESH_TOKEN_EXPIRE_DAYS × 86400`
- [ ] Login success notification (background task)
- [ ] Return full user object: `user_id`, `email`, `full_name`, `user_type`, `stage`, `department`, `year`, `credits`, `xp`, `level`, `daily_streak`, `profile_picture`, `theme`, `is_verified`, `role`

### 1.3 Token Refresh (`POST /api/auth/refresh`)
- [ ] Decode refresh token, confirm `type == "refresh"`
- [ ] Validate token ID against Redis stored value
- [ ] Issue new access token without re-login

### 1.4 Logout (`POST /api/auth/logout`)
- [ ] Delete refresh token key from Redis on logout

---

## SECTION 2 — User Profiles & Settings

### 2.1 Profile Read/Write (`GET/PUT /api/users/me`)
- [ ] Fetch full authenticated user profile
- [ ] Update: `full_name`, `phone`, `bio`, `designation`, `expertise`, `office`, `office_hours`, `qualifications`, `publications`, `research_areas`, `courses_teaching`, `joining_date`
- [ ] Preferred language, timezone, learning style fields
- [ ] Notification preferences object update

### 2.2 Profile Picture Upload (`POST /api/users/me/avatar`)
- [ ] Multipart upload up to 50MB
- [ ] Allowed formats: `.pdf`, `.jpg`, `.jpeg`, `.png`, `.mp3`, `.mp4`, `.txt`, `.py`, `.java`, `.cpp`, `.c`, `.js`, `.html`, `.css`, `.md`, `.json`, `.csv`, `.xlsx`, `.docx`
- [ ] Store URL reference in user document

### 2.3 User Stats & Analytics
- [ ] XP, Level, Credits summary
- [ ] Total sessions, total time spent
- [ ] Completed challenges count, projects completed count
- [ ] Stage progress percentage (`current_stage_progress`)

---

## SECTION 3 — INIXA AI Engine (5-Engine Fallback Broker)

### 3.1 Fallback Chain (in order)
| Priority | Engine | Endpoint | Model |
|---|---|---|---|
| 1 | DuckDuckGo Cloudflare Worker | `https://bitter-sea-46dc.keerthan4531.workers.dev/chat` | `gpt-4o-mini` |
| 2 | LLM7 | `https://api.llm7.io/v1/chat/completions` | `gpt-4o-mini` |
| 3 | BlackBox AI | `https://api.blackbox.ai/api/chat` | Default |
| 4 | Pollinations OpenAI | `https://text.pollinations.ai/openai` | `openai` |
| 5 | Pollinations Simple | `https://text.pollinations.ai` | `openai` |

### 3.2 Engine-specific Behaviors
- [ ] **DuckDuckGo:** Handles both JSON and `data:` SSE streaming response formats
- [ ] **BlackBox:** Strips source-link annotations (`$~~~$...$~~~$`) and footnote markers (`[^N^]`) from responses
- [ ] **All engines:** Detect garbage/HTML responses and skip to next engine
- [ ] **Global timeout:** 90 seconds (`AI_TIMEOUT` env var)
- [ ] **Retry:** Up to 3 retries with exponential backoff (1s, 2s, 4s)
- [ ] **Track last used engine:** `_last_engine` variable returned to UI as label

### 3.3 AI Status Checker
- [ ] Quick-check DDG → BlackBox → Pollinations with 5s timeout each
- [ ] Return `{ online: true/false, engine: "label" }`

### 3.4 Backward-Compatible `AIModelWrapper` Class
- [ ] `generate_content(contents)` — sync wrapper running async in thread pool
- [ ] `generate_content_async(contents)` — pure async route
- [ ] Returns `MockResponse` object with `.text` attribute (Gemini SDK-compatible)
- [ ] `__bool__` always returns `True` (AI always considered available)

### 3.5 Image Generation
- [ ] Endpoint: `https://image.pollinations.ai/prompt/{prompt}`
- [ ] Used in vocabulary builder, writing modules

---

## SECTION 4 — Docker Compiler Sandbox

### 4.1 Supported Languages & Docker Images
**Source: `app/config.py` → `LANG_CONFIG` (7 languages only)**

| Language | Image | Compile | Run |
|---|---|---|---|
| Python | `python:3.11-slim` | — | `python {file}` |
| JavaScript | `node:18-slim` | — | `node {file}` |
| Java | `openjdk:17-slim` | `javac {file}` | `java Main` |
| C | `gcc:12` | `gcc {file} -o main` | `./main` |
| C++ | `gcc:12` | `g++ {file} -o main` | `./main` |
| Go | `golang:1.21` | — | `go run {file}` |
| Rust | `rust:1.70` | `rustc {file} -o main` | `./main` |

> ❌ TypeScript and Ruby are **NOT** supported. Do not port them in Spring Boot unless explicitly added.

### 4.2 Safety Constraints
- [ ] CPU limit: `1.0` core (`DOCKER_CPU`)
- [ ] Memory limit: `512m` (`DOCKER_MEMORY`)
- [ ] Execution timeout: `30 seconds` (`TIMEOUT_SECONDS`)
- [ ] `--network none` — No internet access inside container
- [ ] `--cap-drop ALL --security-opt no-new-privileges` — Privilege escalation blocked
- [ ] `--pids-limit 64` — Process fork bomb prevention

### 4.3 Docker Fallback → Local Execution
- [ ] On startup, `CompilerService.is_docker_available()` runs `docker info` (cached result)
- [ ] If Docker is **unavailable**, falls back to **local subprocess execution** via `LOCAL_CMD_MAP`
- [ ] `execution_mode` field in response: `"docker"` or `"local"` — UI can display this
- [ ] Local fallback supported for: Python, JavaScript, Java, C, C++, Go, Rust (same 7 languages)
- [ ] **For Java Spring Boot migration:** Implement same fallback pattern using `ProcessBuilder`

### 4.4 Endpoints
- [ ] `POST /api/compiler/execute` — Execute code with optional `input_data` and `test_cases[]`
- [ ] `GET /api/compiler/history` — Get last N execution records for user (default 20, max 100)
- [ ] Auto-save execution to `online_compiler` collection with `user_id`, `code`, `language`, `output`, `success`, `executed_at`

### 4.5 Language Course Code Runner (separate endpoint)
- [ ] `POST /api/language-courses/run-code` — Same sandbox, adds AI error hint if execution fails
- [ ] `POST /api/language-courses/submit-exercise` — Execute + AI review + score + credit award

---

## SECTION 5 — Challenges & Submissions

### 5.1 Challenge Listing (`GET /api/challenges`)
- [ ] Filter by: `stage`, `challenge_type`, `difficulty`, `language`, `tags` (comma-separated)
- [ ] Paginated: `limit` (max 100), `skip`
- [ ] Students auto-filtered to their current stage
- [ ] Per-challenge `user_status` injected: `{ attempted, completed, score }`

### 5.2 Challenge Detail (`GET /api/challenges/{id}`)
- [ ] Returns challenge + user's last 10 submissions

### 5.3 Challenge Submission (`POST /api/challenges/{id}/submit`)
Three submission modes:
- [ ] **Voice mode:** Read audio → `SpeechService.speech_to_text()` → `AIService.analyze_english_with_gemini()` → pronunciation score; completed if score ≥ 70
- [ ] **Coding mode:** Run through `CompilerService.execute_code_safely()` → `AIService.code_review()` → score = passed_tests / total_tests × 100; completed if score ≥ 70
- [ ] **Text/Quiz mode:** Case-insensitive exact match → 100 if correct, else 0

### 5.4 Credit Reward on Completion
- [ ] `$inc credits` by `challenge.credits_reward`
- [ ] `$inc completed_challenges` counter
- [ ] `$inc current_stage_progress` by 10% per challenge

---

## SECTION 6 — Credit & XP Economy

### 6.1 Credit Award System (`POST /api/credits/award`)
Full credit config table:
| Task Type | Base Credits | Bonus |
|---|---|---|
| `daily_login` | 10 | +70 bonus |
| `voice_challenge` | 50 | +0.5 per score % |
| `reading_challenge` | 50 | +0.5 per score % |
| `listening_challenge` | 50 | +0.5 per score % |
| `writing_challenge` | 75 | +0.5 per score % |
| `coding_challenge` | 75 | +25/star; +25 medium, +50 hard, +100 expert |
| `project_completion` | 200 | +50 if completed |
| `badge_earned` | 100 | — |
| `streak_extension` | 70 | — |
| `lesson_completion` | 30 | — |
| `quiz_completion` | 20 | +2 per correct answer |
| `peer_review` | 40 | — |
| `profile_completion` | 50 | — |

- [ ] Daily login credits: Max 1 award per day (Redis-tracked)
- [ ] `XP earned = credits × 2` formula

### 6.2 XP Level Calculation Formula
**Source: `app/utils/helpers.py` → `calculate_level()` (lines 385–400)**

> ❌ Old (wrong) formula: `level = floor(XP / 100) + 1`  
> ✅ Correct formula: **Progressive XP Ladder**

```
Level 1: 0 XP needed
Level 2: 1000 XP needed  
Level 3: 1500 XP needed (+1500)
Level 4: 2250 XP needed (+2250)
... each threshold = previous × 1.5
```

- [ ] Port `calculate_level(xp)` exactly — it is a `while` loop, not a formula
- [ ] Returns: `{ level, current_xp (remainder), xp_for_next_level, xp_progress (%) }`
- [ ] Used in credits summary, user profile, and leaderboard

### 6.3 Credit Operations
- [ ] `GET /api/credits/summary` — Balance, XP, transactions summary
- [ ] `GET /api/credits/transactions` — Paginated transaction log
- [ ] `POST /api/credits/transfer` — Peer-to-peer transfer (10–1000 credits), logged both sides, notification to recipient
- [ ] `POST /api/credits/spend` — Spend on marketplace items, logged in `purchases` collection

---

## SECTION 7 — Notifications System

- [ ] `GET /api/notifications` — Paginated, filterable by `unread_only`; includes both personal and broadcast notifications
- [ ] `POST /api/notifications/{id}/read` — Mark single notification as read
- [ ] `POST /api/notifications/read-all` — Bulk mark all as read
- [ ] Notification types: `welcome`, `login`, `system`, `group_request`, `credit_transfer`, `achievement`, `deadline`, `announcement`
- [ ] Priority levels: `low`, `medium`, `high`
- [ ] `action_url` field for deep links

---

## SECTION 8 — Study Groups & Team Channels

- [ ] `POST /api/groups/create` — Create group (name, desc, privacy, dept, year)
- [ ] `GET /api/groups` — My groups + member groups; shows `is_member`, `member_count`
- [ ] `GET /api/groups/discover` — Public groups user hasn't joined yet
- [ ] `GET /api/groups/{id}` — Detail with full member list and roles (Creator/Member)
- [ ] `POST /api/groups/{id}/join` — Instant join for public groups
- [ ] `POST /api/groups/{id}/request` — Join request for private groups → notifies admins
- [ ] `GET /api/groups/{id}/requests` — View pending join requests (admin only)
- [ ] `POST /api/groups/{id}/requests/{req_id}/action` — Approve or reject join request
- [ ] `GET /api/groups/{id}/messages` — Fetch message history
- [ ] `POST /api/groups/{id}/send-message` — HTTP message send + WebSocket broadcast
- [ ] `POST /api/groups/{id}/files` — Upload file to group shared folder

---

## SECTION 9 — Leaderboard System

### 9.1 Coding Leaderboard (`GET /api/leaderboard`)
- [ ] Filter modes: `weekly` (last 7 days), `monthly`, `all_time`
- [ ] Optional filters: `department`, `year`
- [ ] Weekly: MongoDB aggregation pipeline on `submissions` collection
- [ ] Monthly/All-time: From `leaderboard` collection
- [ ] Per-entry: `rank`, `user_name`, `department`, `year`, `stage`, `profile_picture`, `total_score`, `challenges_completed`, `average_score`
- [ ] Viewer's own rank and score injected in response

### 9.2 Career Leaderboard (`GET /api/leaderboard/career`)
- [ ] Score = `(interviews_completed × 10) + (skills_count × 2) + (experience_entries × 5)`
- [ ] Returns top 10 + viewer's rank, score, badge count

---

## SECTION 10 — Code Repository & Version Control

- [ ] `POST /api/repositories` — Create repository (name, description, public/private)
- [ ] `GET /api/repositories` — List with filters: `owner_id`, `is_public`, `language`; includes collaborator access
- [ ] `GET /api/repositories/{id}` — Full repo detail: files, recent 10 commits, contributors (aggregated), `can_edit` flag
- [ ] `POST /api/repositories/{id}/commits` — Create new commit (message, files[], branch)
- [ ] Repository contributor stats via aggregation: commit count, last commit date per author

---

## SECTION 11 — WebSocket Real-Time Channels

### 11.1 Main WS Channel (`/api/ws/{connection_id}?token=`)
- [ ] JWT token validation on connect; close with code 1008 on failure
- [ ] Message types handled:
  - `ping` → `pong` keepalive
  - `group_message` → save to DB → broadcast to group members
  - `@assistant` prefix detection → AI query → dual broadcast (user message + AI response)
  - `typing` → broadcast `user_typing` event to group
  - `pair_programming` → sync code + cursor position to partner

### 11.2 Challenges WS (`/ws/challenges?token=`)
- [ ] Subscribe to live challenge updates by stage
- [ ] `subscribe_to_stage` → fetch active challenges and return list

### 11.3 Project Collaboration WS (`/ws/projects/{project_id}?token=`)
- [ ] Membership/ownership validation before accepting
- [ ] Broadcast `user_joined` / `user_left` events
- [ ] Message types:
  - `cursor_position` → broadcast `cursor_update` (user, file, line, column)
  - `code_change` → broadcast `code_update` (user, file, changes)
  - `chat_message` → broadcast `team_chat`

### 11.4 Stage 3 AI Assistant WS (`/api/ws/stage3?token=`)
- [ ] Character-by-character token streaming with 20ms delay
- [ ] Events: `typing`, `response_start`, `token`, `response_complete`
- [ ] Save conversation to `ai_chats` collection

### 11.5 Stage 1 Roleplay WS (`/api/ws/stage1/roleplay?token=`)
- [ ] Session lookup + active status check per message
- [ ] Build full conversation context from session history
- [ ] Stream AI response character by character (15ms delay)
- [ ] Update `messages[]` and `current_turn` in DB after each exchange
- [ ] `should_end` flag when `current_turn >= max_turns`
- [ ] `speech_analysis` message type: calculate WPM + filler word detection in real-time

---

## SECTION 12 — Stage 1: Communication Skills

### 12.1 Listening Module
- [ ] **Echo Challenge:** Submit audio → STT → pronunciation scoring
- [ ] **Fill the Beats:** Audio playback + blank-filling transcript validation
- [ ] **Direction Follower:** Audio instructions → grid path answer validation
- [ ] **Tone Recognizer:** Classify voice clip tone (happy, angry, professional, casual)

### 12.2 Reading Module
- [ ] Passage selection (Admin-curated, Faculty-selected, or AI-generated)
- [ ] Time-limited reading with comprehension questions (MCQ or short-answer)
- [ ] Reading speed tracking (words per minute)
- [ ] Score + feedback generation

### 12.3 Writing Module
- [ ] **Essay Challenge:** AI real-time grammar, structure, and vocab feedback
- [ ] **Picture Prompt:** Show image → 50-word description → AI evaluation
- [ ] **No-Filter Challenge:** Rewrite sentence without "banned" words → detect violations
- [ ] **Quick Reply Time Attack:** Countdown timer → professional email draft → tone/grammar score
- [ ] **Word Chain:** Construct valid 10-word sentence → logic + vocabulary evaluation

### 12.4 Speaking / Roleplay Module
- [ ] **AI Conversation Partner:** Live voice or text with AI (WebSocket)
- [ ] **English Chatbot (4 Tabs):** General / Conversation / Grammar correction / Pronunciation
- [ ] **Roleplay Sessions:** Scenario-based, system prompt-driven character simulation
  - `POST` to create session → `WS` to converse → `POST` to evaluate + close
  - Session stored in `roleplay_sessions` collection with `system_prompt`, `messages[]`, `current_turn`, `max_turns`, `status`

### 12.5 Vocabulary Builder
- [ ] Flashcard system: English word, English meaning, Tamil meaning, category, example sentence
- [ ] Daily word cards (rotating/randomized)
- [ ] Add custom vocabulary form (word, meaning, Tamil meaning, examples, notes)
- [ ] Vocabulary progress: badges, streaks, downloadable mastery report

---

## SECTION 13 — Student Dashboard (Portal)

- [ ] `GET /api/student/classrooms` — Enrolled classrooms list
- [ ] `GET /api/student/classrooms/{id}` — Classroom detail with teacher info
- [ ] `GET /api/student/materials` — Browse materials by classroom
- [ ] `GET /api/student/assignments` — Active assignments with due dates, criteria
- [ ] `POST /api/student/assignments/{id}/submit` — File or text submission
- [ ] `GET /api/student/assignments/{id}/grade` — View score, execution output, teacher comments
- [ ] `GET /api/student/announcements` — Class-wide and college-wide broadcasts
- [ ] Daily quiz: fetch questions, submit answers, receive credits

---

## SECTION 14 — Faculty Dashboard

- [ ] `POST /api/faculty/classrooms` — Create classroom + auto-generate join code
- [ ] `GET /api/faculty/classrooms` — List own classrooms with student counts
- [ ] `GET /api/faculty/students` — Student directory with averages and challenge stats
- [ ] `POST /api/faculty/materials` — Upload lecture PDFs, slides, code files
- [ ] `POST /api/faculty/assignments` — Create assignment: title, description, due date, test cases, code template, language, reward credits
- [ ] `GET /api/faculty/assignments/{id}/submissions` — View all student submissions
- [ ] `GET/POST /api/faculty/attendance` — Log daily attendance; export history
- [ ] `GET/POST /api/faculty/schedule` — Publish and view timetable / exam dates
- [ ] `POST /api/faculty/ai` — AI assistant for lesson plans, quizzes, test questions
- [ ] `GET /api/faculty/communities` — Browse faculty-only community forums

### 14.A AI Grading Endpoints (`app/routes/ai_grading.py`)
> ⚠️ **STUB/MOCK implementations** — All return hardcoded values. Real AI grading NOT built yet.
> Must be fully implemented in Spring Boot using actual Gemini/INIXA calls.

- [ ] `POST /api/ai/grade-submission` — Returns mock grade=85, plagiarism=2.5, quality metrics (faculty only)
- [ ] `POST /api/ai/bulk-grade` — Returns mock grade=80 for each submission ID
- [ ] `POST /api/ai/check-plagiarism` — Returns mock plagiarism_score=2.5, is_suspicious=false
- [ ] `POST /api/ai/generate-feedback` — Returns mock suggestions/strengths/improvements
- [ ] `POST /api/ai/analyze-patterns` — Returns mock grade distribution and common mistakes

### 14.B Faculty Approval Submissions (`app/routes/misc.py`)
- [ ] `POST /api/approvals/request` — Generic approval request to HOD with notification
- [ ] `POST /api/approvals/faculty-community` — Request to create faculty community (HOD must approve)
- [ ] `POST /api/approvals/faculty-leave` — Leave request auto-routed to dept HOD; calculates leave_days
- [ ] `POST /api/approvals/resource-request` — Hardware/resource request to HOD

---

## SECTION 15 — HOD Dashboard

- [ ] `GET /api/hod/dashboard` — Aggregate dept stats: pass rates, avg marks, attendance %
- [ ] `GET /api/hod/faculty` — Faculty list (filter by status, designation, search text)
- [ ] `POST /api/hod/faculty` — Register new faculty: auto temp-password, welcome email, notification
- [ ] `GET /api/hod/faculty/{id}` — Full faculty profile + performance stats
- [ ] `GET/POST/PUT /api/hod/curriculum` — Create, review, edit syllabus drafts
- [ ] Curriculum state machine: `Draft → Review → HOD Approved → Registrar Finalized`
- [ ] `GET/POST /api/hod/approvals` — Approve course proposals, credit refills, bookings
- [ ] `GET/POST /api/hod/resources` — Register and track hardware assets
- [ ] `GET/POST /api/hod/resource-requests` — Review/approve faculty hardware requests
- [ ] `GET/POST /api/hod/software-licenses` — Track keys, expiry, user assignments, renewals
- [ ] `GET/POST /api/hod/maintenance` — Log lab maintenance tasks, schedule, track status
- [ ] `POST /api/hod/reports` — Generate + export academic performance PDF reports
- [ ] `POST /api/hod/ai` — Natural language HOD AI audit queries

---

## SECTION 16 — Admin Dashboard

- [ ] `GET/POST/PUT/DELETE /api/admin/users` — CRUD for all user accounts
- [ ] Suspend and reactivate user accounts
- [ ] `GET/POST /api/admin/challenges` — Author global coding + communication challenges
- [ ] `GET/POST /api/admin/stage1` — Configure speech audio, vocab words, roleplay scripts
- [ ] `GET /api/admin/stats` — Platform-wide metrics: active users, challenge counts, credit flow

---

## SECTION 17 — Career Preparation Module (Stage 4)

- [ ] `GET /api/career/progress` — Career readiness score and milestones
- [ ] `POST /api/career/interviews` — Start AI mock interview session
- [ ] `GET /api/career/interviews/{id}` — Session detail + feedback
- [ ] `POST /api/career/interviews/{id}/complete` — End session + generate streaming evaluation report
- [ ] `GET/POST /api/career/resume` — Resume upload, parse, score, section recommendations
- [ ] `GET /api/linkedin/checklist` — Profile checklist with task completion status
- [ ] `GET /api/linkedin/analyze` — LinkedIn profile completeness score (checks bio, picture, skills, experience, education, recommendations)
- [ ] `GET /api/linkedin/jobs` — Job search: RapidAPI (LinkedIn Jobs) → local DB fallback
- [ ] `GET/POST /api/career/portfolio` — Portfolio page generation from repos + skills + badges
- [ ] `GET /api/career/alumni` — Alumni directory browse and search
- [ ] `GET /api/career/applications` — Track job application statuses

---

## SECTION 18 — B2B Licensing & Subscription System

- [ ] `POST /api/licensing/activate` — Validate hashed license key, student cap, expiry date
- [ ] `GET /api/licensing/status` — Check current license validity
- [ ] `POST /api/edu-credits/request` — HOD submits department credit refill request
- [ ] `POST /api/edu-credits/approve` — Admin approves and provisions credits
- [ ] `GET /api/edu-credits/usage` — Credit usage reports by dept, classroom, student

---

## SECTION 19 — Database Collections (53+ Collections)

| Category | Collections |
|---|---|
| Core | `users`, `badges`, `analytics`, `notifications`, `certificates` |
| Challenges | `challenges`, `submissions`, `coding_challenges`, `leaderboard` |
| Classroom | `classrooms`, `faculty_classrooms`, `assignments`, `faculty_assignments`, `faculty_submissions`, `attendance`, `faculty_attendance`, `faculty_schedule` |
| Groups | `groups`, `messages`, `group_requests` |
| Code | `code_repositories`, `code_commits`, `ai_code_assistance`, `code_reviews`, `version_control`, `pair_programming`, `technical_docs` |
| AI | `ai_chats`, `ai_tutor_sessions` |
| Forum | `forum_posts`, `forum_comments` |
| Career | `interviews`, `resumes`, `jobs` |
| Communication | `roleplay_sessions`, `speech_analyses`, `writing_challenges`, `voice_challenge_sentences`, `communication_submissions`, `communication_tasks`, `language_course_progress`, `problem_statements` |
| HOD | `hod_approvals`, `hod_reports`, `hod_analytics`, `department_stats`, `faculty_performance` |
| Curriculum | `syllabus`, `approvals`, `approval_history`, `approval_templates`, `approval_workflows` |
| Resources | `resources`, `software_licenses`, `resource_requests`, `maintenance`, `resource_history` |
| Reports | `reports`, `scheduled_reports`, `report_templates` |
| Subscription | `licenses`, `edu_credits`, `credit_refill_requests`, `subscription_analytics`, `renewal_quotes` |
| Finance | `credits`, `credit_transactions`, `payments` |
| Misc | `events`, `courses`, `feedback`, `exams`, `study_materials`, `learning_paths`, `announcements`, `files`, `online_compiler`, `quizzes` |
| **Faculty Ops** *(NEW — found in `helpers.py`)* | `faculty_communities`, `faculty_leaves`, `resource_allocations` |

> **Note on `faculty_communities`:** Created by `execute_approved_action()` when HOD approves a community request.  
> **Note on `faculty_leaves` / `resource_allocations`:** Written via `db.faculty_leaves` and `db.resource_allocations` — ad-hoc collections, no dedicated collection variable.

---

## SECTION 20 — Stage 2 Arcade Module (`app/routes/stage2_arcade.py`)

> ⚠️ This entire module was MISSING from the previous inventory. 13 endpoints registered in `main.py`.

### 20.1 Code Battle Arena
- [ ] `POST /api/stage2/arcade/battle/matchmake` — 1v1 matchmaking; returns `room_id`, problem, opponent

### 20.2 AI Boss Fight
- [ ] `POST /api/stage2/arcade/boss/start` — Start fight vs "Bug Monster" (HP: 100); returns 3 problems with damage values
- [ ] `POST /api/stage2/arcade/boss/attack` — Submit `problem_id` + `code`; returns `damage_dealt`

### 20.3 Bug Hunter Challenge
- [ ] `POST /api/stage2/arcade/bughunter/generate` — Gemini generates buggy Python function (JSON: title, description, buggy_code)
- [ ] `POST /api/stage2/arcade/bughunter/verify` — Check if bug is fixed; awards 50 points on pass

### 20.4 AI Interview Simulator
- [ ] `POST /api/stage2/arcade/interview/analyze` — Gemini acts as interviewer; analyzes code for time/space complexity; returns follow-up question

### 20.5 Code Escape Room
- [ ] `POST /api/stage2/arcade/escape/room?level=1` — 3 levels: decode base64 (L1), fix logic (L2), find pattern (L3)

### 20.6 Daily AI Quests
- [ ] `GET /api/stage2/arcade/quests` — Returns 3 daily quests with rewards (50, 30, 40 credits)

### 20.7 Code Speed Run
- [ ] `POST /api/stage2/arcade/speedrun/start` — Returns 3 problems with 300-second timer

### 20.8 Algorithm Builder
- [ ] `GET /api/stage2/arcade/algorithm/blocks` — Returns drag-and-drop code blocks with ordering

### 20.9 AI Code Reviewer
- [ ] `POST /api/stage2/arcade/review` — Gemini reviews code; awards badges: `"Clean Code"`, `"Efficient Coder"`

### 20.10 Real World Mission
- [ ] `POST /api/stage2/arcade/mission/submit` — AI evaluates project submission; returns score + feedback

### 20.11 AI Personal Mentor
- [ ] `GET /api/stage2/arcade/mentor` — Returns weak topic analysis + auto-generated challenge (e.g., Recursion)

---

## SECTION 21 — Daily Quiz System (`app/routes/daily_quiz.py`)

- [ ] `GET /api/quiz-questions?quiz_type=meaning|fill` — Fetch all quiz questions of a type from `communication_tasks` collection
- [ ] `GET /api/daily-quiz-challenge` — Returns today's date-seeded quiz set: **5 meaning + 5 fill-in-blank**
  - **Seeding logic:** `random.seed(str(date.today()))` — same questions for all users on same day
- [ ] `POST /api/daily-challenge/record-completion` — Record completion for `meaning` or `fill` type; updates `user.daily_challenges.{date}.{type}` in MongoDB
- [ ] `GET /api/daily-challenge/status` — Returns `meaning_completed`, `fill_completed`, `completed` (both done)
  - Tracks both quiz types **independently** per day in user document

> ❌ There is **NO APScheduler** generating daily quizzes. The date-seed approach requires no cron job.

---

## SECTION 22 — AI Learning Paths (`app/routes/learning_paths.py`)

- [ ] `POST /api/learning-paths/generate` — Generates personalized learning path via `AIService.generate_learning_path()`
  - Input context: `stage`, `department`, `skills[]`, `weak_areas`, `interests[]`, `career_goals`
  - Falls back to `generate_default_learning_path()` if AI service fails
  - Saved to `learning_paths_collection` with `current_day=1`, `completed_days=[]`, `progress=0`
- [ ] `GET /api/learning-paths` — List user's generated paths (paginated); returns `overview` (200-char preview), `current_day`, `progress %`

---

## SECTION 23 — Language Courses (`app/routes/language_courses.py`)

- [ ] `GET /api/language-courses/progress` — Per-language progress: `completed_exercises`, `total_credits` from `language_course_progress_collection`
- [ ] `POST /api/language-courses/run-code` — Execute code via `CompilerService.execute_code_safely()` + if error: `AIService.code_help()` returns hint
- [ ] `POST /api/language-courses/submit-exercise` — Full graded flow:
  1. Execute code → check success
  2. `AIService.code_review()` → get score (0–100)
  3. Pass if score ≥ 70
  4. If passed: award `score // 10` credits via `update_user_credits()`
  5. Update `language_course_progress_collection` with `$set` + `$inc`

---

## SECTION 24 — Pair Programming REST (`app/routes/pair_programming.py`)

- [ ] `POST /api/pair-programming/sessions` — Create pair session
  - Validates partner exists
  - Creates session document: `session_id`, `user1_id`, `user2_id`, `language`, `duration`, `status=pending`, `code=""`, `cursor_positions={}`, `chat_messages=[]`
  - Sends in-app notification to partner with `session_id`, `inviter_name`, `language`, `duration`
  - Status lifecycle: `pending → active → completed / cancelled`
- [ ] Real-time collaboration happens over **WS `/ws/projects/{session_id}`** channel (Section 11.3)

---

## SECTION 25 — Badges (`app/routes/badges.py`)

- [ ] `GET /api/badges` — Fetch all user badges from `badges_collection`, grouped by `category`
  - Returns: `badges[]`, `total_badges`, `categories{}` (dict keyed by category name)
  - Badge auto-created on registration: `"Welcome Aboard! 🎉"`

---

## SECTION 26 — Infrastructure Notes (Corrected)

### 26.1 Middleware (ONLY CORS — nothing else)
> ❌ There is **NO rate limiting middleware** in the current codebase.
> ❌ There is **NO request logging middleware**.
> ❌ There is **NO compression (GZip) middleware**.

- [ ] Only middleware: `CORSMiddleware(allow_origins=["*"], allow_credentials=True)`
- [ ] **For Spring Boot:** Add `@CrossOrigin` or `WebMvcConfigurer` CORS config. Add rate limiting (Bucket4j or Spring Cloud Gateway) as a **new feature**.

### 26.2 Email & SMS (Stub — NOT implemented)
> ⚠️ `send_email_async()` in `helpers.py` is a **logger stub only** — no email is ever sent.
> ⚠️ `send_sms_async()` is also a logger stub.

- [ ] **For Spring Boot:** Implement real email via Spring Mail + JavaMailSender (SMTP/SendGrid/Mailgun)
- [ ] Email is called from: `auth.py` (welcome + reset password), `hod/faculty.py` (new faculty welcome), `notification_service.py` (general alerts)
- [ ] Email triggers to implement: welcome, password reset, faculty onboarding

### 26.3 Scheduled Jobs (NONE in current system)
> ❌ **No APScheduler. No cron jobs. No scheduled tasks exist in the codebase.**

- [ ] Daily quiz rotation: handled by `random.seed(date.today())` — no scheduler needed
- [ ] **For Spring Boot:** If scheduled jobs are needed in the new system, use `@Scheduled` with `fixedRate` or `cron` expressions — these will be **new features**, not ports

### 26.4 Previously Missing Details (Still Valid)
- [ ] **Login streak credit formula** (`10 + streak × 2`) — needs Java logic port
- [ ] **Device history tracking** (last 10 logins stored in array)
- [ ] **Peer-to-peer credit transfer** (10–1000 range, bilateral logging)
- [ ] **Credit spend / marketplace purchase recording**
- [ ] **Campus email auto-generation** (`name@campus.com`)
- [ ] **Group file uploads** (per-group shared folder)
- [ ] **Group join request workflow** (pending → admin approve/reject → notification)
- [ ] **Career leaderboard** (separate from coding leaderboard)
- [ ] **Repository contributor aggregation pipeline** (commit counts per author)
- [ ] **Notification broadcast flag** (sent to all users)
- [ ] **WS project collaboration** (cursor tracking, code diffs, team chat)
- [ ] **WS challenge subscription** (real-time active challenge list by stage)
- [ ] **AI chat context** saved to `ai_chats` collection after each WS exchange
- [ ] **`AIModelWrapper.__bool__` = always True** (no offline state possible)
- [ ] **BlackBox response scrubbing regex** (source annotation cleanup)
- [ ] **All 5 WS channels** are separate endpoints, not sub-routes
- [ ] **XP Level formula** = progressive ladder (1000 → 1500 → 2250...), NOT `floor(XP/100)+1`
- [ ] **Docker → Local fallback** in CompilerService (must be replicated in Spring Boot)
- [ ] **AI Grading endpoints** are mock stubs — must be replaced with real AI calls in Spring Boot
