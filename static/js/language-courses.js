/**
 * EduSync Language Courses System - Enhanced for All Stages
 * Integrated with compiler and points system
 */

// =============== LANGUAGE COURSES CONFIGURATION ===============
const LANGUAGE_COURSES_CONFIG = {
    apiBaseUrl: 'http://localhost:8000/api',
    maxExecutionTime: 30000, // 30 seconds
    pointsPerExercise: 50,
    bonusPointsForCorrectOutput: 100
};

let languageCoursesState = {
    currentLanguage: null,
    currentModule: 0,
    currentCourse: null,
    courseProgress: {},
    codeEditor: null,
    isRunning: false,
    userPoints: 0
};

/**
 * Initialize language courses section
 */
async function initLanguageCoursesSection() {
    await loadCourseProgress();
    displayAvailableCourses();
    setupEventListeners();
}

/**
 * Setup event listeners for language course interactions
 */
function setupEventListeners() {
    // Add animation on course card hover
    const courseCards = document.querySelectorAll('.course-card');
    courseCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-10px)';
            this.style.boxShadow = '0 20px 40px rgba(99, 102, 241, 0.3)';
        });
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
            this.style.boxShadow = '0 10px 20px rgba(0, 0, 0, 0.2)';
        });
    });
}

/**
 * Load course progress from backend
 */
async function loadCourseProgress() {
    try {
        const token = localStorage.getItem('access_token');
        if (!token) return;
        
        const response = await fetch(`${LANGUAGE_COURSES_CONFIG.apiBaseUrl}/language-courses/progress`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            const data = await response.json();
            languageCoursesState.courseProgress = data.progress || {};
            localStorage.setItem('course_progress', JSON.stringify(languageCoursesState.courseProgress));
        }
    } catch (error) {
        console.error('Error loading course progress:', error);
        const saved = localStorage.getItem('course_progress');
        if (saved) {
            languageCoursesState.courseProgress = JSON.parse(saved);
        }
    }
}

/**
 * Display available courses
 */
