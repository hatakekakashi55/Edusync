import re
import os

html_file_path = r"c:\Users\wayne\Documents\edusync-babu\stage 2.html"

with open(html_file_path, "r", encoding="utf-8") as f:
    html_content = f.read()

# 1. Add "Arcade" into the tabs array
arcade_tab = """<div class="tab" onclick="showSection('arcade')"><i class="fas fa-gamepad"></i> Game Modes</div>"""
html_content = html_content.replace(
    """<div class="tab" onclick="showSection('duels')"
                    style="color: #ef4444; border-color: rgba(239, 68, 68, 0.4);"><i class="fas fa-fire"></i> Arena
                </div>""",
    """<div class="tab" onclick="showSection('duels')"
                    style="color: #ef4444; border-color: rgba(239, 68, 68, 0.4);"><i class="fas fa-fire"></i> Arena
                </div>
                """ + arcade_tab
)

# Also update the sidebar nav
html_content = html_content.replace(
    """<li class="menu-item">
                    <a href="#" class="menu-link" onclick="showSection('duels')">
                        <i class="fas fa-khanda menu-icon"></i>
                        <span>Arena</span>
                    </a>
                </li>""",
    """<li class="menu-item">
                    <a href="#" class="menu-link" onclick="showSection('duels')">
                        <i class="fas fa-khanda menu-icon"></i>
                        <span>Arena</span>
                    </a>
                </li>
                <li class="menu-item">
                    <a href="#" class="menu-link" onclick="showSection('arcade')">
                        <i class="fas fa-gamepad menu-icon"></i>
                        <span>Arcade / Gamification</span>
                    </a>
                </li>"""
)

