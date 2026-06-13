# EduSync 4.0 — Full-Stack TypeScript Migration Guide (Part 1/2)
### React TSX Frontend + Node.js/Express TypeScript Backend

> **Stack:** React 18 + TypeScript (Vite) · Express.js + TypeScript · MongoDB (Mongoose) · Redis · Socket.io · JWT
> **Source-verified from:** `app/routes/`, `app/services/`, `app/models/`, `app/database.py`
> **Last updated:** June 9, 2026

---

## MODULE SPLIT PLAN

| Module Repo | Contents |
|---|---|
| `edusync-frontend` | React TSX — all UI pages, components, hooks, stores |
| `edusync-backend` | Express TS — all REST APIs, WebSockets, services |
| `edusync-shared` | Shared TypeScript types/interfaces used by both |

### Backend Folder Structure (Express TS)
```
src/
  routes/          # Express routers (one file per section)
  controllers/     # Business logic handlers
  services/        # AI, Compiler, Speech, Notification, etc.
  models/          # Mongoose schemas
  middleware/      # auth, cors, errorHandler
  utils/           # helpers, creditHelpers, levelCalc
  websockets/      # Socket.io namespaces
  config/          # env, langConfig, creditConfig
  types/           # shared TS interfaces
  app.ts
  server.ts
```

### Frontend Folder Structure (React TSX + Vite)
```
src/
  pages/           # One folder per dashboard role
  components/      # Shared UI components
  hooks/           # Custom React hooks (useAuth, useSocket, etc.)
  stores/          # Zustand stores per domain
  services/        # Axios API clients per module
  types/           # Shared interfaces (from edusync-shared)
  utils/           # formatters, levelCalc, creditCalc
  App.tsx
  main.tsx
```

---

## SECTION 1 — Authentication & Session System

### Backend: `src/routes/auth.router.ts` + `src/controllers/auth.controller.ts`

#### 1.1 POST `/api/auth/register`
- [ ] Duplicate email check: `User.findOne({ email })`
- [ ] Duplicate roll number check (students): sparse unique index on `roll_number`
- [ ] BCrypt hash: `bcrypt.hash(password, 12)`
- [ ] Auto-generate `campus_email`: `name.toLowerCase().replace(/\s+/g,'.') + '@campus.com'`
- [ ] Auto-assign student fields on create:
  - `stage: 'freshie'`, `credits: 0`, `xp: 0`, `level: 1`
  - `daily_login_streak: 0`, `weekly_login_streak: 0`
  - `current_stage_progress: 0`, `completed_challenges: 0`
  - `weak_areas: []`, `strengths: []`, `skills: []`, `interests: []`
  - `badges: []`, `achievements: []`, `mood_history: []`
  - `notification_preferences: { email, push, sms, challenge_reminders, deadline_alerts }`
- [ ] Auto-create `badges` doc: `{ name: 'Welcome Aboard! 🎉', user_id, earned_at }`
- [ ] Auto-create `analytics` doc for user
- [ ] Welcome email: `emailService.sendWelcome(user)` (async, non-blocking)
- [ ] In-app welcome notification via `NotificationService.create()`

#### 1.2 POST `/api/auth/login`
- [ ] `bcrypt.compare(password, user.password_hash)`
- [ ] Check `user.is_active` → 403 if false
- [ ] Daily streak: `dayjs().diff(last_login, 'day')` → 1 = continue, >1 = reset
- [ ] Weekly streak: diff ≤ 7 days → continue, else reset
- [ ] Login credit formula: `10 + (daily_streak * 2)` credits → Redis-gated (1/day)
- [ ] Device history: push to `device_history` array, `$slice: -10`
- [ ] `$inc analytics.total_sessions`
- [ ] Issue `access_token` (JWT, 24h) + `refresh_token` (JWT, 30d, HS256)
- [ ] Store refresh token in Redis: `SET refresh:{userId} {tokenId} EX {30*86400}`
- [ ] Background: `notificationService.loginSuccess(userId)`
- [ ] Return: `{ user_id, email, full_name, user_type, stage, department, year, credits, xp, level, daily_streak, profile_picture, theme, is_verified, role, access_token, refresh_token }`

