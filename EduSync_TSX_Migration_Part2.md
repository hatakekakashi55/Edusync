# EduSync 4.0 — Full-Stack TypeScript Migration Guide (Part 2/2)
### React TSX Frontend + Node.js/Express TypeScript Backend

> Continuation from Part 1. Covers Sections 14–26 + module dependency map.

---

## SECTION 14 — Faculty Dashboard

### Backend: `src/routes/faculty/`

#### Core Faculty Routes — `src/routes/faculty/classrooms.router.ts`
- [ ] `POST /api/faculty/classrooms` — create + auto-generate 6-char join code
- [ ] `GET /api/faculty/classrooms` — own classrooms with `student_count`
- [ ] `GET /api/faculty/students` — student directory with averages + challenge stats

#### Materials & Assignments — `src/routes/faculty/materials.router.ts`
- [ ] `POST /api/faculty/materials` — Multer upload: PDFs, slides, code files
- [ ] `POST /api/faculty/assignments` — `{ title, description, due_date, test_cases, code_template, language, reward_credits }`
- [ ] `GET /api/faculty/assignments/:id/submissions` — all student submissions

#### Attendance & Schedule — `src/routes/faculty/attendance.router.ts`
- [ ] `GET/POST /api/faculty/attendance` — log daily; export as CSV
- [ ] `GET/POST /api/faculty/schedule` — timetable + exam dates CRUD

#### Faculty AI — `src/routes/faculty/ai.router.ts`
- [ ] `POST /api/faculty/ai` — lesson plan / quiz / test question generation via INIXA

#### Faculty Communities — `src/routes/faculty/communities.router.ts`
- [ ] `GET /api/faculty/communities` — browse faculty-only forums

#### 14.A AI Grading — `src/routes/aiGrading.router.ts`
> ⚠️ **Replace FastAPI stubs with real INIXA AI calls in TypeScript**

- [ ] `POST /api/ai/grade-submission` — real AI: grade 0-100, plagiarism %, quality metrics (faculty only)
  - Prompt: send submission code + assignment description to `AIService.generate()`
  - Parse structured JSON response for grade, feedback
- [ ] `POST /api/ai/bulk-grade` — loop submissions, call AI for each, return array
- [ ] `POST /api/ai/check-plagiarism` — AI comparison of submission vs past submissions
- [ ] `POST /api/ai/generate-feedback` — AI: `{ suggestions, strengths, improvements }`
- [ ] `POST /api/ai/analyze-patterns` — AI: grade distribution + common mistakes across class

#### 14.B Faculty Approvals — `src/routes/faculty/approvals.router.ts`
- [ ] `POST /api/approvals/request` — generic HOD approval + notification
- [ ] `POST /api/approvals/faculty-community` — request community (HOD must approve)
- [ ] `POST /api/approvals/faculty-leave` — auto-route to dept HOD; calc `leave_days = diff(start, end)`
- [ ] `POST /api/approvals/resource-request` — hardware request to HOD

### Frontend: `src/pages/faculty/`
- [ ] `FacultyDashboard.tsx` — summary cards: classrooms, pending submissions, schedule
- [ ] `ClassroomManager.tsx` — create/manage classrooms + join code display
- [ ] `AssignmentCreator.tsx` — form with test case builder
- [ ] `SubmissionsViewer.tsx` — table with AI grade button
- [ ] `AttendanceTracker.tsx` — date-picker + student checklist + CSV export
- [ ] `AIAssistantPanel.tsx` — lesson plan / quiz generator UI
- [ ] `ApprovalsPage.tsx` — submit leave/community/resource requests

---

## SECTION 15 — HOD Dashboard

### Backend: `src/routes/hod/`

- [ ] `GET /api/hod/dashboard` — aggregate: pass rates, avg marks, attendance % (MongoDB pipeline)
- [ ] `GET /api/hod/faculty` — list (filter: status, designation, search text)
- [ ] `POST /api/hod/faculty` — register faculty: auto temp-password, welcome email, notification
- [ ] `GET /api/hod/faculty/:id` — full profile + performance stats
- [ ] `GET/POST/PUT /api/hod/curriculum` — syllabus CRUD
  - State machine: `draft → review → hod_approved → registrar_finalized`
