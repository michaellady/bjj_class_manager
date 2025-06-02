"""
Database access module for BJJ attendance tracking system.
"""
import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database file path (consistent with database_setup.py)
CURRENT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_SCRIPT_DIR, '..'))
DB_NAME = os.environ.get('DB_NAME', 'bjj_attendance.db')
DB_FILE = os.path.join(PROJECT_ROOT, DB_NAME)

def dict_factory(cursor: sqlite3.Cursor, row: tuple) -> dict:
    """Convert database row to dictionary."""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def get_db_connection():
    """Get a database connection."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = dict_factory
    return conn

# --- Persons Table Functions ---

def add_person(person_id: str, name: Optional[str], enrollment_date: str,
               representative_image_path: Optional[str] = None,
               representative_feature_path: Optional[str] = None,
               notes: Optional[str] = None) -> Optional[str]:
    """Add a new person to the database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        INSERT INTO Persons (
            person_id, name, enrollment_date,
            representative_image_path,
            representative_feature_path,
            notes, last_updated
        )
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            person_id, name, enrollment_date,
            representative_image_path,
            representative_feature_path,
            notes
        ))
        
        conn.commit()
        return person_id
    except sqlite3.Error as e:
        logger.error(f"Error adding person to database: {e}")
        return None
    finally:
        conn.close()

def get_person_by_id(person_id: str):
    """Get a person by their ID."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Persons WHERE person_id = ?", (person_id,))
        return cursor.fetchone()
    except sqlite3.Error as e:
        logger.error(f"Error getting person {person_id}: {e}")
        return None
    finally:
        conn.close()

def update_person_details(person_id: str, **kwargs) -> bool:
    """Update person details."""
    if not kwargs:
        return False
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
        query = f"UPDATE Persons SET {set_clause} WHERE person_id = ?"
        values = list(kwargs.values()) + [person_id]
        cursor.execute(query, values)
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating person details: {e}")
        return False
    finally:
        conn.close()

def get_all_persons():
    """Retrieves all persons from the database."""
    sql = "SELECT * FROM Persons ORDER BY enrollment_date DESC"
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        person_rows = cursor.fetchall()
        return [dict(row) for row in person_rows]
    except sqlite3.Error as e:
        logger.error(f"Database error getting all persons: {e}")
        return []

def delete_person(person_id: str) -> bool:
    """Deletes a person and all their associated data."""
    sql = "DELETE FROM Persons WHERE person_id = ?"
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (person_id,))
        conn.commit()
        if cursor.rowcount == 0:
            logger.warning(f"No person found with ID {person_id} to delete.")
            return False
        logger.info(f"Person {person_id} and associated data deleted successfully.")
        return True
    except sqlite3.Error as e:
        logger.error(f"Database error deleting person {person_id}: {e}")
        return False

# --- ClassImages Table Functions ---

def add_class_image(
    original_filename: str,
    date_taken: str,
    filepath_processed: str,
    processing_status: str = 'pending',
    instagram_shortcode: str = None,
    instagram_caption: str = None,
    instagram_post_url: str = None
) -> Optional[int]:
    """Add a new class image."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO ClassImages (
            original_filename,
            filepath_processed,
            date_taken,
            processing_status,
            instagram_shortcode,
            instagram_caption,
            instagram_post_url,
            last_updated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            original_filename,
            filepath_processed,
            date_taken,
            processing_status,
            instagram_shortcode,
            instagram_caption,
            instagram_post_url
        ))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        logger.error(f"Error adding class image: {e}")
        return None
    finally:
        conn.close()

def get_class_image_by_id(image_id: int):
    """Retrieves a class image by its image_id."""
    sql = "SELECT * FROM ClassImages WHERE class_image_id = ?"
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (image_id,))
        image_row = cursor.fetchone()
        return dict(image_row) if image_row else None
    except sqlite3.Error as e:
        print(f"Database error getting ClassImage {image_id}: {e}")
        return None
    finally:
        conn.close()