#### 1.3 POST `/api/auth/refresh`
- [ ] Decode JWT, verify `payload.type === 'refresh'`
- [ ] `redis.get('refresh:' + userId)` → compare token ID
- [ ] Issue new `access_token` (24h)

#### 1.4 POST `/api/auth/logout`
- [ ] `redis.del('refresh:' + userId)`

### Frontend: `src/pages/auth/`
- [ ] `LoginPage.tsx` — email/password form, token storage in `localStorage`
- [ ] `RegisterPage.tsx` — role selector (student/faculty), form validation
- [ ] `useAuth.ts` hook — wraps login/register/logout, stores user in Zustand `authStore`
- [ ] Auto-refresh access token on 401 via Axios interceptor

---

## SECTION 2 — User Profiles & Settings

### Backend: `src/routes/users.router.ts`

#### 2.1 GET/PUT `/api/users/me`
- [ ] GET: return full user doc (exclude `password_hash`)
- [ ] PUT: allow update of: `full_name`, `phone`, `bio`, `designation`, `expertise`, `office`, `office_hours`, `qualifications`, `publications`, `research_areas`, `courses_teaching`, `joining_date`, `preferred_language`, `timezone`, `learning_style`, `notification_preferences`

#### 2.2 POST `/api/users/me/avatar`
- [ ] Multer multipart, max 50MB
- [ ] Allowed MIME types: pdf, jpg, jpeg, png, mp3, mp4, txt, py, java, cpp, c, js, html, css, md, json, csv, xlsx, docx
- [ ] Store URL in `user.profile_picture`

#### 2.3 GET `/api/users/me/stats`
- [ ] Return: `{ xp, level, credits, total_sessions, total_time_spent, completed_challenges, projects_completed, current_stage_progress }`

### Frontend: `src/pages/profile/`
- [ ] `ProfilePage.tsx` — view/edit form
- [ ] `AvatarUpload.tsx` — drag-drop file upload component
- [ ] `StatsCard.tsx` — XP bar, level badge, credits display

---

## SECTION 3 — INIXA AI Engine (5-Engine Fallback)

### Backend: `src/services/ai.service.ts`

#### 3.1 Fallback Chain
```typescript
const ENGINES = [
  { name: 'DuckDuckGo', url: 'https://bitter-sea-46dc.keerthan4531.workers.dev/chat', model: 'gpt-4o-mini' },
  { name: 'LLM7',       url: 'https://api.llm7.io/v1/chat/completions',               model: 'gpt-4o-mini' },
  { name: 'BlackBox',   url: 'https://api.blackbox.ai/api/chat',                      model: 'default'     },
  { name: 'Pollinations-OAI', url: 'https://text.pollinations.ai/openai',             model: 'openai'      },
  { name: 'Pollinations',     url: 'https://text.pollinations.ai',                    model: 'openai'      },
];
```

#### 3.2 Engine Behaviors
- [ ] **DuckDuckGo:** Parse both `{ message }` JSON and `data: {...}` SSE formats
- [ ] **BlackBox:** Strip `$~~~$...$~~~$` and `[^N^]` markers from response via regex
- [ ] **All engines:** Reject if response contains `<html` or is empty → try next
- [ ] Global timeout: `AI_TIMEOUT` env (default 90s) via `AbortController`
- [ ] Retry: 3 attempts, backoff: 1s → 2s → 4s
- [ ] Track `lastEngine: string` — return in API response as `engine_used`

#### 3.3 GET `/api/ai/status`
- [ ] Ping DDG → BlackBox → Pollinations with 5s timeout each
- [ ] Return `{ online: boolean, engine: string }`

#### 3.4 `AIWrapper` class
```typescript
class AIWrapper {
  async generate(prompt: string): Promise<{ text: string; engine: string }>
  // always returns something; never throws (falls back silently)
  get isAvailable(): boolean { return true; } // always true
}
```

#### 3.5 Image Generation
- [ ] `GET https://image.pollinations.ai/prompt/{encodeURIComponent(prompt)}`
- [ ] Used by: vocabulary builder, writing picture-prompt challenge

---

