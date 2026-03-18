import codecs
import re

file_path = r'c:\Users\wayne\Documents\edusync-babu\communication_stage.html'
with codecs.open(file_path, 'r', 'utf-8') as f:
    text = f.read()

# 1. Update startDirectionFollower spinner
text = text.replace(
    "document.getElementById('directionMapGrid').innerHTML = '<i class=\"fas fa-spinner fa-spin\"></i>';",
    "document.getElementById('directionMapGrid').innerHTML = '<div style=\"grid-column: 1 / -1; text-align: center; padding: 40px;\"><div class=\"loader-ripple\" style=\"margin: 0 auto 20px;\"><div></div><div></div></div><p style=\"color: var(--text-muted); font-size: 16px;\">Generating map...</p></div>';"
)

# 2. Update evaluateDirection loading UI
eval_dir_match = r"(async function evaluateDirection\(selectedName\) \{\s*try \{\s*)(showToast\('info', 'Checking', 'Verifying location\.\.\.'\);)"
eval_dir_replace = r"\1\2\n                showEvalLoading('directionFollowerScreen', 'Verifying your location...');"
text = re.sub(eval_dir_match, eval_dir_replace, text)

# Update the error hide loading
eval_dir_err = r"(showToast\('error', 'Error', 'Evaluation failed'\);)"
eval_dir_err_rep = r"hideEvalLoading('directionFollowerScreen');\n                \1"
text = re.sub(eval_dir_err, eval_dir_err_rep, text)

# 3. Tone Recognizer: also add loading UI if it exists!
# Let's add it for tone recognizer as well to be safe
tone_spinner = "document.getElementById('toneOptions').innerHTML = '<i class=\"fas fa-spinner fa-spin\"></i>';"
tone_spinner_rep = "document.getElementById('toneOptions').innerHTML = '<div style=\"grid-column: 1 / -1; text-align: center; padding: 40px;\"><div class=\"loader-ripple\" style=\"margin: 0 auto 20px;\"><div></div><div></div></div><p style=\"color: var(--text-muted); font-size: 16px;\">Generating tone options...</p></div>';"
text = text.replace(tone_spinner, tone_spinner_rep)

eval_tone_match = r"(async function evaluateTone\(selectedTone\) \{\s*try \{\s*)(showToast\('info', 'Checking', 'Analyzing tone\.\.\.'\);)"
eval_tone_replace = r"\1\2\n                showEvalLoading('toneRecognizerScreen', 'AI is analyzing your tone selection...');"
text = re.sub(eval_tone_match, eval_tone_replace, text)

eval_tone_err = r"(showToast\('error', 'Error', 'Evaluation failed'\);)"
eval_tone_err_rep = r"hideEvalLoading('toneRecognizerScreen');\n                \1"
text = re.sub(eval_tone_err, eval_tone_err_rep, text)

# 4. Fill the Beats: add loading UI too
fill_spinner = "document.getElementById('fillBeatsContent').innerHTML = '<div style=\"text-align: center; padding: 40px;\"><i class=\"fas fa-spinner fa-spin\" style=\"font-size: 48px; color: var(--primary);\"></i><p style=\"margin-top: 15px; color: var(--text-muted);\">Loading challenge...</p></div>';"
fill_spinner_rep = "document.getElementById('fillBeatsContent').innerHTML = '<div style=\"text-align: center; padding: 40px;\"><div class=\"loader-ripple\" style=\"margin: 0 auto 20px;\"><div></div><div></div></div><p style=\"color: var(--text-muted); font-size: 16px;\">Generating your challenge...</p></div>';"
text = text.replace(fill_spinner, fill_spinner_rep)

eval_fill_match = r"(async function submitFillBeats\(\) \{\s*try \{\s*)(showToast\('info', 'Evaluating', 'Checking your answers\.\.\.'\);)"
eval_fill_replace = r"\1\2\n                showEvalLoading('fillBeatsScreen', 'AI is evaluating your answers...');"
text = re.sub(eval_fill_match, eval_fill_replace, text)

eval_fill_err = r"(showToast\('error', 'Error', 'Evaluation failed'\);)"
eval_fill_err_rep = r"hideEvalLoading('fillBeatsScreen');\n                \1"
text = re.sub(eval_fill_err, eval_fill_err_rep, text)

with codecs.open(file_path, 'w', 'utf-8') as f:
    f.write(text)

print("Direction/Tone/Fill modules updated with loaders.")