def get_pending_class_images():
    """Retrieves all class images with 'pending' status."""
    sql = "SELECT * FROM ClassImages WHERE processing_status = 'pending' ORDER BY upload_timestamp"
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        image_rows = cursor.fetchall()
        return [dict(row) for row in image_rows]
    except sqlite3.Error as e:
        print(f"Database error getting pending class images: {e}")
        return []
    finally:
        conn.close()

def update_class_image_status(image_id: int, status: str, error_message: Optional[str] = None) -> bool:
    """Update the processing status of a class image."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE ClassImages 
        SET processing_status = ?, processing_error_message = ?, last_updated = CURRENT_TIMESTAMP
        WHERE class_image_id = ?
        """, (status, error_message, image_id))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating class image status: {e}")
        return False

def delete_class_image(image_id: int):
    """Delete a class image and all associated detections."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ClassImages WHERE class_image_id = ?", (image_id,))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error deleting class image {image_id}: {e}")
        return False

def get_all_class_images(limit: int = None, offset: int = 0):
    """Get all class images with optional pagination."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if limit is not None:
            cursor.execute("""
            SELECT * FROM ClassImages 
            ORDER BY date_taken DESC 
            LIMIT ? OFFSET ?
            """, (limit, offset))
        else:
            cursor.execute("SELECT * FROM ClassImages ORDER BY date_taken DESC")
        return cursor.fetchall()
    except sqlite3.Error as e:
        logger.error("Error getting class images: {e}")
        return []

# --- Detections Table Functions ---

def add_detection(image_id: int, person_id: Optional[str], face_crop_path: str,
                 feature_vector: bytes, bbox_coords: List[float],
                 recognition_confidence: Optional[float] = None,
                 face_quality_score: Optional[float] = None,
                 face_angles: Optional[Tuple[float, float, float]] = None) -> Optional[int]:
    """Add a new detection."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO Detections (
            class_image_id, person_id, face_crop_path, feature_vector,
            bbox_x1, bbox_y1, bbox_x2, bbox_y2,
            recognition_confidence, face_quality_score,
            face_angle_pitch, face_angle_yaw, face_angle_roll
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            image_id, person_id, face_crop_path, feature_vector,
            int(bbox_coords[0]), int(bbox_coords[1]), 
            int(bbox_coords[2]), int(bbox_coords[3]),
            recognition_confidence, face_quality_score,
            face_angles[0] if face_angles else None,
            face_angles[1] if face_angles else None,
            face_angles[2] if face_angles else None
        ))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        logger.error(f"Error adding detection: {e}")
        return None
    finally:
        conn.close()

def get_detections_for_image(image_id: int):
    """Get all detections for a specific class image."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        SELECT * FROM Detections 
        WHERE class_image_id = ?
        ORDER BY detection_id
        """, (image_id,))
        return cursor.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Error getting detections for image {image_id}: {e}")
        return []

def get_detection_by_id(detection_id: int):
    """Retrieves a specific detection by its detection_id."""
    sql = """
    SELECT d.*, p.name as person_name
    FROM Detections d
    LEFT JOIN Persons p ON d.person_id = p.person_id
    WHERE d.detection_id = ?
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (detection_id,))
        detection_row = cursor.fetchone()
        return dict(detection_row) if detection_row else None
    except sqlite3.Error as e:
        print(f"Database error getting detection {detection_id}: {e}")
        return None
    finally:
        conn.close()