- [ ] `GET/POST /api/hod/approvals` — course proposals, credit refills, bookings
- [ ] `GET/POST /api/hod/resources` — register + track hardware assets
- [ ] `GET/POST /api/hod/resource-requests` — review/approve faculty hardware requests
- [ ] `GET/POST /api/hod/software-licenses` — keys, expiry, user assignments, renewals
- [ ] `GET/POST /api/hod/maintenance` — lab maintenance: log, schedule, track status
- [ ] `POST /api/hod/reports` — generate PDF academic performance report
- [ ] `POST /api/hod/ai` — natural language HOD audit queries → INIXA AI

### Frontend: `src/pages/hod/`
- [ ] `HodDashboard.tsx` — dept KPI overview
- [ ] `FacultyManagement.tsx` — table + register faculty modal
- [ ] `CurriculumEditor.tsx` — syllabus form + state machine stepper
- [ ] `ApprovalsBoard.tsx` — pending approvals queue
- [ ] `ResourceTracker.tsx` — hardware + software license tables
- [ ] `ReportsPage.tsx` — generate + download PDF
- [ ] `HodAIConsole.tsx` — natural language query interface

---

## SECTION 16 — Admin Dashboard

### Backend: `src/routes/admin/`

- [ ] `GET/POST/PUT/DELETE /api/admin/users` — full user CRUD
- [ ] `POST /api/admin/users/:id/suspend` — set `is_active: false`
- [ ] `POST /api/admin/users/:id/reactivate` — set `is_active: true`
- [ ] `GET/POST /api/admin/challenges` — author global coding + communication challenges
- [ ] `GET/POST /api/admin/stage1` — configure: speech audio files, vocab words, roleplay scripts
- [ ] `GET /api/admin/stats` — platform metrics: active users, challenge counts, credit flow

### Frontend: `src/pages/admin/`
- [ ] `AdminDashboard.tsx` — platform-wide metrics
- [ ] `UserManagement.tsx` — searchable table, suspend/reactivate actions
- [ ] `ChallengeAuthor.tsx` — form for all challenge types
- [ ] `Stage1Config.tsx` — vocab word manager, roleplay script editor

---

## SECTION 17 — Career Preparation (Stage 4)

### Backend: `src/routes/career/`

- [ ] `GET /api/career/progress` — career readiness score + milestones
- [ ] `POST /api/career/interviews` — start AI mock interview session
- [ ] `GET /api/career/interviews/:id` — session detail + feedback
- [ ] `POST /api/career/interviews/:id/complete` — end + streaming evaluation report (SSE)
- [ ] `GET /api/career/resume` — get parsed resume + score
- [ ] `POST /api/career/resume` — Multer upload → AI parse → score + section recommendations
- [ ] `GET /api/linkedin/checklist` — task completion status
- [ ] `GET /api/linkedin/analyze` — completeness score (bio, picture, skills, experience, education, recommendations)
- [ ] `GET /api/linkedin/jobs` — RapidAPI LinkedIn Jobs → local DB fallback
- [ ] `GET /api/career/portfolio` — portfolio from repos + skills + badges
- [ ] `POST /api/career/portfolio` — generate portfolio page
- [ ] `GET /api/career/alumni` — alumni directory
- [ ] `GET /api/career/applications` — job application tracker

### Frontend: `src/pages/career/`
- [ ] `CareerPage.tsx` — readiness score ring, milestone list
- [ ] `MockInterviewPage.tsx` — AI interview chat with streaming response
- [ ] `ResumeAnalyzer.tsx` — upload + score display + section tips
- [ ] `LinkedInTools.tsx` — checklist + completeness meter
- [ ] `JobBoard.tsx` — job search results, application tracker
- [ ] `PortfolioGenerator.tsx` — preview + publish portfolio

---

## SECTION 18 — B2B Licensing & Subscription

### Backend: `src/routes/licensing.router.ts`