function displayAvailableCourses() {
    const container = document.getElementById('coursesList');
    if (!container) return;
    
    container.innerHTML = '';
    
    const COURSES = {
        'c': {
            id: 'c',
            title: 'C Programming Mastery',
            icon: 'fas fa-c',
            description: 'Master the fundamentals of C programming',
            difficulty: 'Beginner',
            duration: '40 hours',
            modules: 12,
            exercises: 50,
            credits: 500,
            prerequisites: [],
            topics: ['Variables & Data Types', 'Loops & Conditionals', 'Functions', 'Arrays', 'Pointers', 'Strings', 'Structures', 'File I/O']
        },
        'cpp': {
            id: 'cpp',
            title: 'C++ Advanced Programming',
            icon: 'fas fa-plus',
            description: 'Learn object-oriented programming with C++',
            difficulty: 'Intermediate',
            duration: '50 hours',
            modules: 15,
            exercises: 60,
            credits: 650,
            prerequisites: ['c'],
            topics: ['OOP Concepts', 'Classes & Objects', 'Inheritance', 'Polymorphism', 'Templates', 'STL', 'Exception Handling', 'Namespaces']
        },
        'python': {
            id: 'python',
            title: 'Python Full Stack',
            icon: 'fab fa-python',
            description: 'Complete Python programming from basics to advanced',
            difficulty: 'Beginner to Advanced',
            duration: '60 hours',
            modules: 18,
            exercises: 80,
            credits: 800,
            prerequisites: [],
            topics: ['Syntax Basics', 'Data Structures', 'Functions & Modules', 'OOP', 'File Handling', 'Regex', 'Web Scraping', 'Django Basics']
        },
        'javascript': {
            id: 'javascript',
            title: 'JavaScript & Web Development',
            icon: 'fab fa-js-square',
            description: 'Build interactive web applications with JavaScript',
            difficulty: 'Beginner',
            duration: '45 hours',
            modules: 14,
            exercises: 70,
            credits: 700,
            prerequisites: [],
            topics: ['DOM Manipulation', 'Events', 'Async Programming', 'Promises', 'Fetch API', 'ES6+', 'Frameworks Intro', 'Testing']
        },
        'java': {
            id: 'java',
            title: 'Java Enterprise Development',
            icon: 'fab fa-java',
            description: 'Enterprise-level Java programming and design patterns',
            difficulty: 'Intermediate',
            duration: '55 hours',
            modules: 16,
            exercises: 75,
            credits: 750,
            prerequisites: [],
            topics: ['OOP Fundamentals', 'Collections', 'Streams API', 'Multithreading', 'Exception Handling', 'JDBC', 'Spring Basics', 'Design Patterns']
        }
    };
    
    Object.entries(COURSES).forEach(([lang, course]) => {
        const progress = languageCoursesState.courseProgress[lang] || {};
        const isCompleted = progress.completed || false;
        const isActive = progress.active || false;
        const completionPercent = progress.progress || 0;
        const completedModules = progress.completed_modules?.length || 0;
        const creditsEarned = progress.total_credits || 0;
        
        // Check prerequisites
        let prerequisitesMet = true;
        if (course.prerequisites.length > 0) {
            prerequisitesMet = course.prerequisites.every(prereq =>
                languageCoursesState.courseProgress[prereq]?.completed || false
            );
        }
        
        const courseCard = document.createElement('div');
        courseCard.className = `course-card ${!prerequisitesMet ? 'locked' : isCompleted ? 'completed' : isActive ? 'active' : ''}`;
        courseCard.style.cssText = `
            background: var(--glass);
            border: 1px solid var(--glass-border);
            border-radius: 15px;
            padding: 20px;
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
            cursor: ${!prerequisitesMet ? 'not-allowed' : 'pointer'};
            opacity: ${!prerequisitesMet ? '0.6' : '1'};
        `;
        
        courseCard.innerHTML = `
            <div class="course-header" style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 15px;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div style="width: 50px; height: 50px; background: rgba(99, 102, 241, 0.2); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 24px; color: #6366f1;">
                        <i class="${course.icon}"></i>
                    </div>
                    <div>
                        <h3 style="margin: 0; font-size: 16px; color: var(--text);">${course.title}</h3>
                        <p style="margin: 5px 0 0 0; color: var(--text-muted); font-size: 13px;">${course.difficulty}</p>
                    </div>
                </div>
                <div class="course-status" style="padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; background: ${isCompleted ? 'rgba(16, 185, 129, 0.2); color: #10b981' : isActive ? 'rgba(99, 102, 241, 0.2); color: #6366f1' : prerequisitesMet ? 'rgba(148, 163, 184, 0.2); color: var(--text-muted)' : 'rgba(239, 68, 68, 0.2); color: #ef4444'};">
                    ${!prerequisitesMet ? 'LOCKED' : isCompleted ? 'COMPLETED' : isActive ? 'IN PROGRESS' : 'AVAILABLE'}
                </div>
            </div>
            
            <p style="color: var(--text-muted); font-size: 14px; margin-bottom: 15px; line-height: 1.5;">
                ${course.description}
            </p>
            
            <div class="course-stats" style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 15px; padding: 10px 0; border-bottom: 1px solid var(--glass-border);">
                <div style="text-align: center;">
                    <div style="font-size: 18px; font-weight: 700; color: #6366f1;">${course.modules}</div>
                    <div style="font-size: 11px; color: var(--text-muted);">Modules</div>
                </div>
                <div style="text-align: center;">
                    <div style="font-size: 18px; font-weight: 700; color: #10b981;">${course.exercises}</div>
                    <div style="font-size: 11px; color: var(--text-muted);">Exercises</div>
                </div>
                <div style="text-align: center;">
                    <div style="font-size: 18px; font-weight: 700; color: #f59e0b;">${course.credits}</div>
                    <div style="font-size: 11px; color: var(--text-muted);">Credits</div>
                </div>
            </div>
            
            ${isActive || isCompleted ? `
                <div class="course-progress" style="margin-bottom: 15px;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 12px;">
                        <span>Progress</span>
                        <span>${completionPercent}% (${completedModules}/${course.modules} modules)</span>
                    </div>
                    <div style="width: 100%; height: 8px; background: rgba(255,255,255,0.1); border-radius: 10px; overflow: hidden;">
                        <div style="width: ${completionPercent}%; height: 100%; background: linear-gradient(90deg, #6366f1, #10b981); transition: width 0.3s ease;"></div>
                    </div>
                </div>
                <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 15px;">
                    📊 Credits Earned: ${creditsEarned}/${course.credits}
                </div>
            ` : ''}
            
            <div style="display: flex; gap: 10px;">
                ${!prerequisitesMet ? `
                    <button class="btn-disabled" style="flex: 1; opacity: 0.5; cursor: not-allowed;">
                        <i class="fas fa-lock"></i> Complete ${course.prerequisites[0]?.toUpperCase()}
                    </button>
                ` : `
                    <button onclick="startCourse('${lang}')" class="btn-primary" style="flex: 1;">
                        <i class="fas fa-play"></i> ${isCompleted ? 'Review' : isActive ? 'Continue' : 'Start'}
                    </button>
                    <button onclick="viewCourseDetails('${lang}')" class="btn-secondary" style="flex: 1;">
                        <i class="fas fa-info-circle"></i> Details
                    </button>
                `}
            </div>
        `;
        
        container.appendChild(courseCard);
    });
}

