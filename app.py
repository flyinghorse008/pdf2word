from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import os
import uuid
import threading
from werkzeug.utils import secure_filename
from pdf2docx import Converter

app = Flask(__name__, static_folder='static')
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
OUTPUT_FOLDER = os.path.join(BASE_DIR, 'outputs')
ALLOWED_EXTENSIONS = {'pdf'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

conversion_status = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def convert_pdf_to_word(task_id, pdf_path, docx_path):
    try:
        conversion_status[task_id] = {'status': 'processing', 'progress': 0}
        
        cv = Converter(pdf_path)
        
        def progress_callback(progress):
            conversion_status[task_id]['progress'] = int(progress * 100)
        
        cv.convert(docx_path, progress_callback=progress_callback)
        cv.close()
        
        conversion_status[task_id] = {
            'status': 'completed',
            'progress': 100,
            'output_file': os.path.basename(docx_path)
        }
    except Exception as e:
        conversion_status[task_id] = {
            'status': 'failed',
            'error': str(e)
        }

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': '没有文件上传'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400
    
    if file and allowed_file(file.filename):
        task_id = str(uuid.uuid4())
        filename = secure_filename(file.filename)
        pdf_path = os.path.join(UPLOAD_FOLDER, f"{task_id}_{filename}")
        docx_filename = filename.rsplit('.', 1)[0] + '.docx'
        docx_path = os.path.join(OUTPUT_FOLDER, f"{task_id}_{docx_filename}")
        
        file.save(pdf_path)
        
        conversion_status[task_id] = {'status': 'pending', 'progress': 0}
        
        thread = threading.Thread(target=convert_pdf_to_word, args=(task_id, pdf_path, docx_path))
        thread.start()
        
        return jsonify({
            'task_id': task_id,
            'filename': filename,
            'message': '文件上传成功，正在转换中...'
        })
    
    return jsonify({'error': '不支持的文件格式'}), 400

@app.route('/status/<task_id>')
def get_status(task_id):
    if task_id not in conversion_status:
        return jsonify({'error': '任务不存在'}), 404
    
    return jsonify(conversion_status[task_id])

@app.route('/download/<task_id>')
def download_file(task_id):
    if task_id not in conversion_status:
        return jsonify({'error': '任务不存在'}), 404
    
    status = conversion_status[task_id]
    if status['status'] != 'completed':
        return jsonify({'error': '文件还未转换完成'}), 400
    
    output_file = status['output_file']
    file_path = os.path.join(OUTPUT_FOLDER, output_file)
    
    if not os.path.exists(file_path):
        return jsonify({'error': '文件不存在'}), 404
    
    download_name = output_file.split('_', 1)[1] if '_' in output_file else output_file
    return send_file(file_path, as_attachment=True, download_name=download_name)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