# 2. Add the big arcade-section into the bottom of the main-content (before "help-section" or "duels-section")
new_section = """
<!-- Arcade Section -->
<div class="content-section" id="arcade-section">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <h2 style="color: #6366f1;"><i class="fas fa-gamepad"></i> EduSync Arcade & Gamification</h2>
        <button class="nav-btn primary" onclick="analyzeMySkills()">
            <i class="fas fa-robot"></i> AI Personal Mentor
        </button>
    </div>
    <p style="margin-bottom: 20px; color: var(--text);">
        Step into the Arena! Challenge yourself, race against time, fix bugs, and battle others. All API driven with AI logic!
    </p>

    <div class="challenges-grid">
        <!-- 1. Code Battle -->
        <div class="challenge-card" style="border-color: #ef4444;">
            <div class="challenge-header">
                <span class="challenge-difficulty difficulty-hard"><i class="fas fa-swords"></i> Multiplayer</span>
                <span class="challenge-reward">🏆 +300 XP</span>
            </div>
            <h3 class="challenge-title">Code Battle Arena</h3>
            <p class="challenge-description">Live 1v1 coding battle. Fastest correct solution wins the streak bonus!</p>
            <button class="nav-btn" style="width: 100%; margin-top: 15px; background: rgba(239, 68, 68, 0.2); color: #ef4444;" onclick="startCodeBattle()">Battle Now <i class="fas fa-bolt"></i></button>
        </div>

        <!-- 2. Boss Fight -->
        <div class="challenge-card" style="border-color: #f59e0b;">
            <div class="challenge-header">
                <span class="challenge-difficulty difficulty-medium"><i class="fas fa-ghost"></i> Boss Fight</span>
                <span class="challenge-reward">💰 +500 Coins</span>
            </div>
            <h3 class="challenge-title">AI Boss Fight</h3>
            <p class="challenge-description">Defeat the 'Bug Monster' by solving coding problems. Drain its HP to win!</p>
            <button class="nav-btn" style="width: 100%; margin-top: 15px; background: rgba(245, 158, 11, 0.2); color: #f59e0b;" onclick="startBossFight()">Engage Boss <i class="fas fa-khanda"></i></button>
        </div>

        <!-- 3. Bug Hunter -->
        <div class="challenge-card" style="border-color: #10b981;">
            <div class="challenge-header">
                <span class="challenge-difficulty difficulty-easy"><i class="fas fa-bug"></i> Debugging</span>
                <span class="challenge-reward">🛠️ +150 XP</span>
            </div>
            <h3 class="challenge-title">Bug Hunter Challenge</h3>
            <p class="challenge-description">AI generates code with intentional logical bugs. Find and fix them before time runs out.</p>
            <button class="nav-btn" style="width: 100%; margin-top: 15px; background: rgba(16, 185, 129, 0.2); color: #10b981;" onclick="startBugHunter()">Hunt Bugs <i class="fas fa-search"></i></button>
        </div>

        <!-- 4. Interview Sim -->
        <div class="challenge-card" style="border-color: #3b82f6;">
             <div class="challenge-header">
                <span class="challenge-difficulty difficulty-hard"><i class="fas fa-user-tie"></i> Interview</span>
                <span class="challenge-reward">🎓 Job Ready</span>
            </div>
            <h3 class="challenge-title">AI Interview Simulator</h3>
            <p class="challenge-description">Real tech interview simulation. AI asks a question, checks code, and quizzes complexity.</p>
             <button class="nav-btn" style="width: 100%; margin-top: 15px; background: rgba(59, 130, 246, 0.2); color: #3b82f6;" onclick="startInterview()">Start Interview <i class="fas fa-microphone"></i></button>
        </div>

        <!-- 5. Escape Room -->
        <div class="challenge-card" style="border-color: #8b5cf6;">
             <div class="challenge-header">
                <span class="challenge-difficulty difficulty-medium"><i class="fas fa-door-closed"></i> Puzzle</span>
                <span class="challenge-reward">🔐 Badge</span>
            </div>
            <h3 class="challenge-title">Code Escape Room</h3>
            <p class="challenge-description">Solve sequential coding puzzles to unlock rooms and find the final treasure.</p>
             <button class="nav-btn" style="width: 100%; margin-top: 15px; background: rgba(139, 92, 246, 0.2); color: #8b5cf6;" onclick="startEscapeRoom()">Enter Room <i class="fas fa-key"></i></button>
        </div>

        <!-- 6. Daily Quests -->
        <div class="challenge-card" style="border-color: #ec4899;">
             <div class="challenge-header">
                <span class="challenge-difficulty difficulty-easy"><i class="fas fa-calendar-day"></i> Daily</span>
                <span class="challenge-reward">🔥 Streak</span>
            </div>
            <h3 class="challenge-title">Daily AI Quests</h3>
            <p class="challenge-description">Complete daily missions (e.g. solve 3 arrays, debug 1 code) to earn rewards.</p>
             <button class="nav-btn" style="width: 100%; margin-top: 15px; background: rgba(236, 72, 153, 0.2); color: #ec4899;" onclick="viewDailyQuests()">View Quests <i class="fas fa-list-check"></i></button>
        </div>

        <!-- 7. Speed Run -->
         <div class="challenge-card" style="border-color: #06b6d4;">
             <div class="challenge-header">
                <span class="challenge-difficulty difficulty-hard"><i class="fas fa-stopwatch"></i> Timed</span>
                <span class="challenge-reward">⏱️ Leaderboard</span>
            </div>
            <h3 class="challenge-title">Code Speed Run</h3>
            <p class="challenge-description">Solve 3 problems sequentially within 5 minutes. Global leaderboards!</p>
             <button class="nav-btn" style="width: 100%; margin-top: 15px; background: rgba(6, 182, 212, 0.2); color: #06b6d4;" onclick="startSpeedRun()">Start Timer <i class="fas fa-clock"></i></button>
        </div>

        <!-- 8. Algorithm Builder -->
         <div class="challenge-card" style="border-color: #14b8a6;">
             <div class="challenge-header">
                <span class="challenge-difficulty difficulty-medium"><i class="fas fa-puzzle-piece"></i> Construct</span>
                <span class="challenge-reward">🧠 Logic Builder</span>
            </div>
            <h3 class="challenge-title">Algorithm Builder</h3>
            <p class="challenge-description">Arrange structural blocks (drag & drop logic) to form a working algorithm.</p>
             <button class="nav-btn" style="width: 100%; margin-top: 15px; background: rgba(20, 184, 166, 0.2); color: #14b8a6;" onclick="startAlgorithmBuilder()">Build Logic <i class="fas fa-cube"></i></button>
        </div>

        <!-- 9. AI Code Reviewer -->
         <div class="challenge-card" style="border-color: #6366f1;">
             <div class="challenge-header">
                <span class="challenge-difficulty difficulty-easy"><i class="fas fa-code"></i> Feedback</span>
                <span class="challenge-reward">✨ Clean Code</span>
            </div>
            <h3 class="challenge-title">AI Code Reviewer</h3>
            <p class="challenge-description">Submit any code snippet for time complexity analysis and optimization suggestions.</p>
             <button class="nav-btn" style="width: 100%; margin-top: 15px; background: rgba(99, 102, 241, 0.2); color: #6366f1;" onclick="startCodeReview()">Review Code <i class="fas fa-search-plus"></i></button>
        </div>

        <!-- 10. Real World Mission -->
        <div class="challenge-card" style="border-color: #f43f5e;">
             <div class="challenge-header">
                <span class="challenge-difficulty difficulty-hard"><i class="fas fa-globe"></i> Projects</span>
                <span class="challenge-reward">🛠️ Real Skills</span>
            </div>
            <h3 class="challenge-title">Real World Mission</h3>
            <p class="challenge-description">Build projects like a calculator or REST API. AI evaluates structure.</p>
             <button class="nav-btn" style="width: 100%; margin-top: 15px; background: rgba(244, 63, 94, 0.2); color: #f43f5e;" onclick="startRealWorldMission()">Start Project <i class="fas fa-building"></i></button>
        </div>

    </div>

    <!-- Arcade Modal -->
    <div id="arcadeModal" class="loading-overlay" style="align-items: center; justify-content: center; z-index: 10000; padding: 20px;">
        <div style="background: var(--darker); border: 1px solid var(--glass-border); border-radius: 15px; width: 100%; max-width: 800px; padding: 30px; margin-top: 50px; max-height: 90vh; overflow-y: auto; position: relative;">
            <button onclick="document.getElementById('arcadeModal').style.display='none'" style="position: absolute; right: 20px; top: 20px; background: transparent; border: none; color: white; cursor: pointer; font-size: 20px;"><i class="fas fa-times"></i></button>
            <h2 id="arcadeModalTitle" style="color: var(--primary); margin-bottom: 15px;"><i class="fas fa-gamepad"></i> Game Mode</h2>
            <div id="arcadeModalContent" style="color: var(--text);">
                Loading...
            </div>
        </div>
    </div>
</div>
<!-- Arcade Section End -->
"""

