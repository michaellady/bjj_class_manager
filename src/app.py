"""
Flask application for BJJ class attendance tracking system.
"""
import os
import sys
import logging
import json
import time
from datetime import datetime, timedelta
import sqlite3
import requests
import traceback
import base64
import io
from flask import Flask, render_template, request, jsonify, send_from_directory, abort, url_for
from flask_cors import CORS
from PIL import Image, ImageDraw, ImageFont

# Import our Instagram scraper
from src.utils.instagram_scraper import InstagramScraper
from src.utils.technique_extractor import TechniqueExtractor
from src.utils.image_processing import extract_person_features

# Import data access functions
from src.data_access import (
    add_class_image, update_class_image_status, 
    add_detection, get_class_image_by_id, get_detections_for_image,
    get_all_class_images, get_all_persons, get_detections_for_person,
    update_detection_assignment, update_person_name, get_person_by_id,
    get_detection_by_id, delete_person
)

# Configure logging with more detailed format
log_level = os.environ.get('LOG_LEVEL', 'INFO')
numeric_level = getattr(logging, log_level.upper(), logging.INFO)
logging.basicConfig(
    level=numeric_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)
logger.info(f"Starting application with log level: {log_level}")

# Define directories
CURRENT_APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_APP_DIR, '..'))
UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'pictures', 'incoming')
PROCESSED_FOLDER = os.path.join(PROJECT_ROOT, 'pictures', 'processed')
FACE_CROPS_FOLDER = os.path.join(PROJECT_ROOT, 'data', 'face_crops')
REPRESENTATIVE_PERSONS_FOLDER = os.path.join(PROJECT_ROOT, 'data', 'representative_persons')
REPRESENTATIVE_FEATURES_FOLDER = os.path.join(PROJECT_ROOT, 'data', 'representative_features')

# Create folders if they don't exist
for folder in [UPLOAD_FOLDER, PROCESSED_FOLDER, FACE_CROPS_FOLDER, 
               REPRESENTATIVE_PERSONS_FOLDER, REPRESENTATIVE_FEATURES_FOLDER]:
    os.makedirs(folder, exist_ok=True)
    logger.info(f"Created directory: {folder}")

# Get timeouts from environment variables
REQUESTS_TIMEOUT = int(os.environ.get('REQUESTS_TIMEOUT', 300))
INSTAGRAM_TIMEOUT = int(os.environ.get('INSTAGRAM_TIMEOUT', 180))
logger.info(f"Using timeouts: REQUESTS_TIMEOUT={REQUESTS_TIMEOUT}s, INSTAGRAM_TIMEOUT={INSTAGRAM_TIMEOUT}s")

# Initialize Flask app
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload size
CORS(app)
logger.info(f"Flask app initialized with upload folder: {UPLOAD_FOLDER}")

# Database connection
def create_connection(db_file=os.path.join(PROJECT_ROOT, 'bjj_attendance.db')):
    """Create a database connection to the SQLite database"""
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        logger.info(f"Connected to database: {db_file}")
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        return None

@app.route('/')
def index():
    """Render the home page."""
    logger.info("Rendering index page")
    
    # Get basic statistics for the dashboard
    stats = {}
    try:
        conn = create_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get total class images
        cursor.execute("SELECT COUNT(*) as count FROM ClassImages")
        result = cursor.fetchone()
        stats['total_classes'] = result['count'] if result else 0
        
        # Get total students
        cursor.execute("SELECT COUNT(*) as count FROM Persons")
        result = cursor.fetchone()
        stats['total_students'] = result['count'] if result else 0
        
        # Get latest class date
        cursor.execute("SELECT date_taken FROM ClassImages ORDER BY date_taken DESC LIMIT 1")
        result = cursor.fetchone()
        stats['latest_class'] = result['date_taken'] if result else None
        
        # Get total face detections
        cursor.execute("SELECT COUNT(*) as count FROM Detections")
        result = cursor.fetchone()
        stats['total_detections'] = result['count'] if result else 0
        
        conn.close()
    except Exception as e:
        logger.error(f"Error getting stats for index page: {e}")
        stats = {
            'total_classes': 0,
            'total_students': 0,
            'latest_class': None,
            'total_detections': 0
        }
    
    return render_template('index.html', stats=stats)

@app.route('/health')
def health_check():
    """Detailed health check endpoint for GitHub Actions testing."""
    logger.info("Health check requested")
    health_data = {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "app_version": "1.0.0",
        "services": {
            "database": "unknown",
            "file_system": "ok"
        },
        "config": {
            "instagram_timeout": INSTAGRAM_TIMEOUT,
            "requests_timeout": REQUESTS_TIMEOUT,
            "upload_folder_exists": os.path.exists(UPLOAD_FOLDER),
            "debug_mode": app.debug
        }
    }
    
    # Check database connection
    try:
        # Just check if the database file exists first
        db_file = os.path.join(PROJECT_ROOT, 'bjj_attendance.db')
        if not os.path.exists(db_file):
            logger.warning(f"Database file not found at {db_file}")
            health_data["services"]["database"] = f"error: Database file not found at {db_file}"
            health_data["status"] = "error"
        else:
            # Try to connect
            try:
                conn = create_connection()
                if conn:
                    conn.close()
                    health_data["services"]["database"] = "ok"
                else:
                    health_data["services"]["database"] = "error: Could not create connection"
                    health_data["status"] = "error"
            except Exception as e:
                logger.error(f"Database health check failed: {e}")
                health_data["services"]["database"] = f"error: {str(e)}"
                health_data["status"] = "error"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_data["services"]["database"] = f"error: {str(e)}"
        health_data["status"] = "error"
    
    # Check file system 
    try:
        # Test write access to upload folder
        test_file_path = os.path.join(UPLOAD_FOLDER, "health_check_test.txt")
        with open(test_file_path, 'w') as f:
            f.write("test")
        os.remove(test_file_path)
    except Exception as e:
        logger.error(f"File system health check failed: {e}")
        health_data["services"]["file_system"] = f"error: {str(e)}"
        health_data["status"] = "error"
    
    # Add environment details
    try:
        health_data["environment"] = {
            "python_version": sys.version,
            "platform": sys.platform,
            "hostname": os.uname().nodename if hasattr(os, 'uname') else "unknown",
            "current_directory": os.getcwd(),
            "app_directory": CURRENT_APP_DIR,
            "project_root": PROJECT_ROOT,
            "files_in_root": os.listdir(PROJECT_ROOT)[:10]  # Show first 10 files for debugging
        }
    except Exception as e:
        logger.error(f"Error getting environment details: {e}")
    
    # Log health check result
    logger.info(f"Health check result: {health_data['status']}")
    for service, status in health_data["services"].items():
        logger.info(f"Health check - {service}: {status}")
    
    if health_data["status"] == "error":
        return jsonify(health_data), 500
    
    return jsonify(health_data), 200

def fetch_instagram_image(instagram_url):
    """
    Fetch an image from Instagram using the Instagram scraper.
    """
    logger.info(f"Starting Instagram image fetch process for URL: {instagram_url}")
    
    try:
        # Initialize the Instagram scraper
        scraper = InstagramScraper()
        
        # Fetch the post
        logger.info(f"Fetching Instagram post from URL: {instagram_url}")
        start_time = time.time()
        result = scraper.fetch_post(instagram_url)
        
        if not result["success"]:
            logger.error(f"Failed to fetch Instagram post: {result['error']}")
            return {
                "success": False,
                "error": result["error"]
            }
            
        # Get post data
        local_path = result["image_path"]
        shortcode = result["shortcode"]
        caption = result["caption"]
        post_date = result["date"]
        
        logger.info(f"Successfully fetched Instagram post. Image saved to: {local_path}")
        logger.info(f"Post shortcode: {shortcode}")
        logger.info(f"Post date: {post_date}")
        logger.info(f"Caption length: {len(caption) if caption else 0}")
        
        return {
            "success": True,
            "local_path": local_path,
            "shortcode": shortcode,
            "caption": caption,
            "post_date": post_date,
            "post_url": instagram_url,
            "process_time": time.time() - start_time
        }
        
    except Exception as e:
        logger.error(f"Error fetching Instagram image: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {
            "success": False,
            "error": str(e)
        }