def update_detection_assignment(detection_id: int, new_person_id: str = None,
                                is_verified: bool = False, verified_by_user_id: str = None,
                                original_assigned_person_id_to_set: str = None):
    """Updates a detection's assigned person_id and verification status."""
    
    current_detection = get_detection_by_id(detection_id)
    if not current_detection:
        print(f"No detection found with ID {detection_id} to update.")
        return False

    fields_to_update = []
    params = []

    # Only update person_id if it's actually changing
    if new_person_id is not None and new_person_id != current_detection.get('person_id'):
        fields_to_update.append("person_id = ?")
        params.append(new_person_id)
        # If original_assigned_person_id_to_set is provided, use it. Otherwise, use current person_id.
        # This handles the first correction and subsequent corrections.
        o_person_id = original_assigned_person_id_to_set if original_assigned_person_id_to_set is not None else current_detection.get('person_id')
        if o_person_id != new_person_id : # Only set original if it's different from new one
             fields_to_update.append("original_assigned_person_id = ?")
             params.append(o_person_id)

    # Update verification status
    fields_to_update.append("is_verified_by_user = ?")
    params.append(1 if is_verified else 0)
    
    if is_verified:
        fields_to_update.append("verification_timestamp = ?")
        params.append(datetime.now().isoformat())
        if verified_by_user_id:
            fields_to_update.append("verified_by_user_id = ?")
            params.append(verified_by_user_id)
    
    if not fields_to_update:
        print(f"No changes to apply for detection {detection_id}.")
        return False

    sql = f"UPDATE Detections SET {', '.join(fields_to_update)} WHERE detection_id = ?"
    params.append(detection_id)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, tuple(params))
        conn.commit()
        print(f"Detection {detection_id} updated. Assigned to {new_person_id if new_person_id is not None else 'None'}, Verified: {is_verified}")
        return True
    except sqlite3.Error as e:
        print(f"Database error updating detection {detection_id}: {e}")
        return False
    finally:
        conn.close()

def get_detections_for_person(person_id: str):
    """Get all detections for a person with enhanced quality metrics."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        SELECT 
            d.*,
            ci.date_taken,
            ci.original_filename,
            ci.filepath_processed
        FROM Detections d
        JOIN ClassImages ci ON d.class_image_id = ci.class_image_id
        WHERE d.person_id = ?
        ORDER BY ci.date_taken DESC
        """, (person_id,))
        return cursor.fetchall()
    finally:
        conn.close()

def delete_detection(detection_id: int):
    """Deletes a specific detection record."""
    sql = "DELETE FROM Detections WHERE detection_id = ?"
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (detection_id,))
        conn.commit()
        if cursor.rowcount == 0:
            print(f"No detection found with ID {detection_id} to delete.")
            return False
        print(f"Detection {detection_id} deleted successfully.")
        return True
    except sqlite3.Error as e:
        print(f"Database error deleting detection {detection_id}: {e}")
        return False
    finally:
        conn.close()

# --- PersonFeatures Table Functions ---

def add_person_feature(person_id: str, feature_vector: bytes, source_detection_id: int = None,
                      quality_score: float = None, face_angles: Optional[Tuple[float, float, float]] = None):
    """Add a feature vector for a person."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO PersonFeatures (
            person_id, feature_vector, source_detection_id, quality_score,
            face_angle_pitch, face_angle_yaw, face_angle_roll,
            date_added
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            person_id, feature_vector, source_detection_id, quality_score,
            face_angles[0] if face_angles else None,
            face_angles[1] if face_angles else None,
            face_angles[2] if face_angles else None
        ))
        conn.commit()
        feature_id = cursor.lastrowid
        logger.info(f"Added feature {feature_id} for person {person_id}")
        return feature_id
    except sqlite3.Error as e:
        logger.error(f"Error adding feature for person {person_id}: {e}")
        return None
    finally:
        conn.close()

def get_features_for_person(person_id: str, limit: int = None):
    """Get features for a person."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if limit:
            cursor.execute("""
            SELECT * FROM PersonFeatures 
            WHERE person_id = ? AND is_active = 1
            ORDER BY date_added DESC LIMIT ?
            """, (person_id, limit))
        else:
            cursor.execute("""
            SELECT * FROM PersonFeatures 
            WHERE person_id = ? AND is_active = 1
            ORDER BY date_added DESC
            """, (person_id,))
        return cursor.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Error getting features for person {person_id}: {e}")
        return []
    finally:
        conn.close()

