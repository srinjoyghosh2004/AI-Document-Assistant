import os
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import PyPDF2

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'txt'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def extract_text(file_path, filename):
    ext = filename.rsplit('.', 1)[1].lower()
    text = ""
    if ext == 'txt':
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
    elif ext == 'pdf':
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    return text

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Extract text and generate basic stats/summary
        text = extract_text(file_path, filename)
        sentences = [s.strip() for s in text.split('.') if len(s.strip()) > 20]
        summary = ". ".join(sentences[:3]) + "." if sentences else "Document is empty or unreadable."
        
        return jsonify({
            'success': True,
            'filename': filename,
            'summary': summary,
            'total_characters': len(text)
        })
    return jsonify({'error': 'Invalid file type. Please upload a PDF or TXT file.'}), 400

@app.route('/ask', methods=['POST'])
def ask_question():
    data = request.json
    filename = data.get('filename')
    question = data.get('question', '').lower()
    
    if not filename:
        return jsonify({'error': 'No active document found.'}), 400
        
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found on server.'}), 404
        
    text = extract_text(file_path, filename)
    paragraphs = text.split('\n\n')
    
    # Simple document retrieval based on keyword matching
    keywords = [kw for kw in question.split() if len(kw) > 3]
    best_match = "Could not find a direct reference matching your question in the document."
    
    for para in paragraphs:
        if any(kw in para.lower() for kw in keywords):
            best_match = para.strip()
            break
            
    return jsonify({
        'answer': f"Based on the document contents, here is the most relevant reference found:",
        'reference': best_match
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)