/**
 * Start a course
 */
async function startCourse(language) {
    try {
        showLoading();
        
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${LANGUAGE_COURSES_CONFIG.apiBaseUrl}/language-courses/start`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                language: language,
                started_at: new Date().toISOString()
            })
        });
        
        if (response.ok) {
            languageCoursesState.currentLanguage = language;
            await loadCourseProgress();
            openCourseModal(language);
        } else {
            showNotification('Failed to start course', 'error');
        }
    } catch (error) {
        console.error('Error starting course:', error);
        showNotification('Error starting course', 'error');
    } finally {
        hideLoading();
    }
}

/**
 * Open course learning modal
 */
function openCourseModal(language) {
    const COURSES = {
        'c': { title: 'C Programming Mastery', icon: 'fas fa-c' },
        'cpp': { title: 'C++ Advanced Programming', icon: 'fas fa-plus' },
        'python': { title: 'Python Full Stack', icon: 'fab fa-python' },
        'javascript': { title: 'JavaScript & Web Development', icon: 'fab fa-js-square' },
        'java': { title: 'Java Enterprise Development', icon: 'fab fa-java' }
    };
    
    const course = COURSES[language];
    const modal = document.getElementById('courseModal');
    
    if (!modal) {
        createCourseModal();
        return;
    }
    
    // Update modal title
    const titleEl = document.getElementById('courseModalTitle');
    const subtitleEl = document.getElementById('courseModalSubtitle');
    
    if (titleEl) {
        titleEl.innerHTML = `<i class="${course.icon}"></i> ${course.title}`;
    }
    if (subtitleEl) {
        const progress = languageCoursesState.courseProgress[language] || {};
        subtitleEl.textContent = `Module ${(progress.current_module || 0) + 1} • ${progress.progress || 0}% Complete`;
    }
    
    // Show modal
    modal.style.display = 'block';
    
    // Load course content
    loadCourseContent(language);
}

/**
 * Create course learning modal
 */
function createCourseModal() {
    // This should be added to HTML, but if not present, create it dynamically
    const modal = document.createElement('div');
    modal.id = 'courseModal';
    modal.className = 'modal-overlay';
    modal.style.cssText = `
        display: none;
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(2, 6, 23, 0.95);
        z-index: 10000;
        padding: 20px;
        overflow-y: auto;
    `;
    
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 1200px; margin: 0 auto; background: var(--darker); border-radius: 20px; border: 1px solid var(--glass-border); overflow: hidden;">
            <div class="modal-header" style="padding: 20px; border-bottom: 1px solid var(--glass-border); display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h3 id="courseModalTitle" style="font-size: 24px; margin-bottom: 5px;"></h3>
                    <p id="courseModalSubtitle" style="color: var(--text-muted);"></p>
                </div>
                <button onclick="closeCourseModal()" style="background: none; border: none; color: var(--text-muted); font-size: 24px; cursor: pointer;">&times;</button>
            </div>
            <div class="modal-body" style="display: flex; min-height: 600px;">
                <div class="content-side" style="flex: 1; padding: 20px; border-right: 1px solid var(--glass-border); overflow-y: auto; max-height: 600px;">
                    <div id="courseContent">
                        <div style="text-align: center; padding: 40px; color: var(--text-muted);">
                            <i class="fas fa-spinner fa-spin fa-2x"></i>
                            <p style="margin-top: 10px;">Loading course content...</p>
                        </div>
                    </div>
                </div>
                <div class="editor-side" style="flex: 1; padding: 20px; display: flex; flex-direction: column;">
                    <div style="margin-bottom: 15px;">
                        <label style="display: block; margin-bottom: 8px; font-weight: 600;">Code Editor</label>
                        <textarea id="courseCodeEditor" style="width: 100%; height: 200px; padding: 10px; background: rgba(0,0,0,0.5); border: 1px solid var(--glass-border); border-radius: 10px; color: white; font-family: monospace; resize: vertical;"></textarea>
                    </div>
                    <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                        <button onclick="runCourseCode()" class="btn-primary" style="flex: 1;">
                            <i class="fas fa-play"></i> Run
                        </button>
                        <button onclick="submitExercise()" class="btn-success" style="flex: 1;">
                            <i class="fas fa-check"></i> Submit
                        </button>
                        <button onclick="showHint()" class="btn-secondary">
                            <i class="fas fa-lightbulb"></i> Hint
                        </button>
                    </div>
                    <div style="background: rgba(0,0,0,0.3); border-radius: 10px; padding: 15px; overflow-y: auto; flex: 1;">
                        <h4 style="margin-bottom: 10px;">Output:</h4>
                        <pre id="courseCodeOutput" style="margin: 0; color: #10b981; font-size: 12px; white-space: pre-wrap; word-wrap: break-word;">Ready to run code...</pre>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
}

/**
 * Load course content
 */
function loadCourseContent(language) {
    const contentEl = document.getElementById('courseContent');
    if (!contentEl) return;
    
    const MODULES = {
        'c': [
            {title: 'Variables & Data Types', topics: ['Primitive Types', 'Variables', 'Constants', 'Type Casting']},
            {title: 'Operators & Expressions', topics: ['Arithmetic', 'Logical', 'Bitwise', 'Conditional']},
            {title: 'Control Flow', topics: ['If-Else', 'Switch', 'Loops', 'Break & Continue']}
        ],
        'python': [
            {title: 'Python Basics', topics: ['Syntax', 'Variables', 'Data Types', 'Operators']},
            {title: 'Collections', topics: ['Lists', 'Tuples', 'Dictionaries', 'Sets']},
            {title: 'Functions', topics: ['Function Definitions', 'Arguments', 'Return Values', 'Scoping']}
        ]
    };
    
    const modules = MODULES[language] || MODULES['c'];
    const progress = languageCoursesState.courseProgress[language] || {};
    const currentModuleIdx = progress.current_module || 0;
    
    contentEl.innerHTML = `
        <div style="margin-bottom: 20px;">
            <h4 style="margin-bottom: 15px;">Modules</h4>
            ${modules.map((mod, idx) => {
                const isCompleted = progress.completed_modules?.includes(idx) || false;
                const isCurrent = idx === currentModuleIdx;
                return `
                    <div onclick="selectModule(${idx})" style="
                        padding: 12px;
                        margin-bottom: 8px;
                        border-radius: 8px;
                        cursor: pointer;
                        background: ${isCurrent ? 'rgba(99, 102, 241, 0.2)' : isCompleted ? 'rgba(16, 185, 129, 0.1)' : 'rgba(255,255,255,0.05)'};
                        border-left: 3px solid ${isCurrent ? '#6366f1' : isCompleted ? '#10b981' : 'transparent'};
                        transition: all 0.2s;
                    ">
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <i class="fas ${isCompleted ? 'fa-check-circle' : 'fa-circle'}" style="color: ${isCompleted ? '#10b981' : isCurrent ? '#6366f1' : 'var(--text-muted)'}; font-size: 14px;"></i>
                            <div style="flex: 1;">
                                <div style="font-weight: ${isCurrent ? '600' : '500'};">${mod.title}</div>
                                <div style="font-size: 12px; color: var(--text-muted);">${mod.topics.join(', ')}</div>
                            </div>
                        </div>
                    </div>
                `;
            }).join('')}
        </div>
        <div style="padding-top: 15px; border-top: 1px solid var(--glass-border);">
            <h4 style="margin-bottom: 10px;">Current Topic</h4>
            <p style="color: var(--text-muted); line-height: 1.6;">
                ${modules[currentModuleIdx].title}<br>
                Learn: ${modules[currentModuleIdx].topics.join(', ')}
            </p>
        </div>
    `;
}

/**
 * Run course code
 */
async function runCourseCode() {
    if (languageCoursesState.isRunning) return;
    
    languageCoursesState.isRunning = true;
    const codeEditor = document.getElementById('courseCodeEditor');
    const outputEl = document.getElementById('courseCodeOutput');
    
    if (!codeEditor || !outputEl) {
        languageCoursesState.isRunning = false;
        return;
    }
    
    const code = codeEditor.value.trim();
    if (!code) {
        outputEl.textContent = 'Please write some code first...';
        languageCoursesState.isRunning = false;
        return;
    }
    
    try {
        outputEl.textContent = 'Running...';
        showLoading();
        
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${LANGUAGE_COURSES_CONFIG.apiBaseUrl}/language-courses/run-code`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                language: languageCoursesState.currentLanguage,
                code: code,
                module_id: `${languageCoursesState.currentLanguage}_mod_${languageCoursesState.courseProgress[languageCoursesState.currentLanguage]?.current_module || 0}`
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            outputEl.textContent = data.output || data.error || 'Code executed successfully!';
            outputEl.style.color = data.error ? '#ef4444' : '#10b981';
        } else {
            outputEl.textContent = 'Error executing code. Please try again.';
            outputEl.style.color = '#ef4444';
        }
    } catch (error) {
        console.error('Error running code:', error);
        outputEl.textContent = 'Network error. Please try again.';
        outputEl.style.color = '#ef4444';
    } finally {
        languageCoursesState.isRunning = false;
        hideLoading();
    }
}