- [ ] `POST /api/licensing/activate` — validate hashed license key, student cap, expiry
- [ ] `GET /api/licensing/status` — current license validity + remaining days
- [ ] `POST /api/edu-credits/request` — HOD submits dept credit refill request
- [ ] `POST /api/edu-credits/approve` — Admin approves + provisions credits
- [ ] `GET /api/edu-credits/usage` — credit usage by dept / classroom / student

### Frontend: `src/pages/licensing/`
- [ ] `LicenseStatus.tsx` — validity card, student usage gauge
- [ ] `EduCreditsPage.tsx` — request + approve flow (role-gated)

---

## SECTION 19 — Database (Mongoose Schemas)

### `src/models/` — one file per schema group

| File | Mongoose Models |
|---|---|
| `user.model.ts` | `User` |
| `badge.model.ts` | `Badge` |
| `analytics.model.ts` | `Analytics` |
| `notification.model.ts` | `Notification` |
| `certificate.model.ts` | `Certificate` |
| `challenge.model.ts` | `Challenge`, `Submission`, `CodingChallenge`, `Leaderboard` |
| `classroom.model.ts` | `Classroom`, `FacultyClassroom`, `Assignment`, `FacultyAssignment`, `FacultySubmission`, `Attendance`, `FacultyAttendance`, `FacultySchedule` |
| `group.model.ts` | `Group`, `GroupMessage`, `GroupRequest` |
| `repository.model.ts` | `CodeRepository`, `CodeCommit`, `AICodeAssistance`, `CodeReview`, `PairProgramming`, `TechnicalDoc` |
| `ai.model.ts` | `AIChat`, `AITutorSession` |
| `forum.model.ts` | `ForumPost`, `ForumComment` |
| `career.model.ts` | `Interview`, `Resume`, `Job` |
| `communication.model.ts` | `RoleplaySession`, `SpeechAnalysis`, `WritingChallenge`, `VoiceChallenceSentence`, `CommunicationSubmission`, `CommunicationTask`, `LanguageCourseProgress`, `ProblemStatement` |
| `hod.model.ts` | `HODApproval`, `HODReport`, `HODAnalytics`, `DepartmentStats`, `FacultyPerformance` |
| `curriculum.model.ts` | `Syllabus`, `Approval`, `ApprovalHistory`, `ApprovalTemplate`, `ApprovalWorkflow` |
| `resource.model.ts` | `Resource`, `SoftwareLicense`, `ResourceRequest`, `Maintenance`, `ResourceHistory` |
| `report.model.ts` | `Report`, `ScheduledReport`, `ReportTemplate` |
| `subscription.model.ts` | `License`, `EduCredit`, `CreditRefillRequest`, `SubscriptionAnalytics`, `RenewalQuote` |
| `finance.model.ts` | `Credit`, `CreditTransaction`, `Payment` |
| `misc.model.ts` | `Event`, `Course`, `Feedback`, `Exam`, `StudyMaterial`, `LearningPath`, `Announcement`, `File`, `OnlineCompiler`, `Quiz` |
| `facultyOps.model.ts` | `FacultyCommunity`, `FacultyLeave`, `ResourceAllocation` |

> Total: **53+ collections** — each maps to one Mongoose schema with `timestamps: true`

---

## SECTION 20 — Stage 2 Arcade Module

### Backend: `src/routes/stage2/arcade.router.ts`

