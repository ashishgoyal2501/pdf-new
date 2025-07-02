// Backend API endpoints
const API_ENDPOINTS = {
    upload: '/api/upload',
    compress: '/api/compress',
    merge: '/api/merge',
    split: '/api/split',
    lock: '/api/lock',
    convert: '/api/convert'
};

// PDF processing backend integration
document.addEventListener('DOMContentLoaded', function() {
    // DOM elements
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
    
    // Current state variables
    let currentTool = null;
    let currentFiles = [];
    let uploadToken = null;
    let downloadUrl = null;

    // Tool selection
    toolCards.forEach(card => {
        card.addEventListener('click', function() {
            // Set current tool
            currentTool = this.getAttribute('data-tool');
            
            // Update UI
            toolCards.forEach(c => c.style.opacity = '0.6');
            this.style.opacity = '1';
            
            // Scroll to options
            toolOptions.scrollIntoView({ behavior: 'smooth' });
            
            // Update tool title and description
            const toolName = this.querySelector('h3').textContent;
            toolTitle.textContent = toolName;
            toolDescription.textContent = this.querySelector('p').textContent;
            
            // Show relevant options
            document.querySelectorAll('.option-group').forEach(group => {
                group.style.display = 'none';
            });
            
            if (currentTool === 'compress') {
                document.getElementById('compressOptions').style.display = 'block';
            } else if (currentTool === 'split') {
                document.getElementById('splitOptions').style.display = 'block';
            } else if (currentTool === 'lock') {
                document.getElementById('lockOptions').style.display = 'block';
            } else if (currentTool === 'merge') {
                document.getElementById('mergeOptions').style.display = 'block';
            } else if (currentTool === 'convert') {
                document.getElementById('convertOptions').style.display = 'block';
            }
        });
    });
    
    // Compression level display
    compressionLevel.addEventListener('input', function() {
        const values = ['Low (Better Quality)', 'Medium', 'High (Smaller Size)'];
        compressionValue.textContent = values[this.value - 1];
    });
    
    // File selection
    selectFileBtn.addEventListener('click', function() {
        fileInput.click();
    });
    
    fileInput.addEventListener('change', function(e) {
        if (this.files && this.files.length > 0) {
            currentFiles = Array.from(this.files);
            
            // Update file info display
            if (currentFiles.length === 1) {
                fileInfo.innerHTML = `<strong>Selected file:</strong> ${currentFiles[0].name} (${formatFileSize(currentFiles[0].size)})`;
            } else {
                fileInfo.innerHTML = `<strong>Selected ${currentFiles.length} files</strong>`;
            }
            
            // Show preview for the first PDF file
            const pdfFile = currentFiles.find(file => file.type === 'application/pdf');
            if (pdfFile) {
                showPDFPreview(pdfFile);
                previewContainer.style.display = 'block';
            } else {
                previewContainer.style.display = 'none';
            }
            
            // Upload files to backend
            uploadFiles(currentFiles);
        }
    });
    
    // Drag and drop
    uploadBox.addEventListener('dragover', function(e) {
        e.preventDefault();
        this.style.backgroundColor = 'rgba(67, 97, 238, 0.1)';
    });
    
    uploadBox.addEventListener('dragleave', function() {
        this.style.backgroundColor = '';
    });
    
    uploadBox.addEventListener('drop', function(e) {
        e.preventDefault();
        this.style.backgroundColor = '';
        
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            currentFiles = Array.from(e.dataTransfer.files);
            
            // Update file info display
            if (currentFiles.length === 1) {
                fileInfo.innerHTML = `<strong>Selected file:</strong> ${currentFiles[0].name} (${formatFileSize(currentFiles[0].size)})`;
            } else {
                fileInfo.innerHTML = `<strong>Selected ${currentFiles.length} files</strong>`;
            }
            
            // Show preview for the first PDF file
            const pdfFile = currentFiles.find(file => file.type === 'application/pdf');
            if (pdfFile) {
                showPDFPreview(pdfFile);
                previewContainer.style.display = 'block';
            } else {
                previewContainer.style.display = 'none';
            }
            
            // Upload files to backend
            uploadFiles(currentFiles);
        }
    });
    
    // Process document
    processBtn.addEventListener('click', function() {
        if (!currentTool) {
            showToast('Please select a tool first', 'error');
            return;
        }
        
        if (!uploadToken) {
            showToast('Files not uploaded yet', 'error');
            return;
        }
        
        // Prepare processing options based on tool
        let options = {};
        switch(currentTool) {
            case 'compress':
                options = {
                    level: compressionLevel.value
                };
                break;
            case 'split':
                options = {
                    page_range: document.getElementById('pageRange').value
                };
                break;
            case 'lock':
                const password = document.getElementById('password').value;
                const confirmPassword = document.getElementById('confirmPassword').value;
                
                if (password !== confirmPassword) {
                    showToast('Passwords do not match', 'error');
                    return;
                }
                
                if (!password) {
                    showToast('Please enter a password', 'error');
                    return;
                }
                
                options = {
                    password: password
                };
                break;
            case 'convert':
                options = {
                    format: document.getElementById('convertTo').value,
                    quality: document.getElementById('imageQuality').value
                };
                break;
        }
        
        // Show processing UI
        processingContainer.style.display = 'block';
        resultContainer.style.display = 'none';
        
        // Call backend API to process file
        processFile(uploadToken, currentTool, options);
    });
    
    // Download button
    downloadBtn.addEventListener('click', function(e) {
        if (!downloadUrl) {
            e.preventDefault();
            showToast('No file to download', 'error');
        }
    });
    
    // New document button
    newDocumentBtn.addEventListener('click', function() {
        // Reset the UI
        currentFiles = [];
        uploadToken = null;
        downloadUrl = null;
        fileInput.value = '';
        fileInfo.textContent = 'No file selected';
        previewContainer.style.display = 'none';
        resultContainer.style.display = 'none';
        processingContainer.style.display = 'none';
        progressBar.style.width = '0%';
        
        // Reset tool selection
        toolCards.forEach(c => c.style.opacity = '1');
        currentTool = null;
    });
    
    // Helper functions
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    function showPDFPreview(file) {
        pdfPreview.innerHTML = '<p>Loading preview...</p>';
        
        const fileReader = new FileReader();
        
        fileReader.onload = function() {
            const typedarray = new Uint8Array(this.result);
            
            // Load the PDF file
            pdfjsLib.getDocument(typedarray).promise.then(function(pdf) {
                pdfPreview.innerHTML = '';
                
                // For each page, create a canvas and render
                for (let pageNum = 1; pageNum <= Math.min(pdf.numPages, 3); pageNum++) {
                    pdf.getPage(pageNum).then(function(page) {
                        const scale = 0.5;
                        const viewport = page.getViewport({ scale: scale });
                        
                        const canvas = document.createElement('canvas');
                        const context = canvas.getContext('2d');
                        canvas.height = viewport.height;
                        canvas.width = viewport.width;
                        
                        const renderContext = {
                            canvasContext: context,
                            viewport: viewport
                        };
                        
                        const renderTask = page.render(renderContext);
                        
                        renderTask.promise.then(function() {
                            const pageDiv = document.createElement('div');
                            pageDiv.className = 'page-thumbnail';
                            pageDiv.innerHTML = `<p>Page ${pageNum}</p>`;
                            pageDiv.appendChild(canvas);
                            pdfPreview.appendChild(pageDiv);
                        });
                    });
                }
                
                if (pdf.numPages > 3) {
                    const moreText = document.createElement('p');
                    moreText.textContent = `+ ${pdf.numPages - 3} more pages...`;
                    moreText.style.marginTop = '10px';
                    pdfPreview.appendChild(moreText);
                }
            });
        };
        
        fileReader.readAsArrayBuffer(file);
    }
    
    function showToast(message, type = 'success') {
        toast.textContent = message;
        toast.className = 'toast ' + type;
        toast.classList.add('show');
        
        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }
    
    // Backend API integration functions
    function uploadFiles(files) {
        const formData = new FormData();
        files.forEach(file => {
            formData.append('files', file);
        });
        
        // Show loading indicator
        fileInfo.innerHTML += '<div style="margin-top:10px;">Uploading files...</div>';
        
        // Send files to backend
        fetch(API_ENDPOINTS.upload, {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                uploadToken = data.token;
                showToast('Files uploaded successfully', 'success');
            } else {
                showToast('File upload failed: ' + data.message, 'error');
            }
        })
        .catch(error => {
            showToast('Error uploading files: ' + error.message, 'error');
        });
    }
    
    function processFile(token, tool, options) {
        // Start progress animation
        let progress = 0;
        const interval = setInterval(() => {
            progress += Math.random() * 10;
            if (progress >= 90) {
                clearInterval(interval);
            }
            progressBar.style.width = `${progress}%`;
        }, 200);
        
        // Prepare request payload
        const payload = {
            token: token,
            ...options
        };
        
        // Send processing request to backend
        fetch(API_ENDPOINTS[tool], {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        })
        .then(response => response.json())
        .then(data => {
            clearInterval(interval);
            progressBar.style.width = '100%';
            
            setTimeout(() => {
                processingContainer.style.display = 'none';
                
                if (data.success) {
                    resultContainer.style.display = 'block';
                    
                    // Update result info
                    document.getElementById('originalSize').textContent = formatFileSize(data.original_size);
                    document.getElementById('newSize').textContent = formatFileSize(data.new_size);
                    
                    if (data.reduction) {
                        document.getElementById('reduction').textContent = `${data.reduction}%`;
                    } else {
                        document.getElementById('reduction').textContent = 'N/A';
                    }
                    
                    // Set download link
                    downloadUrl = data.download_url;
                    downloadBtn.href = downloadUrl;
                    
                    showToast('Processing completed successfully', 'success');
                } else {
                    showToast('Processing failed: ' + data.message, 'error');
                }
            }, 500);
        })
        .catch(error => {
            clearInterval(interval);
            processingContainer.style.display = 'none';
            showToast('Error processing file: ' + error.message, 'error');
        });
    }
});