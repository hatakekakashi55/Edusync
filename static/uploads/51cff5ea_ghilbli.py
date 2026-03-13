from flask import Flask, request, send_file, render_template
import os
from PIL import Image
import io

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Placeholder function for Ghibli-style conversion
def convert_to_ghibli_style(image_path, output_path):
    # In a real implementation, this would use an AI model (e.g., Stable Diffusion)
    # For now, we'll just add a simple filter as a demo
    img = Image.open(image_path)
    # Simulate some processing (e.g., adjust colors)
    img = img.convert('RGB')
    img.save(output_path, 'PNG')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        return 'No file uploaded', 400
    
    file = request.files['file']
    if file.filename == '':
        return 'No file selected', 400
    
    # Save uploaded file
    input_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(input_path)
    
    # Convert to Ghibli style
    output_filename = 'ghibli_' + file.filename
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)
    convert_to_ghibli_style(input_path, output_path)
    
    # Return the processed image
    return send_file(output_path, mimetype='image/png')

if __name__ == '__main__':
    app.run(debug=True)