- [ ] `POST /api/stage2/arcade/battle/matchmake` — 1v1 match: return `room_id`, problem, opponent
- [ ] `POST /api/stage2/arcade/boss/start` — Bug Monster (HP 100), return 3 problems with damage values
- [ ] `POST /api/stage2/arcade/boss/attack` — `{ problem_id, code }` → compile → `damage_dealt`
- [ ] `POST /api/stage2/arcade/bughunter/generate` — AI generates buggy Python: `{ title, description, buggy_code }`
- [ ] `POST /api/stage2/arcade/bughunter/verify` — compile fixed code → award 50pts if pass
- [ ] `POST /api/stage2/arcade/interview/analyze` — AI interviewer: time/space complexity + follow-up
- [ ] `POST /api/stage2/arcade/escape/room?level=1` — L1: base64 decode, L2: fix logic, L3: find pattern
- [ ] `GET /api/stage2/arcade/quests` — 3 daily quests with rewards (50, 30, 40 credits)
- [ ] `POST /api/stage2/arcade/speedrun/start` — 3 problems, 300s timer
- [ ] `GET /api/stage2/arcade/algorithm/blocks` — drag-and-drop code blocks with correct ordering
- [ ] `POST /api/stage2/arcade/review` — AI code review → award badges: `'Clean Code'`, `'Efficient Coder'`
- [ ] `POST /api/stage2/arcade/mission/submit` — AI evaluates project → score + feedback
- [ ] `GET /api/stage2/arcade/mentor` — weak topic analysis + auto-generated challenge

### Frontend: `src/pages/stage2/`
- [ ] `ArcadePage.tsx` — game mode selector grid
- [ ] `BattleArena.tsx` — 1v1 real-time (Socket.io)
- [ ] `BossFight.tsx` — HP bar + code submission
- [ ] `BugHunter.tsx` — side-by-side buggy/fixed editor
- [ ] `EscapeRoom.tsx` — 3-level puzzle UI
- [ ] `SpeedRun.tsx` — countdown timer + problem list
- [ ] `AlgorithmBuilder.tsx` — drag-and-drop block ordering
- [ ] `DailyQuests.tsx` — quest cards with progress

---

## SECTION 21 — Daily Quiz System

### Backend: `src/routes/dailyQuiz.router.ts`

- [ ] `GET /api/quiz-questions?quiz_type=meaning|fill` — all questions from `communication_tasks`
- [ ] `GET /api/daily-quiz-challenge` — today's seeded set: 5 meaning + 5 fill
  ```typescript
  // Seed logic: deterministic shuffle by date string
  const seed = new Date().toISOString().split('T')[0]; // 'YYYY-MM-DD'
  // Use seedrandom npm package or custom LCG seeded with date hash
  ```
- [ ] `POST /api/daily-challenge/record-completion` — `{ quiz_type: 'meaning'|'fill' }` → update `user.daily_challenges[date][type] = true`
- [ ] `GET /api/daily-challenge/status` — `{ meaning_completed, fill_completed, completed: both }`

> ❌ No cron job needed — date-seed handles rotation automatically.

### Frontend: `src/pages/quiz/`
- [ ] `DailyQuizPage.tsx` — meaning + fill tabs, submit, result display
- [ ] Show credit reward animation on completion

---

## SECTION 22 — AI Learning Paths

### Backend: `src/routes/learningPaths.router.ts`

- [ ] `POST /api/learning-paths/generate`
  - Input: `{ stage, department, skills, weak_areas, interests, career_goals }`
  - Call `AIService.generateLearningPath(context)`
  - On AI failure: `generateDefaultLearningPath(stage, department)`
  - Save: `{ user_id, path_data, current_day: 1, completed_days: [], progress: 0 }`
- [ ] `GET /api/learning-paths?page=1` — list user paths; include `overview` (first 200 chars), `current_day`, `progress %`

### Frontend: `src/pages/learningPaths/`
- [ ] `LearningPathsPage.tsx` — list generated paths, generate new button
- [ ] `PathDetailPage.tsx` — day-by-day curriculum, mark complete

---

## SECTION 23 — Language Courses

### Backend: `src/routes/languageCourses.router.ts`

- [ ] `GET /api/language-courses/progress` — per-language: `{ completed_exercises, total_credits }`
- [ ] `POST /api/language-courses/run-code` — compile + if error: `AIService.codeHelp()` → hint
- [ ] `POST /api/language-courses/submit-exercise`
  ```
  1. CompilerService.execute(code, language)
  2. If success → AIService.codeReview() → score (0-100)
  3. Pass if score >= 70
  4. Award credits: Math.floor(score / 10)
  5. Update language_course_progress: $inc completed_exercises, $inc total_credits
  ```

