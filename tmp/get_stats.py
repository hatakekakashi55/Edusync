import os
import json
import re

stats = {
    "total_lines": 0,
    "total_endpoints": 0,
    "total_models": 0,
    "modules": {
        "models": [],
        "services": [],
        "utils": [],
        "routes": [],
    }
}

def count_lines_and_features(filepath, category=None):
    lines = 0
    endpoints = 0
    models = 0
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = len(content.split('\n'))
            
            # Count endpoints
            endpoints = len(re.findall(r'@router\.(?:get|post|put|delete|patch)', content))
            
            # Count models
            models = len(re.findall(r'class\s+\w+\(.*Model.*\):', content)) + len(re.findall(r'class\s+\w+\(BaseModel\):', content))
            
            stats["total_lines"] += lines
            stats["total_endpoints"] += endpoints
            stats["total_models"] += models
            
            if category:
                stats["modules"][category].append({
                    "name": os.path.basename(filepath),
                    "path": filepath.replace("\\", "/"),
                    "lines": lines,
                    "endpoints": endpoints,
                    "models": models,
                    "size": os.path.getsize(filepath)
                })
                
    except Exception as e:
        print(f"Error reading {filepath}: {e}")

# Process main.py
count_lines_and_features("main.py")

# Process app directory
for root, dirs, files in os.walk("app"):
    if "__pycache__" in root:
        continue
    for file in files:
        if file.endswith(".py"):
            filepath = os.path.join(root, file)
            category = "other"
            if "models" in root:
                category = "models"
            elif "services" in root:
                category = "services"
            elif "utils" in root:
                category = "utils"
            elif "routes" in root:
                category = "routes"
            
            # Create category if it doesn't exist
            if category not in stats["modules"]:
                stats["modules"][category] = []
                
            count_lines_and_features(filepath, category)

with open("tmp/stats.json", "w") as f:
    json.dump(stats, f, indent=2)
print("Stats generated successfully in tmp/stats.json")
