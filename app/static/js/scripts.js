function toggleCoordInputs() {
    const format = document.getElementById('coord_format').value;
    if (format === 'decimal') {
        document.getElementById('decimal-coords').style.display = 'block';
        document.getElementById('dms-coords').style.display = 'none';
        disableDMSInputs(true);
        disableDecimalInputs(false);
    } else {
        document.getElementById('decimal-coords').style.display = 'none';
        document.getElementById('dms-coords').style.display = 'block';
        disableDMSInputs(false);
        disableDecimalInputs(true);
    }
}

function disableDMSInputs(disable) {
    const dmsInputs = document.querySelectorAll('#dms-coords input, #dms-coords select');
    dmsInputs.forEach(input => {
        input.disabled = disable;
    });
}

function disableDecimalInputs(disable) {
    const decimalInputs = document.querySelectorAll('#decimal-coords input');
    decimalInputs.forEach(input => {
        input.disabled = disable;
    });
}

// New function to hide previous results
function hideResults() {
    document.getElementById('results').style.display = 'none';
}

// New function to show processing message
function showProcessingMessage() {
    const processingMessage = document.createElement("div");
    processingMessage.id = "processing-message";
    processingMessage.innerHTML = `
        <p>Processing results, this may take a few minutes...</p>
        <div class="spinner"></div>
    `;
    document.body.appendChild(processingMessage);
}

// New function to hide processing message
function hideProcessingMessage() {
    const processingMessage = document.getElementById('processing-message');
    if (processingMessage) {
        processingMessage.remove();
    }
}

// Update the form submission logic to include hiding/showing results
document.getElementById('recon-form').onsubmit = function(e) {
    e.preventDefault();
    
    // Hide previous results
    hideResults();
    
    // Show processing message
    showProcessingMessage();
    
    const formData = new FormData(this);
    fetch('/', {
        method: 'POST',
        body: formData
    }).then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Unknown error');
            });
        }
        return response.json();
    }).then(data => {
        // Hide processing message
        hideProcessingMessage();

        // Show the results
        document.getElementById('result-map').src = data.map_url;
        document.getElementById('download-coords').href = data.coords_url;
        document.getElementById('download-coords').text = 'Download Selected Coordinates';
        document.getElementById('download-data').href = data.data_url;
        document.getElementById('download-data').text = 'Download Selected Data';
        document.getElementById('download-slr-results').href = data.results_zip_url;
        document.getElementById('download-slr-results').text = 'Download Stepwise Linear Regression Results';
        document.getElementById('results').style.display = 'block';
    }).catch(error => {
        console.error('Error:', error);
        alert('An error occurred: ' + error.message);
        
        // Hide processing message in case of error
        hideProcessingMessage();
    });
}

// Call toggleCoordInputs on page load
window.onload = function() {
    toggleCoordInputs();
}
