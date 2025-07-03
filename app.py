import os
import uuid
import shutil
import subprocess
import zipfile
import io
import fitz  # PyMuPDF
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader, PdfWriter, PdfMerger
from pdf2docx import Converter

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['PROCESSED_FOLDER'] = 'processed'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'}
app.config['FILE_EXPIRY_SECONDS'] = 3600  # 1 hour

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)


def cleanup_old_files(folder):
    now = time.time()
    for root, dirs, files in os.walk(folder):
        for name in files:
            filepath = os.path.join(root, name)
            if os.path.isfile(filepath) and now - os.path.getmtime(filepath) > app.config['FILE_EXPIRY_SECONDS']:
                os.remove(filepath)
        for name in dirs:
            dirpath = os.path.join(root, name)
            if now - os.path.getmtime(dirpath) > app.config['FILE_EXPIRY_SECONDS']:
                shutil.rmtree(dirpath, ignore_errors=True)


def cleanup_all():
    cleanup_old_files(app.config['UPLOAD_FOLDER'])
    cleanup_old_files(app.config['PROCESSED_FOLDER'])


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def compress_with_ghostscript(input_path, output_path, quality='screen'):
    quality_settings = {
        'screen': '/screen',
        'ebook': '/ebook',
        'printer': '/printer',
        'prepress': '/prepress',
        'default': '/default'
    }
    command = [
        'gs', '-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.4',
        f'-dPDFSETTINGS={quality_settings.get(quality, "/screen")}',
        '-dNOPAUSE', '-dQUIET', '-dBATCH',
        '-dColorImageDownsampleType=/Bicubic', '-dColorImageResolution=100',
        '-dGrayImageDownsampleType=/Bicubic', '-dGrayImageResolution=100',
        '-dMonoImageDownsampleType=/Subsample', '-dMonoImageResolution=100',
        f'-sOutputFile={output_path}', input_path
    ]
    subprocess.run(command, check=True, timeout=180)


def compress_with_pymupdf(input_path, output_path):
    doc = fitz.open(input_path)
    for page in doc:
        images = page.get_images(full=True)
        for img in images:
            xref = img[0]
            try:
                pix = fitz.Pixmap(doc, xref)
                if pix.n > 4:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                doc.replace_image(xref, pix)
            except Exception:
                continue
    doc.save(output_path, garbage=4, deflate=True, compress=True)
    doc.close()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload_file():
    cleanup_all()
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


@app.route('/api/compress', methods=['POST'])
def compress_pdf():
    cleanup_all()
    data = request.json
    token = data.get('token')
    level = data.get('level', '3')
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
    compression_method = "Ghostscript"
    try:
        quality = 'screen' if level == '3' else 'ebook'
        compress_with_ghostscript(input_path, output_path, quality)
    except Exception:
        try:
            compress_with_pymupdf(input_path, output_path)
            compression_method = "PyMuPDF"
        except Exception as inner_error:
            return jsonify({'success': False, 'message': f'Compression failed: {str(inner_error)}'}), 500
    original_size = os.path.getsize(input_path)
    new_size = os.path.getsize(output_path)
    shutil.rmtree(upload_dir)
    return jsonify({
        'success': True,
        'download_url': f'/download/{output_filename}',
        'original_size': original_size,
        'new_size': new_size,
        'method': compression_method,
        'reduction': round((1 - (new_size / original_size)) * 100, 1)
    })


@app.route('/api/merge', methods=['POST'])
def merge_pdf():
    cleanup_all()
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


@app.route('/api/split', methods=['POST'])
def split_pdf():
    cleanup_all()
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
                for page_num in range(max(0, start - 1), min(end, total_pages)):
                    writer.add_page(reader.pages[page_num])
            else:
                page_num = int(page_range_str) - 1
                if 0 <= page_num < total_pages:
                    writer.add_page(reader.pages[page_num])
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


@app.route('/api/lock', methods=['POST'])
def lock_pdf():
    cleanup_all()
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
    try:
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
        return jsonify({'success': False, 'message': f'Locking failed: {str(e)}'}), 500


@app.route('/api/convert', methods=['POST'])
def convert_pdf():
    cleanup_all()
    data = request.json
    token = data.get('token')
    target_format = data.get('format', 'docx')
    if not token or target_format not in ['docx', 'jpg']:
        return jsonify({'success': False, 'message': 'Invalid token or format'}), 400
    upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], token)
    if not os.path.exists(upload_dir):
        return jsonify({'success': False, 'message': 'Invalid token'}), 400
    pdf_files = [f for f in os.listdir(upload_dir) if f.lower().endswith('.pdf')]
    if not pdf_files:
        return jsonify({'success': False, 'message': 'No PDF file found'}), 400
    input_path = os.path.join(upload_dir, pdf_files[0])
    if target_format == 'docx':
        output_filename = f"{pdf_files[0].replace('.pdf', '')}.docx"
        output_path = os.path.join(app.config['PROCESSED_FOLDER'], output_filename)
        try:
            cv = Converter(input_path)
            cv.convert(output_path, start=0, end=None)
            cv.close()
        except Exception as e:
            return jsonify({'success': False, 'message': f'DOCX conversion failed: {str(e)}'}), 500
    elif target_format == 'jpg':
        output_folder = os.path.join(app.config['PROCESSED_FOLDER'], f"{token}_jpgs")
        os.makedirs(output_folder, exist_ok=True)
        try:
            doc = fitz.open(input_path)
            for i, page in enumerate(doc):
                pix = page.get_pixmap(dpi=200)
                jpg_path = os.path.join(output_folder, f"page_{i+1}.jpg")
                pix.save(jpg_path)
            doc.close()
            zip_filename = f"{pdf_files[0].replace('.pdf', '')}_images.zip"
            zip_path = os.path.join(app.config['PROCESSED_FOLDER'], zip_filename)
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for img_file in os.listdir(output_folder):
                    zipf.write(os.path.join(output_folder, img_file), arcname=img_file)
            output_path = zip_path
        except Exception as e:
            return jsonify({'success': False, 'message': f'JPG conversion failed: {str(e)}'}), 500
    shutil.rmtree(upload_dir)
    return jsonify({
        'success': True,
        'download_url': f'/download/{os.path.basename(output_path)}',
        'message': f'PDF converted to {target_format.upper()} successfully.'
    })


@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['PROCESSED_FOLDER'], filename, as_attachment=True)


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/help')
def help_page():
    return render_template('help.html')

@app.route('/faq')
def faq():
    return render_template('faq.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

if __name__ == '__main__':
    app.run(debug=True)

if __name__ == '__main__':
    app.run(debug=True)
