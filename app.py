import os
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import PyPDF2
from google import genai
from google.genai import types

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'txt'}
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # Limit file size strictly to 5MB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize the official Gemini Client (reads GEMINI_API_KEY from environment variables)
client = genai.Client()

# Define strict safety settings to block explicit, harmful, or illegal text generation
STRICT_SAFETY_SETTINGS = [
    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE),
    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE),
    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE),
    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE),
]

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def extract_text(file_path, filename):
    ext = filename.rsplit('.', 1)[1].lower()
    text = ""
    try:
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
    except Exception as e:
        print(f"Error parsing file: {e}")
    return text

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part found in request.'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected.'}), 400
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        try:
            # 1. Extract text from the uploaded document
            text = extract_text(file_path, filename)
            
            if not text.strip():
                return jsonify({'error': 'The uploaded document is empty or unreadable.'}), 400

            # 2. Run a safety evaluation check via Gemini API using strict settings
            # We evaluate a snippet of the document to ensure no severe violations exist
            preview_text = text[:3000] # Check the opening text bounds
            prompt = f"Analyze this text snippet for any illegal, sexually explicit, or harmful content. If clean, provide a concise 3-sentence summary:\n\n{preview_text}"

            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    safety_settings=STRICT_SAFETY_SETTINGS,
                    max_output_tokens=200
                )
            )

            # 3. Check if Google's safety filters triggered a block
            if not response.text or (response.candidates and response.candidates[0].finish_reason == types.FinishReason.SAFETY):
                return jsonify({
                    'error': 'Upload rejected: The document contains content that violates safety policies (explicit, harmful, or illicit material).'
                }), 400

            return jsonify({
                'success': True,
                'filename': filename,
                'summary': response.text,
                'total_characters': len(text)
            })

        except Exception as e:
            return jsonify({'error': f'Processing error: {str(e)}'}), 500
            
        finally:
            # CRITICAL SECURITY STEP: Immediately delete the file from the server disk!
            # This ensures zero persistent storage of user-uploaded binaries.
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as cleanup_error:
                    print(f"Cleanup error: {cleanup_error}")

    return jsonify({'error': 'Invalid file type. Only PDF and TXT files are allowed.'}), 400

@app.route('/ask', methods=['POST'])
def ask_question():
    data = request.json
    document_text = data.get('document_text', '')
    question = data.get('question', '')
    
    if not document_text or not question:
        return jsonify({'error': 'Missing document context or question.'}), 400
        
    try:
        # Prompt construction pairing the document text securely with the user question
        prompt = f"Context document contents:\n{document_text[:8000]}\n\nQuestion: {question}\n\nAnswer accurately based only on the context provided:"

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                safety_settings=STRICT_SAFETY_SETTINGS,
                max_output_tokens=500
            )
        )

        # Handle safety blocks during Q&A generation
        if not response.text or (response.candidates and response.candidates[0].finish_reason == types.FinishReason.SAFETY):
            return jsonify({
                'answer': 'I cannot answer this question because the content triggers safety policies regarding explicit or prohibited material.'
            })

        return jsonify({
            'answer': response.text
        })

    except Exception as e:
        return jsonify({'error': f'Error generating response: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=False, port=5000) # Keep debug=False in production environments