def delete_features_for_person(person_id: str):
    """Deletes all feature vectors for a given person_id.
    Useful during person merge operations or if a person is deleted and ON DELETE CASCADE is not set from Persons to PersonFeatures for features.
    (Our schema has ON DELETE CASCADE from Persons to PersonFeatures, so this might be redundant for person deletion but useful for merges before deleting the person record).
    """
    sql = "DELETE FROM PersonFeatures WHERE person_id = ?"
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (person_id,))
        conn.commit()
        print(f"{cursor.rowcount} features deleted for person {person_id}.")
        return cursor.rowcount
    except sqlite3.Error as e:
        print(f"Database error deleting features for person {person_id}: {e}")
        return 0
    finally:
        conn.close()

def get_class_image(image_id: int):
    """Get details for a specific class image."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ClassImages WHERE class_image_id = ?", (image_id,))
        return cursor.fetchone()
    except sqlite3.Error as e:
        logger.error(f"Error getting class image {image_id}: {e}")
        return None

def get_representative_features():
    """Get all representative features for all persons."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        SELECT pf.*, p.name 
        FROM PersonFeatures pf
        JOIN Persons p ON p.person_id = pf.person_id
        WHERE pf.is_representative = 1 AND pf.is_active = 1
        """)
        return cursor.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Error getting representative features: {e}")
        return []

def mark_feature_as_representative(feature_id: int, person_id: str) -> bool:
    """Mark a feature as representative."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # First, unmark any existing representative features
        cursor.execute("""
        UPDATE PersonFeatures 
        SET is_representative = 0 
        WHERE person_id = ? AND is_representative = 1
        """, (person_id,))
        
        # Then mark the new representative feature
        cursor.execute("""
        UPDATE PersonFeatures 
        SET is_representative = 1 
        WHERE feature_id = ? AND person_id = ?
        """, (feature_id, person_id))
        
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error marking feature {feature_id} as representative: {e}")
        return False
    finally:
        conn.close()

def verify_detection(detection_id: int, person_id: str, verified_by: str) -> bool:
    """Mark a detection as verified by a user."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE Detections 
        SET is_verified_by_user = 1,
            verified_by_user_id = ?,
            verification_timestamp = CURRENT_TIMESTAMP,
            person_id = ?
        WHERE detection_id = ?
        """, (verified_by, person_id, detection_id))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error verifying detection {detection_id}: {e}")
        return False