## SECTION 4 — Docker Compiler Sandbox

### Backend: `src/services/compiler.service.ts`

#### 4.1 Language Config
```typescript
const LANG_CONFIG = {
  python:     { image: 'python:3.11-slim',  run: 'python {file}' },
  javascript: { image: 'node:18-slim',       run: 'node {file}' },
  java:       { image: 'openjdk:17-slim',    compile: 'javac {file}', run: 'java Main' },
  c:          { image: 'gcc:12',             compile: 'gcc {file} -o main', run: './main' },
  cpp:        { image: 'gcc:12',             compile: 'g++ {file} -o main', run: './main' },
  go:         { image: 'golang:1.21',        run: 'go run {file}' },
  rust:       { image: 'rust:1.70',          compile: 'rustc {file} -o main', run: './main' },
};
// TypeScript and Ruby NOT supported
```

#### 4.2 Docker Safety
- [ ] CPU: `--cpus=1.0`
- [ ] Memory: `--memory=512m`
- [ ] Timeout: 30s (`child_process` kill signal)
- [ ] Network: `--network none`
- [ ] Caps: `--cap-drop ALL --security-opt no-new-privileges`
- [ ] PIDs: `--pids-limit 64`

#### 4.3 Docker → Local Fallback
- [ ] On startup: `exec('docker info')` → cache result as `dockerAvailable: boolean`
- [ ] If false → use `child_process.spawn()` with same language commands
- [ ] Response includes `execution_mode: 'docker' | 'local'`

#### 4.4 Endpoints
- [ ] `POST /api/compiler/execute` — body: `{ code, language, input_data?, test_cases? }`
- [ ] `GET /api/compiler/history?limit=20` — last N runs for auth user (max 100)
- [ ] Auto-save to `online_compiler` collection: `{ user_id, code, language, output, success, executed_at }`

### Frontend: `src/pages/compiler/`
- [ ] `CompilerPage.tsx` — Monaco editor, language selector, run button, output panel
- [ ] Show `execution_mode` badge (Docker / Local)
- [ ] `HistoryPanel.tsx` — sidebar with past runs

---

## SECTION 5 — Challenges & Submissions

### Backend: `src/routes/challenges.router.ts`

#### 5.1 GET `/api/challenges`
- [ ] Query params: `stage`, `challenge_type`, `difficulty`, `language`, `tags` (comma-sep)
- [ ] Pagination: `limit` (max 100), `skip`
- [ ] Students: auto-filter by `user.stage`
- [ ] Inject `user_status: { attempted, completed, score }` per challenge

#### 5.2 GET `/api/challenges/:id`
- [ ] Return challenge + last 10 user submissions

#### 5.3 POST `/api/challenges/:id/submit`
Three modes:
- [ ] **Voice:** Multer audio → `SpeechService.speechToText()` → `AIService.analyzeEnglish()` → score; pass if ≥ 70
- [ ] **Coding:** `CompilerService.execute()` → `AIService.codeReview()` → score = `passed/total * 100`; pass if ≥ 70
- [ ] **Text/Quiz:** case-insensitive exact match → 100 or 0

#### 5.4 Credit Reward
- [ ] `$inc credits` by `challenge.credits_reward`
- [ ] `$inc completed_challenges`
- [ ] `$inc current_stage_progress` by 10

---

## SECTION 6 — Credit & XP Economy

### Backend: `src/utils/creditHelpers.ts` + `src/routes/credits.router.ts`

#### 6.1 Credit Config
```typescript
const CREDIT_CONFIG = {
  daily_login:        { base: 10, bonus: 70 },
  voice_challenge:    { base: 50, bonus: 0.5 }, // per score %
  reading_challenge:  { base: 50, bonus: 0.5 },
  listening_challenge:{ base: 50, bonus: 0.5 },
  writing_challenge:  { base: 75, bonus: 0.5 },
  coding_challenge:   { base: 75, starBonus: 25, medBonus: 25, hardBonus: 50, expertBonus: 100 },
  project_completion: { base: 200, bonus: 50 },
  badge_earned:       { base: 100 },
  streak_extension:   { base: 70 },
  lesson_completion:  { base: 30 },
  quiz_completion:    { base: 20, perCorrect: 2 },
  peer_review:        { base: 40 },
  profile_completion: { base: 50 },
};
```
- [ ] Daily login: Redis key `daily_credit:{userId}:{date}` — max 1 award/day
- [ ] XP formula: `xp_earned = credits * 2`

