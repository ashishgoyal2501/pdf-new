import os
import uuid
import shutil
import zipfile
import io
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader, PdfWriter, PdfMerger

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['PROCESSED_FOLDER'] = 'processed'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'}

# Set up basic logging
logging.basicConfig(level=logging.ERROR)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload_file():
    try:
        if 'files' not in request.files:
            return jsonify({'success': False, 'message': 'No files uploaded'}), 400

        files = request.files.getlist('files')
        token = str(uuid.uuid4())
        token_dir = os.path.join(app.config['UPLOAD_FOLDER'], token)
        os.makedirs(token_dir, exist_ok=True)

        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(token_dir, filename))

        return jsonify({'success': True, 'token': token, 'message': f'{len(files)} files uploaded successfully'})
    except Exception as e:
        app.logger.error(f"Upload error: {str(e)}")
        return jsonify({'success': False, 'message': 'Server error during upload'}), 500

@app.route('/api/compress', methods=['POST'])
def compress_pdf():
    try:
        data = request.json
        token = data.get('token')
        level = data.get('level', '2')

        if not token:
            return jsonify({'success': False, 'message': 'Missing token'}), 400

        upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], token)
        if not os.path.exists(upload_dir):
            return jsonify({'success': False, 'message': 'Invalid token'}), 400

        pdf_files = [f for f in os.listdir(upload_dir) if f.lower().endswith('.pdf')]
        if not pdf_files:
            return jsonify({'success': False, 'message': 'No PDF file found'}), 400

        input_path = os.path.join(upload_dir, pdf_files[0])
        output_filename = f"compressed_{pdf_files[0]}"
        output_path = os.path.join(app.config['PROCESSED_FOLDER'], output_filename)

        reader = PdfReader(input_path)
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        if level == '3':
            for page in writer.pages:
                page.compress_content_streams()

        with open(output_path, "wb") as f:
            writer.write(f)

        original_size = os.path.getsize(input_path)
        new_size = os.path.getsize(output_path)

        shutil.rmtree(upload_dir)

        return jsonify({
            'success': True,
            'download_url': f'/download/{output_filename}',
            'original_size': original_size,
            'new_size': new_size,
            'reduction': round((1 - (new_size / original_size)) * 100, 1)
        })
    except Exception as e:
        app.logger.error(f"Compression error: {str(e)}")
        return jsonify({'success': False, 'message': 'PDF compression failed'}), 500

@app.route('/api/merge', methods=['POST'])
def merge_pdf():
    try:
        data = request.json
        token = data.get('token')

        if not token:
            return jsonify({'success': False, 'message': 'Missing token'}), 400

        upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], token)
        if not os.path.exists(upload_dir):
            return jsonify({'success': False, 'message': 'Invalid token'}), 400

        pdf_files = [f for f in os.listdir(upload_dir) if f.lower().endswith('.pdf')]
        if len(pdf_files) < 2:
            return jsonify({'success': False, 'message': 'Need at least 2 PDF files to merge'}), 400

        merger = PdfMerger()
        total_size = 0

        for pdf_file in pdf_files:
            file_path = os.path.join(upload_dir, pdf_file)
            merger.append(file_path)
            total_size += os.path.getsize(file_path)

        output_filename = f"merged_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        output_path = os.path.join(app.config['PROCESSED_FOLDER'], output_filename)
        merger.write(output_path)
        merger.close()

        new_size = os.path.getsize(output_path)

        shutil.rmtree(upload_dir)

        return jsonify({
            'success': True,
            'download_url': f'/download/{output_filename}',
            'original_size': total_size,
            'new_size': new_size,
            'reduction': round((1 - (new_size / total_size)) * 100, 1)
        })
    except Exception as e:
        app.logger.error(f"Merge error: {str(e)}")
        return jsonify({'success': False, 'message': 'PDF merge failed'}), 500

@app.route('/api/split', methods=['POST'])
def split_pdf():
    try:
        data = request.json
        token = data.get('token')
        page_range = data.get('page_range', '')

        if not token:
            return jsonify({'success': False, 'message': 'Missing token'}), 400

        upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], token)
        if not os.path.exists(upload_dir):
            return jsonify({'success': False, 'message': 'Invalid token'}), 400

        pdf_files = [f for f in os.listdir(upload_dir) if f.lower().endswith('.pdf')]
        if not pdf_files:
            return jsonify({'success': False, 'message': 'No PDF file found'}), 400

        input_path = os.path.join(upload_dir, pdf_files[0])
        original_size = os.path.getsize(input_path)

        zip_filename = f"split_{pdf_files[0].replace('.pdf', '')}.zip"
        zip_path = os.path.join(app.config['PROCESSED_FOLDER'], zip_filename)

        reader = PdfReader(input_path)
        total_pages = len(reader.pages)

        with zipfile.ZipFile(zip_path, 'w') as zipf:
            ranges = page_range.split(',') if page_range else [f'1-{total_pages}']

            for i, page_range_str in enumerate(ranges):
                writer = PdfWriter()

                if '-' in page_range_str:
                    start, end = map(int, page_range_str.split('-'))
                    start_page = max(1, start)
                    end_page = min(end, total_pages)
                    for page_num in range(start_page - 1, end_page):
                        writer.add_page(reader.pages[page_num])
                else:
                    try:
                        page_num = int(page_range_str) - 1
                        if 0 <= page_num < total_pages:
                            writer.add_page(reader.pages[page_num])
                    except ValueError:
                        pass

                if writer.pages:
                    pdf_bytes = io.BytesIO()
                    writer.write(pdf_bytes)
                    pdf_bytes.seek(0)
                    zipf.writestr(f"page_{i + 1}.pdf", pdf_bytes.read())

        new_size = os.path.getsize(zip_path)

        shutil.rmtree(upload_dir)

        return jsonify({
            'success': True,
            'download_url': f'/download/{zip_filename}',
            'original_size': original_size,
            'new_size': new_size
        })
    except Exception as e:
        app.logger.error(f"Split error: {str(e)}")
        return jsonify({'success': False, 'message': 'PDF split failed'}), 500

@app.route('/api/lock', methods=['POST'])
def lock_pdf():
    try:
        data = request.json
        token = data.get('token')
        password = data.get('password')

        if not token or not password:
            return jsonify({'success': False, 'message': 'Missing token or password'}), 400

        upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], token)
        if not os.path.exists(upload_dir):
            return jsonify({'success': False, 'message': 'Invalid token'}), 400

        pdf_files = [f for f in os.listdir(upload_dir) if f.lower().endswith('.pdf')]
        if not pdf_files:
            return jsonify({'success': False, 'message': 'No PDF file found'}), 400

        input_path = os.path.join(upload_dir, pdf_files[0])
        output_filename = f"locked_{pdf_files[0]}"
        output_path = os.path.join(app.config['PROCESSED_FOLDER'], output_filename)

        reader = PdfReader(input_path)
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        writer.encrypt(password)

        with open(output_path, "wb") as f:
            writer.write(f)

        original_size = os.path.getsize(input_path)
        new_size = os.path.getsize(output_path)

        shutil.rmtree(upload_dir)

        return jsonify({
            'success': True,
            'download_url': f'/download/{output_filename}',
            'original_size': original_size,
            'new_size': new_size
        })
        
    except Exception as e:
        app.logger.error(f"Lock PDF error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Failed to lock PDF: {str(e)}'
        }), 500

@app.route('/download/<filename>')
def download_file(filename):
    try:
        return send_from_directory(app.config['PROCESSED_FOLDER'], filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({'success': False, 'message': 'File not found'}), 404

if __name__ == '__main__':
    app.run(debug=True)
