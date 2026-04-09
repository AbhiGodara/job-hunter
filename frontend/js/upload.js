// Handles drag and drop file upload
const uploadBox = document.getElementById('upload-box');
const fileInput = document.getElementById('resume-upload');
const fileLabel = document.getElementById('file-label');

uploadBox.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadBox.classList.add('dragover');
});

uploadBox.addEventListener('dragleave', () => {
    uploadBox.classList.remove('dragover');
});

uploadBox.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadBox.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) {
        fileInput.files = e.dataTransfer.files;
        updateFileLabel();
    }
});

uploadBox.addEventListener('click', () => {
    fileInput.click();
});

fileInput.addEventListener('change', () => {
    updateFileLabel();
});

function updateFileLabel() {
    if (fileInput.files.length > 0) {
        fileLabel.textContent = fileInput.files[0].name;
        fileLabel.classList.add('file-selected');
    } else {
        fileLabel.textContent = 'Drag & drop your resume (PDF/DOCX) or click to browse';
        fileLabel.classList.remove('file-selected');
    }
}