/**
 * Submit exercise for grading
 */
async function submitExercise() {
    const codeEditor = document.getElementById('courseCodeEditor');
    const outputEl = document.getElementById('courseCodeOutput');
    
    if (!codeEditor) return;
    
    const code = codeEditor.value.trim();
    if (!code) {
        showNotification('Please write some code first', 'error');
        return;
    }
    
    try {
        showLoading();
        
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${LANGUAGE_COURSES_CONFIG.apiBaseUrl}/language-courses/submit-exercise`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                language: languageCoursesState.currentLanguage,
                code: code,
                module_id: `${languageCoursesState.currentLanguage}_mod_${languageCoursesState.courseProgress[languageCoursesState.currentLanguage]?.current_module || 0}`
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            const points = data.score || 0;
            
            outputEl.innerHTML = `
                <strong style="color: #10b981;">✓ Submitted Successfully!</strong><br><br>
                Score: ${points}/100<br>
                Feedback: ${data.feedback || 'Great work!'}<br><br>
                ${data.ai_feedback ? `AI Assistance: ${data.ai_feedback}` : ''}
            `;
            outputEl.style.color = '#10b981';
            
            showNotification(`Exercise submitted! +${points} points`, 'success');
            
            // Update progress
            setTimeout(() => {
                loadCourseProgress();
                displayAvailableCourses();
            }, 1000);
        } else {
            showNotification('Failed to submit exercise', 'error');
        }
    } catch (error) {
        console.error('Error submitting exercise:', error);
        showNotification('Error submitting exercise', 'error');
    } finally {
        hideLoading();
    }
}

/**
 * Show hint for current exercise
 */
function showHint() {
    const hints = {
        'c': 'Hint: Use printf() to print output. Remember semicolons at the end of statements!',
        'python': 'Hint: Use print() for output. Python is case-sensitive!',
        'javascript': 'Hint: Use console.log() for output. Don\'t forget curly braces!',
        'java': 'Hint: Remember the main method syntax. Use System.out.println() for output!',
        'cpp': 'Hint: Use cout for output. Don\'t forget #include <iostream>!'
    };
    
    const hint = hints[languageCoursesState.currentLanguage] || 'Try breaking down the problem into smaller steps.';
    showNotification(hint, 'info');
}

/**
 * View course details
 */
function viewCourseDetails(language) {
    const details = {
        'c': 'C is the foundation of modern programming. Learn pointers, memory management, and efficient coding.',
        'python': 'Python is versatile and beginner-friendly. Master data structures, functions, and OOP concepts.',
        'javascript': 'JavaScript powers the web. Learn DOM manipulation, async programming, and modern frameworks.',
        'java': 'Java is enterprise-grade. Master OOP, design patterns, and scalable applications.',
        'cpp': 'C++ combines power and flexibility. Learn advanced OOP and performance optimization.'
    };
    
    alert(`${language.toUpperCase()}\n\n${details[language] || 'A great programming language to learn!'}`);
}

/**
 * Close course modal
 */
function closeCourseModal() {
    const modal = document.getElementById('courseModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

/**
 * Select a module
 */
function selectModule(moduleIdx) {
    const progress = languageCoursesState.courseProgress[languageCoursesState.currentLanguage];
    if (progress) {
        progress.current_module = moduleIdx;
    }
    loadCourseContent(languageCoursesState.currentLanguage);
}

// =============== HELPER FUNCTIONS ===============
function showNotification(message, type = 'info') {
    let notif = document.getElementById('course-notification');
    if (!notif) {
        notif = document.createElement('div');
        notif.id = 'course-notification';
        document.body.appendChild(notif);
    }
    
    const colors = { success: '#10b981', error: '#ef4444', info: '#3b82f6' };
    notif.style.cssText = `
        position: fixed; top: 20px; right: 20px; padding: 15px 20px;
        background: rgba(15, 23, 42, 0.95); border: 1px solid var(--glass-border);
        border-left: 4px solid ${colors[type]};
        border-radius: 10px; color: white; z-index: 10000;
    `;
    notif.textContent = message;
    notif.style.display = 'block';
    
    setTimeout(() => { notif.style.display = 'none'; }, 3000);
}

function showLoading() {
    let loader = document.getElementById('course-loader');
    if (!loader) {
        loader = document.createElement('div');
        loader.id = 'course-loader';
        loader.innerHTML = '<div style="font-size: 30px; color: #6366f1;"><i class="fas fa-spinner fa-spin"></i></div>';
        loader.style.cssText = `
            position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(2, 6, 23, 0.3); z-index: 9999;
            display: flex; align-items: center; justify-content: center;
        `;
        document.body.appendChild(loader);
    }
    loader.style.display = 'flex';
}

function hideLoading() {
    const loader = document.getElementById('course-loader');
    if (loader) loader.style.display = 'none';
}
