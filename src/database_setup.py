"""
Database setup script for BJJ attendance tracking system.
"""
import sqlite3
import os
import sys

# Define the database file path relative to the project root
# Assuming this script might be run from project root or src/
# If run from src/, '..' goes to project root.
# If run from project root, '.' is project root.
# Let's make it robust by always finding the project root relative to this file's location.
CURRENT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_SCRIPT_DIR, '..'))
DB_NAME = os.environ.get('DB_NAME', "bjj_attendance.db")
DB_FILE = os.path.join(PROJECT_ROOT, DB_NAME)

# Print diagnostics
print(f"Database setup script running in: {os.getcwd()}")
print(f"Script directory: {CURRENT_SCRIPT_DIR}")
print(f"Project root: {PROJECT_ROOT}")
print(f"Database name: {DB_NAME}")
print(f"Database file path: {DB_FILE}")
print(f"Directory exists? {os.path.exists(PROJECT_ROOT)}")
print(f"Directory writeable? {os.access(PROJECT_ROOT, os.W_OK)}")

def create_connection(db_file_path):
    """ Create a database connection to the SQLite database specified by db_file_path """
    conn = None
    try:
        conn = sqlite3.connect(db_file_path)
        print(f"SQLite version: {sqlite3.sqlite_version}")
        print(f"Connected to database at: {db_file_path}")
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        raise e

def create_tables(conn):
    """ Create all necessary tables in the database """
    try:
        c = conn.cursor()
        
        # Drop existing tables if they exist to avoid column mismatch
        tables_to_drop = [
            'ClassTechniques',
            'Techniques',
            'PersonFeatures',
            'Detections',
            'ClassImages',
            'Persons'
        ]
        
        for table in tables_to_drop:
            c.execute(f'DROP TABLE IF EXISTS {table}')
        
        # Create Persons table
        c.execute('''
        CREATE TABLE IF NOT EXISTS Persons (
            person_id TEXT PRIMARY KEY,
            name TEXT,
            enrollment_date TEXT,
            representative_image_path TEXT,
            representative_feature_path TEXT,
            last_updated TEXT,
            notes TEXT
        )
        ''')

        # Create ClassImages table
        c.execute('''
        CREATE TABLE IF NOT EXISTS ClassImages (
            class_image_id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_filename TEXT,
            filepath_processed TEXT,
            date_taken TEXT,
            processing_status TEXT,
            processing_error_message TEXT,
            instagram_shortcode TEXT,
            instagram_caption TEXT,
            instagram_post_url TEXT,
            upload_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            last_updated TEXT
        )
        ''')

        # Create Detections table
        c.execute('''
        CREATE TABLE IF NOT EXISTS Detections (
            detection_id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_image_id INTEGER,
            person_id TEXT,
            face_crop_path TEXT,
            feature_vector BLOB,
            bbox_x1 INTEGER,
            bbox_y1 INTEGER,
            bbox_x2 INTEGER,
            bbox_y2 INTEGER,
            original_assigned_person_id TEXT,
            is_verified_by_user BOOLEAN DEFAULT 0,
            verified_by_user_id TEXT,
            verification_timestamp TEXT,
            recognition_confidence REAL,
            face_quality_score REAL,
            face_angle_pitch REAL,
            face_angle_yaw REAL,
            face_angle_roll REAL,
            brightness_score REAL,
            contrast_score REAL,
            sharpness_score REAL,
            FOREIGN KEY (class_image_id) REFERENCES ClassImages (class_image_id) ON DELETE CASCADE,
            FOREIGN KEY (person_id) REFERENCES Persons (person_id)
        )
        ''')

        # Create PersonFeatures table with face angle columns
        c.execute('''
        CREATE TABLE IF NOT EXISTS PersonFeatures (
            feature_id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id TEXT,
            feature_vector BLOB,
            source_detection_id INTEGER,
            quality_score REAL,
            face_angle_pitch REAL,
            face_angle_yaw REAL,
            face_angle_roll REAL,
            is_representative BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            date_added TEXT,
            FOREIGN KEY (person_id) REFERENCES Persons (person_id) ON DELETE CASCADE,
            FOREIGN KEY (source_detection_id) REFERENCES Detections (detection_id)
        )
        ''')

        # Create Techniques table
        c.execute('''
        CREATE TABLE IF NOT EXISTS Techniques (
            technique_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            category TEXT DEFAULT 'technique',  -- 'technique' or 'position'
            description TEXT,
            last_updated TEXT
        )
        ''')

        # Create ClassTechniques table (junction table)
        c.execute('''
        CREATE TABLE IF NOT EXISTS ClassTechniques (
            class_technique_id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_image_id INTEGER,
            technique_id INTEGER,
            confidence REAL DEFAULT 1.0,
            extraction_method TEXT DEFAULT 'gpt',  -- 'gpt', 'regex', 'manual'
            FOREIGN KEY (class_image_id) REFERENCES ClassImages (class_image_id) ON DELETE CASCADE,
            FOREIGN KEY (technique_id) REFERENCES Techniques (technique_id)
        )
        ''')

        # Commit the table creation first
        conn.commit()

        # Now create indices
        c.execute('CREATE INDEX IF NOT EXISTS idx_detections_person_id ON Detections (person_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_detections_class_image_id ON Detections (class_image_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_person_features_person_id ON PersonFeatures (person_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_class_techniques_class_image_id ON ClassTechniques (class_image_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_class_techniques_technique_id ON ClassTechniques (technique_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_techniques_name ON Techniques (name)')

        # Commit the index creation
        conn.commit()
        print("All tables and indices created successfully")
        
    except sqlite3.Error as e:
        print(f"Error creating tables: {e}")
        raise e

def initialize_database():
    """Initialize the database: connect and create tables."""
    print(f"Initializing database at: {DB_FILE}")
    
    # Ensure the directory for the DB exists (though for project root, it usually does)
    db_dir = os.path.dirname(DB_FILE)
    if db_dir and not os.path.exists(db_dir): # Check if db_dir is not empty (e.g. if DB_FILE is just 'name.db')
        os.makedirs(db_dir, exist_ok=True)
        print(f"Created directory for database: {db_dir}")

    # Test if we can write to the location
    try:
        # Create a test file to verify write permissions
        test_file = os.path.join(PROJECT_ROOT, ".db_test_file")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        print(f"Verified write permission to {PROJECT_ROOT}")
    except Exception as e:
        print(f"WARNING: Write permission test failed: {e}")
        print("Will attempt to create database anyway...")

    try:
        conn = create_connection(DB_FILE)
        if conn is not None:
            create_tables(conn)
            conn.close()
            print("Database initialization process complete.")
            return True
        else:
            print("Failed to create database connection. Tables not created.")
            return False
    except Exception as e:
        print(f"Error during database initialization: {e}")
        return False

def main():
    """ Main function to set up the database """
    try:
        success = initialize_database()
        # Example: You can add a check here to see if the DB file was created
        if os.path.exists(DB_FILE):
            print(f"Database file '{DB_NAME}' is present at '{PROJECT_ROOT}'.")
            print(f"File size: {os.path.getsize(DB_FILE)} bytes")
            print(f"File permissions: {oct(os.stat(DB_FILE).st_mode)}")
            return 0
        else:
            print(f"Database file '{DB_NAME}' was NOT created at '{PROJECT_ROOT}'. Check permissions or errors.")
            return 1
    except Exception as e:
        print(f"Database setup failed: {e}")
        return 1

if __name__ == '__main__':
    print("Running Database Setup...")
    exit_code = main()
    sys.exit(exit_code)