import os
import uuid
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader, PdfWriter, PdfMerger
import zipfile
import io
from datetime import datetime

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['PROCESSED_FOLDER'] = 'processed'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB limit
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'}

# Ensure folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload_file():
    # Check if files were uploaded
    if 'files' not in request.files:
        return jsonify({'success': False, 'message': 'No files uploaded'}), 400
    
    files = request.files.getlist('files')
    token = str(uuid.uuid4())
    token_dir = os.path.join(app.config['UPLOAD_FOLDER'], token)
    os.makedirs(token_dir, exist_ok=True)
    
    # Save uploaded files
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(token_dir, filename))
    
    return jsonify({
        'success': True,
        'token': token,
        'message': f'{len(files)} files uploaded successfully'
    })

@app.route('/api/compress', methods=['POST'])
def compress_pdf():
    data = request.json
    token = data.get('token')
    level = data.get('level', '2')
    
    if not token:
        return jsonify({'success': False, 'message': 'Missing token'}), 400
    
    upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], token)
    if not os.path.exists(upload_dir):
        return jsonify({'success': False, 'message': 'Invalid token'}), 400
    
    # Find the first PDF file
    pdf_files = [f for f in os.listdir(upload_dir) if f.lower().endswith('.pdf')]
    if not pdf_files:
        return jsonify({'success': False, 'message': 'No PDF file found'}), 400
    
    # Process file
    input_path = os.path.join(upload_dir, pdf_files[0])
    output_filename = f"compressed_{pdf_files[0]}"
    output_path = os.path.join(app.config['PROCESSED_FOLDER'], output_filename)
    
    # Simple compression simulation
    reader = PdfReader(input_path)
    writer = PdfWriter()
    
    for page in reader.pages:
        writer.add_page(page)
    
    # Set compression level
    if level == '3':  # High compression
        for page in writer.pages:
            page.compress_content_streams()
    
    with open(output_path, "wb") as f:
        writer.write(f)
    
    # Clean up upload directory
    shutil.rmtree(upload_dir)
    
    return jsonify({
        'success': True,
        'download_url': f'/download/{output_filename}',
        'original_size': os.path.getsize(input_path),
        'new_size': os.path.getsize(output_path),
        'reduction': round((1 - (os.path.getsize(output_path) / os.path.getsize(input_path))) * 100, 1)
    })

@app.route('/api/merge', methods=['POST'])
def merge_pdf():
    data = request.json
    token = data.get('token')
    
    if not token:
        return jsonify({'success': False, 'message': 'Missing token'}), 400
    
    upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], token)
    if not os.path.exists(upload_dir):
        return jsonify({'success': False, 'message': 'Invalid token'}), 400
    
    # Get all PDF files
    pdf_files = [f for f in os.listdir(upload_dir) if f.lower().endswith('.pdf')]
    if len(pdf_files) < 2:
        return jsonify({'success': False, 'message': 'Need at least 2 PDF files to merge'}), 400
    
    # Merge PDFs
    merger = PdfMerger()
    total_size = 0
    
    for pdf_file in pdf_files:
        file_path = os.path.join(upload_dir, pdf_file)
        merger.append(file_path)
        total_size += os.path.getsize(file_path)
    
    # Save merged PDF
    output_filename = f"merged_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    output_path = os.path.join(app.config['PROCESSED_FOLDER'], output_filename)
    merger.write(output_path)
    merger.close()
    
    # Clean up upload directory
    shutil.rmtree(upload_dir)
    
    return jsonify({
        'success': True,
        'download_url': f'/download/{output_filename}',
        'original_size': total_size,
        'new_size': os.path.getsize(output_path),
        'reduction': round((1 - (os.path.getsize(output_path) / total_size)) * 100, 1)
    })

@app.route('/api/split', methods=['POST'])
def split_pdf():
    data = request.json
    token = data.get('token')
    page_range = data.get('page_range', '')
    
    if not token:
        return jsonify({'success': False, 'message': 'Missing token'}), 400
    
    upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], token)
    if not os.path.exists(upload_dir):
        return jsonify({'success': False, 'message': 'Invalid token'}), 400
    
    # Find the first PDF file
    pdf_files = [f for f in os.listdir(upload_dir) if f.lower().endswith('.pdf')]
    if not pdf_files:
        return jsonify({'success': False, 'message': 'No PDF file found'}), 400
    
    input_path = os.path.join(upload_dir, pdf_files[0])
    original_size = os.path.getsize(input_path)
    
    # Create a zip file for the split pages
    zip_filename = f"split_{pdf_files[0].replace('.pdf', '')}.zip"
    zip_path = os.path.join(app.config['PROCESSED_FOLDER'], zip_filename)
    
    reader = PdfReader(input_path)
    total_pages = len(reader.pages)
    
    # Create ZIP file with split pages
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        # Split based on page ranges
        ranges = page_range.split(',') if page_range else [f'1-{total_pages}']
        
        for i, page_range_str in enumerate(ranges):
            writer = PdfWriter()
            
            if '-' in page_range_str:
                start, end = map(int, page_range_str.split('-'))
                start = max(1, min(start, total_pages))
                end = max(start, min(end, total_pages))
                
                for page_num in range(start-1, end):
                    writer.add_page(reader.pages[page_num])
            else:
                page_num = int(page_range_str) - 1
                if 0 <= page_num < total_pages:
                    writer.add_page(reader.pages[page_num])
            
            if len(writer.pages) > 0:
                # Write PDF to memory and add to zip
                pdf_bytes = io.BytesIO()
                writer.write(pdf_bytes)
                pdf_bytes.seek(0)
                
                # Add to zip
                output_filename = f"page_{i+1}.pdf"
                zipf.writestr(output_filename, pdf_bytes.read())
    
    # Clean up upload directory
    shutil.rmtree(upload_dir)
    
    return jsonify({
        'success': True,
        'download_url': f'/download/{zip_filename}',
        'original_size': original_size,
        'new_size': os.path.getsize(zip_path)
    })

@app.route('/api/lock', methods=['POST'])
def lock_pdf():
    data = request.json
    token = data.get('token')
    password = data.get('password')
    
    if not token:
        return jsonify({'success': False, 'message': 'Missing token'}), 400
    
    if not password:
        return jsonify({'success': False, 'message': 'Password is required'}), 400
    
    upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], token)
    if not os.path.exists(upload_dir):
        return jsonify({'success': False, 'message': 'Invalid token'}), 400
    
    # Find the first PDF file
    pdf_files = [f for f in os.listdir(upload_dir) if f.lower().endswith('.pdf')]
    if not pdf_files:
        return jsonify({'success': False, 'message': 'No PDF file found'}), 400
    
    # Process file
    input_path = os.path.join(upload_dir, pdf_files[0])
    output_filename = f"locked_{pdf_files[0]}"
    output_path = os.path.join(app.config['PROCESSED_FOLDER'], output_filename)
    
    reader = PdfReader(input_path)
    writer = PdfWriter()
    
    # Add all pages to the writer
    for page in reader.pages:
        writer.add_page(page)
    
    # Encrypt the PDF with the password
    writer.encrypt(password)
    
    # Save the encrypted PDF to a file
    with open(output_path, "wb") as f:
        writer.write(f)
    
    # Clean up upload directory
    shutil.rmtree(upload_dir)
    
    return jsonify({
        'success': True,
        'download_url': f'/download/{output_filename}',
        'original_size': os.path.getsize(input_path),
        'new_size': os.path.getsize(output_path)
    })

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(
        app.config['PROCESSED_FOLDER'],
        filename,
        as_attachment=True
    )

if __name__ == '__main__':
    app.run(debug=False)
