#!/usr/bin/env python
"""
Script to initialize the BJJ attendance database with the correct schema.
"""
import os
import sqlite3
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("init_database")

# Database path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(CURRENT_DIR, 'bjj_attendance.db')

def init_database():
    """Initialize the database with the correct schema."""
    try:
        # Connect to the database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        # Begin transaction
        cursor.execute("BEGIN TRANSACTION;")
        
        # Create ClassImages table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ClassImages (
            class_image_id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_filename TEXT,
            filepath_processed TEXT,
            date_taken TEXT,
            processing_status TEXT,
            error_message TEXT,
            instagram_shortcode TEXT,
            instagram_caption TEXT,
            instagram_post_url TEXT,
            processed_image_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create Persons table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS Persons (
            person_id TEXT PRIMARY KEY,
            name TEXT,
            representative_image_path TEXT,
            representative_feature_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create Detections table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS Detections (
            detection_id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_image_id INTEGER,
            person_id TEXT,
            face_crop_path TEXT,
            feature_vector BLOB,
            confidence REAL,
            original_assigned_person_id TEXT,
            is_verified BOOLEAN DEFAULT 0,
            bbox_x1 REAL,
            bbox_y1 REAL,
            bbox_x2 REAL,
            bbox_y2 REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_image_id) REFERENCES ClassImages(class_image_id),
            FOREIGN KEY (person_id) REFERENCES Persons(person_id)
        )
        ''')
        
        # Create Techniques table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS Techniques (
            technique_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create ClassTechniques table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ClassTechniques (
            class_technique_id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_image_id INTEGER,
            technique_id INTEGER,
            confidence REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_image_id) REFERENCES ClassImages(class_image_id),
            FOREIGN KEY (technique_id) REFERENCES Techniques(technique_id)
        )
        ''')
        
        # Commit the transaction
        conn.commit()
        logger.info("Database schema initialized successfully.")
        
        # Check if tables were created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        logger.info("Tables in database:")
        for table in tables:
            logger.info(f"  {table[0]}")
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        logger.error(f"SQLite error: {e}")
        return False
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False

if __name__ == "__main__":
    logger.info(f"Starting database initialization for: {DB_PATH}")
    success = init_database()
    if success:
        logger.info("Database initialization completed successfully.")
    else:
        logger.error("Database initialization failed.") 