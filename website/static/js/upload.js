const uploadForm = document.getElementById('uploadForm');
const fileInput = document.getElementById('fileUpload');
const fileError = document.getElementById('fileError');
const maxFileSize = 50 * 1024 * 1024; // 50 MB in bytes

fileInput.addEventListener('change', function() {
fileError.style.display = 'none'; // Hide error on new file selection
fileError.textContent = '';
if (this.files && this.files[0]) {
    if (this.files[0].size > maxFileSize) {
    fileError.textContent = 'File is too large. Maximum size is 50MB.';
    fileError.style.display = 'block';
    this.value = ''; // Reset the file input
    }
}
});

uploadForm.addEventListener('submit', function(event) {
if (fileInput.files && fileInput.files[0]) {
    if (fileInput.files[0].size > maxFileSize) {
    fileError.textContent = 'File is too large (max 50MB). Please select a smaller file.';
    fileError.style.display = 'block';
    event.preventDefault(); // Prevent form submission
    }
} else if (fileInput.hasAttribute('required') && (!fileInput.files || fileInput.files.length === 0)) {
    // This check ensures a file is selected if the input is required
    // It might be redundant if the browser's native 'required' validation fires first
    fileError.textContent = 'Please select a file to upload.';
    fileError.style.display = 'block';
    event.preventDefault(); // Prevent form submission if no file is chosen
}
});