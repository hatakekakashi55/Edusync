def check_html_balance(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Simple tag balancer for <div> and <main>
    tags = []
    import re
    # We only care about div, main, aside, section
    pattern = re.compile(r'<(div|main|aside)\b|/(div|main|aside)>')
    
    depth = 0
    max_depth = 0
    
    lines = content.split('\n')
    for i, line in enumerate(lines):
        matches = pattern.findall(line)
        for m in matches:
            if m[0]: # Opening
                depth += 1
                if depth > max_depth: max_depth = depth
            else: # Closing
                depth -= 1
                if depth < 0:
                    print(f"Negative depth at line {i+1}: {line}")
                    # return i+1
    
    print(f"Final depth: {depth}")
    return depth

check_html_balance(r"c:\Users\wayne\Documents\edusync-babu\stage 2.html")
