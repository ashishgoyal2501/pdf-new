// Enhanced script.js with better UX

const API_ENDPOINTS = {
    upload: '/api/upload',
    compress: '/api/compress',
    merge: '/api/merge',
    split: '/api/split',
    lock: '/api/lock',
    convert: '/api/convert'
};

document.addEventListener('DOMContentLoaded', function() {
    const toolCards = document.querySelectorAll('.tool-card');
    const uploadBox = document.getElementById('uploadBox');
    const fileInput = document.getElementById('fileInput');
    const selectFileBtn = document.getElementById('selectFileBtn');
    const fileInfo = document.getElementById('fileInfo');
    const previewContainer = document.getElementById('previewContainer');
    const pdfPreview = document.getElementById('pdfPreview');
    const processingContainer = document.getElementById('processingContainer');
    const resultContainer = document.getElementById('resultContainer');
    const progressBar = document.getElementById('progressBar');
    const downloadBtn = document.getElementById('downloadBtn');
    const newDocumentBtn = document.getElementById('newDocumentBtn');
    const processBtn = document.getElementById('processBtn');
    const toolOptions = document.getElementById('toolOptions');
    const toolTitle = document.getElementById('toolTitle');
    const toolDescription = document.getElementById('toolDescription');
    const compressionLevel = document.getElementById('compressionLevel');
    const compressionValue = document.getElementById('compressionValue');
    const toast = document.getElementById('toast');

    let currentTool = null;
    let currentFiles = [];
    let uploadToken = null;
    let downloadUrl = null;

    // Tool selection UX
    toolCards.forEach(card => {
        card.addEventListener('click', function() {
            currentTool = this.getAttribute('data-tool');
            toolCards.forEach(c => c.classList.remove('selected'));
            this.classList.add('selected');

            toolOptions.scrollIntoView({ behavior: 'smooth', block: 'center' });
            toolTitle.textContent = this.querySelector('h3').textContent;
            toolDescription.textContent = this.querySelector('p').textContent;

            document.querySelectorAll('.option-group').forEach(group => {
                group.style.display = 'none';
            });

            const toolMap = {
                compress: 'compressOptions',
                split: 'splitOptions',
                lock: 'lockOptions',
                merge: 'mergeOptions',
                convert: 'convertOptions'
            };
            if (toolMap[currentTool]) {
                document.getElementById(toolMap[currentTool]).style.display = 'block';
            }
        });
    });

    compressionLevel.addEventListener('input', function() {
        const values = ['Low (Better Quality)', 'Medium', 'High (Smaller Size)'];
        compressionValue.textContent = values[this.value - 1];
    });

    selectFileBtn.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', function() {
        handleFileSelection(this.files);
    });

    uploadBox.addEventListener('dragover', e => {
        e.preventDefault();
        uploadBox.classList.add('highlight');
    });
    uploadBox.addEventListener('dragleave', () => uploadBox.classList.remove('highlight'));
    uploadBox.addEventListener('drop', function(e) {
        e.preventDefault();
        uploadBox.classList.remove('highlight');
        handleFileSelection(e.dataTransfer.files);
    });

    processBtn.addEventListener('click', function() {
        if (!currentTool) return showToast('Please select a tool', 'error');
        if (!uploadToken) return showToast('Files not uploaded yet', 'error');

        let options = {};
        if (currentTool === 'compress') {
            options.level = compressionLevel.value;
        } else if (currentTool === 'split') {
            options.page_range = document.getElementById('pageRange').value;
        } else if (currentTool === 'lock') {
            const pwd = document.getElementById('password').value;
            const confirm = document.getElementById('confirmPassword').value;
            if (!pwd || pwd !== confirm) return showToast('Passwords must match and not be empty', 'error');
            options.password = pwd;
        } else if (currentTool === 'convert') {
            options.format = document.getElementById('convertTo').value;
            options.quality = document.getElementById('imageQuality').value;
        }

        processingContainer.style.display = 'block';
        resultContainer.style.display = 'none';
        processFile(uploadToken, currentTool, options);
    });

    downloadBtn.addEventListener('click', e => {
        if (!downloadUrl) {
            e.preventDefault();
            showToast('No file to download', 'error');
        }
    });

    newDocumentBtn.addEventListener('click', () => resetUI());

    function handleFileSelection(files) {
        currentFiles = Array.from(files);
        fileInput.value = '';

        if (!currentFiles.length) return;

        if (currentFiles.length === 1) {
            fileInfo.innerHTML = `<strong>Selected file:</strong> ${currentFiles[0].name} (${formatFileSize(currentFiles[0].size)})`;
        } else {
            fileInfo.innerHTML = `<strong>Selected ${currentFiles.length} files</strong>`;
        }

        const pdfFile = currentFiles.find(file => file.type === 'application/pdf');
        previewContainer.style.display = pdfFile ? 'block' : 'none';
        if (pdfFile) showPDFPreview(pdfFile);

        uploadFiles(currentFiles);
    }

    function resetUI() {
        currentFiles = [];
        uploadToken = null;
        downloadUrl = null;
        fileInput.value = '';
        fileInfo.textContent = 'No file selected';
        previewContainer.style.display = 'none';
        resultContainer.style.display = 'none';
        processingContainer.style.display = 'none';
        progressBar.style.width = '0%';
        toolCards.forEach(c => c.classList.remove('selected'));
        currentTool = null;
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function showToast(message, type = 'success') {
        toast.textContent = message;
        toast.className = 'toast ' + type;
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 3000);
    }

    function showPDFPreview(file) {
        pdfPreview.innerHTML = '<p>Loading preview...</p>';
        const reader = new FileReader();
        reader.onload = function() {
            const typedarray = new Uint8Array(this.result);
            pdfjsLib.getDocument(typedarray).promise.then(pdf => {
                pdfPreview.innerHTML = '';
                for (let i = 1; i <= Math.min(pdf.numPages, 3); i++) {
                    pdf.getPage(i).then(page => {
                        const scale = 0.5;
                        const viewport = page.getViewport({ scale });
                        const canvas = document.createElement('canvas');
                        const context = canvas.getContext('2d');
                        canvas.height = viewport.height;
                        canvas.width = viewport.width;
                        const renderTask = page.render({ canvasContext: context, viewport });
                        renderTask.promise.then(() => {
                            const pageDiv = document.createElement('div');
                            pageDiv.className = 'page-thumbnail';
                            pageDiv.innerHTML = `<p>Page ${i}</p>`;
                            pageDiv.appendChild(canvas);
                            pdfPreview.appendChild(pageDiv);
                        });
                    });
                }
            });
        };
        reader.readAsArrayBuffer(file);
    }

    function uploadFiles(files) {
        const formData = new FormData();
        files.forEach(file => formData.append('files', file));
        fileInfo.innerHTML += '<div class="text-sm text-blue-500 mt-1">Uploading...</div>';

        fetch(API_ENDPOINTS.upload, { method: 'POST', body: formData })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                uploadToken = data.token;
                showToast('Files uploaded', 'success');
            } else {
                showToast('Upload failed: ' + data.message, 'error');
            }
        })
        .catch(err => showToast('Error: ' + err.message, 'error'));
    }

    function processFile(token, tool, options) {
        let progress = 0;
        const interval = setInterval(() => {
            progress += Math.random() * 10;
            if (progress >= 90) clearInterval(interval);
            progressBar.style.width = `${progress}%`;
        }, 200);

        const payload = { token, ...options };
        fetch(API_ENDPOINTS[tool], {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(res => res.json())
        .then(data => {
            clearInterval(interval);
            progressBar.style.width = '100%';
            setTimeout(() => {
                processingContainer.style.display = 'none';
                if (data.success) {
                    resultContainer.style.display = 'block';
                    document.getElementById('originalSize').textContent = formatFileSize(data.original_size);
                    document.getElementById('newSize').textContent = formatFileSize(data.new_size);
                    document.getElementById('reduction').textContent = data.reduction ? `${data.reduction}%` : 'N/A';
                    downloadUrl = data.download_url;
                    downloadBtn.href = downloadUrl;
                    showToast('Done! Ready to download', 'success');
                } else {
                    showToast(data.message || 'Processing failed', 'error');
                }
            }, 500);
        })
        .catch(err => {
            clearInterval(interval);
            processingContainer.style.display = 'none';
            showToast('Error: ' + err.message, 'error');
        });
    }
});