def update_person_name(person_id: str, new_name: str) -> bool:
    """Updates a person's name."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE Persons 
        SET name = ?, last_updated = CURRENT_TIMESTAMP
        WHERE person_id = ?
        """, (new_name, person_id))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating person name: {e}")
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    print("Running data_access.py for testing...")
    # Ensure database and tables exist by running database_setup.py first
    
    # Test Persons functions
    test_person_id = "test-person-001"
    test_person_id2 = "test-person-002"

    print(f"\nAttempting to add person: {test_person_id}")
    add_person(test_person_id, "Test Person One", representative_image_path="path/to/img1.jpg")
    
    print(f"\nAttempting to add person: {test_person_id2}")
    add_person(test_person_id2, "Test Person Two", representative_feature_path="path/to/feat2.npy")

    print("\nGetting all persons:")
    all_p = get_all_persons()
    for p_item in all_p: # Renamed loop variable
        print(p_item)

    print(f"\nGetting person by ID: {test_person_id}")
    person = get_person_by_id(test_person_id)
    print(person)

    print(f"\nUpdating person: {test_person_id}")
    update_person_details(test_person_id, name="Test Person One Updated", representative_feature_path="path/to/new_feat1.npy")
    person_updated = get_person_by_id(test_person_id)
    print(person_updated)
    print("\n--- Testing Complete for Persons ---")

    # Test ClassImages functions
    print("\n--- Testing ClassImages Functions ---")
    test_image_file = "test_image_01.jpg"
    test_date_taken = datetime.now().isoformat()
    img_id1 = None # Initialize img_id1
    
    print(f"Attempting to add ClassImage: {test_image_file}")
    img_id1 = add_class_image(test_image_file, test_date_taken, filepath_processed=f"processed/{test_image_file}")
    
    if img_id1:
        print(f"\nGetting ClassImage by ID: {img_id1}")
        img1 = get_class_image_by_id(img_id1)
        print(img1)

        print(f"\nUpdating ClassImage status for ID: {img_id1}")
        update_class_image_status(img_id1, "completed")
        img1_updated = get_class_image_by_id(img_id1)
        print(img1_updated)

    print("\nAdding another image to test pending...")
    img_id2_pending = add_class_image("test_image_02.jpg", datetime.now().isoformat(), processing_status="pending")
    
    print("\nGetting pending ClassImages:")
    pending_images = get_pending_class_images()
    for img_p_item in pending_images: # Renamed loop variable
        print(img_p_item)

    print("\n--- Testing get_all_class_images ---")
    all_images_test = get_all_class_images()
    print(f"Found {len(all_images_test)} total class images.")
    completed_images_test = get_all_class_images(status="completed")
    print(f"Found {len(completed_images_test)} completed class images.")
    paginated_images_test = get_all_class_images(limit=1, offset=0)
    print(f"Found {len(paginated_images_test)} paginated class images (limit 1, offset 0).")
    print("\n--- Testing Complete for ClassImages ---")

    # Test Detections functions
    print("\n--- Testing Detections Functions ---")
    det_id1 = None # Initialize
    det_id2_unknown = None # Initialize
    if img_id1 and test_person_id:
        print(f"Attempting to add detection for image_id {img_id1} and person_id {test_person_id}")
        dummy_feature_bytes = sqlite3.Binary(b'\x00\x01\x02\x03\x04')
        det_id1 = add_detection(
            image_id=img_id1,
            person_id=test_person_id,
            face_crop_path=f"crops/img{img_id1}_det1.jpg",
            bbox_coords=[10, 20, 60, 80],
            recognition_confidence=0.95,
            face_quality_score=0.9,
            face_angles=(0, 0, 0)
        )
        det_id2_unknown = add_detection(
            image_id=img_id1,
            face_crop_path=f"crops/img{img_id1}_det2_unknown.jpg",
            bbox_coords=[100, 20, 150, 80],
            feature_vector=sqlite3.Binary(b'\x05\x06\x07\x08'),
            recognition_confidence=0.9,
            face_quality_score=0.8,
            face_angles=(0, 0, 0)
        )

        if det_id1:
            print(f"\nGetting detection by ID: {det_id1}")
            det1 = get_detection_by_id(det_id1)
            print(det1)

            print(f"\nUpdating detection assignment for ID: {det_id1}")
            update_detection_assignment(det_id1, new_person_id=test_person_id2, is_verified=True)
            det1_updated = get_detection_by_id(det_id1)
            print(det1_updated)
        
        print(f"\nGetting detections for image_id {img_id1}:")
        img_detections = get_detections_for_image(img_id1)
        for det_item in img_detections:
            print(det_item)

        print(f"\nGetting detections for person_id {test_person_id2} (after correction):")
        person_detections = get_detections_for_person(test_person_id2)
        for p_det_item in person_detections:
            print(p_det_item)
        
        # Test PersonFeatures functions
        print("\n--- Testing PersonFeatures Functions ---")
        if det_id1:
            print(f"Adding feature for person {test_person_id2} from detection {det_id1}")
            feat_id1 = add_person_feature(test_person_id2, dummy_feature_bytes, source_detection_id=det_id1)
            add_person_feature(test_person_id2, sqlite3.Binary(b'\x0A\x0B\x0C'), source_detection_id=None)

            if feat_id1:
                print(f"\nGetting features for person {test_person_id2}:")
                features_p2 = get_features_for_person(test_person_id2)
                for f_p2_item in features_p2:
                    print(f"  Feature ID: {f_p2_item['feature_id']}, Vector (bytes): {f_p2_item['feature_vector'][:10]}...")

                print(f"\nGetting features for person {test_person_id2} with limit 1:")
                features_p2_limit = get_features_for_person(test_person_id2, limit=1)
                print(features_p2_limit)
    else:
        print("Skipping Detections and PersonFeatures tests as prerequisite image_id or person_id not available from previous tests.")
    
    print("\n--- Testing Complete for Detections & PersonFeatures ---")

    # Optional: Full cleanup of test data
    # print("\n--- Cleaning up test data ---")
    # if det_id1: delete_detection(det_id1)
    # if det_id2_unknown: delete_detection(det_id2_unknown)
    # if img_id1: delete_class_image(img_id1)
    # if img_id2_pending: delete_class_image(img_id2_pending)
    # if test_person_id: delete_person(test_person_id) # Cascade should handle PersonFeatures
    # if test_person_id2: delete_person(test_person_id2)
    # print("--- Cleanup Complete ---")
    # Test Detections functions
    print("\n--- Testing Detections Functions ---")
    if img_id1 and test_person_id: # Use IDs from previous tests if they exist
        print(f"Attempting to add detection for image_id {img_id1} and person_id {test_person_id}")
        # Convert a dummy numpy array to bytes for feature_vector BLOB
        dummy_feature_bytes = sqlite3.Binary(b'\x00\x01\x02\x03\x04') # Example byte string
        det_id1 = add_detection(
            image_id=img_id1,
            person_id=test_person_id,
            face_crop_path=f"crops/img{img_id1}_det1.jpg",
            bbox_coords=[10, 20, 60, 80],
            recognition_confidence=0.95,
            face_quality_score=0.9,
            face_angles=(0, 0, 0)
        )
        det_id2_unknown = add_detection( # Unassigned detection
            image_id=img_id1,
            face_crop_path=f"crops/img{img_id1}_det2_unknown.jpg",
            bbox_coords=[100, 20, 150, 80],
            feature_vector=sqlite3.Binary(b'\x05\x06\x07\x08'),
            recognition_confidence=0.9,
            face_quality_score=0.8,
            face_angles=(0, 0, 0)
        )

        if det_id1:
            print(f"\nGetting detection by ID: {det_id1}")
            det1 = get_detection_by_id(det_id1)
            print(det1)

            print(f"\nUpdating detection assignment for ID: {det_id1}")
            update_detection_assignment(det_id1, new_person_id=test_person_id2, is_verified=True) # Correcting to person 2
            det1_updated = get_detection_by_id(det_id1)
            print(det1_updated)
        
        print(f"\nGetting detections for image_id {img_id1}:")
        img_detections = get_detections_for_image(img_id1)
        for det in img_detections:
            print(det)

        print(f"\nGetting detections for person_id {test_person_id2} (after correction):")
        person_detections = get_detections_for_person(test_person_id2)
        for p_det in person_detections:
            print(p_det)
        
        # Test PersonFeatures functions
        print("\n--- Testing PersonFeatures Functions ---")
        if det_id1: # Assuming det_id1 was successfully created and now linked to test_person_id2
            print(f"Adding feature for person {test_person_id2} from detection {det_id1}")
            feat_id1 = add_person_feature(test_person_id2, dummy_feature_bytes, source_detection_id=det_id1)
            add_person_feature(test_person_id2, sqlite3.Binary(b'\x0A\x0B\x0C'), source_detection_id=None) # Another feature

            if feat_id1:
                print(f"\nGetting features for person {test_person_id2}:")
                features_p2 = get_features_for_person(test_person_id2)
                for f_p2 in features_p2:
                    print(f"  Feature ID: {f_p2['feature_id']}, Vector (bytes): {f_p2['feature_vector'][:10]}...") # Print first 10 bytes

                print(f"\nGetting features for person {test_person_id2} with limit 1:")
                features_p2_limit = get_features_for_person(test_person_id2, limit=1)
                print(features_p2_limit)
        
        # Cleanup (optional, can be commented out during dev)
        # if det_id1:
        #     print(f"\nDeleting detection ID: {det_id1}")
        #     delete_detection(det_id1)
        # if det_id2_unknown:
        #     delete_detection(det_id2_unknown)
        # delete_features_for_person(test_person_id) # Should be empty if person was corrected
        # delete_features_for_person(test_person_id2)

    else:
        print("Skipping Detections and PersonFeatures tests as prerequisite image_id or person_id not available from previous tests.")
    
    print("\n--- Testing Complete for Detections & PersonFeatures ---")