@app.route('/api/images/upload', methods=['POST'])
def upload_image():
    """Upload a class photo from URL or file."""
    try:
        # Start timing the request
        start_time = time.time()
        logger.info("Received image upload request")
        
        # Get input parameters
        image_url = request.form.get('image_url')
        file = request.files.get('file')
        date = request.form.get('date')
        caption = request.form.get('caption', '')
        
        logger.info(f"Upload parameters: URL={image_url}, File={file.filename if file else None}, date={date}, caption_length={len(caption)}")
        
        if not image_url and not file:
            logger.warning("No image URL or file provided in upload request")
            return jsonify({"error": "No image URL or file provided"}), 400
        
        # Process based on input type (URL or file)
        if file:
            # Handle file upload
            logger.info(f"Processing uploaded file: {file.filename}")
            
            # Create filename with timestamp to avoid conflicts
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{file.filename}"
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            
            # Ensure upload directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Save uploaded file
            file.save(file_path)
            logger.info(f"Saved uploaded file to {file_path}")
            
            # Store image information in database
            image_id = add_class_image(
                original_filename=file.filename,
                filepath_processed=file_path,
                date_taken=date or datetime.now().isoformat(),
                processing_status="pending"
            )
            
            if not image_id:
                logger.error("Failed to store image information in database")
                return jsonify({
                    "success": False,
                    "error": "Database error: Failed to store image information"
                }), 500
                
            logger.info(f"Stored image information in database with ID {image_id}")
            
            # Process the image with face recognition and student matching
            try:
                # Extract techniques from caption
                techniques = {}
                if caption:
                    technique_extractor = TechniqueExtractor()
                    techniques = technique_extractor.extract_techniques(caption)
                    logger.info(f"Extracted techniques: {json.dumps(techniques)}")
                
                # Import here to avoid circular imports
                from src.attendance_manager import process_new_class_image
                
                # Process the class image with improved person identification
                process_result = process_new_class_image(
                    image_id=image_id,
                    image_path=file_path,
                    image_date_taken_iso=date or datetime.now().isoformat()
                )
                
                if process_result:
                    logger.info(f"Successfully processed image {image_id} with face recognition and matching")
                    # Get the number of detections for this image
                    conn = create_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM Detections WHERE class_image_id = ?", (image_id,))
                    num_detections = cursor.fetchone()[0]
                    conn.close()
                    
                    # Return success response
                    return jsonify({
                        "success": True,
                        "image_id": image_id,
                        "processing_time": time.time() - start_time,
                        "num_persons_detected": num_detections,
                        "techniques_extracted": techniques
                    }), 201
                else:
                    logger.error(f"Failed to process image {image_id}")
                    return jsonify({
                        "success": True,
                        "image_id": image_id,
                        "processing_error": "Failed to process image with face recognition",
                        "processing_time": time.time() - start_time
                    }), 201
                
            except Exception as processing_error:
                logger.error(f"Error processing image: {processing_error}")
                # Update image status to error
                update_class_image_status(image_id, "error", str(processing_error))
                
                # Still return success for the upload, but indicate processing error
                return jsonify({
                    "success": True,
                    "image_id": image_id,
                    "processing_error": str(processing_error),
                    "processing_time": time.time() - start_time
                }), 201
                
        elif image_url:
            # Check if it's an Instagram URL
            is_instagram = 'instagram.com' in image_url
            logger.info(f"URL is{'n' if not is_instagram else ''} Instagram URL: {image_url}")
            
            if is_instagram:
                logger.info(f"Processing Instagram URL: {image_url}")
                
                # Call our Instagram fetching function
                fetch_result = fetch_instagram_image(image_url)
                
                if not fetch_result["success"]:
                    logger.error(f"Failed to fetch Instagram image: {fetch_result.get('error', 'Unknown error')}")
                    return jsonify({
                        "success": False,
                        "error": f"Failed to fetch Instagram image: {fetch_result.get('error', 'Unknown error')}"
                    }), 500
                
                logger.info(f"Successfully fetched Instagram image to {fetch_result['local_path']} in {fetch_result['process_time']:.2f}s")
                
                # Use the caption from Instagram if available and none provided
                if not caption and fetch_result.get("caption"):
                    caption = fetch_result["caption"]
                    logger.info(f"Using caption from Instagram post: {caption[:50]}...")
                    
                # Use the post date if available and none provided
                if not date and fetch_result.get("post_date"):
                    date = fetch_result["post_date"].isoformat()
                    logger.info(f"Using date from Instagram post: {date}")
                    
                # Store image information in database
                image_id = add_class_image(
                    original_filename=os.path.basename(fetch_result["local_path"]),
                    filepath_processed=fetch_result["local_path"],
                    date_taken=date or datetime.now().isoformat(),
                    processing_status="pending",
                    instagram_shortcode=fetch_result.get("shortcode"),
                    instagram_caption=caption,
                    instagram_post_url=image_url
                )
                
                if not image_id:
                    logger.error("Failed to store image information in database")
                    return jsonify({
                        "success": False,
                        "error": "Database error: Failed to store image information"
                    }), 500
                    
                logger.info(f"Stored image information in database with ID {image_id}")
                
                # Process the image with face recognition and student matching
                try:
                    # Extract techniques from caption
                    techniques = {}
                    if caption:
                        technique_extractor = TechniqueExtractor()
                        techniques = technique_extractor.extract_techniques(caption)
                        logger.info(f"Extracted techniques: {json.dumps(techniques)}")
                    
                    # Import here to avoid circular imports
                    from src.attendance_manager import process_new_class_image
                    
                    # Process the class image with improved person identification
                    process_result = process_new_class_image(
                        image_id=image_id,
                        image_path=fetch_result["local_path"],
                        image_date_taken_iso=date or datetime.now().isoformat()
                    )
                    
                    if process_result:
                        logger.info(f"Successfully processed image {image_id} with face recognition and matching")
                        # Get the number of detections for this image
                        conn = create_connection()
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM Detections WHERE class_image_id = ?", (image_id,))
                        num_detections = cursor.fetchone()[0]
                        conn.close()
                        
                        # Return success response
                        return jsonify({
                            "success": True,
                            "image_id": image_id,
                            "processing_time": time.time() - start_time,
                            "num_persons_detected": num_detections,
                            "techniques_extracted": techniques
                        }), 201
                    else:
                        logger.error(f"Failed to process image {image_id}")
                        return jsonify({
                            "success": True,
                            "image_id": image_id,
                            "processing_error": "Failed to process image with face recognition",
                            "processing_time": time.time() - start_time
                        }), 201
                    
                except Exception as processing_error:
                    logger.error(f"Error processing image: {processing_error}")
                    # Update image status to error
                    update_class_image_status(image_id, "error", str(processing_error))
                    
                    # Still return success for the upload, but indicate processing error
                    return jsonify({
                        "success": True,
                        "image_id": image_id,
                        "processing_error": str(processing_error),
                        "processing_time": time.time() - start_time
                    }), 201
                    
            else:
                # Handle direct URL uploads
                logger.info(f"Processing direct image URL (non-Instagram): {image_url}")
                # Logic for direct URLs would go here
                return jsonify({
                    "success": False,
                    "error": "Direct URL uploads not implemented yet"
                }), 501
        
    except Exception as e:
        logger.error(f"Error in upload_image endpoint: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/images/<int:image_id>/detections', methods=['GET'])
def get_detections(image_id):
    """Get detections for a class image."""
    logger.info(f"Getting detections for image_id={image_id}")
    
    # Mock data for testing
    detections = []
    for i in range(18):  # Simulate 18 faces
        detections.append({
            "detection_id": i + 1,
            "person_id": f"test_person_{i}",
            "face_crop_path": f"/static_crops/test_face_{i}.jpg",
            "confidence": 0.95
        })
    
    logger.info(f"Returning {len(detections)} detections for image_id={image_id}")
    return jsonify({
        "image_info": {
            "class_image_id": image_id,
            "processing_status": "completed",
            "date_taken": "2025-06-02"
        },
        "detections": detections
    }), 200

@app.route('/api/detections/<int:detection_id>/reassign_to_new_person', methods=['POST'])
def reassign_to_new_person(detection_id):
    """Reassign a detection to a new person."""
    logger.info(f"Reassigning detection_id={detection_id} to new person")
    
    # Mock data for testing
    new_person_id = f"new_person_{detection_id}"
    
    logger.info(f"Created new person with ID {new_person_id} for detection_id={detection_id}")
    return jsonify({
        "success": True,
        "new_person_id": new_person_id
    }), 200

@app.route('/api/persons/<person_id>/update', methods=['POST'])
def update_person(person_id):
    """Update a person's information."""
    # Get request data
    data = request.json
    name = data.get('name')
    
    logger.info(f"Updating person {person_id} with name: {name}")
    
    # Mock update
    logger.info(f"Successfully updated person {person_id} with name: {name}")
    
    return jsonify({
        "success": True,
        "person_id": person_id,
        "name": name
    }), 200

@app.route('/api/images/<int:image_id>/attendance', methods=['GET'])
def get_attendance(image_id):
    """Get attendance for a class."""
    logger.info(f"Getting attendance for image_id={image_id}")
    
    # Mock data for testing
    attendees = []
    for i in range(18):
        attendees.append({
            "person_id": f"test_person_{i}",
            "name": f"Test Person {i}",
            "confidence": 0.95
        })
    
    logger.info(f"Returning attendance with {len(attendees)} attendees for image_id={image_id}")
    return jsonify({
        "class_image_id": image_id,
        "date": "2025-06-02",
        "attendees": attendees
    }), 200

@app.route('/debug-page')
def debug_page():
    """Render a debug page to check tab navigation."""
    logger.info("Rendering debug page")
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Debug Navigation</title>
        <style>
            body { font-family: Arial; padding: 20px; }
            .nav { display: flex; margin-bottom: 20px; }
            .nav a { margin-right: 15px; padding: 8px; background: #eee; text-decoration: none; }
            .nav a.active { background: #007bff; color: white; }
            .section { border: 1px solid #ddd; padding: 20px; margin-bottom: 10px; display: none; }
            .active-section { display: block; }
            #log { background: #f5f5f5; padding: 10px; height: 200px; overflow-y: auto; font-family: monospace; }
        </style>
    </head>
    <body>
        <h1>Debug Navigation</h1>
        
        <div class="nav">
            <a href="#section1" class="active">Section 1</a>
            <a href="#section2">Section 2</a>
            <a href="#section3">Section 3</a>
        </div>
        
        <div id="section1" class="section active-section">
            <h2>Section 1 Content</h2>
            <p>This is the content of section 1.</p>
        </div>
        
        <div id="section2" class="section">
            <h2>Section 2 Content</h2>
            <p>This is the content of section 2.</p>
        </div>
        
        <div id="section3" class="section">
            <h2>Section 3 Content</h2>
            <p>This is the content of section 3.</p>
        </div>
        
        <h3>Debug Log</h3>
        <div id="log"></div>
        
        <script>
            // Debug logging function
            function log(message) {
                const logDiv = document.getElementById('log');
                const entry = document.createElement('div');
                entry.textContent = new Date().toISOString().slice(11, 19) + ': ' + message;
                logDiv.appendChild(entry);
                logDiv.scrollTop = logDiv.scrollHeight;
            }
            
            // Log initial state
            log('Page loaded');
            log('Active sections: ' + document.querySelectorAll('.active-section').length);
            
            // Tab navigation
            document.querySelectorAll('.nav a').forEach(link => {
                log('Setting up click handler for: ' + link.textContent);
                
                link.addEventListener('click', function(e) {
                    log('Clicked: ' + this.textContent);
                    e.preventDefault();
                    
                    try {
                        const targetId = this.getAttribute('href');
                        log('Target ID: ' + targetId);
                        
                        // Hide all sections
                        document.querySelectorAll('.section').forEach(section => {
                            section.classList.remove('active-section');
                            log('Removed active-section from: ' + section.id);
                        });
                        
                        // Show target section
                        const targetSection = document.querySelector(targetId);
                        log('Target section found: ' + (targetSection !== null));
                        
                        if (targetSection) {
                            targetSection.classList.add('active-section');
                            log('Added active-section to: ' + targetId);
                        } else {
                            log('ERROR: Target section not found: ' + targetId);
                        }
                        
                        // Update active nav link
                        document.querySelectorAll('.nav a').forEach(navLink => {
                            navLink.classList.remove('active');
                            log('Removed active from nav: ' + navLink.textContent);
                        });
                        
                        this.classList.add('active');
                        log('Added active to: ' + this.textContent);
                    } catch (error) {
                        log('ERROR: ' + error.message);
                    }
                });
            });
        </script>
    </body>
    </html>
    """

@app.route('/log-js', methods=['POST'])
def log_js():
    """Log JavaScript console messages."""
    data = request.json
    if data and 'message' in data:
        level = data.get('level', 'info')
        message = data['message']
        logger.info(f"JS Console [{level}]: {message}")
    return jsonify({"status": "ok"})

@app.route('/api/class-images', methods=['GET'])
def get_class_images():
    """Get all class images with pagination."""
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        days = request.args.get('days', None, type=int)
        
        # Calculate offset
        offset = (page - 1) * per_page
        
        # Calculate date filter if 'days' is provided
        date_filter = None
        if days and days != 'all':
            end_date = datetime.now().isoformat()
            start_date = (datetime.now() - timedelta(days=days)).isoformat()
            date_filter = (start_date, end_date)
        
        # Get images from database with date filter
        conn = create_connection()
        
        # Enable dictionary row factory
        conn.row_factory = sqlite3.Row
        
        # Create separate cursors for each query
        cursor = conn.cursor()
        count_cursor = conn.cursor()
        
        # Initialize total_count to 0
        total_count = 0
        
        if date_filter:
            # Get images with date filter
            cursor.execute("""
                SELECT * FROM ClassImages 
                WHERE date_taken BETWEEN ? AND ?
                ORDER BY date_taken DESC 
                LIMIT ? OFFSET ?
            """, (date_filter[0], date_filter[1], per_page, offset))
            
            # Get total count for pagination
            count_cursor.execute("""
                SELECT COUNT(*) as total FROM ClassImages
                WHERE date_taken BETWEEN ? AND ?
            """, (date_filter[0], date_filter[1]))
        else:
            # Get all images
            cursor.execute("""
                SELECT * FROM ClassImages 
                ORDER BY date_taken DESC 
                LIMIT ? OFFSET ?
            """, (per_page, offset))
            
            # Get total count for pagination
            count_cursor.execute("SELECT COUNT(*) as total FROM ClassImages")
        
        # Fetch results
        images = cursor.fetchall()
        count_result = count_cursor.fetchone()
        
        # Convert row objects to dictionaries
        images_list = []
        for row in images:
            image_dict = {}
            for key in row.keys():
                image_dict[key] = row[key]
            images_list.append(image_dict)
            
        # Get count value
        if count_result:
            total_count = count_result['total']
            
        conn.close()
        
        # Create empty array if no images are found
        images_list = images_list or []
        
        logger.info(f"Found {len(images_list)} class images, total count: {total_count}")
        
        return jsonify({
            "success": True,
            "images": images_list,
            "pagination": {
                "total": total_count,
                "page": page,
                "per_page": per_page,
                "total_pages": max(1, (total_count + per_page - 1) // per_page)
            }
        }), 200
    except Exception as e:
        logger.error(f"Error getting class images: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/class-images/<int:image_id>', methods=['GET'])
def get_class_image_details(image_id):
    """Get details for a specific class image including all detections."""
    try:
        # Get image from database
        image = get_class_image_by_id(image_id)
        if not image:
            logger.error(f"Class image with ID {image_id} not found")
            return jsonify({
                "success": False,
                "error": f"Class image with ID {image_id} not found"
            }), 404
        
        # Get detections for this image
        detections = get_detections_for_image(image_id)
        
        # Get techniques taught in this class
        conn = create_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.technique_id, t.name, t.category, ct.confidence
            FROM ClassTechniques ct
            JOIN Techniques t ON ct.technique_id = t.technique_id
            WHERE ct.class_image_id = ?
        """, (image_id,))
        
        techniques_rows = cursor.fetchall()
        techniques = []
        for row in techniques_rows:
            technique_dict = {}
            for key in row.keys():
                technique_dict[key] = row[key]
            techniques.append(technique_dict)
            
        conn.close()
        
        # Check if detections is None or empty
        if not detections:
            logger.warning(f"No detections found for image ID {image_id}")
            detections = []
        
        # Filter out binary data from detections
        filtered_detections = []
        for detection in detections:
            # Create a new dict without the binary feature_vector
            filtered_detection = {}
            for key, value in detection.items():
                # Skip feature_vector and other binary fields
                if key != 'feature_vector' and not isinstance(value, bytes):
                    filtered_detection[key] = value
            filtered_detections.append(filtered_detection)
        
        # Organize detections by person
        persons = {}
        for detection in filtered_detections:
            person_id = detection.get('person_id')
            if not person_id:
                logger.warning(f"Detection without person_id found for image {image_id}")
                continue
                
            if person_id not in persons:
                # Get person details
                person = get_person_by_id(person_id)
                if person:
                    persons[person_id] = {
                        "person_id": person_id,
                        "name": person.get('name', 'Unknown'),
                        "detections": []
                    }
                else:
                    persons[person_id] = {
                        "person_id": person_id,
                        "name": "Unknown",
                        "detections": []
                    }
            
            # Add detection
            persons[person_id]["detections"].append(detection)
        
        # Convert to list
        attendees = list(persons.values())
        
        logger.info(f"Returning details for image ID {image_id} with {len(attendees)} attendees")
        
        return jsonify({
            "success": True,
            "image": image,
            "attendees": attendees,
            "techniques": techniques,
            "total_attendees": len(attendees),
            "total_detections": len(filtered_detections)
        }), 200
    except Exception as e:
        logger.error(f"Error getting class image details: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/class-images/<int:image_id>', methods=['DELETE'])
def delete_class_image(image_id):
    """Delete a class image and its associated data."""
    try:
        # Get image from database to check if it exists
        image = get_class_image_by_id(image_id)
        if not image:
            logger.error(f"Class image with ID {image_id} not found for deletion")
            return jsonify({
                "success": False,
                "error": f"Class image with ID {image_id} not found"
            }), 404
        
        # Store the file paths for deletion after database entries are removed
        file_paths_to_delete = []
        
        # Get the image path
        if image.get('filepath_processed'):
            file_paths_to_delete.append(image['filepath_processed'])
        
        if image.get('processed_image_path'):
            file_paths_to_delete.append(image['processed_image_path'])
        
        # Get detections to find face crop files
        detections = get_detections_for_image(image_id)
        if detections:
            for detection in detections:
                if detection.get('face_crop_path'):
                    file_paths_to_delete.append(detection['face_crop_path'])
        
        # Begin transaction to delete database entries
        conn = create_connection()
        cursor = conn.cursor()
        
        try:
            # Disable foreign key constraints temporarily
            cursor.execute("PRAGMA foreign_keys = OFF;")
            
            # Begin transaction
            cursor.execute("BEGIN TRANSACTION;")
            
            # First, identify persons who will have no detections after this class image is deleted
            cursor.execute("""
                SELECT p.person_id, p.representative_image_path, p.representative_feature_path 
                FROM Persons p
                WHERE p.person_id IN (
                    SELECT DISTINCT d.person_id 
                    FROM Detections d 
                    WHERE d.class_image_id = ?
                )
                AND (
                    SELECT COUNT(d2.detection_id) 
                    FROM Detections d2 
                    WHERE d2.person_id = p.person_id AND d2.class_image_id != ?
                ) = 0
            """, (image_id, image_id))
            
            persons_to_delete = cursor.fetchall()
            logger.info(f"Found {len(persons_to_delete)} persons to delete who will have no remaining detections")
            
            # Add representative image and feature paths to files to delete
            for person in persons_to_delete:
                if isinstance(person, dict) or hasattr(person, 'keys'):
                    # If result is a dict or dict-like
                    person_id = person['person_id']
                    if person.get('representative_image_path'):
                        file_paths_to_delete.append(person['representative_image_path'])
                    if person.get('representative_feature_path'):
                        file_paths_to_delete.append(person['representative_feature_path'])
                else:
                    # If result is a tuple
                    person_id = person[0]
                    if person[1]:  # representative_image_path
                        file_paths_to_delete.append(person[1])
                    if person[2]:  # representative_feature_path
                        file_paths_to_delete.append(person[2])
                
                logger.info(f"Person {person_id} will be deleted as they will have no remaining detections")
            
            # Delete related records first
            # Delete from ClassTechniques
            cursor.execute("DELETE FROM ClassTechniques WHERE class_image_id = ?", (image_id,))
            
            # Delete from Detections
            cursor.execute("DELETE FROM Detections WHERE class_image_id = ?", (image_id,))
            
            # Delete persons who no longer have any detections
            if persons_to_delete:
                person_ids = []
                for person in persons_to_delete:
                    if isinstance(person, dict) or hasattr(person, 'keys'):
                        person_ids.append(person['person_id'])
                    else:
                        person_ids.append(person[0])
                
                # Build the SQL query with placeholders for the IN clause
                placeholders = ', '.join(['?' for _ in person_ids])
                delete_query = f"DELETE FROM Persons WHERE person_id IN ({placeholders})"
                
                # Execute the delete query
                cursor.execute(delete_query, person_ids)
                logger.info(f"Deleted {len(person_ids)} persons with no remaining detections")
            
            # Finally delete the image record
            cursor.execute("DELETE FROM ClassImages WHERE class_image_id = ?", (image_id,))
            
            # Commit the transaction
            conn.commit()
            
            # Re-enable foreign key constraints
            cursor.execute("PRAGMA foreign_keys = ON;")
            
            logger.info(f"Successfully deleted class image {image_id} from database")
            
        except Exception as db_error:
            # Rollback in case of error
            conn.rollback()
            cursor.execute("PRAGMA foreign_keys = ON;")
            logger.error(f"Database error while deleting class image {image_id}: {db_error}")
            raise db_error
        finally:
            conn.close()
        
        # Delete the files from disk
        deleted_files = []
        for file_path in file_paths_to_delete:
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
                    deleted_files.append(file_path)
                    logger.info(f"Deleted file: {file_path}")
            except Exception as file_error:
                logger.error(f"Error deleting file {file_path}: {file_error}")
        
        return jsonify({
            "success": True,
            "message": f"Class image {image_id} successfully deleted",
            "deleted_files": deleted_files,
            "deleted_persons": len(persons_to_delete) if persons_to_delete else 0
        }), 200
        
    except Exception as e:
        logger.error(f"Error deleting class image {image_id}: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/persons', methods=['GET'])
def get_persons():
    """Get all persons with pagination."""
    try:
        # Get all persons
        persons = get_all_persons()
        
        # For each person, get their attendance count
        conn = create_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        for person in persons:
            # Count distinct class images where this person was detected
            cursor.execute("""
                SELECT COUNT(DISTINCT class_image_id) as attendance_count FROM Detections
                WHERE person_id = ?
            """, (person['person_id'],))
            
            result = cursor.fetchone()
            
            # Handle both dictionary and tuple return types
            if result:
                if isinstance(result, dict) or hasattr(result, 'keys'):
                    person['attendance_count'] = result['attendance_count']
                else:
                    # If result is a tuple
                    person['attendance_count'] = result[0]
            else:
                person['attendance_count'] = 0
            
            # Get most recent class attended
            cursor.execute("""
                SELECT ci.date_taken FROM Detections d
                JOIN ClassImages ci ON d.class_image_id = ci.class_image_id
                WHERE d.person_id = ?
                ORDER BY ci.date_taken DESC
                LIMIT 1
            """, (person['person_id'],))
            
            result = cursor.fetchone()
            
            # Handle both dictionary and tuple return types
            if result:
                if isinstance(result, dict) or hasattr(result, 'keys'):
                    person['last_attended'] = result['date_taken']
                else:
                    # If result is a tuple
                    person['last_attended'] = result[0]
            else:
                person['last_attended'] = None
        
        conn.close()
        
        return jsonify({
            "success": True,
            "persons": persons,
            "total": len(persons)
        }), 200
    except Exception as e:
        logger.error(f"Error getting persons: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/persons/<person_id>/attendance_details', methods=['GET'])
def get_person_attendance_details(person_id):
    """Get detailed attendance information for a specific person."""
    try:
        # Get person info
        person_info = get_person_by_id(person_id)
        if not person_info:
            logger.warning(f"Person {person_id} not found")
            return jsonify({
                "success": False,
                "error": f"Person {person_id} not found"
            }), 404
        
        # Get person's detections with additional information
        attendance_details = get_detections_for_person(person_id)
        
        # Process attendance details to include face crop URLs
        processed_attendance = []
        for attendance in attendance_details:
            attendance_data = dict(attendance)  # Create a copy to avoid modifying the original
            
            # Remove binary fields that can't be serialized to JSON
            if 'feature_vector' in attendance_data:
                del attendance_data['feature_vector']
            
            # Add face crop URL if available
            if attendance_data.get('face_crop_path'):
                crop_path = attendance_data['face_crop_path']
                # Just provide the path - the frontend will use data-url API to fetch the image
                attendance_data['face_crop_url'] = crop_path
            
            # Add class image URL if available
            class_image = get_class_image_by_id(attendance_data.get('class_image_id'))
            if class_image and class_image.get('instagram_shortcode'):
                attendance_data['instagram_shortcode'] = class_image['instagram_shortcode']
            
            processed_attendance.append(attendance_data)
        
        # Include representative image URL if available
        if person_info.get('representative_image_path'):
            rep_image_path = person_info['representative_image_path']
            person_info['image_url'] = f"/data/representative_persons/{os.path.basename(rep_image_path)}"
        
        # Return person info and attendance details
        return jsonify({
            "person_info": person_info,
            "attendance_details": processed_attendance
        })
    except Exception as e:
        logger.error(f"Error getting person attendance details: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/detections/<int:detection_id>/reassign', methods=['POST'])
def reassign_detection(detection_id):
    """Reassign a detection to a different person."""
    logger.info(f"Reassigning detection_id={detection_id}")
    
    try:
        data = request.json
        new_person_id = data.get('new_person_id')
        original_person_id = data.get('original_person_id')
        
        if not new_person_id:
            return jsonify({
                "success": False,
                "error": "No new_person_id provided"
            }), 400
        
        # Get current detection details
        detection = get_detection_by_id(detection_id)
        if not detection:
            return jsonify({
                "success": False,
                "error": f"Detection with ID {detection_id} not found"
            }), 404
        
        current_person_id = detection.get('person_id')
        if not current_person_id:
            return jsonify({
                "success": False,
                "error": "Detection is not currently assigned to any person"
            }), 400
        
        # Verify the provided original_person_id matches the actual one
        if original_person_id and original_person_id != current_person_id:
            logger.warning(f"Provided original_person_id {original_person_id} doesn't match actual {current_person_id}")
        
        # Get the person we're reassigning from
        original_person = get_person_by_id(current_person_id)
        if not original_person:
            return jsonify({
                "success": False,
                "error": f"Original person with ID {current_person_id} not found"
            }), 404
        
        # Reassign the detection
        update_success = update_detection_assignment(
            detection_id=detection_id,
            new_person_id=new_person_id,
            is_verified=True,  # Mark as verified since this is a manual action
            original_assigned_person_id_to_set=current_person_id
        )
        
        if not update_success:
            return jsonify({
                "success": False,
                "error": "Failed to update detection assignment"
            }), 500
        
        # Check if the original person has any detections left
        remaining_detections = get_detections_for_person(current_person_id)
        
        original_person_deleted = False
        if not remaining_detections:
            logger.info(f"Person {current_person_id} has no remaining detections, deleting...")
            
            # Delete representative files
            rep_image_path = original_person.get('representative_image_path')
            rep_feature_path = original_person.get('representative_feature_path')
            
            if rep_image_path and os.path.exists(rep_image_path):
                try:
                    os.remove(rep_image_path)
                    logger.info(f"Deleted representative image: {rep_image_path}")
                except Exception as e:
                    logger.error(f"Error deleting representative image {rep_image_path}: {e}")
            
            if rep_feature_path and os.path.exists(rep_feature_path):
                try:
                    os.remove(rep_feature_path)
                    logger.info(f"Deleted representative feature: {rep_feature_path}")
                except Exception as e:
                    logger.error(f"Error deleting representative feature {rep_feature_path}: {e}")
            
            # Delete the person
            delete_success = delete_person(current_person_id)
            if delete_success:
                logger.info(f"Successfully deleted person {current_person_id}")
                original_person_deleted = True
            else:
                logger.error(f"Failed to delete person {current_person_id}")
        
        # Return success response
        return jsonify({
            "success": True,
            "detection_id": detection_id,
            "new_person_id": new_person_id,
            "original_person_id": current_person_id,
            "original_person_deleted": original_person_deleted
        }), 200
        
    except Exception as e:
        logger.error(f"Error reassigning detection {detection_id}: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/persons/<person_id>/update-name', methods=['POST'])
def update_person_name_endpoint(person_id):
    """Update a person's name."""
    try:
        data = request.json
        if not data or 'name' not in data:
            return jsonify({
                "success": False,
                "error": "Missing name parameter"
            }), 400
        
        new_name = data['name']
        
        # Update the person's name
        success = update_person_name(person_id, new_name)
        
        if success:
            return jsonify({
                "success": True,
                "person_id": person_id,
                "new_name": new_name
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": f"Failed to update name for person {person_id}"
            }), 500
    except Exception as e:
        logger.error(f"Error updating person name: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/attendance/history', methods=['GET'])
def get_attendance_history():
    """Get attendance history statistics."""
    try:
        # Get date range parameters
        days = request.args.get('days', 30, type=int)
        student_id = request.args.get('student_id', 'all')
        
        # Calculate start date
        end_date = datetime.now().isoformat()
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        conn = create_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get total classes in date range
        if student_id == 'all':
            cursor.execute("""
                SELECT COUNT(*) as total_count FROM ClassImages
                WHERE date_taken BETWEEN ? AND ?
            """, (start_date, end_date))
        else:
            # Only count classes this student attended
            cursor.execute("""
                SELECT COUNT(DISTINCT ci.class_image_id) as total_count FROM ClassImages ci
                JOIN Detections d ON ci.class_image_id = d.class_image_id
                WHERE ci.date_taken BETWEEN ? AND ?
                AND d.person_id = ?
            """, (start_date, end_date, student_id))
        
        result = cursor.fetchone()
        total_classes = result['total_count'] if isinstance(result, dict) else result[0]
        
        # Get total unique students in date range
        cursor.execute("""
            SELECT COUNT(DISTINCT person_id) as total_students FROM Detections d
            JOIN ClassImages ci ON d.class_image_id = ci.class_image_id
            WHERE ci.date_taken BETWEEN ? AND ?
        """, (start_date, end_date))
        
        result = cursor.fetchone()
        total_students = result['total_students'] if isinstance(result, dict) else result[0]
        
        # Get average attendance per class
        avg_attendance = 0
        if total_classes > 0:
            cursor.execute("""
                SELECT ci.class_image_id, COUNT(DISTINCT d.person_id) as attendance
                FROM ClassImages ci
                LEFT JOIN Detections d ON ci.class_image_id = d.class_image_id
                WHERE ci.date_taken BETWEEN ? AND ?
                GROUP BY ci.class_image_id
            """, (start_date, end_date))
            
            classes_rows = cursor.fetchall()
            classes = []
            for row in classes_rows:
                if isinstance(row, dict):
                    classes.append(row)
                else:
                    # Convert tuple to dict
                    classes.append({
                        'class_image_id': row[0],
                        'attendance': row[1]
                    })
            
            total_attendance = sum(c['attendance'] for c in classes)
            avg_attendance = total_attendance / total_classes if total_classes > 0 else 0
        
        # Get student leaderboard
        cursor.execute("""
            SELECT p.person_id, p.name, COUNT(DISTINCT d.class_image_id) as classes_attended
            FROM Persons p
            JOIN Detections d ON p.person_id = d.person_id
            JOIN ClassImages ci ON d.class_image_id = ci.class_image_id
            WHERE ci.date_taken BETWEEN ? AND ?
            GROUP BY p.person_id
            ORDER BY classes_attended DESC
            LIMIT 10
        """, (start_date, end_date))
        
        leaderboard_rows = cursor.fetchall()
        leaderboard = []
        for row in leaderboard_rows:
            if isinstance(row, dict):
                person_dict = dict(row)
            else:
                # Convert tuple to dict
                person_dict = {
                    'person_id': row[0],
                    'name': row[1],
                    'classes_attended': row[2]
                }
            
            # Calculate attendance percentage
            person_dict['attendance_percentage'] = (person_dict['classes_attended'] / total_classes) * 100 if total_classes > 0 else 0
            leaderboard.append(person_dict)
        
        # Get recent class attendance records
        cursor.execute("""
            SELECT ci.class_image_id, ci.date_taken, ci.instagram_post_url, ci.instagram_caption,
                   COUNT(DISTINCT d.person_id) as attendees
            FROM ClassImages ci
            LEFT JOIN Detections d ON ci.class_image_id = d.class_image_id
            WHERE ci.date_taken BETWEEN ? AND ?
            GROUP BY ci.class_image_id
            ORDER BY ci.date_taken DESC
            LIMIT 20
        """, (start_date, end_date))
        
        attendance_records_rows = cursor.fetchall()
        attendance_records = []
        
        for row in attendance_records_rows:
            if isinstance(row, dict):
                record = dict(row)
            else:
                # Convert tuple to dict
                record = {
                    'class_image_id': row[0],
                    'date_taken': row[1],
                    'instagram_post_url': row[2],
                    'instagram_caption': row[3],
                    'attendees': row[4]
                }
            
            # Get techniques for this class
            cursor.execute("""
                SELECT t.name, t.category
                FROM ClassTechniques ct
                JOIN Techniques t ON ct.technique_id = t.technique_id
                WHERE ct.class_image_id = ?
            """, (record['class_image_id'],))
            
            techniques_rows = cursor.fetchall()
            techniques = []
            for tech_row in techniques_rows:
                if isinstance(tech_row, dict):
                    techniques.append(tech_row)
                else:
                    techniques.append({
                        'name': tech_row[0],
                        'category': tech_row[1]
                    })
            
            record['techniques'] = techniques
            attendance_records.append(record)
        
        conn.close()
        
        return jsonify({
            "success": True,
            "stats": {
                "total_classes": total_classes,
                "total_students": total_students,
                "avg_attendance": round(avg_attendance, 1),
                "date_range": {
                    "start": start_date,
                    "end": end_date,
                    "days": days
                }
            },
            "leaderboard": leaderboard,
            "attendance_records": attendance_records
        }), 200
    except Exception as e:
        logger.error(f"Error getting attendance history: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/techniques/history', methods=['GET'])
def get_techniques_history():
    """Get technique history statistics."""
    try:
        # Get filter parameters
        days = request.args.get('days', 30, type=int)
        category = request.args.get('category', 'all')
        sort_by = request.args.get('sort_by', 'frequency')
        
        # Calculate start date
        end_date = datetime.now().isoformat()
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        conn = create_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get total techniques in date range
        if category == 'all':
            cursor.execute("""
                SELECT COUNT(DISTINCT t.technique_id) as total_count FROM Techniques t
                JOIN ClassTechniques ct ON t.technique_id = ct.technique_id
                JOIN ClassImages ci ON ct.class_image_id = ci.class_image_id
                WHERE ci.date_taken BETWEEN ? AND ?
            """, (start_date, end_date))
        else:
            cursor.execute("""
                SELECT COUNT(DISTINCT t.technique_id) as total_count FROM Techniques t
                JOIN ClassTechniques ct ON t.technique_id = ct.technique_id
                JOIN ClassImages ci ON ct.class_image_id = ci.class_image_id
                WHERE ci.date_taken BETWEEN ? AND ?
                AND t.category = ?
            """, (start_date, end_date, category))
        
        result = cursor.fetchone()
        total_techniques = result['total_count'] if isinstance(result, dict) else result[0]
        
        # Get most frequently taught technique
        if category == 'all':
            cursor.execute("""
                SELECT t.name, COUNT(*) as frequency
                FROM Techniques t
                JOIN ClassTechniques ct ON t.technique_id = ct.technique_id
                JOIN ClassImages ci ON ct.class_image_id = ci.class_image_id
                WHERE ci.date_taken BETWEEN ? AND ?
                GROUP BY t.technique_id
                ORDER BY frequency DESC
                LIMIT 1
            """, (start_date, end_date))
        else:
            cursor.execute("""
                SELECT t.name, COUNT(*) as frequency
                FROM Techniques t
                JOIN ClassTechniques ct ON t.technique_id = ct.technique_id
                JOIN ClassImages ci ON ct.class_image_id = ci.class_image_id
                WHERE ci.date_taken BETWEEN ? AND ?
                AND t.category = ?
                GROUP BY t.technique_id
                ORDER BY frequency DESC
                LIMIT 1
            """, (start_date, end_date, category))
        
        top_technique_result = cursor.fetchone()
        top_technique = top_technique_result['name'] if top_technique_result and isinstance(top_technique_result, dict) else (
            top_technique_result[0] if top_technique_result else "None")
        
        # Get classes with techniques
        cursor.execute("""
            SELECT COUNT(DISTINCT ci.class_image_id) as class_count FROM ClassImages ci
            JOIN ClassTechniques ct ON ci.class_image_id = ct.class_image_id
            WHERE ci.date_taken BETWEEN ? AND ?
        """, (start_date, end_date))
        
        result = cursor.fetchone()
        classes_with_techniques = result['class_count'] if isinstance(result, dict) else result[0]
        
        # Get technique history
        query = """
            SELECT t.technique_id, t.name, t.category, 
                   COUNT(*) as frequency,
                   MAX(ci.date_taken) as last_taught
            FROM Techniques t
            JOIN ClassTechniques ct ON t.technique_id = ct.technique_id
            JOIN ClassImages ci ON ct.class_image_id = ci.class_image_id
            WHERE ci.date_taken BETWEEN ? AND ?
        """
        
        params = [start_date, end_date]
        
        if category != 'all':
            query += " AND t.category = ?"
            params.append(category)
        
        query += " GROUP BY t.technique_id"
        
        if sort_by == 'frequency':
            query += " ORDER BY frequency DESC"
        elif sort_by == 'recent':
            query += " ORDER BY last_taught DESC"
        elif sort_by == 'alphabetical':
            query += " ORDER BY t.name ASC"
        
        cursor.execute(query, params)
        technique_rows = cursor.fetchall()
        techniques = []
        
        for row in technique_rows:
            if isinstance(row, dict):
                techniques.append(dict(row))
            else:
                # Convert tuple to dict
                techniques.append({
                    'technique_id': row[0],
                    'name': row[1],
                    'category': row[2],
                    'frequency': row[3],
                    'last_taught': row[4]
                })
        
        conn.close()
        
        return jsonify({
            "success": True,
            "stats": {
                "total_techniques": total_techniques,
                "top_technique": top_technique,
                "classes_with_techniques": classes_with_techniques,
                "date_range": {
                    "start": start_date,
                    "end": end_date,
                    "days": days
                }
            },
            "techniques": techniques
        }), 200
    except Exception as e:
        logger.error(f"Error getting techniques history: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

def get_or_create_placeholder():
    """Get placeholder image or create one if it doesn't exist."""
    placeholder_path = os.path.join(PROCESSED_FOLDER, "placeholder.jpg")
    
    # If placeholder exists, return its path
    if os.path.exists(placeholder_path):
        return placeholder_path
        
    # Otherwise, create a simple placeholder image
    try:
        # Create a directory if it doesn't exist
        os.makedirs(PROCESSED_FOLDER, exist_ok=True)
        
        # Create a simple placeholder image
        img = Image.new('RGB', (400, 300), color=(240, 240, 240))
        d = ImageDraw.Draw(img)
        d.text((150, 150), "Image Not Found", fill=(100, 100, 100))
        
        # Save the image
        img.save(placeholder_path)
        logger.info(f"Created placeholder image at {placeholder_path}")
        
        return placeholder_path
    except Exception as e:
        logger.error(f"Failed to create placeholder image: {e}")
        return None

@app.route('/pictures/processed/<path:filename>')
def serve_processed_picture(filename):
    """Serve processed class images."""
    try:
        # First try to serve from the PROCESSED_FOLDER
        filepath = os.path.join(PROCESSED_FOLDER, filename)
        if os.path.exists(filepath):
            return send_from_directory(PROCESSED_FOLDER, filename)
            
        # If not found, try to find the file in the database
        try:
            conn = create_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Try to find the image by filename
            cursor.execute("""
                SELECT filepath_processed FROM ClassImages 
                WHERE original_filename = ?
            """, (filename,))
            
            result = cursor.fetchone()
            if result and result['filepath_processed']:
                full_path = result['filepath_processed']
                logger.info(f"Found full path in database: {full_path}")
                
                if os.path.exists(full_path):
                    # Use send_file with the absolute path
                    from flask import send_file
                    return send_file(full_path)
            
            conn.close()
        except Exception as e:
            logger.error(f"Error querying database for image: {e}")
        
        # If still not found, serve placeholder
        logger.warning(f"Processed image not found: {filename}. Serving placeholder.")
        placeholder_path = get_or_create_placeholder()
        if placeholder_path and os.path.exists(placeholder_path):
            return send_from_directory(os.path.dirname(placeholder_path), os.path.basename(placeholder_path))
        
        # If placeholder creation failed, return 404
        abort(404)
    except Exception as e:
        logger.error(f"Error serving processed picture {filename}: {e}")
        abort(500)

@app.route('/pictures/incoming/<path:filename>')
def serve_incoming_image(filename):
    """Serve images from the incoming directory."""
    logger.info(f"Incoming image request: {filename}")
    try:
        # Ensure the path is safe
        safe_filename = os.path.basename(filename)
        filepath = os.path.join(UPLOAD_FOLDER, safe_filename)
        
        logger.info(f"Attempting to serve incoming image: {filepath}")
        
        if os.path.exists(filepath):
            logger.info(f"Found and serving incoming image: {filepath}")
            response = send_from_directory(UPLOAD_FOLDER, safe_filename)
            # Add CORS headers explicitly
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            return response
        
        # If not found, try to find in database by instagram shortcode
        if "instagram_" in filename and filename.endswith(".jpg"):
            try:
                shortcode = filename.replace("instagram_", "").replace(".jpg", "")
                logger.info(f"Trying to find Instagram image with shortcode: {shortcode}")
                
                conn = create_connection()
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Try to find the image by Instagram shortcode
                cursor.execute("""
                    SELECT original_filename, filepath_processed FROM ClassImages 
                    WHERE instagram_shortcode = ?
                """, (shortcode,))
                
                result = cursor.fetchone()
                if result:
                    # Try filepath_processed first
                    if result['filepath_processed'] and os.path.exists(result['filepath_processed']):
                        logger.info(f"Serving Instagram image from full path: {result['filepath_processed']}")
                        from flask import send_file
                        response = send_file(result['filepath_processed'])
                        response.headers['Access-Control-Allow-Origin'] = '*'
                        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                        return response
                    
                    # Then try original_filename
                    if result['original_filename']:
                        alt_path = os.path.join(UPLOAD_FOLDER, result['original_filename'])
                        if os.path.exists(alt_path):
                            logger.info(f"Serving Instagram image from alt path: {alt_path}")
                            response = send_from_directory(UPLOAD_FOLDER, result['original_filename'])
                            response.headers['Access-Control-Allow-Origin'] = '*'
                            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                            return response
                
                # Also try raw shortcode (without instagram_ prefix)
                instagram_file = f"{shortcode}.jpg"
                instagram_path = os.path.join(UPLOAD_FOLDER, instagram_file)
                if os.path.exists(instagram_path):
                    logger.info(f"Serving Instagram image with raw shortcode: {instagram_path}")
                    response = send_from_directory(UPLOAD_FOLDER, instagram_file)
                    response.headers['Access-Control-Allow-Origin'] = '*'
                    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                    return response
                
                # Log what we found in the database
                logger.warning(f"Instagram shortcode {shortcode} not found or no matching files on disk")
                
                conn.close()
            except Exception as e:
                logger.error(f"Error finding Instagram image by shortcode: {e}")
                logger.error(traceback.format_exc())
        
        # Also check if the filename might be available without the instagram_ prefix
        if filename.startswith("instagram_"):
            raw_filename = filename.replace("instagram_", "")
            raw_filepath = os.path.join(UPLOAD_FOLDER, raw_filename)
            if os.path.exists(raw_filepath):
                logger.info(f"Found image without instagram_ prefix: {raw_filepath}")
                response = send_from_directory(UPLOAD_FOLDER, raw_filename)
                response.headers['Access-Control-Allow-Origin'] = '*'
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                return response
        
        # Log what images are actually available in the directory
        try:
            available_files = os.listdir(UPLOAD_FOLDER)
            logger.info(f"Files available in {UPLOAD_FOLDER}: {available_files}")
        except Exception as e:
            logger.error(f"Error listing directory: {e}")
        
        # If image is still not found, create and serve placeholder
        logger.warning(f"Incoming image not found: {filename}. Serving placeholder.")
        placeholder_path = get_or_create_placeholder()
        if placeholder_path and os.path.exists(placeholder_path):
            response = send_from_directory(os.path.dirname(placeholder_path), os.path.basename(placeholder_path))
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            return response
        
        # If placeholder doesn't exist or fails, return 404
        abort(404)
    except Exception as e:
        logger.error(f"Error serving incoming image {filename}: {e}")
        logger.error(traceback.format_exc())
        abort(500)

@app.route('/data/face_crops/<path:filename>')
def serve_face_crop_2(filename):
    """Serve face crop images (alternate route)."""
    try:
        filepath = os.path.join(FACE_CROPS_FOLDER, filename)
        if os.path.exists(filepath):
            return send_from_directory(FACE_CROPS_FOLDER, filename)
            
        # If not found, serve placeholder
        logger.warning(f"Face crop not found: {filename}. Serving placeholder.")
        placeholder_path = get_or_create_placeholder()
        if placeholder_path and os.path.exists(placeholder_path):
            return send_from_directory(os.path.dirname(placeholder_path), os.path.basename(placeholder_path))
        
        # If placeholder creation failed, return 404
        abort(404)
    except Exception as e:
        logger.error(f"Error serving face crop {filename}: {e}")
        abort(500)

@app.route('/api/images/direct-serve', methods=['GET'])
def serve_image_by_path():
    """Directly serve an image from its full filepath."""
    try:
        filepath = request.args.get('path')
        logger.info(f"Direct serve request for path: {filepath}")
        
        if not filepath:
            return jsonify({"error": "No file path provided"}), 400
            
        # Security check - make sure the path is within allowed directories
        safe_path = os.path.abspath(filepath)
        logger.info(f"Resolved safe path: {safe_path}")
        
        if not (safe_path.startswith(UPLOAD_FOLDER) or 
                safe_path.startswith(PROCESSED_FOLDER) or
                safe_path.startswith(FACE_CROPS_FOLDER) or
                safe_path.startswith(REPRESENTATIVE_PERSONS_FOLDER)):
            logger.warning(f"Attempted to access unauthorized path: {filepath}")
            return jsonify({"error": "Access to this file path is not allowed"}), 403
            
        if not os.path.exists(safe_path) or not os.path.isfile(safe_path):
            logger.warning(f"File not found at path: {safe_path}")
            return jsonify({"error": "File not found"}), 404
            
        # Serve the file directly
        from flask import send_file, current_app
        logger.info(f"Serving file directly from path: {safe_path}")
        response = send_file(safe_path)
        
        # Add CORS headers explicitly
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        
        return response
            
    except Exception as e:
        logger.error(f"Error serving file by path: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/debug-image')
def debug_image():
    """Render a debug page to check image loading directly."""
    logger.info("Rendering image debug page")
    return render_template('debug_image.html')

@app.route('/api/images/data-url', methods=['GET'])
def serve_image_as_data_url():
    """Serve an image as a data URL that can be embedded directly in HTML."""
    try:
        # Check for image_id first
        image_id = request.args.get('id')
        if image_id:
            logger.info(f"Data URL request for image ID: {image_id}")
            try:
                # Get the image path from database
                conn = create_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT filepath_processed as processed_image_path FROM ClassImages WHERE class_image_id = ?", 
                    (image_id,)
                )
                result = cursor.fetchone()
                conn.close()
                
                if result and result[0]:
                    path = result[0]
                    logger.info(f"Found path for image ID {image_id}: {path}")
                else:
                    logger.warning(f"No image found for ID {image_id}")
                    return jsonify({"error": "Image not found"}), 404
            except Exception as e:
                logger.error(f"Database error looking up image ID {image_id}: {e}")
                return jsonify({"error": f"Error looking up image: {str(e)}"}), 500
        else:
            # Try path or shortcode if no ID provided
            path = request.args.get('path')
            if not path:
                # Try shortcode
                shortcode = request.args.get('shortcode')
                if shortcode:
                    path = os.path.join(UPLOAD_FOLDER, f"instagram_{shortcode}.jpg")
                else:
                    return jsonify({"error": "No path, id, or shortcode provided"}), 400
        
        logger.info(f"Data URL request for path: {path}")
        
        # Security check for path
        safe_path = os.path.abspath(path)
        if not (safe_path.startswith(UPLOAD_FOLDER) or 
                safe_path.startswith(PROCESSED_FOLDER) or
                safe_path.startswith(FACE_CROPS_FOLDER) or
                safe_path.startswith(REPRESENTATIVE_PERSONS_FOLDER)):
            logger.warning(f"Attempted to access unauthorized path: {path}")
            return jsonify({"error": "Access to this file path is not allowed"}), 403
        
        if not os.path.exists(safe_path) or not os.path.isfile(safe_path):
            logger.warning(f"File not found at path: {safe_path}")
            return jsonify({"error": "File not found"}), 404
        
        # Read the file and convert to base64
        with open(safe_path, 'rb') as img_file:
            img_data = img_file.read()
            
        # Determine mime type
        import mimetypes
        mime_type, _ = mimetypes.guess_type(safe_path)
        if not mime_type:
            mime_type = 'image/jpeg'  # Default to JPEG
        
        # Create the data URL
        encoded = base64.b64encode(img_data).decode('utf-8')
        data_url = f"data:{mime_type};base64,{encoded}"
        
        # Return the data URL
        return jsonify({
            "success": True,
            "data_url": data_url,
            "mime_type": mime_type,
            "file_size": len(img_data)
        })
        
    except Exception as e:
        logger.error(f"Error serving image as data URL: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/api/persons/<person_id>', methods=['GET'])
def get_person_details(person_id):
    """Get basic details for a specific person."""
    try:
        # Get person info
        person_info = get_person_by_id(person_id)
        if not person_info:
            logger.warning(f"Person {person_id} not found")
            return jsonify({
                "success": False,
                "error": f"Person {person_id} not found"
            }), 404
        
        # Include representative image URL if available
        if person_info.get('representative_image_path'):
            rep_image_path = person_info['representative_image_path']
            person_info['image_url'] = f"/data/representative_persons/{os.path.basename(rep_image_path)}"
        
        # Return person info
        return jsonify({
            "success": True,
            "person_info": person_info
        })
    except Exception as e:
        logger.error(f"Error getting person details: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)