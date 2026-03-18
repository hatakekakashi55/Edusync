import codecs
file_path = r'c:\Users\wayne\Documents\edusync-babu\communication_stage.html'
with codecs.open(file_path, 'r', 'utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'directionFollowerScreen' in line:
        print(f'L{i+1}: {line.strip()[:150]}')
