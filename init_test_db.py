#!/usr/bin/env python3
"""
Initialize the test database and create necessary test data.
"""
import os
import sqlite3
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database settings
DB_NAME = os.environ.get('DB_NAME', 'test_bjj_attendance.db')
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), DB_NAME)

# Create necessary directories
TEST_DIRS = [
    'pictures/incoming',
    'data/face_crops',
    'data/representative_features',
    'data/representative_persons'
]

def create_test_directories():
    """Create necessary test directories."""
    for directory in TEST_DIRS:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"Created directory: {directory}")

def initialize_database():
    """Initialize the test database with necessary tables."""
    # Remove existing database file if it exists
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        logger.info(f"Removed existing database: {DB_PATH}")

    # Create a new database with the required schema
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create ClassImages table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ClassImages (
        class_image_id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_filename TEXT,
        date_taken TEXT,
        filepath_processed TEXT,
        processing_status TEXT,
        instagram_shortcode TEXT,
        instagram_caption TEXT,
        instagram_post_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Create Persons table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Persons (
        person_id TEXT PRIMARY KEY,
        name TEXT,
        representative_image_path TEXT,
        representative_feature_vector BLOB,
        last_detected_date TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Create Detections table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Detections (
        detection_id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_image_id INTEGER,
        face_crop_path TEXT,
        feature_vector BLOB,
        person_id TEXT,
        original_assigned_person_id TEXT,
        confidence REAL,
        is_verified BOOLEAN,
        bounding_box TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (class_image_id) REFERENCES ClassImages(class_image_id),
        FOREIGN KEY (person_id) REFERENCES Persons(person_id)
    )
    ''')

    # Create Techniques table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Techniques (
        technique_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        category TEXT,
        last_updated TIMESTAMP
    )
    ''')

    # Create ClassTechniques table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ClassTechniques (
        class_technique_id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_image_id INTEGER,
        technique_id INTEGER,
        confidence REAL,
        extraction_method TEXT,
        FOREIGN KEY (class_image_id) REFERENCES ClassImages(class_image_id),
        FOREIGN KEY (technique_id) REFERENCES Techniques(technique_id)
    )
    ''')

    # Create some test data
    cursor.execute('''
    INSERT INTO Persons (person_id, name) VALUES 
    ('test_person_1', 'Test Person 1'),
    ('test_person_2', 'Test Person 2')
    ''')

    # Add a test technique
    cursor.execute('''
    INSERT INTO Techniques (name, category, last_updated) VALUES
    ('Arm Bar', 'technique', CURRENT_TIMESTAMP),
    ('Guard', 'position', CURRENT_TIMESTAMP)
    ''')

    # Commit changes and close connection
    conn.commit()
    conn.close()
    logger.info(f"Initialized database: {DB_PATH}")

if __name__ == '__main__':
    logger.info("Initializing test environment...")
    create_test_directories()
    initialize_database()
    logger.info("Test environment initialized successfully.") 