### Frontend: `src/pages/languageCourses/`
- [ ] `LanguageCoursesPage.tsx` — language track grid (Python, JS, Java, C, C++, Go, Rust)
- [ ] `CourseExercise.tsx` — editor + run + submit + AI hint panel

---

## SECTION 24 — Pair Programming

### Backend: `src/routes/pairProgramming.router.ts`

- [ ] `POST /api/pair-programming/sessions`
  - Validate partner `user_id` exists
  - Create: `{ session_id, user1_id, user2_id, language, duration, status: 'pending', code: '', cursor_positions: {}, chat_messages: [] }`
  - Notify partner via `NotificationService`: `{ session_id, inviter_name, language, duration }`
  - Lifecycle: `pending → active → completed | cancelled`
- [ ] Real-time via Socket.io `/projects` namespace with `session_id` as room (Section 11.3)

### Frontend: `src/pages/pairProgramming/`
- [ ] `PairSessionLauncher.tsx` — partner search + session create
- [ ] `PairEditor.tsx` — collaborative Monaco editor + cursor overlays + chat panel

---

## SECTION 25 — Badges

### Backend: `src/routes/badges.router.ts`

- [ ] `GET /api/badges` — all user badges from `badges` collection, grouped by `category`
  ```typescript
  // Response shape:
  { badges: Badge[], total_badges: number, categories: Record<string, Badge[]> }
  ```
- [ ] Auto-create on registration: `{ name: 'Welcome Aboard! 🎉', category: 'milestone', user_id }`

### Frontend: `src/pages/badges/`
- [ ] `BadgesPage.tsx` — category tabs, badge grid with earned/locked states

---

## SECTION 26 — Infrastructure & Configuration

### Backend Config: `src/config/`

#### 26.1 CORS — `src/middleware/cors.middleware.ts`
```typescript
import cors from 'cors';
app.use(cors({ origin: '*', credentials: true }));
// For production: restrict origin to frontend domain
```
> ❌ No rate limiting, logging, or compression in original — add these as NEW features:
- [ ] **NEW:** Rate limiting via `express-rate-limit` (not in original FastAPI)
- [ ] **NEW:** Request logging via `morgan`
- [ ] **NEW:** Response compression via `compression`

#### 26.2 Email — `src/services/email.service.ts`
> ⚠️ Original FastAPI `send_email_async()` is a logger stub — never sends real email.
> **Implement real email in TypeScript:**

```typescript
import nodemailer from 'nodemailer';
// or @sendgrid/mail for SendGrid
// or mailgun-js for Mailgun

const transporter = nodemailer.createTransport({ /* SMTP config */ });

async function sendWelcomeEmail(user: User): Promise<void>
async function sendPasswordResetEmail(user: User, token: string): Promise<void>
async function sendFacultyOnboardingEmail(faculty: User, tempPassword: string): Promise<void>
```
- [ ] Triggered from: `auth.controller.ts` (welcome, reset), `hod.controller.ts` (faculty onboard), `notification.service.ts` (alerts)

#### 26.3 Scheduled Jobs — `src/jobs/`
> ❌ No APScheduler in original — date-seed handles quiz rotation.
> Add NEW scheduled jobs if needed using `node-cron`:

```typescript
import cron from 'node-cron';
// Example: daily leaderboard refresh at midnight
cron.schedule('0 0 * * *', () => leaderboardService.refreshMonthly());
```

#### 26.4 Redis — `src/config/redis.ts`
```typescript
import { createClient } from 'redis';
const redis = createClient({ url: process.env.REDIS_URL });
// Used for:
// - refresh tokens: SET refresh:{userId} {tokenId} EX {seconds}
// - daily credit gate: SET daily_credit:{userId}:{date} 1 EX 86400
// - AI status cache
```

#### 26.5 Environment Variables — `.env`
```
MONGODB_URI=
REDIS_URL=
JWT_SECRET=
REFRESH_TOKEN_EXPIRE_DAYS=30
AI_TIMEOUT=90
DOCKER_CPU=1.0
DOCKER_MEMORY=512m
TIMEOUT_SECONDS=30
SMTP_HOST=
SMTP_PORT=
SMTP_USER=
SMTP_PASS=
RAPIDAPI_KEY=
PORT=5000
```

