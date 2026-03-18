import codecs
import re

file_path = r'c:\Users\wayne\Documents\edusync-babu\communication_stage.html'
with codecs.open(file_path, 'r', 'utf-8') as f:
    text = f.read()

# 1. Replace all loading challenge spinners
old_loader_pattern = r'<div style="text-align: center; padding: 40px;"><i class="fas fa-spinner fa-spin" style="font-size: 48px; color: var\(--primary\);"></i><p style="margin-top: 15px; color: var\(--text-muted\);">Loading challenge...</p></div>'
new_loader_html = r'<div style="text-align: center; padding: 40px;"><div class="loader-ripple" style="margin: 0 auto 20px;"><div></div><div></div></div><p style="color: var(--text-muted); font-size: 16px;">Generating your challenge...</p></div>'
text = re.sub(old_loader_pattern, new_loader_html, text)

# For innerHTML strings
old_loader_pattern2 = r'innerHTML = \'<div style="text-align: center; padding: 40px;"><i class="fas fa-spinner fa-spin" style="font-size: 48px; color: var\(--primary\);"></i><p style="margin-top: 15px; color: var\(--text-muted\);">Loading challenge...<\/p><\/div>\';'
new_loader_html2 = 'innerHTML = `<div style="text-align: center; padding: 40px;"><div class="loader-ripple" style="margin: 0 auto 20px;"><div></div><div></div></div><p style="color: var(--text-muted); font-size: 16px;">Generating your challenge...</p></div>`;'
text = re.sub(old_loader_pattern2, new_loader_html2, text)

# 2. Add eval loader global functions
script_start = r'// ==========================================================\s*// 1. GLOBAL VARIABLES AND CONFIGURATION'
eval_funcs = '''
// ==========================================================
// 1. GLOBAL VARIABLES AND CONFIGURATION

        function showEvalLoading(containerId, msg) {
            const container = document.getElementById(containerId);
            if (!container) return;
            Array.from(container.children).forEach(c => {
                if (!c.classList.contains('eval-loader')) c.style.display = 'none';
            });
            let loader = container.querySelector('.eval-loader');
            if (!loader) {
                loader = document.createElement('div');
                loader.className = 'eval-loader';
                container.appendChild(loader);
            }
            loader.innerHTML = `<div style="text-align: center; padding: 40px;"><div class="loader-ripple" style="margin: 0 auto 20px;"><div></div><div></div></div><p style="color: var(--text-muted); font-size: 16px;">${msg}</p></div>`;
            loader.style.display = 'block';
        }

        function hideEvalLoading(containerId) {
            const container = document.getElementById(containerId);
            if (!container) return;
            const loader = container.querySelector('.eval-loader');
            if (loader) loader.style.display = 'none';
            Array.from(container.children).forEach(c => {
                if (!c.classList.contains('eval-loader')) c.style.display = '';
            });
        }
'''
if 'showEvalLoading' not in text:
    text = re.sub(script_start, eval_funcs, text)

# Helper function to inject loading state into submit functions safely
def safe_replace(pattern, repl, content, count=1):
    return re.sub(pattern, repl, content, count=count)

# Listening
if "showEvalLoading('listeningChallengeContent'" not in text:
    text = safe_replace(r"(if \(submitBtn\) submitBtn\.disabled = true;)", r"\1\n                showEvalLoading('listeningChallengeContent', 'AI is evaluating your answer...');", text)
    text = safe_replace(r"(showToast\('error', 'Evaluation Failed')", r"hideEvalLoading('listeningChallengeContent');\n                    \1", text)
    text = safe_replace(r"(showToast\('error', 'Network Error')", r"hideEvalLoading('listeningChallengeContent');\n                \1", text)

# Reading
if "showEvalLoading('readingChallengeContent'" not in text:
    text = safe_replace(r"(if \(document\.getElementById\('readingSubmitBtn'\)\) document\.getElementById\('readingSubmitBtn'\)\.disabled = true;)", r"\1\n                showEvalLoading('readingChallengeContent', 'AI is analyzing your reading...');", text)
    text = safe_replace(r"(showToast\('error', 'Evaluation Error')", r"hideEvalLoading('readingChallengeContent');\n                    \1", text)
    text = safe_replace(r"(showToast\('error', 'Submission Error')", r"hideEvalLoading('readingChallengeContent');\n                \1", text)

# Writing
if "showEvalLoading('writingChallengeContent'" not in text:
    text = safe_replace(r"(document\.getElementById\('writingAnswer'\)\.disabled = true;)", r"\1\n                showEvalLoading('writingChallengeContent', 'AI is analyzing your writing...');", text)
    text = safe_replace(r"(showToast\('error', 'Submission Error', error\.message \|\| 'Could not evaluate your essay\. Please try again\.'\);\s+document\.getElementById\('writingAnswer'\)\.disabled = false;)", r"hideEvalLoading('writingChallengeContent');\n                \1", text)

# Speaking
if "showEvalLoading('speakingChallengeContent'" not in text:
    text = safe_replace(r"(document\.getElementById\('speakingSubmitBtn'\)\.disabled = true;)", r"\1\n                showEvalLoading('speakingChallengeContent', 'AI is analyzing your speech...');", text)
    text = safe_replace(r"(showToast\('error', 'Evaluation Error', 'Failed to evaluate recording'\);)", r"hideEvalLoading('speakingChallengeContent');\n                    \1", text)
    text = safe_replace(r"(showToast\('error', 'Submission Error', 'Could not submit recording: ' \+ error\.message\);)", r"hideEvalLoading('speakingChallengeContent');\n                \1", text)

with codecs.open(file_path, 'w', 'utf-8') as f:
    f.write(text)

print("HTML updated successfully!")
