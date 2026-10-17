from flask import Flask, render_template, request, jsonify
import os
import re
import time
import base64
from google import genai
from google.genai import types
import PyPDF2

app = Flask(__name__)

# Initialize the Google GenAI client using your environment API key
client = genai.Client()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'txt', 'pdf', 'png', 'jpg', 'jpeg'}

def contains_prohibited_content(text):
    """
    Scans input text for patterns related to illegal acts, fraud, self-harm, 
    violence, hate speech, sexually explicit material, pornography, or child safety violations (CSAM).
    """
    if not text:
        return False
        
    prohibited_patterns = [
        r'\b(csam|csae|minor abuse|child exploitation)\b',
        r'\b(suicide|self-harm|cut myself|end my life)\b',
        r'\b(how to make a bomb|explosive recipe|illegal weapon)\b',
        r'\b(hatespeech|racial slur|kill all|white supremacy target)\b',
        r'\b(pornography|sexually explicit|xxx video|incest)\b',
        r'\b(bank fraud scheme|money laundering guide|stolen credit card network)\b'
    ]
    
    lower_text = text.lower()
    for pattern in prohibited_patterns:
        if re.search(pattern, lower_text):
            return True
            
    return False

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
        filename = file.filename
        file_ext = filename.rsplit('.', 1)[1].lower()
        
        try:
            if file_ext in {'txt', 'pdf'}:
                extracted_text = ""
                if file_ext == 'txt':
                    extracted_text = file.read().decode('utf-8', errors='ignore')
                elif file_ext == 'pdf':
                    reader = PyPDF2.PdfReader(file)
                    for page in reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            extracted_text += page_text + "\n"
                            
                if not extracted_text.strip():
                    return jsonify({'error': 'Could not extract text from the document.'}), 400
                
                if contains_prohibited_content(extracted_text):
                    return jsonify({'error': 'Upload rejected: Document contains restricted, harmful, or prohibited content policies.'}), 400
                    
                return jsonify({'text': extracted_text, 'type': 'text'})
                
            elif file_ext in {'png', 'jpg', 'jpeg'}:
                image_bytes = file.read()
                if not image_bytes:
                    return jsonify({'error': 'Uploaded image file is empty.'}), 400
                
                encoded_image = base64.b64encode(image_bytes).decode('utf-8')
                mime_type = f"image/{'jpeg' if file_ext == 'jpg' else file_ext}"
                
                return jsonify({
                    'image_data': encoded_image,
                    'mime_type': mime_type,
                    'type': 'image'
                })
                
        except Exception as e:
            return jsonify({'error': f'Parsing error: {str(e)}'}), 500
            
    return jsonify({'error': 'Invalid file type. Please upload a PDF, TXT, or image file (PNG, JPG, JPEG).'}), 400

@app.route('/ask', methods=['POST'])
def ask_question():
    data = request.get_json()
    document_text = data.get('document_text', '')
    image_data = data.get('image_data', '')
    mime_type = data.get('mime_type', 'image/jpeg')
    question = data.get('question', '')
    
    if (not document_text and not image_data) or not question:
        return jsonify({'error': 'Missing document/image content or question.'}), 400
        
    if contains_prohibited_content(question) or (document_text and contains_prohibited_content(document_text)):
        return jsonify({'error': 'Request blocked: Inquiries involving illegal acts, fraud, self-harm, hate speech, sexually explicit material, or child exploitation are strictly prohibited.'}), 400
        
    system_instruction = (
        "You are a secure, ethical, and professional document and image assistant. You must strictly refuse to assist with, "
        "generate, summarize, or promote any illegal acts, fraud, financial scams, self-harm, "
        "violence, hate speech, harassment, sexually explicit material, pornography, or any form "
        "of child exploitation and abuse (CSAM). Inspect both text and visual media thoroughly. "
        "If any uploaded image or document touches upon these restricted topics, immediately and firmly refuse. "
        "Safely and accurately assist with all other valid, legal documents and images."
    )
    
    contents = []
    if image_data:
        img_bytes = base64.b64decode(image_data)
        image_part = types.Part.from_bytes(data=img_bytes, mime_type=mime_type)
        contents.append(image_part)
        contents.append(f"User Question regarding the image: {question}")
    else:
        prompt = f"Reference Document:\n---\n{document_text}\n---\n\nUser Question: {question}"
        contents.append(prompt)
    
    strict_safety_config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        safety_settings=[
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
            ),
        ]
    )
    
    models_to_try = ['gemini-3.8-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']
    
    last_error = ""
    for model_name in models_to_try:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=strict_safety_config
                )
                if response and response.text:
                    return jsonify({'answer': response.text})
            except Exception as e:
                last_error = str(e)
                if '503' in last_error or 'UNAVAILABLE' in last_error:
                    time.sleep(1)
                    continue
                else:
                    break
                    
    return jsonify({'error': f'Request could not be processed due to safety policies or server capacity: {last_error}'}), 500

if __name__ == '__main__':
    app.run(debug=True)