#### 26.6 App Entry — `src/app.ts` + `src/server.ts`
```typescript
// app.ts — Express app setup
import express from 'express';
import { createServer } from 'http';
import { Server as SocketServer } from 'socket.io';

const app = express();
const httpServer = createServer(app);
const io = new SocketServer(httpServer, { cors: { origin: '*' } });

// Middleware
app.use(cors(...));
app.use(express.json({ limit: '50mb' }));

// Routes
app.use('/api/auth', authRouter);
app.use('/api/users', usersRouter);
// ... all routers

// Socket.io namespaces
registerMainSocket(io);
registerChallengesSocket(io);
registerProjectsSocket(io);
registerStage3Socket(io);
registerRoleplaySocket(io);

export { app, httpServer, io };
```

---

## MODULE DEPENDENCY MAP

```
edusync-frontend (React TSX)
├── depends on → edusync-backend REST API (Axios)
├── depends on → edusync-backend Socket.io (socket.io-client)
└── depends on → edusync-shared types

edusync-backend (Express TS)
├── services/ai.service.ts        ← used by: challenges, stage1, stage2, faculty, hod, career
├── services/compiler.service.ts  ← used by: compiler, challenges, language-courses, stage2
├── services/speech.service.ts    ← used by: stage1/listening, stage1/speaking, challenges
├── services/email.service.ts     ← used by: auth, hod, notifications
├── utils/levelCalc.ts            ← used by: credits, profile, leaderboard
├── utils/creditHelpers.ts        ← used by: credits, challenges, quiz, stage1, stage2
└── services/notification.service.ts ← used by: auth, groups, credits, pair-programming, hod
```

---

## BUILD ORDER (Recommended for Module Splitting)

```
Phase 1 — Core Infrastructure
  1. edusync-shared: types, interfaces
  2. backend: app.ts, config, middleware, models, auth module
  3. frontend: Vite setup, authStore, LoginPage, RegisterPage

Phase 2 — Student Core
  4. backend: student dashboard, classrooms, assignments, compiler
  5. frontend: StudentDashboard, CompilerPage, AssignmentPages

Phase 3 — Learning Modules
  6. backend: stage1, stage2, challenges, daily-quiz, language-courses
  7. frontend: Stage1Pages, Stage2ArcadePage, ChallengePage

Phase 4 — Collaboration
  8. backend: groups, websockets (all 5 namespaces), pair-programming, repositories
  9. frontend: GroupChat, PairEditor, RepoPages

Phase 5 — Faculty & HOD
  10. backend: faculty routes, hod routes, ai-grading (real implementation)
  11. frontend: FacultyDashboard, HODDashboard

Phase 6 — Admin & Career
  12. backend: admin, career, linkedin, licensing
  13. frontend: AdminDashboard, CareerPage, LicensingPage

Phase 7 — Economy & Gamification
  14. backend: credits, leaderboard, badges, learning-paths
  15. frontend: CreditsDashboard, LeaderboardPage, BadgesPage
```

---

## KEY PORTING RULES (FastAPI → Express TS)

| FastAPI Pattern | Express TS Equivalent |
|---|---|
| `@app.post(path)` | `router.post(path, controller)` |
| `Depends(get_current_user)` | `authMiddleware` function |
| `BackgroundTasks.add_task()` | `setImmediate(() => asyncFn())` or Bull queue |
| `asyncio.sleep(0.02)` | `await new Promise(r => setTimeout(r, 20))` |
| `motor` (async MongoDB) | `mongoose` with async/await |
| `redis.set(k, v, ex=N)` | `redis.setEx(k, N, v)` |
| `websocket.send_json()` | `socket.emit(event, data)` |
| `websocket.send_text()` | `socket.emit('token', char)` |
| `StreamingResponse` | Express `res.write()` SSE or Socket.io streaming |
| Pydantic models | Zod schemas + TypeScript interfaces |
| FastAPI `File(...)` upload | Multer middleware |
| `random.seed(date)` | `seedrandom` npm package |
