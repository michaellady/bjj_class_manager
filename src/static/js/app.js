// IIFE to fix syntax errors
(function() {
  // Wait for DOM to be fully loaded
  document.addEventListener("DOMContentLoaded", function() {
    console.log("BJJ Attendance Tracker JS Loaded");
    
    // API and folder configuration
    const API_BASE_URL = '/api';
    const UPLOAD_FOLDER = '/Users/mikelady/dev/class_pictures/pictures/incoming';
    const PROCESSED_FOLDER = '/Users/mikelady/dev/class_pictures/pictures/processed';
    
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
    
    // --- DOM ELEMENTS ---
    
    // Upload Form Elements
    const uploadForm = document.getElementById('uploadForm');
    const imageUrlInput = document.getElementById('imageUrl');
    const classDateInput = document.getElementById('classDate');
    const uploadStatusDiv = document.getElementById('status');
    
    // Attendance Section Elements
    const dateRangeSelect = document.getElementById('dateRange');
    const studentFilterSelect = document.getElementById('studentFilter');
    const applyFiltersBtn = document.getElementById('applyFilters');
    const totalClassesElement = document.getElementById('totalClasses');
    const totalStudentsElement = document.getElementById('totalStudents');
    const avgAttendanceElement = document.getElementById('avgAttendance');
    const leaderboardBody = document.getElementById('leaderboardBody');
    const attendanceTableBody = document.getElementById('attendanceTableBody');
    
    // Class Gallery Elements
    const galleryDateRangeSelect = document.getElementById('galleryDateRange');
    const applyGalleryFiltersBtn = document.getElementById('applyGalleryFilters');
    const galleryContainer = document.getElementById('galleryContainer');
    const galleryPagination = document.getElementById('galleryPagination');
    
    // Students Section Elements
    const studentsContainer = document.getElementById('studentsContainer');
    const studentsPagination = document.getElementById('studentsPagination');
    const studentDetailView = document.getElementById('studentDetailView');
    const studentDetailImage = document.getElementById('studentDetailImage');
    const studentDetailName = document.getElementById('studentDetailName');
    const studentDetailClasses = document.getElementById('studentDetailClasses');
    const studentAttendanceHistory = document.getElementById('studentAttendanceHistory');
    const backToStudentsBtn = document.getElementById('backToStudentsBtn');
    const editStudentNameBtn = document.getElementById('editStudentNameBtn');
    const reassignStudentBtn = document.getElementById('reassignStudentBtn');
    
    // Reassignment Modal Elements
    const reassignmentModal = document.getElementById('reassignmentModal');
    const currentStudentImage = document.getElementById('currentStudentImage');
    const currentStudentName = document.getElementById('currentStudentName');
    const targetStudentSelect = document.getElementById('targetStudentSelect');
    const confirmReassignBtn = document.getElementById('confirmReassignBtn');
    
    // --- TAB FUNCTIONALITY ---
    
    // Tab Navigation Helper
    function showTabById(targetId) {
      console.log("Showing tab:", targetId);
      
      // Hide all sections
      document.querySelectorAll('main section').forEach(section => {
        section.classList.remove('active-section');
        section.classList.add('hidden-section');
      });
      
      // Show target section
      const targetSection = document.getElementById(targetId);
      if (targetSection) {
        targetSection.classList.add('active-section');
        targetSection.classList.remove('hidden-section');
        
        // Load appropriate data based on the tab
        if (targetId === 'attendance-section') {
          fetchAttendanceHistory();
        } else if (targetId === 'gallery-section') {
          fetchClassGallery();
        } else if (targetId === 'students-section') {
          fetchAllStudents();
        }
      }
      
      // Update active nav links
      document.querySelectorAll('header nav ul li a').forEach(navLink => {
        navLink.classList.remove('active');
        if (navLink.getAttribute('href') === `#${targetId}`) {
          navLink.classList.add('active');
        }
      });
      
      // Update URL hash
      window.location.hash = '#' + targetId;
    }
    
    // Set up tab navigation
    document.querySelectorAll('header nav ul li a').forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const targetId = e.target.getAttribute('href').substring(1);
        showTabById(targetId);
      });
    });
    
    // --- UPLOAD FUNCTIONALITY ---
    
    // Handle image upload
    async function handleImageUpload(event) {
      event.preventDefault();
      console.log("Form submission detected");
      logToServer("Form submission detected");
      
      // Get form values
      const imageUrl = imageUrlInput ? imageUrlInput.value.trim() : '';
      const classDate = classDateInput ? classDateInput.value.trim() : '';
      
      if (!imageUrl) {
        if (uploadStatusDiv) uploadStatusDiv.textContent = 'Please enter an Instagram URL.';
        return;
      }
      
      if (uploadStatusDiv) uploadStatusDiv.textContent = 'Uploading and processing...';
      
      try {
        // Prepare form data
        const formData = new FormData();
        formData.append('image_url', imageUrl);
        if (classDate) {
          formData.append('date', classDate);
        }
        
        // Make API request
        const response = await fetch(`${API_BASE_URL}/images/upload`, {
          method: 'POST',
          body: formData,
        });
        
        const result = await response.json();
        
        if (!response.ok) {
          throw new Error(result.error || `HTTP error! status: ${response.status}`);
        }
        
        // Update UI with success
        if (uploadStatusDiv) {
          uploadStatusDiv.textContent = `Success! Processed image with ID: ${result.image_id}`;
        }
        
        // Clear form inputs
        if (imageUrlInput) imageUrlInput.value = '';
        if (classDateInput) classDateInput.value = '';
        
        // Refresh class gallery
        fetchClassGallery();
        
      } catch (error) {
        console.error('Upload error:', error);
        logToServer(`Upload error: ${error.message}`, 'error');
        
        if (uploadStatusDiv) {
          uploadStatusDiv.textContent = `Upload failed: ${error.message}`;
        }
      }
    }
    
    // --- GALLERY FUNCTIONALITY ---
    
    // Fetch class gallery
    async function fetchClassGallery() {
      console.log("Fetching class gallery...");
      if (galleryContainer) galleryContainer.innerHTML = '<div class="loading-indicator">Loading class pictures...</div>';
      
      try {
        const days = galleryDateRangeSelect ? galleryDateRangeSelect.value : '30';
        const page = 1;
        const perPage = 12;
        
        const response = await fetch(`${API_BASE_URL}/class-images?days=${days}&page=${page}&per_page=${perPage}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        
        // Display gallery images
        if (galleryContainer) {
          galleryContainer.innerHTML = '';
          
          if (!data.images || data.images.length === 0) {
            galleryContainer.innerHTML = '<p>No class pictures found in the selected date range.</p>';
          } else {
            const galleryGrid = document.createElement('div');
            galleryGrid.classList.add('gallery-grid');
            
            data.images.forEach(image => {
              const galleryItem = document.createElement('div');
              galleryItem.classList.add('gallery-item');
              
              // Create image element with placeholder initially
              const img = document.createElement('img');
              img.src = 'data:image/svg+xml;charset=UTF-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22200%22%20height%3D%22200%22%20viewBox%3D%220%200%20200%20200%22%20preserveAspectRatio%3D%22none%22%3E%3Cpath%20fill%3D%22%23CCCCCC%22%20d%3D%22M0%200h200v200H0z%22%2F%3E%3Ctext%20fill%3D%22%23333333%22%20font-family%3D%22Arial%2CHelvetica%2Csans-serif%22%20font-size%3D%2220%22%20dy%3D%22.3em%22%20x%3D%22100%22%20y%3D%22100%22%20text-anchor%3D%22middle%22%3ELoading...%3C%2Ftext%3E%3C%2Fsvg%3E';
              img.alt = 'Class image';
              img.classList.add('gallery-image');
              img.dataset.imageId = image.class_image_id;
              
              // Load actual image
              fetch(`${API_BASE_URL}/images/data-url?id=${image.class_image_id}`)
                .then(response => {
                  if (!response.ok) {
                    // Create a friendly error message on the image
                    const errorOverlay = document.createElement('div');
                    errorOverlay.classList.add('image-error-overlay');
                    errorOverlay.textContent = 'Image not available';
                    galleryItem.appendChild(errorOverlay);
                    throw new Error("Failed to load image");
                  }
                  return response.json();
                })
                .then(data => {
                  if (data.success && data.data_url) {
                    img.src = data.data_url;
                  }
                })
                .catch(error => {
                  console.error(`Error loading image ${image.class_image_id}:`, error);
                  // Add error class to show visual indication
                  img.classList.add('image-load-error');
                  
                  // Show class date more prominently when image fails to load
                  const dateDiv = galleryItem.querySelector('.gallery-date');
                  if (dateDiv) {
                    dateDiv.classList.add('date-prominent');
                  }
                });
              
              // Date display
              const dateDiv = document.createElement('div');
              dateDiv.classList.add('gallery-date');
              dateDiv.textContent = new Date(image.date_taken).toLocaleDateString();
              
              // View button
              const viewBtn = document.createElement('button');
              viewBtn.classList.add('view-details-btn');
              viewBtn.textContent = 'View Details';
              viewBtn.dataset.imageId = image.class_image_id;
              viewBtn.addEventListener('click', () => {
                // Show image details
                showClassImageDetails(image.class_image_id);
              });
              
              galleryItem.appendChild(img);
              galleryItem.appendChild(dateDiv);
              galleryItem.appendChild(viewBtn);
              galleryGrid.appendChild(galleryItem);
            });
            
            galleryContainer.appendChild(galleryGrid);
          }
          
          // Set up pagination if needed
          if (galleryPagination && data.pagination && data.pagination.total_pages > 1) {
            galleryPagination.innerHTML = '';
            
            for (let i = 1; i <= data.pagination.total_pages; i++) {
              const pageLink = document.createElement('a');
              pageLink.href = '#';
              pageLink.textContent = i;
              if (i === data.pagination.page) {
                pageLink.classList.add('active');
              }
              
              pageLink.addEventListener('click', (e) => {
                e.preventDefault();
                loadGalleryPage(i, days, perPage);
              });
              
              galleryPagination.appendChild(pageLink);
            }
          }
        }
      } catch (error) {
        console.error("Error fetching class gallery:", error);
        if (galleryContainer) {
          galleryContainer.innerHTML = `<p>Error loading class gallery: ${error.message}</p>`;
        }
      }
    }
    
    // Load a specific page of the gallery
    async function loadGalleryPage(page, days, perPage) {
      console.log(`Loading gallery page ${page}`);
      if (galleryContainer) galleryContainer.innerHTML = '<div class="loading-indicator">Loading class pictures...</div>';
      
      try {
        const response = await fetch(`${API_BASE_URL}/class-images?days=${days}&page=${page}&per_page=${perPage}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        
        // Update the gallery display
        fetchClassGallery();
        
        // Update active pagination link
        if (galleryPagination) {
          const links = galleryPagination.querySelectorAll('a');
          links.forEach(link => {
            link.classList.remove('active');
            if (parseInt(link.textContent) === page) {
              link.classList.add('active');
            }
          });
        }
      } catch (error) {
        console.error(`Error loading gallery page ${page}:`, error);
        if (galleryContainer) {
          galleryContainer.innerHTML = `<p>Error loading gallery page: ${error.message}</p>`;
        }
      }
    }
    
    // Show class image details
    function showClassImageDetails(imageId) {
      console.log(`Showing details for class image ID: ${imageId}`);
      
      // Create a modal dialog for showing image details
      const modal = document.createElement('div');
      modal.classList.add('modal');
      modal.style.display = 'block';
      
      // Create modal content
      modal.innerHTML = `
        <div class="modal-content">
          <span class="close">&times;</span>
          <h3>Class Image Details</h3>
          <div class="modal-body">
            <div class="image-container">
              <img src="data:image/svg+xml;charset=UTF-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22400%22%20height%3D%22300%22%20viewBox%3D%220%200%20400%20300%22%20preserveAspectRatio%3D%22none%22%3E%3Cpath%20fill%3D%22%23CCCCCC%22%20d%3D%22M0%200h400v300H0z%22%2F%3E%3Ctext%20fill%3D%22%23333333%22%20font-family%3D%22Arial%2CHelvetica%2Csans-serif%22%20font-size%3D%2220%22%20dy%3D%22.3em%22%20x%3D%22200%22%20y%3D%22150%22%20text-anchor%3D%22middle%22%3ELoading...%3C%2Ftext%3E%3C%2Fsvg%3E" alt="Class Image">
            </div>
            <div class="details-container">
              <div class="loading">Loading image details...</div>
              <div class="action-buttons" style="margin-top: 20px;">
                <button class="btn btn-danger" id="deleteImageBtn">Delete Class Picture</button>
              </div>
            </div>
          </div>
        </div>
      `;
      
      // Add to document
      document.body.appendChild(modal);
      
      // Setup close button
      const closeButton = modal.querySelector('.close');
      closeButton.addEventListener('click', () => {
        document.body.removeChild(modal);
      });
      
      // Close when clicking outside modal content
      modal.addEventListener('click', (e) => {
        if (e.target === modal) {
          document.body.removeChild(modal);
        }
      });
      
      // Load image
      const modalImage = modal.querySelector('.image-container img');
      const detailsContainer = modal.querySelector('.details-container');
      
      // Fetch image data
      fetch(`${API_BASE_URL}/images/data-url?id=${imageId}`)
        .then(response => {
          if (!response.ok) throw new Error("Failed to load image");
          return response.json();
        })
        .then(data => {
          if (data.success && data.data_url) {
            modalImage.src = data.data_url;
          }
        })
        .catch(error => {
          console.error(`Error loading image ${imageId}:`, error);
          modalImage.alt = "Error loading image";
        });
      
      // Fetch image details
      fetch(`${API_BASE_URL}/class-images/${imageId}`)
        .then(response => {
          if (!response.ok) throw new Error("Failed to load image details");
          return response.json();
        })
        .then(data => {
          // Update details section
          const image = data.image;
          
          detailsContainer.querySelector('.loading').remove();
          
          const detailsHTML = `
            <div class="image-details">
              <h4>Image Information</h4>
              <p><strong>Date:</strong> ${new Date(image.date_taken).toLocaleDateString()}</p>
              <p><strong>Attendees:</strong> ${data.total_attendees || 0} students</p>
              <p><strong>Techniques:</strong> ${data.techniques ? data.techniques.length : 0} recorded</p>
              ${image.instagram_post_url ? `<p><strong>Instagram:</strong> <a href="${image.instagram_post_url}" target="_blank">View Original Post</a></p>` : ''}
            </div>
          `;
          
          detailsContainer.insertAdjacentHTML('afterbegin', detailsHTML);
          
          // Setup delete button
          const deleteBtn = detailsContainer.querySelector('#deleteImageBtn');
          deleteBtn.addEventListener('click', () => {
            // Ask for confirmation with more detailed warning
            const confirmMessage = `Are you sure you want to delete this class picture from ${new Date(image.date_taken).toLocaleDateString()}?\n\nThis will permanently delete:\n- The class picture\n- All attendance records for this class\n- Any students who only appear in this class\n\nThis action cannot be undone.`;
            
            if (confirm(confirmMessage)) {
              deleteClassImage(image.class_image_id, modal);
            }
          });
        })
        .catch(error => {
          console.error(`Error loading image details for ${imageId}:`, error);
          detailsContainer.querySelector('.loading').innerHTML = `<div class="error">Error: ${error.message}</div>`;
        });
    }
    
    // Delete a class image
    async function deleteClassImage(imageId, modal) {
      console.log(`Deleting class image ID: ${imageId}`);
      
      try {
        const response = await fetch(`${API_BASE_URL}/class-images/${imageId}`, {
          method: 'DELETE'
        });
        
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || `Server error: ${response.status}`);
        }
        
        // Get the response data
        const result = await response.json();
        
        // Success - remove modal and refresh gallery
        document.body.removeChild(modal);
        
        // Show success message with deletion details
        let successMessage = 'Class picture successfully deleted.';
        
        // Add details about persons if any were deleted
        if (result.deleted_persons && result.deleted_persons > 0) {
          successMessage += ` Also removed ${result.deleted_persons} student${result.deleted_persons !== 1 ? 's' : ''} with no remaining attendance records.`;
        }
        
        alert(successMessage);
        
        // Refresh gallery
        fetchClassGallery();
        
      } catch (error) {
        console.error(`Error deleting class image ${imageId}:`, error);
        alert(`Failed to delete class picture: ${error.message}`);
      }
    }
    
    // --- STUDENTS FUNCTIONALITY ---
    
    // Fetch all students
    async function fetchAllStudents() {
      console.log("Fetching all students...");
      if (studentsContainer) studentsContainer.innerHTML = '<div class="loading-indicator">Loading students...</div>';
      
      try {
        const response = await fetch(`${API_BASE_URL}/persons`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        
        // Display students
        if (studentsContainer) {
          studentsContainer.innerHTML = '';
          
          if (!data.length && !data.persons) {
            studentsContainer.innerHTML = '<p>No students found.</p>';
            return;
          }
          
          const students = data.persons || data;
          
          // Update the section title with the total number of students
          const sectionTitle = document.querySelector('#students-section h2');
          if (sectionTitle) {
            sectionTitle.innerHTML = `<i class="fas fa-users"></i> Students (${students.length})`;
          }
          
          // Directly add student cards to the studentsContainer instead of creating a nested grid
          students.forEach(student => {
            const studentCard = document.createElement('div');
            studentCard.classList.add('student-card');
            studentCard.dataset.personId = student.person_id;
            
            // Simple image placeholder
            const img = document.createElement('img');
            img.src = 'data:image/svg+xml;charset=UTF-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22150%22%20height%3D%22150%22%20viewBox%3D%220%200%20150%20150%22%20preserveAspectRatio%3D%22none%22%3E%3Cpath%20fill%3D%22%23CCCCCC%22%20d%3D%22M0%200h150v150H0z%22%2F%3E%3Ctext%20fill%3D%22%23333333%22%20font-family%3D%22Arial%2CHelvetica%2Csans-serif%22%20font-size%3D%2214%22%20dy%3D%22.3em%22%20x%3D%2275%22%20y%3D%2275%22%20text-anchor%3D%22middle%22%3ELoading...%3C%2Ftext%3E%3C%2Fsvg%3E';
            img.alt = student.name || 'Unnamed Student';
            
            const nameDiv = document.createElement('div');
            nameDiv.classList.add('student-name');
            nameDiv.textContent = student.name || `Unnamed (${student.person_id.slice(-6)})`;
            
            const statsDiv = document.createElement('div');
            statsDiv.classList.add('student-stats');
            statsDiv.innerHTML = `
              <div>${student.attendance_count || 0} classes</div>
              <div>Last seen: ${student.last_attended ? new Date(student.last_attended).toLocaleDateString() : 'N/A'}</div>
            `;
            
            studentCard.appendChild(img);
            studentCard.appendChild(nameDiv);
            studentCard.appendChild(statsDiv);
            
            // Add click handler for student details
            studentCard.addEventListener('click', () => {
              showStudentDetail(student.person_id);
            });
            
            // Try to load student image
            if (student.representative_image_path) {
              // If there's a representative image path, use it
              const encodedPath = encodeURIComponent(student.representative_image_path);
              fetch(`${API_BASE_URL}/images/data-url?path=${encodedPath}`)
                .then(response => {
                  if (!response.ok) throw new Error("Failed to load image");
                  return response.json();
                })
                .then(data => {
                  if (data.success && data.data_url) {
                    img.src = data.data_url;
                  }
                })
                .catch(error => {
                  console.error(`Error loading image for student ${student.person_id}:`, error);
                  // Leave the placeholder image if there's an error
                });
            }
            // If no representative image path, try to get an image from the detail endpoint
            else {
              fetch(`${API_BASE_URL}/persons/${student.person_id}`)
                .then(response => {
                  if (!response.ok) throw new Error("Failed to load student details");
                  return response.json();
                })
                .then(data => {
                  if (data.success && data.person_info && data.person_info.representative_image_path) {
                    const encodedPath = encodeURIComponent(data.person_info.representative_image_path);
                    return fetch(`${API_BASE_URL}/images/data-url?path=${encodedPath}`);
                  }
                  throw new Error("No representative image available");
                })
                .then(response => {
                  if (!response.ok) throw new Error("Failed to load image");
                  return response.json();
                })
                .then(data => {
                  if (data.success && data.data_url) {
                    img.src = data.data_url;
                  }
                })
                .catch(error => {
                  console.error(`Error loading image for student ${student.person_id}:`, error);
                  // Just keep the placeholder image
                  img.src = 'data:image/svg+xml;charset=UTF-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22150%22%20height%3D%22150%22%20viewBox%3D%220%200%20150%20150%22%20preserveAspectRatio%3D%22none%22%3E%3Cpath%20fill%3D%22%23CCCCCC%22%20d%3D%22M0%200h150v150H0z%22%2F%3E%3Ctext%20fill%3D%22%23333333%22%20font-family%3D%22Arial%2CHelvetica%2Csans-serif%22%20font-size%3D%2214%22%20dy%3D%22.3em%22%20x%3D%2275%22%20y%3D%2275%22%20text-anchor%3D%22middle%22%3ENo%20Image%3C%2Ftext%3E%3C%2Fsvg%3E';
                });
            }
            
            studentsContainer.appendChild(studentCard);
          });
        }
      } catch (error) {
        console.error("Error fetching students:", error);
        if (studentsContainer) {
          studentsContainer.innerHTML = `<p>Error loading students: ${error.message}</p>`;
        }
      }
    }
    
    // Show student detail
    async function showStudentDetail(personId) {
      console.log(`Showing details for student ID: ${personId}`);
      
      // Store the current person ID globally for later use
      window.currentViewingPersonId = personId;
      
      // Hide students grid and show detail view
      if (studentsContainer) studentsContainer.parentElement.style.display = 'none';
      if (studentsPagination) studentsPagination.style.display = 'none';
      if (studentDetailView) studentDetailView.style.display = 'block';
      
      // Show loading state
      if (studentDetailName) studentDetailName.textContent = 'Loading...';
      if (studentDetailImage) studentDetailImage.src = 'data:image/svg+xml;charset=UTF-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22150%22%20height%3D%22150%22%20viewBox%3D%220%200%20150%20150%22%20preserveAspectRatio%3D%22none%22%3E%3Cpath%20fill%3D%22%23CCCCCC%22%20d%3D%22M0%200h150v150H0z%22%2F%3E%3Ctext%20fill%3D%22%23333333%22%20font-family%3D%22Arial%2CHelvetica%2Csans-serif%22%20font-size%3D%2214%22%20dy%3D%22.3em%22%20x%3D%2275%22%20y%3D%2275%22%20text-anchor%3D%22middle%22%3ELoading...%3C%2Ftext%3E%3C%2Fsvg%3E';
      if (studentDetailClasses) studentDetailClasses.textContent = '...';
      if (studentAttendanceHistory) studentAttendanceHistory.innerHTML = '<div class="loading-indicator">Loading attendance history...</div>';
      
      try {
        // Fetch student details
        const response = await fetch(`${API_BASE_URL}/persons/${personId}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        
        // Update student details
        if (studentDetailName) studentDetailName.textContent = data.person_info.name || 'Unknown Student';
        
        // Set up edit name button
        if (editStudentNameBtn) {
          editStudentNameBtn.onclick = () => {
            const currentName = data.person_info.name || '';
            const newName = prompt('Enter a new name for this student:', currentName);
            
            if (newName !== null && newName !== currentName) {
              updateStudentName(personId, newName);
            }
          };
        }
        
        // Try to load student image
        if (data.person_info && data.person_info.representative_image_path && studentDetailImage) {
          try {
            const encodedPath = encodeURIComponent(data.person_info.representative_image_path);
            const imageResponse = await fetch(`${API_BASE_URL}/images/data-url?path=${encodedPath}`);
            
            if (imageResponse.ok) {
              const imageData = await imageResponse.json();
              if (imageData.success && imageData.data_url) {
                studentDetailImage.src = imageData.data_url;
              } else {
                // Fallback to placeholder if no data URL
                studentDetailImage.src = 'data:image/svg+xml;charset=UTF-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22150%22%20height%3D%22150%22%20viewBox%3D%220%200%20150%20150%22%20preserveAspectRatio%3D%22none%22%3E%3Cpath%20fill%3D%22%23CCCCCC%22%20d%3D%22M0%200h150v150H0z%22%2F%3E%3Ctext%20fill%3D%22%23333333%22%20font-family%3D%22Arial%2CHelvetica%2Csans-serif%22%20font-size%3D%2214%22%20dy%3D%22.3em%22%20x%3D%2275%22%20y%3D%2275%22%20text-anchor%3D%22middle%22%3ENo%20Image%3C%2Ftext%3E%3C%2Fsvg%3E';
              }
            }
          } catch (imageError) {
            console.error('Error loading student detail image:', imageError);
            // Set fallback image on error
            if (studentDetailImage) studentDetailImage.src = 'data:image/svg+xml;charset=UTF-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22150%22%20height%3D%22150%22%20viewBox%3D%220%200%20150%20150%22%20preserveAspectRatio%3D%22none%22%3E%3Cpath%20fill%3D%22%23CCCCCC%22%20d%3D%22M0%200h150v150H0z%22%2F%3E%3Ctext%20fill%3D%22%23333333%22%20font-family%3D%22Arial%2CHelvetica%2Csans-serif%22%20font-size%3D%2214%22%20dy%3D%22.3em%22%20x%3D%2275%22%20y%3D%2275%22%20text-anchor%3D%22middle%22%3ENo%20Image%3C%2Ftext%3E%3C%2Fsvg%3E';
          }
        } else {
          // No representative image found
          if (studentDetailImage) studentDetailImage.src = 'data:image/svg+xml;charset=UTF-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22150%22%20height%3D%22150%22%20viewBox%3D%220%200%20150%20150%22%20preserveAspectRatio%3D%22none%22%3E%3Cpath%20fill%3D%22%23CCCCCC%22%20d%3D%22M0%200h150v150H0z%22%2F%3E%3Ctext%20fill%3D%22%23333333%22%20font-family%3D%22Arial%2CHelvetica%2Csans-serif%22%20font-size%3D%2214%22%20dy%3D%22.3em%22%20x%3D%2275%22%20y%3D%2275%22%20text-anchor%3D%22middle%22%3ENo%20Image%3C%2Ftext%3E%3C%2Fsvg%3E';
        }
        
        // Now try to fetch attendance details
        try {
          const detailsResponse = await fetch(`${API_BASE_URL}/persons/${personId}/attendance_details`);
          if (detailsResponse.ok) {
            const detailsData = await detailsResponse.json();
            
            if (detailsData.attendance_details && detailsData.attendance_details.length > 0) {
              if (studentDetailClasses) studentDetailClasses.textContent = detailsData.attendance_details.length;
              
              // Display attendance history
              if (studentAttendanceHistory) {
                studentAttendanceHistory.innerHTML = '';
                
                // Sort by date (most recent first)
                const sortedRecords = [...detailsData.attendance_details].sort(
                  (a, b) => new Date(b.date_taken) - new Date(a.date_taken)
                );
                
                sortedRecords.forEach(record => {
                  const item = document.createElement('div');
                  item.classList.add('attendance-item');
                  item.innerHTML = `
                    <div class="attendance-date">${new Date(record.date_taken).toLocaleDateString()}</div>
                    <div class="attendance-class">Class ID: ${record.class_image_id}</div>
                    <button class="view-class-btn" data-image-id="${record.class_image_id}">View Class</button>
                  `;
                  
                  // Add button click handler
                  const viewBtn = item.querySelector('.view-class-btn');
                  if (viewBtn) {
                    viewBtn.addEventListener('click', () => {
                      // Show class image details
                      showClassImageDetails(record.class_image_id);
                    });
                  }
                  
                  studentAttendanceHistory.appendChild(item);
                });
              }
            } else {
              // No attendance records found
              if (studentDetailClasses) studentDetailClasses.textContent = '0';
              if (studentAttendanceHistory) studentAttendanceHistory.innerHTML = '<p>No attendance records found for this student.</p>';
            }
          } else {
            throw new Error(`HTTP error! status: ${detailsResponse.status}`);
          }
        } catch (attendanceError) {
          console.error('Error fetching attendance details:', attendanceError);
          if (studentDetailClasses) studentDetailClasses.textContent = 'N/A';
          if (studentAttendanceHistory) studentAttendanceHistory.innerHTML = '<p>Could not load attendance records.</p>';
        }
      } catch (error) {
        console.error(`Error loading student details for ${personId}:`, error);
        if (studentDetailName) studentDetailName.textContent = 'Error loading student details';
        if (studentDetailImage) studentDetailImage.src = 'data:image/svg+xml;charset=UTF-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22150%22%20height%3D%22150%22%20viewBox%3D%220%200%20150%20150%22%20preserveAspectRatio%3D%22none%22%3E%3Cpath%20fill%3D%22%23CCCCCC%22%20d%3D%22M0%200h150v150H0z%22%2F%3E%3Ctext%20fill%3D%22%23333333%22%20font-family%3D%22Arial%2CHelvetica%2Csans-serif%22%20font-size%3D%2214%22%20dy%3D%22.3em%22%20x%3D%2275%22%20y%3D%2275%22%20text-anchor%3D%22middle%22%3EError%3C%2Ftext%3E%3C%2Fsvg%3E';
        if (studentAttendanceHistory) studentAttendanceHistory.innerHTML = `<p>Error: ${error.message}</p>`;
      }
    }
    
    // Hide student detail and return to list
    function hideStudentDetail() {
      if (studentDetailView) studentDetailView.style.display = 'none';
      if (studentsContainer) studentsContainer.parentElement.style.display = 'block';
      if (studentsPagination) studentsPagination.style.display = 'block';
    }
    
    // Show reassignment modal
    async function showReassignmentModal() {
      // Set current student information in the modal
      if (currentStudentImage) currentStudentImage.src = studentDetailImage.src;
      if (currentStudentName) currentStudentName.textContent = studentDetailName.textContent;
      
      // Fetch all students for the target select dropdown
      try {
        const response = await fetch(`${API_BASE_URL}/persons`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        
        // Populate select dropdown
        if (targetStudentSelect) {
          targetStudentSelect.innerHTML = '<option value="">Select a student...</option>';
          
          const students = data.persons || data;
          
          // Add all students except the current one
          students.forEach(student => {
            if (student.person_id !== window.currentViewingPersonId) {
              const option = document.createElement('option');
              option.value = student.person_id;
              option.textContent = student.name || `Unnamed (${student.person_id.slice(-6)})`;
              targetStudentSelect.appendChild(option);
            }
          });
        }
        
        // Show the modal
        if (reassignmentModal) reassignmentModal.style.display = 'block';
      } catch (error) {
        console.error("Error fetching students for reassignment:", error);
        alert(`Error loading students: ${error.message}`);
      }
    }
    
    // Handle reassignment
    async function handleReassignment() {
      const newPersonId = targetStudentSelect.value;
      if (!newPersonId) {
        alert("Please select a target student.");
        return;
      }
      
      const currentPersonId = window.currentViewingPersonId;
      if (!currentPersonId) {
        alert("Current student information is missing. Please try again.");
        return;
      }
      
      if (!confirm(`Are you sure you want to reassign this student's detection to ${targetStudentSelect.options[targetStudentSelect.selectedIndex].text}?`)) {
        return;
      }
      
      try {
        // Get detections for current person to get the detection ID
        const detailsResponse = await fetch(`${API_BASE_URL}/persons/${currentPersonId}/attendance_details`);
        if (!detailsResponse.ok) throw new Error(`HTTP error! status: ${detailsResponse.status}`);
        const detailsData = await detailsResponse.json();
        
        if (!detailsData.attendance_details || detailsData.attendance_details.length === 0) {
          alert("No detections found for this student.");
          return;
        }
        
        // For now, we'll just reassign the first detection
        // In a more complete implementation, you'd want to let the user choose which detection to reassign
        const detection = detailsData.attendance_details[0];
        const detectionId = detection.detection_id;
        
        // Call the reassign API
        const response = await fetch(`${API_BASE_URL}/detections/${detectionId}/reassign`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            new_person_id: newPersonId,
            original_person_id: currentPersonId
          })
        });
        
        const result = await response.json();
        
        if (!response.ok) {
          throw new Error(result.error || `Failed to reassign detection: ${response.statusText}`);
        }
        
        // Close the modal
        if (reassignmentModal) reassignmentModal.style.display = 'none';
        
        // Check if the current student was deleted (no more detections)
        if (result.original_person_deleted) {
          alert(`Detection reassigned successfully. The student has been deleted since this was their only detection.`);
          // Go back to the students list since this student no longer exists
          hideStudentDetail();
          fetchAllStudents(); // Refresh the students list
        } else {
          // Refresh the current student's details
          showStudentDetail(currentPersonId);
          alert(`Detection reassigned successfully.`);
        }
      } catch (error) {
        console.error('Error reassigning detection:', error);
        alert(`Error reassigning detection: ${error.message}`);
      }
    }
    
    // Update student name
    async function updateStudentName(personId, newName) {
      try {
        const response = await fetch(`${API_BASE_URL}/persons/${personId}/update-name`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ name: newName })
        });
        
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        
        if (data.success) {
          console.log(`Successfully updated name for person ${personId} to ${newName}`);
          
          // Update the name in the UI
          if (studentDetailName) studentDetailName.textContent = newName;
          
          // Show success message
          alert(`Name updated successfully to "${newName}"`);
          
          // Refresh the students list in the background
          fetchAllStudents();
        } else {
          throw new Error(data.error || 'Unknown error');
        }
      } catch (error) {
        console.error(`Error updating name for person ${personId}:`, error);
        alert(`Error updating name: ${error.message}`);
      }
    }
    
    // --- ATTENDANCE HISTORY FUNCTIONALITY ---
    
    // Fetch attendance history
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
              
              // Add click handler for student links
              const studentLink = row.querySelector('.student-link');
              if (studentLink) {
                studentLink.addEventListener('click', (e) => {
                  e.preventDefault();
                  showStudentDetail(person.person_id);
                });
              }
              
              leaderboardBody.appendChild(row);
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
              
              // Add click handler
              const viewBtn = row.querySelector('.view-details-btn');
              if (viewBtn) {
                viewBtn.addEventListener('click', () => {
                  showClassImageDetails(record.class_image_id);
                });
              }
              
              attendanceTableBody.appendChild(row);
            });
          }
        }
        
        // Populate student filter if needed
        if (studentFilterSelect && studentFilterSelect.options.length <= 1 && data.leaderboard.length > 0) {
          data.leaderboard.forEach(person => {
            const option = document.createElement('option');
            option.value = person.person_id;
            option.textContent = person.name || `ID: ${person.person_id.slice(-6)}...`;
            studentFilterSelect.appendChild(option);
          });
        }
      } catch (error) {
        console.error("Error fetching attendance history:", error);
        if (leaderboardBody) leaderboardBody.innerHTML = `<tr><td colspan="4">Error: ${error.message}</td></tr>`;
        if (attendanceTableBody) attendanceTableBody.innerHTML = `<tr><td colspan="4">Error: ${error.message}</td></tr>`;
      }
    }
    
    // --- SIMPLE GALLERY IMAGE ENHANCEMENT ---
    
    // This function is no longer needed since we're loading images directly in fetchClassGallery
    function enhanceGalleryImages() {
      console.log("Gallery image enhancement not needed - images loaded directly");
    }
    
    // Expose enhanceGalleryImages globally for template to call
    window.enhanceGalleryImages = enhanceGalleryImages;
    
    // --- SETUP EVENT LISTENERS ---
    
    // Upload form
    if (uploadForm) {
      console.log("Found upload form, adding event listener");
      uploadForm.addEventListener('submit', handleImageUpload);
    }
    
    // Attendance filters
    if (applyFiltersBtn) {
      applyFiltersBtn.addEventListener('click', fetchAttendanceHistory);
    }
    
    // Gallery filters
    if (applyGalleryFiltersBtn) {
      applyGalleryFiltersBtn.addEventListener('click', fetchClassGallery);
    }
    
    // Back to students button
    if (backToStudentsBtn) {
      backToStudentsBtn.addEventListener('click', hideStudentDetail);
    }
    
    // Reassign student button
    if (reassignStudentBtn) {
      reassignStudentBtn.addEventListener('click', showReassignmentModal);
    }
    
    // Confirm reassignment button
    if (confirmReassignBtn) {
      confirmReassignBtn.addEventListener('click', handleReassignment);
    }
    
    // Close reassignment modal when clicking on X
    if (reassignmentModal) {
      const closeBtn = reassignmentModal.querySelector('.close');
      if (closeBtn) {
        closeBtn.addEventListener('click', () => {
          reassignmentModal.style.display = 'none';
        });
      }
      
      // Close when clicking outside modal content
      window.addEventListener('click', (e) => {
        if (e.target === reassignmentModal) {
          reassignmentModal.style.display = 'none';
        }
      });
    }
    
    // --- INITIAL SETUP ---
    
    // Show tab from hash if present, otherwise default to upload section
    const hashFromUrl = window.location.hash;
    if (hashFromUrl) {
      const targetId = hashFromUrl.replace('#', '');
      showTabById(targetId);
    } else {
      showTabById('upload-section');
    }
  });
})(); 