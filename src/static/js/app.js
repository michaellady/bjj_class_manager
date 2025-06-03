// Log JavaScript events to server for debugging
function logToServer(message, level = 'info') {
    try {
        fetch('/log-js', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: message,
                level: level
            })
        }).catch(err => console.error('Error logging to server:', err));
    } catch (e) {
        console.error('Error sending log to server:', e);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    console.log("BJJ Attendance Tracker JS Loaded");
    logToServer("BJJ Attendance Tracker JS Loaded");

    const API_BASE_URL = 'http://127.0.0.1:5001/api'; 
    const UPLOAD_FOLDER = '/Users/mikelady/dev/class_pictures/pictures/incoming'; // Path to incoming pictures
    const PROCESSED_FOLDER = '/Users/mikelady/dev/class_pictures/pictures/processed'; // Path to processed pictures

    // DOM Elements - New Dashboard
    const uploadForm = document.getElementById('upload-form');
    const imageFilesInput = document.getElementById('image-files-input');
    const imageUrlInput = document.getElementById('image-url-input'); 
    const uploadStatusDiv = document.getElementById('upload-status');
    
    // Attendance Section Elements
    const dateRangeSelect = document.getElementById('dateRange');
    const studentFilterSelect = document.getElementById('studentFilter');
    const applyFiltersBtn = document.getElementById('applyFilters');
    const totalClassesElement = document.getElementById('totalClasses');
    const totalStudentsElement = document.getElementById('totalStudents');
    const avgAttendanceElement = document.getElementById('avgAttendance');
    const leaderboardBody = document.getElementById('leaderboardBody');
    const attendanceTableBody = document.getElementById('attendanceTableBody');
    const imageDetailsModal = document.getElementById('imageDetailsModal');
    const modalImage = document.getElementById('modalImage');
    const modalAttendees = document.getElementById('modalAttendees');
    
    // Class Gallery Elements
    const galleryDateRangeSelect = document.getElementById('galleryDateRange');
    const applyGalleryFiltersBtn = document.getElementById('applyGalleryFilters');
    const galleryContainer = document.getElementById('galleryContainer');
    const galleryPagination = document.getElementById('galleryPagination');
    
    const loadPersonsBtn = document.getElementById('load-persons-btn');
    const personsListContainer = document.getElementById('persons-list-container');
    const startManualMergeBtn = document.getElementById('start-manual-merge-btn');
    const confirmManualMergeBtn = document.getElementById('confirm-manual-merge-btn'); 
    const cancelManualMergeBtn = document.getElementById('cancel-manual-merge-btn');
    const manualMergeSelectionArea = document.getElementById('manual-merge-selection-area');
    const manualMergeCandidateCardsContainer = document.getElementById('manual-merge-candidate-cards');
    const manualMergeCanonicalSelectionContainer = document.getElementById('manual-merge-canonical-selection');
    const executeManualMergeBtn = document.getElementById('execute-manual-merge-btn'); 
    
    const loadClassImagesBtn = document.getElementById('load-class-images-btn');
    const classImagesContainer = document.getElementById('class-images-container');

    // DOM Elements - Image Detail & Verification Section
    const imageDetailSection = document.getElementById('image-detail-section');
    const backToDashboardBtn = document.getElementById('back-to-dashboard-btn'); 
    const imageDetailFilename = document.getElementById('image-detail-filename');
    const mainClassImage = document.getElementById('main-class-image');
    const detectionsGrid = document.getElementById('detections-grid');
    
    // DOM Elements - Student Detail Section
    const studentDetailSection = document.getElementById('student-detail-section');
    const studentDetailInfo = document.getElementById('student-detail-info'); // Added missing reference
    const studentDetailRepImage = document.getElementById('student-detail-rep-image');
    const studentDetailName = document.getElementById('student-detail-name');
    const studentDetailId = document.getElementById('student-detail-id');
    const studentDetailEnrollment = document.getElementById('student-detail-enrollment');
    const studentDetailAttendanceSummary = document.getElementById('student-detail-attendance-summary');
    const studentAttendanceGallery = document.getElementById('student-attendance-gallery');
    const backToDashboardFromStudentBtn = document.getElementById('back-to-dashboard-from-student-btn');

    const allMainSections = [
        document.getElementById('image-upload-section'),
        document.getElementById('dashboard-overview'),
        document.getElementById('persons-list-section'),
        document.getElementById('class-images-section'),
        document.getElementById('image-detail-section'), 
        document.getElementById('student-detail-section'), 
        document.getElementById('merge-tool-section') 
    ];

    // DOM Elements - Suggestion Merge Tool (original, now potentially hidden or integrated)
    const suggestMergesBtnOld = document.getElementById('suggest-merges-btn'); 
    const mergePreviewAreaOld = document.getElementById('merge-preview-area');
    const candidateCardsContainerOld = document.getElementById('candidate-cards');
    const canonicalSelectionContainerOld = document.getElementById('canonical-selection');
    // Ensure HTML uses unique IDs if both merge tools are present simultaneously
    // The ID "confirm-merge-btn" is used in HTML for the suggestion section.
    const confirmMergeBtnSuggestion = document.querySelector('#merge-tool-section #confirm-merge-btn'); 
    const skipSuggestionBtnOld = document.querySelector('#merge-tool-section #skip-suggestion-btn');
    const cancelMergeBtnSuggestion = document.querySelector('#merge-tool-section #cancel-merge-btn');


    let allPersonsCache = [];
    let currentSuggestionQueue = [];
    let currentMergeCandidates = []; 
    let selectedCanonicalId = null; 
    let isManualMergeMode = false;
    let manuallySelectedPersonsForMerge = new Set();
    let currentViewingImageId = null; 
    let currentViewingPersonId = null; 

    // --- Helper Functions ---
    function createPersonCard(person, inMergeMode = false) {
        const card = document.createElement('div');
        card.classList.add('person-card'); 
        card.dataset.personId = person.person_id;

        if (inMergeMode) {
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.classList.add('manual-merge-checkbox');
            checkbox.dataset.personId = person.person_id;
            checkbox.checked = manuallySelectedPersonsForMerge.has(person.person_id);
            checkbox.addEventListener('change', (e) => {
                if (e.target.checked) {
                    manuallySelectedPersonsForMerge.add(person.person_id);
                } else {
                    manuallySelectedPersonsForMerge.delete(person.person_id);
                }
                updateConfirmManualMergeButtonState();
            });
            card.appendChild(checkbox);
        }

        const img = document.createElement('img');
        img.src = person.image_url ? person.image_url : 'https://via.placeholder.com/150?text=No+Image';
        img.alt = `Rep image for ${person.person_id}`;
        img.onerror = () => { img.src = 'https://via.placeholder.com/150?text=Error'; };

        const nameText = document.createElement('p');
        nameText.textContent = person.name || `ID: ...${person.person_id.slice(-12)}`;
        nameText.classList.add('person-name'); 

        const idText = document.createElement('p');
        idText.classList.add('person-id');
        idText.textContent = `(ID: ...${person.person_id.slice(-12)})`;
        
        const summaryText = document.createElement('p');
        summaryText.textContent = person.attendance_summary || `Enrolled: ${person.enrollment_date ? new Date(person.enrollment_date).toLocaleDateString() : 'N/A'}`;
        
        card.appendChild(img);
        card.appendChild(nameText);
        if (!person.name) card.appendChild(idText); 
        else idText.style.fontSize = '0.7em'; 
        card.appendChild(summaryText);
        
        if (!inMergeMode) {
            card.style.cursor = 'pointer';
            card.addEventListener('click', () => loadAndShowStudentDetails(person.person_id));
        }
        return card;
    }
    
    function updateConfirmManualMergeButtonState() {
        if (confirmManualMergeBtn) { 
            confirmManualMergeBtn.disabled = manuallySelectedPersonsForMerge.size < 2;
        }
    }

    function createClassImageListItem(imageRec) {
        const item = document.createElement('div');
        item.classList.add('class-image-list-item'); 
        item.dataset.imageId = imageRec.class_image_id;
        item.style.padding = '10px';
        item.style.borderBottom = '1px solid #eee';
        item.style.display = 'flex'; 
        item.style.justifyContent = 'space-between';
        item.style.alignItems = 'center';

        const contentPart = document.createElement('div');
        contentPart.style.cursor = 'pointer';
        contentPart.style.flexGrow = '1'; 
        contentPart.innerHTML = `
            <p><strong>File:</strong> ${imageRec.original_filename}</p>
            <p><strong>Date Taken:</strong> ${new Date(imageRec.date_taken).toLocaleString()}</p>
            <p><strong>Status:</strong> ${imageRec.processing_status}</p>
            ${imageRec.processing_error_message ? `<p style="color:red;">Error: ${imageRec.processing_error_message}</p>` : ''}
        `;
        contentPart.addEventListener('click', () => loadAndShowImageDetections(imageRec.class_image_id, imageRec.original_filename));
        item.appendChild(contentPart);
        
        const deleteBtn = document.createElement('button');
        deleteBtn.classList.add('delete-class-image-btn');
        deleteBtn.dataset.imageId = imageRec.class_image_id;
        deleteBtn.textContent = 'Delete';
        deleteBtn.style.marginLeft = '10px';
        deleteBtn.style.backgroundColor = '#dc3545';
        deleteBtn.style.color = 'white';
        deleteBtn.style.border = 'none';
        deleteBtn.style.padding = '5px 10px';
        deleteBtn.style.cursor = 'pointer';
        deleteBtn.addEventListener('click', handleDeleteClassImage);
        item.appendChild(deleteBtn);
        
        return item;
    }

    async function handleDeleteClassImage(event) {
        event.stopPropagation(); 
        const imageId = parseInt(event.target.dataset.imageId || currentViewingImageId);
        
        // Validate image ID
        if (!imageId || isNaN(imageId)) {
            console.error('Invalid or missing image ID for deletion');
            if(uploadStatusDiv) uploadStatusDiv.textContent = 'Failed to delete: Invalid or missing image ID.';
            return;
        }

        if (!confirm(`Are you sure you want to delete Class Image ID ${imageId} and all its associated data? This action cannot be undone.`)) {
            return;
        }
        
        if(uploadStatusDiv) uploadStatusDiv.textContent = `Deleting Class Image ${imageId}...`;
        try {
            const response = await fetch(`${API_BASE_URL}/classimages/${imageId}`, { method: 'DELETE' });
            const result = await response.json(); 
            if (!response.ok) throw new Error(result.message || result.error || `HTTP error! Status: ${response.status}`);
            if(uploadStatusDiv) uploadStatusDiv.textContent = result.message || `Class Image ${imageId} deleted successfully.`;
            
            // If we're in the image detail view, go back to dashboard
            if (currentViewingImageId === imageId) {
                currentViewingImageId = null; // Clear the current image ID
                showMainDashboard();
            }
            
            fetchClassImages(); // Refresh the class images list
        } catch (error) {
            console.error(`Error deleting class image ${imageId}:`, error);
            if(uploadStatusDiv) uploadStatusDiv.textContent = `Failed to delete Class Image ${imageId}: ${error.message}`;
            alert(`Failed to delete Class Image ${imageId}: ${error.message}`);
        }
    }
    
    function displayClassImagesList(images) {
        if (!classImagesContainer) return;
        classImagesContainer.innerHTML = '';
        if (!images || images.length === 0) {
            classImagesContainer.innerHTML = '<p>No class images found or loaded.</p>';
            return;
        }
        images.forEach(imgRec => {
            const item = createClassImageListItem(imgRec);
            classImagesContainer.appendChild(item);
        });
    }

    function displayPersonsList(persons, inMergeMode = false) {
        if (!personsListContainer) return;
        personsListContainer.innerHTML = ''; 
        if (!persons || persons.length === 0) {
            personsListContainer.innerHTML = '<p>No students found or loaded.</p>';
            return;
        }
        persons.forEach(person => {
            const card = createPersonCard(person, inMergeMode);
            personsListContainer.appendChild(card);
        });
    }
    
    function toggleManualMergeMode(enable) {
        isManualMergeMode = enable;
        if (startManualMergeBtn) startManualMergeBtn.style.display = enable ? 'none' : 'inline-block';
        if (confirmManualMergeBtn) confirmManualMergeBtn.style.display = enable ? 'inline-block' : 'none';
        if (cancelManualMergeBtn) cancelManualMergeBtn.style.display = enable ? 'inline-block' : 'none';
        if (manualMergeSelectionArea) manualMergeSelectionArea.style.display = 'none'; 
        
        manuallySelectedPersonsForMerge.clear();
        updateConfirmManualMergeButtonState();
        displayPersonsList(allPersonsCache, isManualMergeMode); 
    }

    function populateManualMergeSelectionArea() {
        if (!manualMergeCandidateCardsContainer || !manualMergeCanonicalSelectionContainer || !executeManualMergeBtn) return;

        manualMergeCandidateCardsContainer.innerHTML = '';
        manualMergeCanonicalSelectionContainer.innerHTML = '';
        currentMergeCandidates = []; 
        selectedCanonicalId = null;
        executeManualMergeBtn.disabled = true;

        if (manuallySelectedPersonsForMerge.size < 2) {
            alert("Please select at least two students to merge.");
            if (manualMergeSelectionArea) manualMergeSelectionArea.style.display = 'none';
            return;
        }

        manuallySelectedPersonsForMerge.forEach(pid => {
            const personData = allPersonsCache.find(p => p.person_id === pid);
            if (personData) {
                currentMergeCandidates.push(personData); 
                const card = createPersonCard(personData, false); 
                card.classList.remove('person-card');
                card.classList.add('candidate-card'); 
                manualMergeCandidateCardsContainer.appendChild(card);

                const radioLabel = document.createElement('label');
                const radioInput = document.createElement('input');
                radioInput.type = 'radio';
                radioInput.name = 'manual_canonical_id';
                radioInput.value = personData.person_id;
                radioInput.addEventListener('change', (e) => {
                    selectedCanonicalId = e.target.value;
                    if (executeManualMergeBtn) executeManualMergeBtn.disabled = false;
                });
                radioLabel.appendChild(radioInput);
                radioLabel.appendChild(document.createTextNode(` Keep: ${personData.name || personData.person_id.slice(-12)}`));
                manualMergeCanonicalSelectionContainer.appendChild(radioLabel);
            }
        });
        if (manualMergeSelectionArea) manualMergeSelectionArea.style.display = 'block';
    }

    function showMainDashboard() {
        allMainSections.forEach(section => {
            if (section && section.id !== 'image-detail-section' && section.id !== 'student-detail-section') {
                section.style.display = 'block'; 
            } else if (section) {
                section.style.display = 'none';
            }
        });
        if(isManualMergeMode) toggleManualMergeMode(false); 
        if(manualMergeSelectionArea) manualMergeSelectionArea.style.display = 'none'; // Ensure this is hidden too
    }
    
    function showSpecificView(sectionToShowId) {
        allMainSections.forEach(section => {
            if (section) { 
                section.style.display = (section.id === sectionToShowId) ? 'block' : 'none';
            }
        });
        if (isManualMergeMode && sectionToShowId !== 'persons-list-section' && sectionToShowId !== 'manual-merge-selection-area') {
            toggleManualMergeMode(false);
        }
    }
    
    function showImageDetailView() {
        currentViewingImageId = null; 
        showSpecificView('image-detail-section');
    }

    function showStudentDetailView() {
        currentViewingPersonId = null;
        showSpecificView('student-detail-section');
    }

    // --- Image Upload ---
    async function handleImageUpload(event) {
        event.preventDefault();
        const file = imageFilesInput.files[0];
        const imageUrl = imageUrlInput.value.trim();

        if (!file && !imageUrl) {
            if(uploadStatusDiv) uploadStatusDiv.textContent = 'Please select a file or enter an image URL.';
            return;
        }
        const formData = new FormData();
        if (file) { 
            formData.append('file', file);
        } else if (imageUrl) {
            formData.append('image_url', imageUrl);
        }
        if(uploadStatusDiv) uploadStatusDiv.textContent = 'Uploading and processing...';
        try {
            const response = await fetch(`${API_BASE_URL}/images/upload`, {
                method: 'POST',
                body: formData,
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.message || result.error || `HTTP error! status: ${response.status}`);
            }
            if(uploadStatusDiv) uploadStatusDiv.textContent = `Success: ${result.message} (Image ID: ${result.image_id})`;
            if(imageFilesInput) imageFilesInput.value = ''; 
            if(imageUrlInput) imageUrlInput.value = ''; 
            fetchClassImages(); 
        } catch (error) {
            console.error('Upload error:', error);
            if(uploadStatusDiv) uploadStatusDiv.textContent = `Upload failed: ${error.message}`;
        }
    }

    // --- API Call Functions (Persons & Class Images) ---
    async function fetchAllPersons() {
        if(uploadStatusDiv) uploadStatusDiv.textContent = 'Loading students...';
        try {
            const response = await fetch(`${API_BASE_URL}/persons`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            allPersonsCache = await response.json();
            displayPersonsList(allPersonsCache, isManualMergeMode); 
            if(uploadStatusDiv) uploadStatusDiv.textContent = `Loaded ${allPersonsCache.length} students.`;
            console.log("Persons loaded:", allPersonsCache);
        } catch (error) {
            console.error("Error fetching persons:", error);
            if(personsListContainer) personsListContainer.innerHTML = `<p>Error loading persons: ${error.message}</p>`;
            if(uploadStatusDiv) uploadStatusDiv.textContent = `Error loading persons.`;
        }
    }

    async function fetchClassImages() {
        if(uploadStatusDiv) uploadStatusDiv.textContent = 'Loading class images...';
        if(classImagesContainer) classImagesContainer.innerHTML = 'Loading class images...';
        try {
            const response = await fetch(`${API_BASE_URL}/classimages`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const images = await response.json();
            displayClassImagesList(images);
            if(uploadStatusDiv) uploadStatusDiv.textContent = `Loaded ${images.length} class images.`;
            console.log("Class images loaded:", images);
        } catch (error) {
            console.error("Error fetching class images:", error);
            if(classImagesContainer) classImagesContainer.innerHTML = `<p>Error loading class images: ${error.message}</p>`;
            if(uploadStatusDiv) uploadStatusDiv.textContent = `Error loading class images.`;
        }
    }

    async function loadAndShowImageDetections(imageId, originalFilename) {
        currentViewingImageId = imageId; // Ensure this is set
        showImageDetailView();
        if(imageDetailFilename) imageDetailFilename.textContent = `Details for: ${originalFilename} (Image ID: ${imageId})`;
        if(mainClassImage) {
            mainClassImage.src = 'https://via.placeholder.com/600x400?text=Loading...';
        }
        if(detectionsGrid) detectionsGrid.innerHTML = '<p>Loading detections...</p>';
        try {
            const response = await fetch(`${API_BASE_URL}/images/${imageId}/detections`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            
            // Load main image using data URL method
            if(mainClassImage && data.image_info) {
                // Check if we have Instagram shortcode or filepath
                if (data.image_info.instagram_shortcode) {
                    loadMainImageWithDataUrl(data.image_info.instagram_shortcode);
                } else if (data.image_info.filepath_processed) {
                    loadMainImageWithDataUrlByPath(data.image_info.filepath_processed);
                } else {
                    mainClassImage.src = 'https://via.placeholder.com/600x400?text=Main+Image+Not+Found';
                }
            }

            if(detectionsGrid) detectionsGrid.innerHTML = ''; 
            if (!data.detections || data.detections.length === 0) {
                if(detectionsGrid) detectionsGrid.innerHTML = '<p>No detections found for this image.</p>';
                return;
            }

            data.detections.forEach(det => {
                const card = document.createElement('div');
                card.classList.add('detection-card'); 
                card.style.border = det.is_verified_by_user ? '2px solid green' : '2px solid orange';
                card.style.padding = '10px';
                card.style.margin = '5px';

                const cropImg = document.createElement('img');
                cropImg.src = det.face_crop_url || 'https://via.placeholder.com/100?text=No+Crop';
                cropImg.alt = `Detection ${det.detection_id}`;
                cropImg.style.maxWidth = '100px';
                cropImg.onerror = () => { cropImg.src = 'https://via.placeholder.com/100?text=Error';};

                const personInfo = document.createElement('p');
                personInfo.textContent = `Assigned: ${det.person_name || det.person_id || 'Unknown'}`;
                
                const verifyBtn = document.createElement('button');
                verifyBtn.textContent = det.is_verified_by_user ? 'Verified' : 'Verify Correct';
                verifyBtn.disabled = det.is_verified_by_user;
                verifyBtn.dataset.detectionId = det.detection_id;
                verifyBtn.addEventListener('click', handleVerifyDetection);

                const correctBtn = document.createElement('button');
                correctBtn.textContent = 'Correct Assignment';
                correctBtn.dataset.detectionId = det.detection_id;
                correctBtn.dataset.currentPersonId = det.person_id || 'UNKNOWN';
                correctBtn.addEventListener('click', handleOpenCorrectionModal);
                
                card.appendChild(cropImg);
                card.appendChild(personInfo);
                card.appendChild(verifyBtn);
                card.appendChild(correctBtn);
                if(detectionsGrid) detectionsGrid.appendChild(card);
            });
        } catch (error) {
            console.error(`Error fetching detections for image ${imageId}:`, error);
            if(detectionsGrid) detectionsGrid.innerHTML = `<p>Error loading detections: ${error.message}</p>`;
            if(mainClassImage) mainClassImage.src = 'https://via.placeholder.com/600x400?text=Error';
        }
    }

    // Helper function for loading main image with data URL
    async function loadMainImageWithDataUrl(shortcode) {
        try {
            const response = await fetch(`/api/images/data-url?shortcode=${shortcode}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            
            const data = await response.json();
            if (!data.success || !data.data_url) {
                throw new Error(data.error || 'Failed to get data URL');
            }
            
            console.log('Successfully loaded main image via data URL');
            mainClassImage.src = data.data_url;
        } catch (error) {
            console.error("Error loading main image:", error);
            mainClassImage.src = 'https://via.placeholder.com/600x400?text=Main+Image+Not+Found';
        }
    }

    // Helper function for loading main image with data URL by path
    async function loadMainImageWithDataUrlByPath(filepath) {
        try {
            const encodedPath = encodeURIComponent(filepath);
            const response = await fetch(`/api/images/data-url?path=${encodedPath}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            
            const data = await response.json();
            if (!data.success || !data.data_url) {
                throw new Error(data.error || 'Failed to get data URL');
            }
            
            console.log('Successfully loaded main image via data URL');
            mainClassImage.src = data.data_url;
        } catch (error) {
            console.error("Error loading main image:", error);
            mainClassImage.src = 'https://via.placeholder.com/600x400?text=Main+Image+Not+Found';
        }
    }

    async function handleVerifyDetection(event) {
        const detectionId = event.target.dataset.detectionId;
        if(uploadStatusDiv) uploadStatusDiv.textContent = `Verifying detection ${detectionId}...`;
        try {
            const response = await fetch(`${API_BASE_URL}/detections/${detectionId}/verify`, { method: 'POST' });
            const result = await response.json();
            if (!response.ok) throw new Error(result.message || result.error || 'Verification failed');
            
            if(uploadStatusDiv) uploadStatusDiv.textContent = `Detection ${detectionId} verified.`;
            const button = event.target;
            button.textContent = 'Verified';
            button.disabled = true;
            button.closest('.detection-card').style.borderColor = 'green';
        } catch (error) {
            console.error('Verification error:', error);
            if(uploadStatusDiv) uploadStatusDiv.textContent = `Verification failed for ${detectionId}: ${error.message}`;
        }
    }

    function handleOpenCorrectionModal(event) {
        const detectionId = event.target.dataset.detectionId;
        const currentPersonId = event.target.dataset.currentPersonId;
        const newPersonId = prompt(`Enter new Person ID for detection ${detectionId} (was ${currentPersonId}).\nLeave blank for 'Unknown', or type existing ID.`, currentPersonId);
        if (newPersonId === null) return; 
        handleCorrectDetection(detectionId, newPersonId.trim() || null); 
    }
    
    async function handleCorrectDetection(detectionId, newPersonIdOrNull) {
        if(uploadStatusDiv) uploadStatusDiv.textContent = `Correcting detection ${detectionId}...`;
        const payload = { new_person_id: newPersonIdOrNull };
        try {
            const response = await fetch(`${API_BASE_URL}/detections/${detectionId}/correct`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.message || result.error || 'Correction failed');

            if(uploadStatusDiv) uploadStatusDiv.textContent = `Detection ${detectionId} corrected to ${newPersonIdOrNull || 'Unknown'}.`;
            
            const cardToUpdate = Array.from(detectionsGrid.querySelectorAll('.detection-card'))
                                .find(card => card.querySelector(`button[data-detection-id="${detectionId}"]`));
            if (cardToUpdate && result.detection) {
                const personInfoP = cardToUpdate.querySelector('p'); 
                const verifyBtn = cardToUpdate.querySelector(`button[data-detection-id="${detectionId}"][data-action="verify"]`); // More specific selector
                const correctBtn = cardToUpdate.querySelector(`button[data-detection-id="${detectionId}"][data-action="correct"]`);


                personInfoP.textContent = `Assigned: ${result.detection.person_name || result.detection.person_id || 'Unknown'}`;
                cardToUpdate.style.borderColor = 'green'; 
                if(verifyBtn) { 
                    verifyBtn.textContent = 'Verified';
                    verifyBtn.disabled = true;
                }
                 // Update currentPersonId on the correct button if it exists
                if (correctBtn) {
                    correctBtn.dataset.currentPersonId = result.detection.person_id || 'UNKNOWN';
                }
            } else if (currentViewingImageId) { 
                const imageToRefresh = document.querySelector(`.class-image-list-item[data-image-id="${currentViewingImageId}"] p strong`);
                const originalFilenameToRefresh = imageToRefresh ? imageToRefresh.textContent.replace('File: ','') : "current image";
                loadAndShowImageDetections(currentViewingImageId, originalFilenameToRefresh);
            }
        } catch (error) {
            console.error('Correction error:', error);
            if(uploadStatusDiv) uploadStatusDiv.textContent = `Correction failed for ${detectionId}: ${error.message}`;
        }
    }

    // --- Student Detail View Functions ---
    async function loadAndShowStudentDetails(personId) {
        currentViewingPersonId = personId;
        showStudentDetailView();
        if (!studentDetailInfo || !studentAttendanceGallery || !studentDetailRepImage || !studentDetailName || !studentDetailId || !studentDetailEnrollment || !studentDetailAttendanceSummary) {
            console.error("One or more student detail DOM elements are missing.");
            return;
        }

        studentDetailRepImage.src = 'https://via.placeholder.com/150?text=Loading...';
        studentDetailRepImage.alt = 'Loading...';
        studentDetailName.textContent = 'Loading...';
        studentDetailId.textContent = 'ID: Loading...';
        studentDetailEnrollment.textContent = 'Enrolled: Loading...';
        studentDetailAttendanceSummary.textContent = 'Total Attendances Recorded: Loading...';
        studentAttendanceGallery.innerHTML = '<p>Loading attendance records...</p>';

        try {
            const response = await fetch(`${API_BASE_URL}/persons/${personId}/attendance_details`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();

            const person = data.person_info;
            studentDetailRepImage.src = person.image_url || 'https://via.placeholder.com/150?text=No+Image';
            studentDetailRepImage.alt = `Representative image for ${person.name || person.person_id}`;
            studentDetailName.textContent = person.name || 'N/A';
            studentDetailId.textContent = `ID: ${person.person_id}`;
            studentDetailEnrollment.textContent = `Enrolled: ${person.enrollment_date ? new Date(person.enrollment_date).toLocaleDateString() : 'N/A'}`;
            
            const attendance = data.attendance_details;
            studentDetailAttendanceSummary.textContent = `Total Attendances Recorded: ${attendance.length}`;
            
            studentAttendanceGallery.innerHTML = ''; 
            if (attendance.length === 0) {
                studentAttendanceGallery.innerHTML = '<p>No attendance records found for this student.</p>';
            } else {
                attendance.forEach(att => {
                    const attCard = document.createElement('div');
                    attCard.classList.add('student-attendance-card'); 
                    attCard.style.border = '1px solid #eee';
                    attCard.style.padding = '8px';
                    attCard.style.textAlign = 'center';
                    
                    const imgThumb = document.createElement('img');
                    imgThumb.src = att.face_crop_url || att.main_class_image_url || 'https://via.placeholder.com/100?text=Class+Pic';
                    imgThumb.alt = `Class on ${new Date(att.date_taken).toLocaleDateString()}`;
                    imgThumb.style.maxWidth = '100px';
                    imgThumb.style.maxHeight = '100px';
                    imgThumb.style.marginBottom = '5px';
                    imgThumb.onerror = () => { imgThumb.src = 'https://via.placeholder.com/100?text=Error';};

                    const dateText = document.createElement('p');
                    dateText.textContent = new Date(att.date_taken).toLocaleDateString();
                    dateText.style.fontSize = '0.8em';

                    const viewClassBtn = document.createElement('button');
                    viewClassBtn.textContent = "View Class Details";
                    viewClassBtn.style.marginTop = "5px";
                    viewClassBtn.addEventListener('click', () => loadAndShowImageDetections(att.class_image_id, att.original_filename));

                    const reassignBtn = document.createElement('button');
                    reassignBtn.textContent = "Reassign this Detection";
                    reassignBtn.style.marginTop = "5px";
                    reassignBtn.style.marginLeft = "5px";
                    reassignBtn.style.backgroundColor = "#ffc107"; // Yellowish for caution/edit
                    reassignBtn.dataset.detectionId = att.detection_id;
                    reassignBtn.dataset.currentPersonId = personId; // The student whose page we are on
                    reassignBtn.addEventListener('click', handleOpenCorrectionModalFromStudentPage);
                    
                    attCard.appendChild(imgThumb);
                    attCard.appendChild(dateText);
                    attCard.appendChild(viewClassBtn);
                    attCard.appendChild(reassignBtn);
                    
                    studentAttendanceGallery.appendChild(attCard);
                });
            }
        } catch (error) {
            console.error(`Error fetching student details for ${personId}:`, error);
            // Clear loading states and show error in the main info area
            studentDetailRepImage.src = 'https://via.placeholder.com/150?text=Error';
            studentDetailName.textContent = 'Error';
            studentDetailId.textContent = `ID: ${personId}`;
            studentDetailEnrollment.textContent = `Error loading details.`;
            studentDetailAttendanceSummary.textContent = '';
            if(studentAttendanceGallery) studentAttendanceGallery.innerHTML = `<p>Error loading attendance: ${error.message}</p>`;
        }
    }

    function handleOpenCorrectionModalFromStudentPage(event) {
        const detectionId = event.target.dataset.detectionId;
        const studentPagePersonId = event.target.dataset.currentPersonId; // Person whose page we are on
        
        // We want to reassign this detection AWAY from studentPagePersonId
        // Options: 1. Assign to existing other person, 2. Mark as Unknown, 3. Create new person from this detection
        const action = prompt(`Reassign detection ${detectionId} (currently assigned to student ${studentPagePersonId.slice(-6)}...)?\n1. Assign to existing Person ID\n2. Mark as 'Unknown'\n3. Create NEW Person from this detection\nEnter 1, 2, or 3:`);

        if (action === '1') {
            const newPersonId = prompt(`Enter the existing Person ID to assign this detection to:`);
            if (newPersonId && newPersonId.trim() !== "") {
                handleCorrectDetection(detectionId, newPersonId.trim(), studentPagePersonId); // Pass original for logging
            } else if (newPersonId !== null) { // User entered blank but didn't cancel
                alert("No Person ID entered. Reassignment cancelled.");
            }
        } else if (action === '2') {
            handleCorrectDetection(detectionId, null, studentPagePersonId); // Pass null for 'Unknown'
        } else if (action === '3') {
            // This requires a new backend endpoint & logic
            handleReassignToNewPerson(detectionId, studentPagePersonId);
        } else if (action !== null) { // User entered something invalid but didn't cancel
            alert("Invalid option selected.");
        }
    }

    async function handleReassignToNewPerson(detectionId, originalPersonId) {
        if (!confirm(`This will create a NEW person entry based on detection ${detectionId} and remove it from student ${originalPersonId.slice(-6)}.... Proceed?`)) {
            return;
        }
        if(uploadStatusDiv) uploadStatusDiv.textContent = `Creating new person from detection ${detectionId}...`;
        try {
            // This endpoint needs to be created: POST /api/detections/<detection_id>/reassign_to_new_person
            const response = await fetch(`${API_BASE_URL}/detections/${detectionId}/reassign_to_new_person`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                // Optionally, pass originalPersonId if backend needs it for logging the change source
                body: JSON.stringify({ original_person_id_of_detection: originalPersonId })
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.message || result.error || 'Failed to reassign to new person.');
            }
            if(uploadStatusDiv) uploadStatusDiv.textContent = result.message || `Detection ${detectionId} reassigned to new person ${result.new_person_id.slice(-6)}...`;
            alert(result.message || `Detection ${detectionId} reassigned to new person ${result.new_person_id}.`);
            
            // Refresh current student's details (as one attendance was removed)
            // And refresh the main persons list (as a new person was added)
            if(currentViewingPersonId) loadAndShowStudentDetails(currentViewingPersonId);
            fetchAllPersons();

        } catch (error) {
            console.error('Error reassigning to new person:', error);
            if(uploadStatusDiv) uploadStatusDiv.textContent = `Error: ${error.message}`;
            alert(`Error: ${error.message}`);
        }
    }

    // --- Attendance History Functions ---
    async function fetchAttendanceHistory() {
        console.log("Fetching attendance history...");
        if (leaderboardBody) leaderboardBody.innerHTML = '<tr><td colspan="4">Loading...</td></tr>';
        if (attendanceTableBody) attendanceTableBody.innerHTML = '<tr><td colspan="4">Loading...</td></tr>';
        
        try {
            const days = dateRangeSelect ? dateRangeSelect.value : '30';
            const studentId = studentFilterSelect ? studentFilterSelect.value : 'all';
            
            const response = await fetch(`${API_BASE_URL}/attendance/history?days=${days}&student_id=${studentId}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            
            // Update stats
            if (totalClassesElement) totalClassesElement.textContent = data.stats.total_classes;
            if (totalStudentsElement) totalStudentsElement.textContent = data.stats.total_students;
            if (avgAttendanceElement) avgAttendanceElement.textContent = data.stats.avg_attendance;
            
            // Update leaderboard
            if (leaderboardBody) {
                leaderboardBody.innerHTML = '';
                if (data.leaderboard.length === 0) {
                    leaderboardBody.innerHTML = '<tr><td colspan="4">No attendance data found</td></tr>';
                } else {
                    data.leaderboard.forEach((person, index) => {
                        const row = document.createElement('tr');
                        row.innerHTML = `
                            <td>${index + 1}</td>
                            <td><a href="#" class="student-link" data-person-id="${person.person_id}">${person.name || 'Unknown'}</a></td>
                            <td>${person.classes_attended}</td>
                            <td>${person.attendance_percentage.toFixed(1)}%</td>
                        `;
                        leaderboardBody.appendChild(row);
                    });
                    
                    // Add event listeners to student links
                    const studentLinks = leaderboardBody.querySelectorAll('.student-link');
                    studentLinks.forEach(link => {
                        link.addEventListener('click', (e) => {
                            e.preventDefault();
                            const personId = e.target.dataset.personId;
                            loadAndShowStudentDetails(personId);
                        });
                    });
                }
            }
            
            // Update attendance records table
            if (attendanceTableBody) {
                attendanceTableBody.innerHTML = '';
                if (data.attendance_records.length === 0) {
                    attendanceTableBody.innerHTML = '<tr><td colspan="4">No class records found</td></tr>';
                } else {
                    data.attendance_records.forEach(record => {
                        const row = document.createElement('tr');
                        
                        // Format techniques
                        let techniquesHtml = '';
                        if (record.techniques && record.techniques.length > 0) {
                            const techniquesList = record.techniques.map(t => t.name).join(', ');
                            techniquesHtml = `<span title="${techniquesList}">${record.techniques.length} techniques</span>`;
                        } else {
                            techniquesHtml = '<span>None recorded</span>';
                        }
                        
                        row.innerHTML = `
                            <td>${new Date(record.date_taken).toLocaleDateString()}</td>
                            <td>${record.attendees} students</td>
                            <td>${techniquesHtml}</td>
                            <td>
                                <button class="view-details-btn" data-image-id="${record.class_image_id}">View Details</button>
                            </td>
                        `;
                        attendanceTableBody.appendChild(row);
                    });
                    
                    // Add event listeners to view details buttons
                    const viewDetailsButtons = attendanceTableBody.querySelectorAll('.view-details-btn');
                    viewDetailsButtons.forEach(button => {
                        button.addEventListener('click', (e) => {
                            const imageId = e.target.dataset.imageId;
                            openImageDetailsModal(imageId);
                        });
                    });
                }
            }
            
            // Populate student filter if not already populated
            if (studentFilterSelect && studentFilterSelect.options.length <= 1) {
                // Add all students from the leaderboard to the filter
                data.leaderboard.forEach(person => {
                    const option = document.createElement('option');
                    option.value = person.person_id;
                    option.textContent = person.name || `ID: ${person.person_id.slice(-6)}...`;
                    studentFilterSelect.appendChild(option);
                });
            }
            
            console.log("Attendance history loaded:", data);
            
        } catch (error) {
            console.error("Error fetching attendance history:", error);
            if (leaderboardBody) leaderboardBody.innerHTML = `<tr><td colspan="4">Error: ${error.message}</td></tr>`;
            if (attendanceTableBody) attendanceTableBody.innerHTML = `<tr><td colspan="4">Error: ${error.message}</td></tr>`;
        }
    }
    
    async function openImageDetailsModal(imageId) {
        if (!imageDetailsModal || !modalImage || !modalAttendees) return;
        
        modalAttendees.innerHTML = 'Loading attendees...';
        modalImage.src = 'https://via.placeholder.com/400x300?text=Loading...';
        
        try {
            const response = await fetch(`${API_BASE_URL}/class-images/${imageId}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            
            // Show attendees first (while image loads)
            modalAttendees.innerHTML = '';
            if (data.attendees && data.attendees.length > 0) {
                const attendeesList = document.createElement('ul');
                attendeesList.classList.add('attendees-list');
                
                data.attendees.forEach(attendee => {
                    const listItem = document.createElement('li');
                    listItem.innerHTML = `
                        <a href="#" class="student-link" data-person-id="${attendee.person_id}">${attendee.name || 'Unknown'}</a>
                        <span class="detection-count">(${attendee.detections.length} detection${attendee.detections.length !== 1 ? 's' : ''})</span>
                    `;
                    attendeesList.appendChild(listItem);
                });
                
                modalAttendees.appendChild(attendeesList);
                
                // Add event listeners to student links
                const studentLinks = modalAttendees.querySelectorAll('.student-link');
                studentLinks.forEach(link => {
                    link.addEventListener('click', (e) => {
                        e.preventDefault();
                        const personId = e.target.dataset.personId;
                        imageDetailsModal.style.display = 'none';
                        loadAndShowStudentDetails(personId);
                    });
                });
            } else {
                modalAttendees.innerHTML = '<p>No attendees found for this class.</p>';
            }
            
            // Show modal right away (while image is loading)
            imageDetailsModal.style.display = 'block';
            
            // Load the image using data URL method
            if (data.image && data.image.instagram_shortcode) {
                // Use the most reliable method - Data URL
                loadModalImageWithDataUrl(data.image.instagram_shortcode);
            } else if (data.image && data.image.filepath_processed) {
                loadModalImageWithDataUrlByPath(data.image.filepath_processed);
            } else {
                modalImage.src = 'https://via.placeholder.com/400x300?text=No+Image+Available';
            }
            
        } catch (error) {
            console.error(`Error fetching image details for ${imageId}:`, error);
            modalAttendees.innerHTML = `<p>Error loading attendees: ${error.message}</p>`;
            modalImage.src = 'https://via.placeholder.com/400x300?text=Error';
        }
    }
    
    async function loadModalImageWithDataUrl(shortcode) {
        try {
            const response = await fetch(`/api/images/data-url?shortcode=${shortcode}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            
            const data = await response.json();
            if (!data.success || !data.data_url) {
                throw new Error(data.error || 'Failed to get data URL');
            }
            
            console.log('Successfully loaded modal image via data URL');
            modalImage.src = data.data_url;
        } catch (error) {
            console.error("Error loading modal image:", error);
            modalImage.src = 'https://via.placeholder.com/400x300?text=Image+Not+Found';
        }
    }

    async function loadModalImageWithDataUrlByPath(filepath) {
        try {
            const encodedPath = encodeURIComponent(filepath);
            const response = await fetch(`/api/images/data-url?path=${encodedPath}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            
            const data = await response.json();
            if (!data.success || !data.data_url) {
                throw new Error(data.error || 'Failed to get data URL');
            }
            
            console.log('Successfully loaded modal image via data URL');
            modalImage.src = data.data_url;
        } catch (error) {
            console.error("Error loading modal image:", error);
            modalImage.src = 'https://via.placeholder.com/400x300?text=Image+Not+Found';
        }
    }

    // --- Class Gallery Functions ---
    async function fetchClassGallery() {
        console.log("Fetching class gallery...");
        if (galleryContainer) galleryContainer.innerHTML = '<div class="loading-indicator">Loading class pictures...</div>';
        
        try {
            const days = galleryDateRangeSelect ? galleryDateRangeSelect.value : '30';
            const page = 1; // Start with first page
            const perPage = 12; // Show 12 images per page
            
            const response = await fetch(`${API_BASE_URL}/class-images?days=${days}&page=${page}&per_page=${perPage}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            
            console.log("Gallery API response:", data);
            
            // Display gallery images
            if (galleryContainer) {
                galleryContainer.innerHTML = '';
                
                if (!data.images || data.images.length === 0) {
                    galleryContainer.innerHTML = '<p>No class pictures found in the selected date range.</p>';
                } else {
                    const galleryGrid = document.createElement('div');
                    galleryGrid.classList.add('gallery-grid');
                    
                    // Process each image
                    for (let index = 0; index < data.images.length; index++) {
                        const image = data.images[index];
                        console.log(`Processing gallery image ${index}:`, image);
                        
                        const galleryItem = document.createElement('div');
                        galleryItem.classList.add('gallery-item');
                        
                        // Create loading indicator
                        const loadingDiv = document.createElement('div');
                        loadingDiv.textContent = 'Loading image...';
                        loadingDiv.style.padding = '10px';
                        loadingDiv.style.textAlign = 'center';
                        galleryItem.appendChild(loadingDiv);
                        
                        // Date and metadata
                        const date = document.createElement('div');
                        date.classList.add('gallery-date');
                        date.textContent = new Date(image.date_taken).toLocaleDateString();
                        galleryItem.appendChild(date);
                        
                        // Attendees count
                        const attendeesDiv = document.createElement('div');
                        attendeesDiv.className = 'attendees-count';
                        attendeesDiv.innerHTML = '<i class="fas fa-users"></i> 18 attendees';
                        galleryItem.appendChild(attendeesDiv);
                        
                        // View details button
                        const viewBtn = document.createElement('button');
                        viewBtn.classList.add('view-details-btn');
                        viewBtn.textContent = 'View Details';
                        viewBtn.dataset.imageId = image.class_image_id;
                        viewBtn.addEventListener('click', () => {
                            loadAndShowImageDetections(image.class_image_id, image.original_filename);
                        });
                        galleryItem.appendChild(viewBtn);
                        
                        // Add to grid immediately, then load image asynchronously
                        galleryGrid.appendChild(galleryItem);
                        
                        // USE DATA URL METHOD - Loading image with data URL approach
                        if (image.instagram_shortcode) {
                            fetchDataUrlImage(image.instagram_shortcode, galleryItem, loadingDiv);
                        } else if (image.filepath_processed) {
                            const encodedPath = encodeURIComponent(image.filepath_processed);
                            fetchDataUrlImageByPath(encodedPath, galleryItem, loadingDiv);
                        } else {
                            showPlaceholder(galleryItem, loadingDiv);
                        }
                    }
                    
                    galleryContainer.appendChild(galleryGrid);
                }
                
                // Set up pagination
                if (galleryPagination && data.pagination) {
                    galleryPagination.innerHTML = '';
                    
                    if (data.pagination.total_pages > 1) {
                        for (let i = 1; i <= data.pagination.total_pages; i++) {
                            const pageLink = document.createElement('a');
                            pageLink.href = '#';
                            pageLink.textContent = i;
                            if (i === data.pagination.page) {
                                pageLink.classList.add('active');
                            }
                            
                            pageLink.addEventListener('click', (e) => {
                                e.preventDefault();
                                fetchClassGalleryPage(i, days, perPage);
                            });
                            
                            galleryPagination.appendChild(pageLink);
                        }
                    }
                }
            }
            
            console.log("Class gallery loaded:", data);
            
        } catch (error) {
            console.error("Error fetching class gallery:", error);
            if (galleryContainer) {
                galleryContainer.innerHTML = `<p>Error loading class gallery: ${error.message}</p>`;
            }
        }
    }

    // Helper function to fetch and display image using Data URL method
    async function fetchDataUrlImage(shortcode, galleryItem, loadingDiv) {
        try {
            const response = await fetch(`/api/images/data-url?shortcode=${shortcode}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            
            const data = await response.json();
            if (!data.success || !data.data_url) {
                throw new Error(data.error || 'Failed to get data URL');
            }
            
            // Create and add the image
            const img = document.createElement('img');
            img.src = data.data_url;
            img.alt = 'Class Image';
            img.style.width = '100%';
            img.style.marginBottom = '10px';
            
            // Replace loading indicator with image
            galleryItem.removeChild(loadingDiv);
            galleryItem.insertBefore(img, galleryItem.firstChild);
        } catch (error) {
            console.error('Error loading image via data URL:', error);
            showPlaceholder(galleryItem, loadingDiv);
        }
    }

    // Helper function to fetch and display image by path using Data URL method
    async function fetchDataUrlImageByPath(encodedPath, galleryItem, loadingDiv) {
        try {
            const response = await fetch(`/api/images/data-url?path=${encodedPath}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            
            const data = await response.json();
            if (!data.success || !data.data_url) {
                throw new Error(data.error || 'Failed to get data URL');
            }
            
            // Create and add the image
            const img = document.createElement('img');
            img.src = data.data_url;
            img.alt = 'Class Image';
            img.style.width = '100%';
            img.style.marginBottom = '10px';
            
            // Replace loading indicator with image
            galleryItem.removeChild(loadingDiv);
            galleryItem.insertBefore(img, galleryItem.firstChild);
        } catch (error) {
            console.error('Error loading image via data URL:', error);
            showPlaceholder(galleryItem, loadingDiv);
        }
    }

    // Helper function to show placeholder when image loading fails
    function showPlaceholder(galleryItem, loadingDiv) {
        // Create placeholder image
        const placeholder = document.createElement('img');
        placeholder.src = 'https://via.placeholder.com/200x200?text=BJJ+Class+Image';
        placeholder.alt = 'Image not available';
        placeholder.style.width = '100%';
        placeholder.style.marginBottom = '10px';
        
        // Replace loading indicator with placeholder
        galleryItem.removeChild(loadingDiv);
        galleryItem.insertBefore(placeholder, galleryItem.firstChild);
    }

    async function fetchClassGalleryPage(page, days, perPage) {
        if (galleryContainer) galleryContainer.innerHTML = '<div class="loading-indicator">Loading class pictures...</div>';
        
        try {
            const response = await fetch(`${API_BASE_URL}/class-images?days=${days}&page=${page}&per_page=${perPage}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            
            // Update the gallery with the new page data
            if (galleryContainer) {
                galleryContainer.innerHTML = '';
                
                if (!data.images || data.images.length === 0) {
                    galleryContainer.innerHTML = '<p>No class pictures found in the selected date range.</p>';
                } else {
                    const galleryGrid = document.createElement('div');
                    galleryGrid.classList.add('gallery-grid');
                    
                    // Process each image
                    for (let index = 0; index < data.images.length; index++) {
                        const image = data.images[index];
                        console.log(`Processing gallery image ${index}:`, image);
                        
                        const galleryItem = document.createElement('div');
                        galleryItem.classList.add('gallery-item');
                        
                        // Create loading indicator
                        const loadingDiv = document.createElement('div');
                        loadingDiv.textContent = 'Loading image...';
                        loadingDiv.style.padding = '10px';
                        loadingDiv.style.textAlign = 'center';
                        galleryItem.appendChild(loadingDiv);
                        
                        // Date and metadata
                        const date = document.createElement('div');
                        date.classList.add('gallery-date');
                        date.textContent = new Date(image.date_taken).toLocaleDateString();
                        galleryItem.appendChild(date);
                        
                        // Attendees count
                        const attendeesDiv = document.createElement('div');
                        attendeesDiv.className = 'attendees-count';
                        attendeesDiv.innerHTML = '<i class="fas fa-users"></i> 18 attendees';
                        galleryItem.appendChild(attendeesDiv);
                        
                        // View details button
                        const viewBtn = document.createElement('button');
                        viewBtn.classList.add('view-details-btn');
                        viewBtn.textContent = 'View Details';
                        viewBtn.dataset.imageId = image.class_image_id;
                        viewBtn.addEventListener('click', () => {
                            loadAndShowImageDetections(image.class_image_id, image.original_filename);
                        });
                        galleryItem.appendChild(viewBtn);
                        
                        // Add to grid immediately, then load image asynchronously
                        galleryGrid.appendChild(galleryItem);
                        
                        // USE DATA URL METHOD - Loading image with data URL approach
                        if (image.instagram_shortcode) {
                            fetchDataUrlImage(image.instagram_shortcode, galleryItem, loadingDiv);
                        } else if (image.filepath_processed) {
                            const encodedPath = encodeURIComponent(image.filepath_processed);
                            fetchDataUrlImageByPath(encodedPath, galleryItem, loadingDiv);
                        } else {
                            showPlaceholder(galleryItem, loadingDiv);
                        }
                    }
                    
                    galleryContainer.appendChild(galleryGrid);
                }
                
                // Update pagination active state
                if (galleryPagination) {
                    const pageLinks = galleryPagination.querySelectorAll('a');
                    pageLinks.forEach(link => {
                        link.classList.remove('active');
                        if (parseInt(link.textContent) === page) {
                            link.classList.add('active');
                        }
                    });
                }
            }
            
        } catch (error) {
            console.error(`Error fetching class gallery page ${page}:`, error);
            if (galleryContainer) {
                galleryContainer.innerHTML = `<p>Error loading class gallery: ${error.message}</p>`;
            }
        }
    }

    // --- Merge Tool Functions ---
    function displayMergeCandidates(candidates, targetContainer, canonicalRadioName, onCanonicalSelectCallback) {
        if (!targetContainer) { console.error("Target container for merge candidates is null"); return; }
        targetContainer.innerHTML = ''; 
        const canonicalRadioContainer = (canonicalRadioName === 'manual_canonical_id') ? manualMergeCanonicalSelectionContainer : canonicalSelectionContainerOld;
        if(canonicalRadioContainer) canonicalRadioContainer.innerHTML = ''; 
        
        currentMergeCandidates = candidates; 
        selectedCanonicalId = null; 
        
        const executeBtn = (canonicalRadioName === 'manual_canonical_id') ? executeManualMergeBtn : confirmMergeBtnSuggestion;
        if(executeBtn) executeBtn.disabled = true;

        if (!candidates || candidates.length < 2) {
            if (canonicalRadioName === 'manual_canonical_id' && manualMergeSelectionArea) manualMergeSelectionArea.style.display = 'none';
            else if (mergePreviewAreaOld) mergePreviewAreaOld.style.display = 'none';
            return;
        }

        candidates.forEach(candidate => {
            const card = createPersonCard(candidate, false); 
            card.classList.remove('person-card');
            card.classList.add('candidate-card');
            targetContainer.appendChild(card);

            if (canonicalRadioContainer) {
                const radioLabel = document.createElement('label');
                const radioInput = document.createElement('input');
                radioInput.type = 'radio';
                radioInput.name = canonicalRadioName;
                radioInput.value = candidate.person_id;
                radioInput.addEventListener('change', (e) => {
                    selectedCanonicalId = e.target.value;
                    if(executeBtn) executeBtn.disabled = false;
                    if(onCanonicalSelectCallback) onCanonicalSelectCallback();
                });
                radioLabel.appendChild(radioInput);
                radioLabel.appendChild(document.createTextNode(` Keep: ${candidate.name || candidate.person_id.slice(-12)}`));
                canonicalRadioContainer.appendChild(radioLabel);
            }
        });
        if (canonicalRadioName === 'manual_canonical_id' && manualMergeSelectionArea) manualMergeSelectionArea.style.display = 'block';
        else if (mergePreviewAreaOld) mergePreviewAreaOld.style.display = 'block';
    }
    
    function processNextSuggestion() { 
        if (currentSuggestionQueue.length > 0) {
            const nextSuggestion = currentSuggestionQueue.shift();
            displayMergeCandidates(nextSuggestion.group_members, candidateCardsContainerOld, 'suggested_canonical_id', () => {
                if(confirmMergeBtnSuggestion) confirmMergeBtnSuggestion.disabled = (selectedCanonicalId === null);
            });
        } else {
            alert("No more merge suggestions.");
            if(mergePreviewAreaOld) mergePreviewAreaOld.style.display = 'none';
            const mergeToolSection = document.getElementById('merge-tool-section');
            if(mergeToolSection) mergeToolSection.style.display = 'none';
        }
    }

    async function fetchMergeSuggestions() { 
        if(uploadStatusDiv) uploadStatusDiv.textContent = 'Fetching merge suggestions...';
        try {
            const response = await fetch(`${API_BASE_URL}/suggestions`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            currentSuggestionQueue = await response.json(); 
            console.log("Suggestions loaded:", currentSuggestionQueue);
            const mergeToolSection = document.getElementById('merge-tool-section');
            if (currentSuggestionQueue.length > 0) {
                if(mergeToolSection) mergeToolSection.style.display = 'block'; 
                processNextSuggestion();
                if(uploadStatusDiv) uploadStatusDiv.textContent = `Found ${currentSuggestionQueue.length} suggestion(s).`;
            } else {
                alert("No merge suggestions found at this time.");
                if(mergePreviewAreaOld) mergePreviewAreaOld.style.display = 'none';
                if(mergeToolSection) mergeToolSection.style.display = 'none';
                if(uploadStatusDiv) uploadStatusDiv.textContent = 'No merge suggestions found.';
            }
        } catch (error) {
            console.error("Error fetching suggestions:", error);
            if(candidateCardsContainerOld) candidateCardsContainerOld.innerHTML = `<p>Error loading suggestions: ${error.message}</p>`;
            if(mergePreviewAreaOld) mergePreviewAreaOld.style.display = 'block';
            if(uploadStatusDiv) uploadStatusDiv.textContent = 'Error fetching suggestions.';
        }
    }

    async function performMerge(idsToMerge, canonicalIdToKeep) { 
        if (!canonicalIdToKeep || !idsToMerge || idsToMerge.length < 2) {
            alert("Internal error: Not enough information for merge.");
            return false;
        }
        if (!idsToMerge.includes(canonicalIdToKeep)) {
            alert("Internal error: Canonical ID must be one of the selected candidates for merge.");
            return false;
        }
        const payload = { ids_to_merge: idsToMerge, canonical_id: canonicalIdToKeep };
        if(uploadStatusDiv) uploadStatusDiv.textContent = `Merging IDs into ${canonicalIdToKeep}...`;
        try {
            const response = await fetch(`${API_BASE_URL}/merge`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.message || result.error || `HTTP error! status: ${response.status}`);
            alert(`Merge successful: ${result.message}`);
            if(uploadStatusDiv) uploadStatusDiv.textContent = `Merge successful: ${result.message}`;
            fetchAllPersons(); 
            return true; 
        } catch (error) {
            console.error("Error performing merge:", error);
            alert(`Merge failed: ${error.message}`);
            if(uploadStatusDiv) uploadStatusDiv.textContent = `Merge failed: ${error.message}`;
            return false; 
        }
    }

    // --- Event Listeners ---
    if (uploadForm) uploadForm.addEventListener('submit', handleImageUpload);
    if (loadPersonsBtn) loadPersonsBtn.addEventListener('click', fetchAllPersons);
    if (loadClassImagesBtn) loadClassImagesBtn.addEventListener('click', fetchClassImages);
    
    // Attendance section event listeners
    if (applyFiltersBtn) {
        applyFiltersBtn.addEventListener('click', fetchAttendanceHistory);
    }
    
    // Tab navigation event listeners
    document.querySelectorAll('header nav ul li a').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = e.target.getAttribute('href').substring(1);
            logToServer(`Tab navigation: clicked on ${e.target.textContent} (target: #${targetId})`);
            
            // Remove active class from all links
            document.querySelectorAll('header nav ul li a').forEach(navLink => {
                navLink.classList.remove('active');
            });
            
            // Add active class to clicked link
            e.target.classList.add('active');
            
            // Hide all sections
            document.querySelectorAll('main section').forEach(section => {
                section.classList.add('hidden-section');
                section.classList.remove('active-section');
                logToServer(`Tab navigation: hiding section #${section.id}`);
            });
            
            // Show target section
            const targetSection = document.getElementById(targetId);
            if (targetSection) {
                targetSection.classList.remove('hidden-section');
                targetSection.classList.add('active-section');
                logToServer(`Tab navigation: showing section #${targetId}`);
                
                // Load data for the section if needed
                if (targetId === 'attendance-section') {
                    logToServer('Tab navigation: loading attendance data');
                    fetchAttendanceHistory();
                } else if (targetId === 'gallery-section') {
                    logToServer('Tab navigation: loading gallery data');
                    fetchClassGallery();
                }
            } else {
                logToServer(`Tab navigation ERROR: target section #${targetId} not found`, 'error');
            }
        });
    });
    
    // Gallery section event listeners
    if (applyGalleryFiltersBtn) {
        applyGalleryFiltersBtn.addEventListener('click', fetchClassGallery);
    }
    
    // Image modal close button
    const modalCloseBtn = document.querySelector('#imageDetailsModal .close');
    if (modalCloseBtn) {
        modalCloseBtn.addEventListener('click', () => {
            imageDetailsModal.style.display = 'none';
        });
    }
    
    // Close modal when clicking outside of it
    window.addEventListener('click', (e) => {
        if (e.target === imageDetailsModal) {
            imageDetailsModal.style.display = 'none';
        }
    });
    
    if (backToDashboardBtn) backToDashboardBtn.addEventListener('click', () => {
        currentViewingImageId = null; // Clear the current image ID when going back
        showMainDashboard();
    });
    if (backToDashboardFromStudentBtn) backToDashboardFromStudentBtn.addEventListener('click', showMainDashboard);

    // Add event listener for delete button in image detail view
    const deleteCurrentImageBtn = document.getElementById('delete-current-image-btn');
    if (deleteCurrentImageBtn) deleteCurrentImageBtn.addEventListener('click', handleDeleteClassImage);

    // Manual Merge Listeners
    if (startManualMergeBtn) startManualMergeBtn.addEventListener('click', () => toggleManualMergeMode(true));
    if (cancelManualMergeBtn) cancelManualMergeBtn.addEventListener('click', () => {
        toggleManualMergeMode(false);
        if(manualMergeSelectionArea) manualMergeSelectionArea.style.display = 'none';
    });
    if (confirmManualMergeBtn) confirmManualMergeBtn.addEventListener('click', populateManualMergeSelectionArea);
    
    if (executeManualMergeBtn) {
        executeManualMergeBtn.addEventListener('click', async () => {
            if (!selectedCanonicalId || manuallySelectedPersonsForMerge.size < 2) {
                alert("Please select at least two students and a canonical ID to keep.");
                return;
            }
            const idsToMergeArray = Array.from(manuallySelectedPersonsForMerge);
            const success = await performMerge(idsToMergeArray, selectedCanonicalId);
            if (success) {
                toggleManualMergeMode(false); 
                if(manualMergeSelectionArea) manualMergeSelectionArea.style.display = 'none';
            }
        });
    }

    // Suggestion-based Merge Tool Listeners
    if (suggestMergesBtnOld) suggestMergesBtnOld.addEventListener('click', fetchMergeSuggestions);
    
    if (confirmMergeBtnSuggestion) { 
        confirmMergeBtnSuggestion.addEventListener('click', async () => {
            if (!selectedCanonicalId || !currentMergeCandidates || currentMergeCandidates.length < 2) {
                alert("Please select a canonical ID from the suggested group.");
                return;
            }
            const idsToMergeFromSuggestion = currentMergeCandidates.map(p => p.person_id);
            const success = await performMerge(idsToMergeFromSuggestion, selectedCanonicalId);
            if (success) {
                if (currentSuggestionQueue.length > 0) { 
                    processNextSuggestion();
                } else {
                    if(mergePreviewAreaOld) mergePreviewAreaOld.style.display = 'none';
                    const mergeToolSection = document.getElementById('merge-tool-section');
                    if(mergeToolSection) mergeToolSection.style.display = 'none';
                }
            }
        });
    }
    if (skipSuggestionBtnOld) {
        skipSuggestionBtnOld.addEventListener('click', () => {
            console.log("Skipping current merge suggestion.");
            processNextSuggestion(); 
        });
    }
    if (cancelMergeBtnSuggestion) { 
        cancelMergeBtnSuggestion.addEventListener('click', () => {
            if(candidateCardsContainerOld) candidateCardsContainerOld.innerHTML = '';
            if(canonicalSelectionContainerOld) canonicalSelectionContainerOld.innerHTML = '';
            if(mergePreviewAreaOld) mergePreviewAreaOld.style.display = 'none';
            const mergeToolSection = document.getElementById('merge-tool-section');
            if(mergeToolSection) mergeToolSection.style.display = 'none'; 
            console.log("Suggestion merge selection cleared.");
        });
    }
    
    // Initialize view - check if we should show a specific tab based on URL hash
    const hashFromUrl = window.location.hash;
    if (hashFromUrl) {
        const targetTabLink = document.querySelector(`header nav ul li a[href="${hashFromUrl}"]`);
        if (targetTabLink) {
            logToServer(`Initializing with tab from URL hash: ${hashFromUrl}`);
            targetTabLink.click();
        } else {
            logToServer(`Hash ${hashFromUrl} in URL but no matching tab found`, 'warn');
            showMainDashboard();
        }
    } else {
        // Default initialization
        showMainDashboard();
        
        // Load attendance history data for the default tab
        const defaultActiveTab = document.querySelector('header nav ul li a.active');
        if (defaultActiveTab) {
            const defaultTabTarget = defaultActiveTab.getAttribute('href');
            logToServer(`Default active tab: ${defaultActiveTab.textContent} (${defaultTabTarget})`);
            if (defaultTabTarget === '#attendance-section') {
                fetchAttendanceHistory();
            } else if (defaultTabTarget === '#gallery-section') {
                fetchClassGallery();
            }
        } else {
            logToServer('No default active tab found', 'warn');
        }
    }
    
    // Always load these regardless of the active tab
    fetchAllPersons(); // Load persons on page load
    fetchClassImages(); // Load class images on page load

    // At the beginning of document.addEventListener('DOMContentLoaded', () => {...}) function, after variable declarations
    function enhanceGalleryImages() {
        console.log("=== GALLERY DEBUG: enhanceGalleryImages called ===");
        
        // Find all gallery images
        const galleryItems = document.querySelectorAll('.gallery-item img.gallery-image');
        console.log(`Found ${galleryItems.length} gallery images to enhance`);
        
        if (galleryItems.length === 0) {
            console.log("No gallery images found to enhance");
            return;
        }
        
        galleryItems.forEach((img, index) => {
            // Get the original src
            const originalSrc = img.getAttribute('src');
            console.log(`Processing image #${index}: ${originalSrc}`);
            
            // Check if the image is already a placeholder
            if (originalSrc.includes('placeholder.jpg')) {
                console.log(`Image #${index} is already showing a placeholder`);
                
                // Try to find Instagram shortcode from class image ID
                const galleryItem = img.closest('.gallery-item');
                if (galleryItem) {
                    const imageId = galleryItem.getAttribute('data-image-id');
                    if (imageId) {
                        console.log(`Found image ID: ${imageId}, will try to fetch Instagram image`);
                        
                        // First, try to get the class image details to find the shortcode
                        fetch(`/api/class-images/${imageId}`)
                            .then(response => {
                                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                                return response.json();
                            })
                            .then(data => {
                                if (data.success && data.image && data.image.instagram_shortcode) {
                                    const shortcode = data.image.instagram_shortcode;
                                    console.log(`Found Instagram shortcode from API: ${shortcode}`);
                                    
                                    // Try method 1: Instagram incoming folder path
                                    const incomingPath = `/pictures/incoming/instagram_${shortcode}.jpg`;
                                    console.log(`Trying Instagram incoming path: ${incomingPath}`);
                                    
                                    // Create a temporary image to test if this path works
                                    const testImg = new Image();
                                    testImg.onload = function() {
                                        console.log(`Instagram incoming path worked for ${shortcode}`);
                                        img.src = incomingPath;
                                    };
                                    testImg.onerror = function() {
                                        console.log(`Instagram incoming path failed for ${shortcode}, trying data URL method`);
                                        
                                        // Try method 3: Data URL method as fallback
                                        fetch(`/api/images/data-url?shortcode=${shortcode}`)
                                            .then(response => {
                                                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                                                return response.json();
                                            })
                                            .then(data => {
                                                if (data.success && data.data_url) {
                                                    console.log(`Successfully loaded data URL for ${shortcode}`);
                                                    img.src = data.data_url;
                                                } else {
                                                    throw new Error(data.error || 'Failed to get data URL');
                                                }
                                            })
                                            .catch(error => {
                                                console.error(`All methods failed for ${shortcode}: ${error.message}`);
                                                // Keep the placeholder as is
                                            });
                                    };
                                    testImg.src = incomingPath;
                                } else if (data.success && data.image && data.image.filepath_processed) {
                                    // Not an Instagram image, but we have a filepath
                                    const filepath = data.image.filepath_processed;
                                    console.log(`Found filepath from API: ${filepath}`);
                                    
                                    // Use data URL method for this file
                                    const encodedPath = encodeURIComponent(filepath);
                                    fetch(`/api/images/data-url?path=${encodedPath}`)
                                        .then(response => {
                                            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                                            return response.json();
                                        })
                                        .then(data => {
                                            if (data.success && data.data_url) {
                                                console.log(`Successfully loaded data URL for filepath`);
                                                img.src = data.data_url;
                                            } else {
                                                throw new Error(data.error || 'Failed to get data URL');
                                            }
                                        })
                                        .catch(error => {
                                            console.error(`Failed to load image via data URL: ${error.message}`);
                                            // Keep the placeholder as is
                                        });
                                }
                            })
                            .catch(error => {
                                console.error(`Error fetching class image details: ${error.message}`);
                                // Keep the placeholder as is
                            });
                    }
                }
                return;
            }
            
            // Extract filename from path
            const pathParts = originalSrc.split('/');
            const filename = pathParts[pathParts.length - 1];
            
            // Check if this is an Instagram image from filename pattern
            if (filename.startsWith('instagram_')) {
                console.log(`Image #${index} appears to be Instagram image: ${filename}`);
                
                // Extract shortcode from filename
                const shortcodeMatch = filename.match(/instagram_([A-Za-z0-9_-]+)\.jpg/);
                if (shortcodeMatch && shortcodeMatch[1]) {
                    const shortcode = shortcodeMatch[1];
                    console.log(`Found Instagram shortcode: ${shortcode}`);
                    
                    // Use method 3: Data URL method (most reliable)
                    fetch(`/api/images/data-url?shortcode=${shortcode}`)
                        .then(response => {
                            console.log(`Data URL API response status for ${shortcode}: ${response.status}`);
                            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                            return response.json();
                        })
                        .then(data => {
                            console.log(`Data URL API response for ${shortcode}:`, data);
                            if (data.success && data.data_url) {
                                console.log(`Successfully loaded data URL for ${shortcode}`);
                                img.src = data.data_url;
                            } else {
                                throw new Error(data.error || 'Failed to get data URL');
                            }
                        })
                        .catch(error => {
                            console.error(`Error loading image via data URL: ${error.message}`);
                            // Try method 1 as fallback
                            const incomingPath = `/pictures/incoming/instagram_${shortcode}.jpg`;
                            console.log(`Trying Instagram incoming path as fallback: ${incomingPath}`);
                            img.src = incomingPath;
                        });
                }
            } else if (originalSrc.includes('/pictures/processed/')) {
                // This might be a non-Instagram image, or it might be misidentified
                console.log(`Image #${index} appears to be a processed local image`);
                
                // Check if it matches the Instagram filename pattern in a different way
                const instagramMatch = filename.match(/501933063_([0-9]+)_([0-9]+)_n\.jpg/);
                if (instagramMatch) {
                    console.log(`Image #${index} appears to be Instagram image with filename pattern: ${filename}`);
                    
                    // For these, we'll use the direct path but from the incoming folder
                    const incomingPath = `/pictures/incoming/${filename}`;
                    console.log(`Trying Instagram incoming path: ${incomingPath}`);
                    
                    // Create a temporary image to test if this path works
                    const testImg = new Image();
                    testImg.onload = function() {
                        console.log(`Instagram incoming path worked for ${filename}`);
                        img.src = incomingPath;
                    };
                    testImg.onerror = function() {
                        console.log(`Instagram incoming path failed for ${filename}, trying data URL method`);
                        
                        // Try direct-serve API as fallback
                        const fullPath = `${UPLOAD_FOLDER}/${filename}`;
                        const encodedPath = encodeURIComponent(fullPath);
                        
                        fetch(`/api/images/direct-serve?path=${encodedPath}`)
                            .then(response => {
                                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                                return response.blob();
                            })
                            .then(blob => {
                                const objectUrl = URL.createObjectURL(blob);
                                img.src = objectUrl;
                                console.log(`Loaded image via direct-serve API`);
                            })
                            .catch(error => {
                                console.error(`All methods failed for ${filename}: ${error.message}`);
                                // Keep using the current path
                            });
                    };
                    testImg.src = incomingPath;
                } else {
                    // This is a regular processed image, use data URL method
                    const fullPath = `${PROCESSED_FOLDER}/${filename}`;
                    const encodedPath = encodeURIComponent(fullPath);
                    
                    console.log(`Enhancing processed image: ${filename}`);
                    console.log(`Full path: ${fullPath}`);
                    
                    // Use data URL method
                    fetch(`/api/images/data-url?path=${encodedPath}`)
                        .then(response => {
                            console.log(`Data URL API response status for ${filename}: ${response.status}`);
                            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                            return response.json();
                        })
                        .then(data => {
                            if (data.success && data.data_url) {
                                console.log(`Successfully loaded data URL for ${filename}`);
                                img.src = data.data_url;
                            } else {
                                throw new Error(data.error || 'Failed to get data URL');
                            }
                        })
                        .catch(error => {
                            console.error(`Error loading image via data URL: ${error}`);
                            // Keep using the current path
                        });
                }
            } else {
                console.log(`Image #${index} doesn't match any known pattern: ${originalSrc}`);
            }
        });
    }
    
    // Expose enhanceGalleryImages function globally for the template to call
    window.enhanceGalleryImages = enhanceGalleryImages;
    
    // Set up a MutationObserver to detect when new gallery items are added
    if (galleryContainer) {
        const observer = new MutationObserver(function(mutations) {
            let shouldEnhance = false;
            
            mutations.forEach(function(mutation) {
                if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                    // Check if any of the added nodes are gallery items with images
                    mutation.addedNodes.forEach(function(node) {
                        if (node.nodeType === 1 && (
                            node.classList.contains('gallery-item') || 
                            node.querySelector('.gallery-item')
                        )) {
                            shouldEnhance = true;
                        }
                    });
                }
            });
            
            if (shouldEnhance) {
                console.log("Detected new gallery items added to DOM, enhancing images");
                // Wait a short time for images to be fully added
                setTimeout(enhanceGalleryImages, 300);
            }
        });
        
        // Configure and start the observer
        observer.observe(galleryContainer, { 
            childList: true,
            subtree: true
        });
        
        console.log("Gallery mutation observer set up");
    }
    
    // Handle gallery tab click
    document.querySelectorAll('header nav ul li a').forEach(link => {
        link.addEventListener('click', (e) => {
            const targetId = e.target.getAttribute('href');
            if (targetId === '#gallery-section') {
                console.log("Gallery tab clicked, will enhance images after display");
                // Wait for gallery to be shown before enhancing images
                setTimeout(enhanceGalleryImages, 500);
            }
        });
    });
    
    // Enhance modal image display using data URL method
    function enhanceModalImage(modalImage) {
        if (!modalImage) return;
        
        const originalSrc = modalImage.getAttribute('src');
        if (!originalSrc) return;
        
        console.log(`Enhancing modal image: ${originalSrc}`);
        
        // Check if this is an Instagram image from filename pattern
        if (originalSrc.includes('instagram_')) {
            const pathParts = originalSrc.split('/');
            const filename = pathParts[pathParts.length - 1];
            const shortcodeMatch = filename.match(/instagram_([A-Za-z0-9_-]+)\.jpg/);
            
            if (shortcodeMatch && shortcodeMatch[1]) {
                const shortcode = shortcodeMatch[1];
                console.log(`Found Instagram shortcode in modal: ${shortcode}`);
                
                // Use data URL method for Instagram images
                fetch(`/api/images/data-url?shortcode=${shortcode}`)
                    .then(response => {
                        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                        return response.json();
                    })
                    .then(data => {
                        if (data.success && data.data_url) {
                            console.log(`Successfully loaded data URL for modal Instagram image`);
                            modalImage.src = data.data_url;
                        } else {
                            throw new Error(data.error || 'Failed to get data URL');
                        }
                    })
                    .catch(error => {
                        console.error(`Error loading modal image via data URL: ${error.message}`);
                        // Keep the original src
                    });
            }
        } else if (originalSrc.includes('/pictures/processed/') || originalSrc.includes('/pictures/incoming/')) {
            // This is a processed or incoming picture, extract the path
            const pathParts = originalSrc.includes('/pictures/processed/') 
                ? originalSrc.split('/pictures/processed/')
                : originalSrc.split('/pictures/incoming/');
                
            if (pathParts.length > 1 && pathParts[1]) {
                const filename = pathParts[1];
                const folder = originalSrc.includes('/pictures/processed/') ? PROCESSED_FOLDER : UPLOAD_FOLDER;
                const fullPath = `${folder}/${filename}`;
                const encodedPath = encodeURIComponent(fullPath);
                
                console.log(`Enhancing modal image with path: ${fullPath}`);
                
                // Use data URL method
                fetch(`/api/images/data-url?path=${encodedPath}`)
                    .then(response => {
                        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                        return response.json();
                    })
                    .then(data => {
                        if (data.success && data.data_url) {
                            console.log(`Successfully loaded data URL for modal image`);
                            modalImage.src = data.data_url;
                        } else {
                            throw new Error(data.error || 'Failed to get data URL');
                        }
                    })
                    .catch(error => {
                        console.error(`Error loading modal image via data URL: ${error.message}`);
                        // Keep the original src
                    });
            }
        }
    }
    
    // Export enhanceModalImage to global scope
    window.enhanceModalImage = enhanceModalImage;
    
    // If gallery section is already active on page load, enhance images
    if (document.querySelector('#gallery-section:not(.hidden-section)')) {
        console.log("Gallery section is active on page load, enhancing images");
        setTimeout(enhanceGalleryImages, 500);
    }
});