#### 6.2 XP Level Calculator — `src/utils/levelCalc.ts`
```typescript
// Port EXACTLY from helpers.py calculate_level()
function calculateLevel(xp: number): { level: number; currentXp: number; xpForNext: number; xpProgress: number } {
  let level = 1;
  let threshold = 1000;
  let remaining = xp;
  while (remaining >= threshold) {
    remaining -= threshold;
    level++;
    threshold = Math.floor(threshold * 1.5);
  }
  return {
    level,
    currentXp: remaining,
    xpForNext: threshold,
    xpProgress: Math.round((remaining / threshold) * 100),
  };
}
```
> ❌ Do NOT use `Math.floor(xp/100)+1` — that is wrong.

#### 6.3 Endpoints
- [ ] `GET /api/credits/summary` — balance, XP, level breakdown, transaction count
- [ ] `GET /api/credits/transactions?page=1&limit=20` — paginated log
- [ ] `POST /api/credits/transfer` — body: `{ to_user_id, amount (10–1000), note }`; bilateral log + notification
- [ ] `POST /api/credits/spend` — body: `{ item_id, amount }`; logged in `purchases`

### Frontend: `src/pages/credits/`
- [ ] `CreditsDashboard.tsx` — balance card, XP ring, level badge
- [ ] `TransactionHistory.tsx` — paginated list
- [ ] `TransferModal.tsx` — peer transfer form

---

## SECTION 7 — Notifications System

### Backend: `src/routes/notifications.router.ts`

- [ ] `GET /api/notifications?page=1&unread_only=false` — personal + broadcast notifications
- [ ] `POST /api/notifications/:id/read` — mark single read
- [ ] `POST /api/notifications/read-all` — bulk mark all read
- [ ] Types: `welcome | login | system | group_request | credit_transfer | achievement | deadline | announcement`
- [ ] Priority: `low | medium | high`
- [ ] Field: `action_url` (deep link to relevant page)

### Frontend: `src/components/NotificationBell.tsx`
- [ ] Badge count, dropdown list, mark-read actions
- [ ] Real-time updates via Socket.io `notification` event

---

## SECTION 8 — Study Groups & Team Channels

### Backend: `src/routes/groups.router.ts`

- [ ] `POST /api/groups` — create: `{ name, description, privacy, department, year }`
- [ ] `GET /api/groups` — my groups + member groups; include `is_member`, `member_count`
- [ ] `GET /api/groups/discover` — public groups user hasn't joined
- [ ] `GET /api/groups/:id` — detail + full member list with roles (Creator/Member)
- [ ] `POST /api/groups/:id/join` — instant join for public
- [ ] `POST /api/groups/:id/request` — join request for private → notify admins
- [ ] `GET /api/groups/:id/requests` — pending requests (admin only)
- [ ] `POST /api/groups/:id/requests/:reqId/action` — `{ action: 'approve'|'reject' }`
- [ ] `GET /api/groups/:id/messages?limit=50&before=<msgId>` — paginated history
- [ ] `POST /api/groups/:id/messages` — HTTP send + Socket.io broadcast
- [ ] `POST /api/groups/:id/files` — Multer upload to group folder

### Frontend: `src/pages/groups/`
- [ ] `GroupsPage.tsx` — list + discover tabs
- [ ] `GroupChatPage.tsx` — real-time chat with Socket.io, file upload
- [ ] `GroupDetailPage.tsx` — members, requests management

---

## SECTION 9 — Leaderboard System

### Backend: `src/routes/leaderboard.router.ts`

#### 9.1 GET `/api/leaderboard?mode=weekly|monthly|all_time&department=&year=`
- [ ] Weekly: aggregate `submissions` collection (last 7 days)
- [ ] Monthly/All-time: query `leaderboard` collection
- [ ] Per entry: `{ rank, user_name, department, year, stage, profile_picture, total_score, challenges_completed, average_score }`
- [ ] Inject viewer's own rank + score

