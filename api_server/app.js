const fileInput = document.getElementById('fileInput');
const fileName = document.getElementById('fileName');
const processButton = document.getElementById('processButton');
const uploadSection = document.getElementById('uploadSection');
const status = document.getElementById('status');
const results = document.getElementById('results');
const imageContainer = document.getElementById('imageContainer');
const logoutButton = document.getElementById('logoutButton');

let selectedFile = null;

// Check authentication status on page load
(async function checkAuth() {
    try {
        const response = await fetch('/api/auth/status');
        const data = await response.json();
        
        if (data.auth_enabled && !data.authenticated) {
            window.location.href = '/';
            return;
        }
        
        if (data.auth_enabled && logoutButton) {
            logoutButton.style.display = 'block';
        }
    } catch (error) {
        console.error('Auth check failed:', error);
    }
})();

// Logout button handler
if (logoutButton) {
    logoutButton.addEventListener('click', async () => {
        try {
            const response = await fetch('/api/auth/logout', {
                method: 'POST'
            });
            
            if (response.ok) {
                window.location.href = '/';
            }
        } catch (error) {
            console.error('Logout failed:', error);
        }
    });
}

// File input change
fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        if (!file.name.endsWith('.dat')) {
            showStatus('error', 'Please select a .dat file');
            return;
        }
        selectedFile = file;
        fileName.textContent = `Selected: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
        processButton.disabled = false;
    }
});

// Drag and drop
uploadSection.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadSection.classList.add('dragover');
});

uploadSection.addEventListener('dragleave', () => {
    uploadSection.classList.remove('dragover');
});

uploadSection.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadSection.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file) {
        if (!file.name.endsWith('.dat')) {
            showStatus('error', 'Please drop a .dat file');
            return;
        }
        selectedFile = file;
        fileInput.files = e.dataTransfer.files;
        fileName.textContent = `Selected: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
        processButton.disabled = false;
    }
});

// Process button
processButton.addEventListener('click', async () => {
    if (!selectedFile) return;
    
    processButton.disabled = true;
    showStatus('processing', 'Processing scatterers file... This may take a minute.');
    results.classList.remove('show');
    imageContainer.innerHTML = '';
    
    const formData = new FormData();
    formData.append('file', selectedFile);
    
    try {
        const response = await fetch('/api/v1/scanner/process', {
            method: 'POST',
            body: formData,
            credentials: 'include'  // Include cookies for session
        });
        
        if (response.status === 401) {
            // Unauthorized - redirect to login
            window.location.href = '/';
            return;
        }
        
        const data = await response.json();
        
        if (response.ok && data.status === 'success') {
            showStatus('success', 'Processing completed successfully!');
            displayResults(data);
        } else {
            showStatus('error', `Error: ${data.detail || 'Unknown error'}`);
            processButton.disabled = false;
        }
    } catch (error) {
        showStatus('error', `Error: ${error.message}`);
        processButton.disabled = false;
    }
});

function showStatus(type, message) {
    status.className = `status ${type}`;
    status.innerHTML = type === 'processing' 
        ? `<div class="spinner"></div><p>${message}</p>`
        : `<p>${message}</p>`;
}

function displayResults(data) {
    results.classList.add('show');
    imageContainer.innerHTML = '';
    
    if (data.images && data.images.grayscale) {
        const grayscaleCard = createImageCard('Grayscale OCT Scan', data.images.grayscale);
        imageContainer.appendChild(grayscaleCard);
    }
    
    if (data.images && data.images.hot) {
        const hotCard = createImageCard('Hot Colormap OCT Scan', data.images.hot);
        imageContainer.appendChild(hotCard);
    }
    
    processButton.disabled = false;
}

function createImageCard(title, imageUrl) {
    const card = document.createElement('div');
    card.className = 'image-card';
    
    const fullUrl = window.location.origin + imageUrl;
    
    card.innerHTML = `
        <h3>${title}</h3>
        <img src="${fullUrl}" alt="${title}" onclick="window.open('${fullUrl}', '_blank')">
        <a href="${fullUrl}" class="download-link" download>Download Image</a>
    `;
    
    return card;
}

