import codecs
import re

file_path = r'c:\Users\wayne\Documents\edusync-babu\communication_stage.html'
with codecs.open(file_path, 'r', 'utf-8') as f:
    text = f.read()

start_idx = text.find('id="directionFollowerScreen"')
if start_idx != -1:
    end_idx = text.find('id="toneRecognizerScreen"', start_idx)
    section = text[start_idx:end_idx]
    with codecs.open(r'c:\Users\wayne\Documents\edusync-babu\temp_dir_html.txt', 'w', 'utf-8') as out:
        out.write(section)
    print("Exported section")
else:
    print("Not found")
