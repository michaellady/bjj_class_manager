"""
Flask application for BJJ class attendance tracking system.
"""
import os
import sys
import logging
import json
from datetime import datetime
import sqlite3
from flask import Flask, render_template, request, jsonify, send_from_directory, abort
from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# Initialize Flask app
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload size
CORS(app)

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
    return render_template('index.html')

@app.route('/health')
def health_check():
    """Detailed health check endpoint for GitHub Actions testing."""
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

@app.route('/api/images/upload', methods=['POST'])
def upload_image():
    """Upload a class photo from URL."""
    try:
        # Get image URL from request
        image_url = request.form.get('image_url')
        date = request.form.get('date')
        caption = request.form.get('caption', '')
        
        if not image_url:
            return jsonify({"error": "No image URL provided"}), 400
        
        logger.info(f"Received upload request with URL: {image_url}")
        
        # Mock processing
        image_id = 123  # In a real app, this would be from the database
        
        # Return success response
        return jsonify({
            "success": True,
            "message": "Image uploaded successfully",
            "image_id": image_id
        }), 201
        
    except Exception as e:
        logger.error(f"Error uploading image: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/images/<int:image_id>/detections', methods=['GET'])
def get_detections(image_id):
    """Get detections for a class image."""
    # Mock data for testing
    detections = []
    for i in range(18):  # Simulate 18 faces
        detections.append({
            "detection_id": i + 1,
            "person_id": f"test_person_{i}",
            "face_crop_path": f"/static_crops/test_face_{i}.jpg",
            "confidence": 0.95
        })
    
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
    # Mock data for testing
    new_person_id = f"new_person_{detection_id}"
    
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
    
    # Mock update
    logger.info(f"Updated person {person_id} with name: {name}")
    
    return jsonify({
        "success": True,
        "person_id": person_id,
        "name": name
    }), 200

@app.route('/api/images/<int:image_id>/attendance', methods=['GET'])
def get_attendance(image_id):
    """Get attendance for a class."""
    # Mock data for testing
    attendees = []
    for i in range(18):
        attendees.append({
            "person_id": f"test_person_{i}",
            "name": f"Test Person {i}",
            "confidence": 0.95
        })
    
    return jsonify({
        "class_image_id": image_id,
        "date": "2025-06-02",
        "attendees": attendees
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)