#### 9.2 GET `/api/leaderboard/career`
- [ ] Score = `(interviews_completed * 10) + (skills_count * 2) + (experience_entries * 5)`
- [ ] Return top 10 + viewer rank, score, badge count

### Frontend: `src/pages/leaderboard/`
- [ ] `LeaderboardPage.tsx` — tabs: Coding / Career, mode filter, dept/year filter
- [ ] Own rank highlight card

---

## SECTION 10 — Code Repository & Version Control

### Backend: `src/routes/repositories.router.ts`

- [ ] `POST /api/repositories` — `{ name, description, is_public }`
- [ ] `GET /api/repositories?owner_id=&is_public=&language=` — own + collaborator repos
- [ ] `GET /api/repositories/:id` — files, recent 10 commits, contributor stats (`can_edit` flag)
  - Contributor aggregation: `$group by author_id → count commits, last_commit_date`
- [ ] `POST /api/repositories/:id/commits` — `{ message, files: [{path, content}], branch }`

### Frontend: `src/pages/repositories/`
- [ ] `RepoListPage.tsx` — grid of repos
- [ ] `RepoDetailPage.tsx` — file tree, commit log, contributor chart
- [ ] `CommitEditor.tsx` — file editor with commit message

---

## SECTION 11 — WebSocket Real-Time (Socket.io)

### Backend: `src/websockets/` — Socket.io namespaces

> **Replace FastAPI WebSocket with Socket.io namespaces in Express**

#### 11.1 Main Namespace `/` — `src/websockets/main.socket.ts`
- [ ] JWT auth middleware on `connection` event (disconnect with error on failure)
- [ ] Events:
  - `ping` → emit `pong`
  - `group_message` → save to DB → `socket.to(groupRoom).emit('group_message', ...)`
  - `@assistant` prefix → `AIService.generate()` → emit user msg + AI response
  - `typing` → `socket.to(groupRoom).emit('user_typing', { userId, name })`
  - `pair_programming` → sync `{ code, cursorPosition }` to partner room

#### 11.2 Challenges Namespace `/challenges` — `src/websockets/challenges.socket.ts`
- [ ] JWT auth on connect
- [ ] `subscribe_to_stage` event → query active challenges → emit list

#### 11.3 Projects Namespace `/projects` — `src/websockets/projects.socket.ts`
- [ ] Validate membership/ownership on connect
- [ ] `user_joined` / `user_left` broadcasts
- [ ] `cursor_position` → `cursor_update: { userId, file, line, column }`
- [ ] `code_change` → `code_update: { userId, file, changes }`
- [ ] `chat_message` → `team_chat`

#### 11.4 Stage3 AI Namespace `/stage3` — `src/websockets/stage3.socket.ts`
- [ ] Token streaming: emit `token` events with 20ms delay per character
- [ ] Event sequence: `typing` → `response_start` → `token` (×N) → `response_complete`
- [ ] Save full conversation to `ai_chats` collection

#### 11.5 Stage1 Roleplay Namespace `/stage1/roleplay` — `src/websockets/roleplay.socket.ts`
- [ ] Session lookup + `status === 'active'` check per message
- [ ] Build full history context from `session.messages[]`
- [ ] Stream AI response: character-by-character, 15ms delay
- [ ] After exchange: `$push messages`, `$inc current_turn`
- [ ] `should_end: true` when `current_turn >= max_turns`
- [ ] `speech_analysis` event: calculate WPM + count filler words in real-time

### Frontend: `src/hooks/useSocket.ts`
- [ ] `useSocket(namespace)` hook — connect, auto-reconnect, cleanup on unmount
- [ ] `useGroupChat(groupId)` — wraps main namespace group events
- [ ] `useProjectCollab(projectId)` — wraps projects namespace

---

## SECTION 12 — Stage 1: Communication Skills

### Backend: `src/routes/stage1/`

