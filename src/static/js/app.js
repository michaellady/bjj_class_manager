document.addEventListener('DOMContentLoaded', () => {
    console.log("BJJ Attendance Tracker JS Loaded");

    const API_BASE_URL = 'http://127.0.0.1:5001/api'; 

    // DOM Elements - New Dashboard
    const uploadForm = document.getElementById('upload-form');
    const imageFilesInput = document.getElementById('image-files-input');
    const imageUrlInput = document.getElementById('image-url-input'); 
    const uploadStatusDiv = document.getElementById('upload-status');
    
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
        if(mainClassImage) mainClassImage.src = ''; 
        if(detectionsGrid) detectionsGrid.innerHTML = '<p>Loading detections...</p>';
        try {
            const response = await fetch(`${API_BASE_URL}/images/${imageId}/detections`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            
            if(mainClassImage && data.image_info) {
                const mainImgFilename = data.image_info.filepath_processed ? 
                                   data.image_info.filepath_processed.split('/').pop() : 
                                   data.image_info.original_filename;
                mainClassImage.src = `/static/incoming_pictures/${mainImgFilename}`; 
                mainClassImage.onerror = () => { mainClassImage.src = 'https://via.placeholder.com/600x400?text=Main+Image+Not+Found';};
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
    
    // Initialize view
    showMainDashboard(); 
    fetchAllPersons(); // Load persons on page load
    fetchClassImages(); // Load class images on page load
});