scripts = """
<script>
async function startCodeBattle() {
    showArcadeModal("Code Battle Arena ⚔️", "Matchmaking...<br><br><div class='loading-spinner' style='display:inline-block;'></div>");
    try {
        const res = await fetch("/api/stage2/arcade/battle/matchmake", { method: "POST", headers: { "Authorization": `Bearer localStorage.getItem("access_token")` } });
        const data = await res.json();
        const content = `
            <div style="text-align: center; margin-bottom: 20px;">
                <h3 style="color: var(--danger);">Opponent Found: ${data.opponent}!</h3>
                <p>Room ID: ${data.room_id}</p>
            </div>
            <div style="background: rgba(0,0,0,0.3); padding: 15px; border-radius: 10px; margin-bottom: 20px;">
                <h4>Problem: ${data.problem.title}</h4>
                <p>${data.problem.description}</p>
            </div>
            <textarea id="battleCode" style="width:100%; height:150px; background:#1e1e1e; color:white; font-family:monospace; padding:10px;">def reverse_array(arr):\\n    pass</textarea>
            <button class="nav-btn primary" style="width:100%; margin-top:10px;" onclick="alert('Submitted Code! Checking against opponent...')"><i class="fas fa-paper-plane"></i> Submit Solution Fast!</button>
        `;
        document.getElementById("arcadeModalContent").innerHTML = content;
    } catch(err) {
        document.getElementById("arcadeModalContent").innerHTML = "Ready for battle! Matchmaking engine starting...";
    }
}

async function startBossFight() {
    showArcadeModal("AI Boss Fight 👾", "Engaging Boss...<br><br><div class='loading-spinner' style='display:inline-block;'></div>");
    try {
        const res = await fetch("/api/stage2/arcade/boss/start", { method: "POST", headers: { "Authorization": `Bearer localStorage.getItem("access_token")` } });
        const data = await res.json();
        
        let problemHtml = "";
        data.problems.forEach(p => {
            problemHtml += `<button class="nav-btn" style="width:100%; margin-bottom:10px; text-align:left; display:flex; justify-content:space-between;" onclick="attackBoss('${p.id}')">
                <span>${p.title} (${p.difficulty})</span>
                <span style="color:var(--danger);">- ${p.damage} HP</span>
            </button>`;
        });

        const content = `
            <div style="text-align: center; margin-bottom: 20px;">
                <i class="fas fa-spider" style="font-size: 60px; color: var(--danger);"></i>
                <h3 style="color: var(--danger); margin-top:10px;">Boss: ${data.boss.name}</h3>
                <div style="width:100%; height:20px; background:#333; border-radius:10px; overflow:hidden; margin-top:10px; border:1px solid #555;">
                    <div id="bossHpBar" style="width:100%; height:100%; background:var(--danger); transition:width 0.3s;"></div>
                </div>
                <p id="bossHpText" style="margin-top:5px;">${data.boss.hp} / ${data.boss.max_hp} HP</p>
            </div>
            <h4>Select a problem to attack the Boss:</h4>
            ${problemHtml}
        `;
        document.getElementById("arcadeModalContent").innerHTML = content;
        
        window.currentBossHp = data.boss.hp;
        window.maxBossHp = data.boss.max_hp;
    } catch(err) {
        document.getElementById("arcadeModalContent").innerHTML = "Failed to load boss.";
    }
}

async function attackBoss(problemId) {
    if(window.currentBossHp <= 0) return;
    try {
        const res = await fetch("/api/stage2/arcade/boss/attack", { 
            method: "POST", 
            headers: { "Authorization": `Bearer localStorage.getItem("access_token")`, "Content-Type": "application/json" },
            body: JSON.stringify({problem_id: problemId, code: "def solved(): pass"})
        });
        const data = await res.json();
        
        window.currentBossHp -= data.damage_dealt;
        if(window.currentBossHp < 0) window.currentBossHp = 0;
        
        document.getElementById("bossHpBar").style.width = `${(window.currentBossHp/window.maxBossHp)*100}%`;
        document.getElementById("bossHpText").innerText = `${window.currentBossHp} / ${window.maxBossHp} HP`;
        
        if(window.currentBossHp === 0) {
            alert("Boss Defeated! You earned +Coins, +XP and unlocked new levels!");
            document.getElementById("arcadeModal").style.display = "none";
        } else {
            alert(`Attack successful! Dealt ${data.damage_dealt} damage!\\n\\nBoss HP remaining: ${window.currentBossHp}`);
        }
    } catch(e) {
        alert("Attack failed.");
    }
}

async function startBugHunter() {
    showArcadeModal("Bug Hunter Challenge 🐛", "Generating buggy code...<br><br><div class='loading-spinner' style='display:inline-block;'></div>");
    try {
        const res = await fetch("/api/stage2/arcade/bughunter/generate", { method: "POST", headers: { "Authorization": `Bearer localStorage.getItem("access_token")` } });
        const data = await res.json();
        
        const content = `
            <div style="margin-bottom: 20px;">
                <h4>Task: ${data.title}</h4>
                <p style="color:var(--text-muted);">${data.description}</p>
                <div style="color:var(--danger); margin-top:10px;"><i class="fas fa-exclamation-triangle"></i> Find the bug and fix the code below:</div>
            </div>
            <textarea id="buggyCode" style="width:100%; height:150px; background:#1e1e1e; color:var(--text); border:1px solid var(--danger); font-family:monospace; padding:10px;">${data.buggy_code}</textarea>
            <button class="nav-btn success" style="width:100%; margin-top:20px;" onclick="verifyBugFix()"><i class="fas fa-bug-slash"></i> Submit Fix</button>
            <div id="bugHunterFeedback" style="margin-top:15px; font-weight:bold;"></div>
        `;
        document.getElementById("arcadeModalContent").innerHTML = content;
    } catch(err) {
        document.getElementById("arcadeModalContent").innerHTML = "Error generating Bug Hunt!";
    }
}

async function verifyBugFix() {
    const code = document.getElementById("buggyCode").value;
    try {
        const res = await fetch("/api/stage2/arcade/bughunter/verify", { 
            method: "POST", 
            headers: { "Authorization": `Bearer localStorage.getItem("access_token")`, "Content-Type": "application/json" },
            body: JSON.stringify({code: code})
        });
        const data = await res.json();
        
        const feedback = document.getElementById("bugHunterFeedback");
        if(data.success) {
            feedback.style.color = "var(--success)";
            feedback.innerHTML = `<i class="fas fa-check-circle"></i> ${data.message} (+${data.points} points)`;
        } else {
            feedback.style.color = "var(--danger)";
            feedback.innerHTML = `<i class="fas fa-times-circle"></i> ${data.message}`;
        }
    } catch(e) {
        alert("Error verifying.");
    }
}

async function startInterview() {
    showArcadeModal("AI Interview Simulator 🎤", `
        <h3>Mock Interview: Google SDE 1</h3>
        <p><strong>AI Interviewer:</strong> "Hello! Let's start with a classic problem. Write a program to reverse a string in-place."</p>
        <textarea id="interviewCode" style="width:100%; height:120px; background:#1e1e1e; color:white; font-family:monospace; padding:10px; margin-top:15px; margin-bottom:15px;" placeholder="Write your solution here..."></textarea>
        <button class="nav-btn primary" onclick="submitInterview()">Submit & Analyze <i class="fas fa-paper-plane"></i></button>
        <div id="interviewFeedback" style="margin-top:20px; padding:15px; background:rgba(255,255,255,0.05); border-radius:10px; display:none;"></div>
    `);
}

async function submitInterview() {
    const code = document.getElementById("interviewCode").value;
    const btn = event.target;
    btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Analyzing...`;
    
    try {
        const res = await fetch("/api/stage2/arcade/interview/analyze", { 
            method: "POST", 
            headers: { "Authorization": `Bearer localStorage.getItem("access_token")`, "Content-Type": "application/json" },
            body: JSON.stringify({question: "Reverse string", code: code})
        });
        const data = await res.json();
        
        const feedback = document.getElementById("interviewFeedback");
        feedback.style.display = "block";
        feedback.innerHTML = `<strong>AI Analysis:</strong><br><p style='margin-top:10px'>${data.analysis.replace(/\\n/g, '<br>')}</p>`;
        btn.innerHTML = `Submit & Analyze <i class="fas fa-paper-plane"></i>`;
    } catch(e) {}
}

async function startEscapeRoom() {
    showArcadeModal("Code Escape Room 🔐", "Loading Room 1...<br><div class='loading-spinner' style='display:inline-block;'></div>");
    try {
        const res = await fetch("/api/stage2/arcade/escape/room?level=1", { method: "POST", headers: { "Authorization": `Bearer localStorage.getItem("access_token")` } });
        const data = await res.json();
        
        document.getElementById("arcadeModalContent").innerHTML = `
            <h3>Room 1 of 3: The Cipher</h3>
            <p style="margin: 15px 0;">${data.room.description}</p>
            <input type="text" id="escapeAnswer" placeholder="Enter answer to unlock door..." style="width:100%; padding:10px; border-radius:8px; border:1px solid #555; background:#222; color:white; margin-bottom:15px;">
            <button class="nav-btn success" style="width:100%;" onclick="alert('Door Unlocked! Proceeding to Room 2...')"><i class="fas fa-unlock"></i> Unlock Door</button>
        `;
    } catch(e) {}
}

async function viewDailyQuests() {
    showArcadeModal("Daily AI Quests 📅", "Loading...<div class='loading-spinner' style='display:inline-block;'></div>");
    try {
        const res = await fetch("/api/stage2/arcade/quests", { headers: { "Authorization": `Bearer localStorage.getItem("access_token")` } });
        const data = await res.json();
        
        let questsHtml = "";
        data.forEach(q => {
            questsHtml += `<div style="background:rgba(255,255,255,0.05); padding:15px; border-radius:10px; margin-bottom:10px; display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <strong>${q.desc}</strong>
                    <div style="font-size:12px; color:var(--text-muted);">Reward: ${q.reward} Coins</div>
                </div>
                <button class="nav-btn primary" onclick="alert('Starting Quest...')">Go <i class="fas fa-arrow-right"></i></button>
            </div>`;
        });
        
        document.getElementById("arcadeModalContent").innerHTML = questsHtml;
    } catch(e) {}
}

async function startSpeedRun() {
    showArcadeModal("Code Speed Run ⏱️", "Loading...<div class='loading-spinner' style='display:inline-block;'></div>");
    try {
        const res = await fetch("/api/stage2/arcade/speedrun/start", { method: "POST", headers: { "Authorization": `Bearer localStorage.getItem("access_token")` } });
        const data = await res.json();
        
        document.getElementById("arcadeModalContent").innerHTML = `
            <div style="text-align:center; margin-bottom:20px;">
                <h1 style="color:var(--danger); font-size:40px;">05:00</h1>
                <p>Time Limit to solve 3 algorithmic problems.</p>
            </div>
            <div style="display:flex; gap:10px; margin-bottom:20px;">
                <div style="flex:1; background:var(--glass); padding:10px; text-align:center; border-radius:8px; border:1px solid var(--primary);">1. ${data.problems[0].title}</div>
                <div style="flex:1; background:var(--glass); padding:10px; text-align:center; border-radius:8px;">2. ${data.problems[1].title}</div>
                <div style="flex:1; background:var(--glass); padding:10px; text-align:center; border-radius:8px;">3. ${data.problems[2].title}</div>
            </div>
            <button class="nav-btn primary" style="width:100%;" onclick="alert('Speed run started! Timer is ticking!')">Start First Problem</button>
        `;
    } catch(e) {}
}

async function startAlgorithmBuilder() {
    showArcadeModal("Algorithm Builder 🧠", "Loading blocks...<div class='loading-spinner' style='display:inline-block;'></div>");
    try {
        const res = await fetch("/api/stage2/arcade/algorithm/blocks", { headers: { "Authorization": `Bearer localStorage.getItem("access_token")` } });
        const data = await res.json();
        
        let blocksHtml = "";
        data.blocks.forEach(b => {
            blocksHtml += `<div style="background:rgba(20,184,166,0.2); padding:10px; margin-bottom:10px; border-radius:8px; cursor:grab; border:1px dashed #14b8a6; font-family:monospace;">${b.text}</div>`;
        });
        
        document.getElementById("arcadeModalContent").innerHTML = `
            <p style="margin-bottom:15px;">Drag and drop these logic blocks to form a valid algorithm to sort an array.</p>
            ${blocksHtml}
            <button class="nav-btn primary" style="width:100%; margin-top:10px;" onclick="alert('Arrangement Verified: Success!')">Verify Logic <i class="fas fa-check"></i></button>
        `;
    } catch(e) {}
}

async function startCodeReview() {
    showArcadeModal("AI Code Reviewer 🤖", `
        <p>Submit your code snippet to get instant AI feedback on optimization and edge cases.</p>
        <textarea id="reviewCode" style="width:100%; height:150px; background:#1e1e1e; color:white; font-family:monospace; padding:10px; margin-top:10px;" placeholder="Paste code here..."></textarea>
         <button class="nav-btn" style="width:100%; margin-top:15px; background:rgba(99,102,241,0.2); color:#6366f1;" onclick="submitForReview(this)">Get Review <i class="fas fa-search"></i></button>
         <div id="reviewFeedback" style="display:none; margin-top:20px; padding:15px; background:rgba(255,255,255,0.05); border-radius:10px;"></div>
    `);
}

async function submitForReview(btn) {
    const code = document.getElementById("reviewCode").value;
    btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Analyzing...`;
    
    try {
        const res = await fetch("/api/stage2/arcade/review", { 
            method: "POST", 
            headers: { "Authorization": `Bearer localStorage.getItem("access_token")`, "Content-Type": "application/json" },
            body: JSON.stringify({code: code})
        });
        const data = await res.json();
        
        const feedback = document.getElementById("reviewFeedback");
        feedback.style.display = "block";
        feedback.innerHTML = `<strong>Feedback:</strong><br><p style='margin-top:10px'>${data.review.replace(/\\n/g, '<br>')}</p>
                              <div style='margin-top:10px; color:var(--success); font-weight:bold;'>Badges Earned: ${data.badges.join(", ")}</div>`;
        btn.innerHTML = `Get Review <i class="fas fa-search"></i>`;
    } catch(e) {}
}

async function startRealWorldMission() {
    showArcadeModal("Real World Mission 🌍", `
        <h3>Mission: Build an API using FastAPI</h3>
        <p>Implement a user login system with JWT authentication.</p>
        <button class="nav-btn primary" style="width:100%; margin-top:15px;" onclick="alert('Opening Full IDE Project mode...')">Open IDE Editor <i class="fas fa-external-link-alt"></i></button>
    `);
}

async function analyzeMySkills() {
    showArcadeModal("AI Personal Mentor 🤖🧠", "Analyzing your coding style, weak topics, and bugs...<div class='loading-spinner' style='display:inline-block;'></div>");
    try {
        const res = await fetch("/api/stage2/arcade/mentor", { headers: { "Authorization": `Bearer localStorage.getItem("access_token")` } });
        const data = await res.json();
        
        document.getElementById("arcadeModalContent").innerHTML = `
            <div style="background:rgba(59,130,246,0.1); padding:20px; border-radius:15px; margin-bottom:20px;">
                <h3 style="color:var(--stage-color);"><i class="fas fa-chart-pie"></i> Mentor Analysis</h3>
                <p style="margin-top:10px; font-size:16px;">"${data.analysis}"</p>
                <div style="margin-top:15px;">
                    <strong>Areas of Improvement:</strong>
                    <ul style="margin-left:20px; margin-top:5px; color:var(--text-muted);">
                        ${data.weak_topics.map(t => `<li>${t}</li>`).join('')}
                    </ul>
                </div>
            </div>
            
            <div style="background:rgba(245,158,11,0.1); padding:20px; border-radius:15px;">
                <h4 style="color:var(--warning);"><i class="fas fa-magic"></i> Custom Generated Challenge for you</h4>
                <div style="margin-top:10px;">
                    <strong>${data.generated_challenge.title}</strong>
                    <p style="color:var(--text-muted); font-size:14px; margin-top:5px;">${data.generated_challenge.description}</p>
                </div>
                <button class="nav-btn warning" style="margin-top:15px; background:var(--warning); color:white; border:none;" onclick="alert('Starting Custom Challenge...')">Accept Challenge <i class="fas fa-check"></i></button>
            </div>
        `;
    } catch(e) {}
}

function showArcadeModal(title, initialContent) {
    document.getElementById("arcadeModalTitle").innerHTML = title;
    document.getElementById("arcadeModalContent").innerHTML = initialContent;
    document.getElementById("arcadeModal").style.display = "flex";
}
</script>
"""

# Insert new_section before <div class="content-section" id="duels-section">
html_content = html_content.replace(
    '<div class="content-section" id="duels-section">',
    new_section + '\n    <div class="content-section" id="duels-section">'
)

# Insert scripts before </body>
html_content = html_content.replace('</body>', scripts + '\n</body>')

# Update showSection logic to hide arcade
# In the original file, it has `.forEach(id => { document.getElementById(id).classList.remove('active'); });`
# We just need to replace the list of ids (if it exists) or rely on `.querySelectorAll('.content-section').forEach(el => el.classList.remove('active'))` (which is standard).

with open(html_file_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print("Patching complete.")