#### 12.1 Listening Module — `src/routes/stage1/listening.router.ts`
- [ ] **Echo Challenge:** `POST /api/stage1/listening/echo` — audio upload → STT → pronunciation score
- [ ] **Fill the Beats:** `POST /api/stage1/listening/fill` — validate blank answers vs transcript
- [ ] **Direction Follower:** `POST /api/stage1/listening/direction` — validate grid path array
- [ ] **Tone Recognizer:** `POST /api/stage1/listening/tone` — classify tone via AI

#### 12.2 Reading Module — `src/routes/stage1/reading.router.ts`
- [ ] Passage selection: admin-curated, faculty-selected, or AI-generated
- [ ] `GET /api/stage1/reading/passage` — return passage + comprehension questions
- [ ] `POST /api/stage1/reading/submit` — validate answers, track WPM, score + AI feedback

#### 12.3 Writing Module — `src/routes/stage1/writing.router.ts`
- [ ] **Essay:** `POST /api/stage1/writing/essay` — AI grammar/structure/vocab feedback
- [ ] **Picture Prompt:** `POST /api/stage1/writing/picture` — 50-word description → AI eval
- [ ] **No-Filter:** `POST /api/stage1/writing/nofilter` — detect banned word usage
- [ ] **Quick Reply:** `POST /api/stage1/writing/quickreply` — countdown + email draft → AI score
- [ ] **Word Chain:** `POST /api/stage1/writing/wordchain` — 10-word sentence logic eval

#### 12.4 Speaking / Roleplay — `src/routes/stage1/speaking.router.ts`
- [ ] `POST /api/stage1/roleplay/sessions` — create session: `{ scenario, system_prompt, max_turns }`
  - Stores: `system_prompt`, `messages[]`, `current_turn: 0`, `max_turns`, `status: 'active'`
- [ ] `POST /api/stage1/roleplay/sessions/:id/evaluate` — end + AI evaluation + close
- [ ] Real-time via Socket.io `/stage1/roleplay` namespace (Section 11.5)
- [ ] English Chatbot: 4 modes: `general | conversation | grammar | pronunciation`

#### 12.5 Vocabulary Builder — `src/routes/stage1/vocabulary.router.ts`
- [ ] `GET /api/stage1/vocabulary/cards` — daily rotating flashcards (word, meaning, tamil_meaning, category, example)
- [ ] `POST /api/stage1/vocabulary/custom` — add custom word
- [ ] `GET /api/stage1/vocabulary/progress` — badges, streak, mastery %
- [ ] `GET /api/stage1/vocabulary/report` — downloadable mastery report

### Frontend: `src/pages/stage1/`
- [ ] `ListeningPage.tsx` — 4 sub-challenge tabs
- [ ] `ReadingPage.tsx` — timed reader, MCQ/short-answer
- [ ] `WritingPage.tsx` — 5 challenge type selector
- [ ] `SpeakingPage.tsx` — chatbot tabs + roleplay launcher
- [ ] `VocabularyPage.tsx` — flashcard deck, custom word form, progress chart

---

## SECTION 13 — Student Dashboard

### Backend: `src/routes/student/`

- [ ] `GET /api/student/classrooms` — enrolled classrooms
- [ ] `GET /api/student/classrooms/:id` — detail + teacher info
- [ ] `GET /api/student/materials?classroom_id=` — materials browser
- [ ] `GET /api/student/assignments` — active assignments (due date, criteria)
- [ ] `POST /api/student/assignments/:id/submit` — file or text submission (Multer)
- [ ] `GET /api/student/assignments/:id/grade` — score, output, teacher comments
- [ ] `GET /api/student/announcements` — class + college-wide
- [ ] `GET /api/student/quiz/daily` — today's quiz (5 meaning + 5 fill via date-seed)
- [ ] `POST /api/student/quiz/submit` — submit answers → credit award

### Frontend: `src/pages/student/`
- [ ] `StudentDashboard.tsx` — overview: classrooms, pending assignments, announcements
- [ ] `ClassroomPage.tsx` — materials, assignments tab
- [ ] `AssignmentSubmitPage.tsx` — Monaco editor or file upload
- [ ] `GradePage.tsx` — score breakdown
- [ ] `DailyQuizPage.tsx` — timed quiz UI
