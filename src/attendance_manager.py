import os
import uuid
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import shutil
import cv2 # For saving representative images if needed, though main.py used it.
from datetime import datetime # For date_taken in ClassImages if needed by process_new_class_image
import sqlite3 # Needed for sqlite3.Binary()
import logging
from typing import List, Dict, Tuple, Optional

import src.data_access as da
from src.utils.image_processing import extract_person_features # Import the core processing function
from src.utils.face_quality import FaceQualityAnalyzer
# We'll need to load features from .npy files, so direct path access is also needed.

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration (should ideally be centralized in a config.py later)
# These paths should point to directories relative to the project root.
# data_access.py defines PROJECT_ROOT which we can use.
REPRESENTATIVE_IMAGE_DIR = os.path.join(da.PROJECT_ROOT, "data", "representative_persons")
REPRESENTATIVE_FEATURE_DIR = os.path.join(da.PROJECT_ROOT, "data", "representative_features")
FACE_CROP_DIR = os.path.join(da.PROJECT_ROOT, "data", "face_crops") # For storing all detected face crops

SIMILARITY_THRESHOLD = 0.9  # From main.py
KNOWN_PERSON_FEATURE_UPDATE_STRATEGY = 'average' # From main.py
MAX_FEATURES_PER_PERSON_FOR_AVG = 5 # From main.py (renamed for clarity)

# Initialize face quality analyzer
face_analyzer = FaceQualityAnalyzer()

os.makedirs(REPRESENTATIVE_IMAGE_DIR, exist_ok=True)
os.makedirs(REPRESENTATIVE_FEATURE_DIR, exist_ok=True)
os.makedirs(FACE_CROP_DIR, exist_ok=True)


def _load_representative_feature_from_path(feature_path: str):
    """Loads a .npy feature file."""
    if feature_path and os.path.exists(feature_path):
        try:
            return np.load(feature_path)
        except Exception as e:
            print(f"[ERROR] Could not load feature from {feature_path}: {e}")
    return None

def _save_representative_feature_to_path(person_id: str, feature_embedding: np.ndarray):
    """Saves a representative feature embedding to a .npy file and returns the path."""
    try:
        # Ensure the feature dir for this person_id exists if it's nested, though here it's flat
        # os.makedirs(REPRESENTATIVE_FEATURE_DIR, exist_ok=True) # Already done globally
        feature_filename = f"{person_id}.npy"
        feature_path = os.path.join(REPRESENTATIVE_FEATURE_DIR, feature_filename)
        np.save(feature_path, feature_embedding)
        print(f"[INFO] Representative feature saved/updated for {person_id} to {feature_path}")
        return feature_path
    except Exception as e_save_feat:
        print(f"[ERROR] Could not save representative feature for {person_id}: {e_save_feat}")
        return None

def _save_representative_image(person_id: str, new_face_crop_source_path: str):
    """Copies the new_face_crop_source_path to be the representative image for person_id."""
    try:
        # os.makedirs(REPRESENTATIVE_IMAGE_DIR, exist_ok=True) # Already done globally
        image_filename = f"{person_id}.jpg" # Assuming jpg
        dest_path = os.path.join(REPRESENTATIVE_IMAGE_DIR, image_filename)
        shutil.copyfile(new_face_crop_source_path, dest_path)
        print(f"[INFO] Representative image saved/updated for {person_id} to {dest_path}")
        return dest_path
    except Exception as e_save_img:
        print(f"[ERROR] Could not save representative image for {person_id} from {new_face_crop_source_path}: {e_save_img}")
        return None

def get_dynamic_threshold(num_samples: int) -> float:
    """Return a dynamic threshold based on number of samples."""
    base_threshold = 0.85
    if num_samples < 2:
        return base_threshold + 0.05  # More strict with few samples
    elif num_samples < 5:
        return base_threshold
    else:
        return base_threshold - 0.05  # More lenient with many samples

def update_person_features(person_id: str, new_feature_vector: np.ndarray, face_angles: Tuple[float, float, float], quality_score: float, detection_id: Optional[int] = None):
    """Store multiple feature vectors per person for better matching."""
    conn = sqlite3.connect(da.DB_FILE)
    cursor = conn.cursor()
    
    try:
        # Store the new feature
        cursor.execute("""
        INSERT INTO PersonFeatures (
            person_id, feature_vector, source_detection_id, 
            quality_score, face_angle_pitch, face_angle_yaw, face_angle_roll
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            person_id, 
            sqlite3.Binary(new_feature_vector.tobytes()),
            detection_id,
            quality_score,
            face_angles[0],
            face_angles[1],
            face_angles[2]
        ))
        
        # Get all features for this person
        cursor.execute("""
        SELECT feature_vector 
        FROM PersonFeatures 
        WHERE person_id = ? 
        AND is_active = 1
        ORDER BY quality_score DESC
        LIMIT 5
        """, (person_id,))
        
        features = [np.frombuffer(row[0], dtype=np.float32) for row in cursor.fetchall()]
        
        # Update representative feature as weighted average of recent features
        weights = np.linspace(1.0, 0.6, len(features))  # Higher weight for better quality features
        weights = weights / np.sum(weights)  # Normalize weights
        
        representative_feature = np.average(features, axis=0, weights=weights)
        rep_feature_path = _save_representative_feature_to_path(person_id, representative_feature)
        
        if rep_feature_path:
            da.update_person_details(person_id, representative_feature_path=rep_feature_path)
        
        conn.commit()
    finally:
        conn.close()

def identify_person_improved(new_feature_vector: np.ndarray, face_angles: Tuple[float, float, float], quality_score: float) -> Tuple[Optional[str], float, bool]:
    """
    Enhanced person identification with multiple similarity metrics and confidence scoring.
    
    Returns:
        Tuple of (person_id, confidence_score, is_reliable_match)
    """
    new_feature = new_feature_vector.reshape(1, -1)
    best_match = None
    max_confidence = -1
    
    # Get all known persons
    all_persons = da.get_all_persons()
    
    for person in all_persons:
        person_id = person['person_id']
        
        # Get feature count for dynamic threshold
        feature_count = person.get('feature_count', 0)
        threshold = get_dynamic_threshold(feature_count)
        
        # Get all feature vectors for this person
        conn = sqlite3.connect(da.DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
        SELECT feature_vector, quality_score, face_angle_pitch, face_angle_yaw, face_angle_roll
        FROM PersonFeatures 
        WHERE person_id = ? AND is_active = 1
        """, (person_id,))
        features_data = cursor.fetchall()
        conn.close()
        
        if not features_data:
            continue
        
        # Calculate similarities and angle differences
        similarities = []
        angle_penalties = []
        
        for feature_data in features_data:
            feature_vector = np.frombuffer(feature_data[0], dtype=np.float32)
            stored_quality = feature_data[1]
            stored_angles = feature_data[2:5]
            
            # Calculate cosine similarity
            similarity = cosine_similarity(new_feature, feature_vector.reshape(1, -1))[0][0]
            
            # Calculate angle difference penalty
            angle_diff = sum(abs(a1 - a2) for a1, a2 in zip(face_angles, stored_angles)) / 3
            angle_penalty = max(0, 1 - angle_diff / 45)  # Normalize to 0-1
            
            # Weight by quality scores
            quality_weight = np.sqrt(quality_score * stored_quality)
            
            similarities.append(similarity * quality_weight)
            angle_penalties.append(angle_penalty)
        
        # Calculate confidence score
        max_similarity = max(similarities)
        avg_similarity = np.mean(similarities)
        avg_angle_penalty = np.mean(angle_penalties)
        
        # Combined confidence score
        confidence = (
            0.5 * max_similarity +    # Best match is most important
            0.3 * avg_similarity +    # Average similarity adds robustness
            0.2 * avg_angle_penalty   # Angle similarity helps confirm
        )
        
        if confidence > max_confidence and confidence > threshold:
            max_confidence = confidence
            best_match = (person_id, confidence)
    
    if best_match:
        return best_match[0], max_confidence, max_confidence > (get_dynamic_threshold(1) + 0.1)
    return None, max_confidence, False

def process_new_class_image(image_id: int, image_path: str, image_date_taken_iso: str):
    """
    Processes a single class image with improved face quality analysis and matching.
    Automatically creates new persons for unmatched face detections.
    """
    logger.info(f"Starting processing for image_id: {image_id}, path: {image_path}")
    if not os.path.exists(image_path):
        logger.error(f"Image path does not exist: {image_path}")
        da.update_class_image_status(image_id, "error", "Image file not found at path.")
        return False

    try:
        # Extract faces and features from the image
        detected_data_list = extract_person_features(image_path)

        if not detected_data_list:
            logger.info(f"No persons detected in image_id: {image_id}")
            da.update_class_image_status(image_id, "completed", "No persons detected.")
            return True

        # Analyze image quality
        image = cv2.imread(image_path)
        if image is None:
            logger.error(f"Could not read image: {image_path}")
            da.update_class_image_status(image_id, "error", "Could not read image file.")
            return False

        num_detections = 0
        for i, detected_data in enumerate(detected_data_list):
            feature_vector = detected_data["embedding"]
            bbox = detected_data["bbox_xyxy"]
            cropped_np_image = detected_data["cropped_image_np"]

            # Get face crop path
            detection_crop_filename = f"img{image_id}_det{i}.jpg"
            detection_crop_filepath = os.path.join(FACE_CROP_DIR, detection_crop_filename)

            # Save face crop
            cv2.imwrite(detection_crop_filepath, cv2.cvtColor(cropped_np_image, cv2.COLOR_RGB2BGR))

            # Analyze face quality and angles
            quality_metrics = face_analyzer.analyze_face_quality(cropped_np_image)
            face_angles = face_analyzer.get_face_angles(cropped_np_image)
            angle_quality = face_analyzer.get_angle_quality_score(*face_angles)

            # Combined quality score
            overall_quality = 0.7 * quality_metrics['overall_quality'] + 0.3 * angle_quality

            # Identify person with improved matching
            person_id, confidence, is_reliable = identify_person_improved(
                feature_vector, face_angles, overall_quality
            )

            # If no match found, create a new person
            if not person_id:
                # Generate new person ID
                new_person_id = str(uuid.uuid4())
                
                # Save representative feature
                new_rep_feature_path = _save_representative_feature_to_path(new_person_id, feature_vector)
                if not new_rep_feature_path:
                    logger.error(f"Failed to save representative feature for new person {new_person_id}")
                    continue

                # Save representative image
                new_rep_image_path = _save_representative_image(new_person_id, detection_crop_filepath)
                if not new_rep_image_path:
                    # Cleanup feature file if image saving fails
                    if os.path.exists(new_rep_feature_path):
                        os.remove(new_rep_feature_path)
                    logger.error(f"Failed to save representative image for new person {new_person_id}")
                    continue

                # Add the new person to database
                person_id = da.add_person(
                    person_id=new_person_id,
                    name=None,  # User can name them later
                    enrollment_date=image_date_taken_iso,  # Use image date as enrollment date
                    representative_feature_path=new_rep_feature_path,
                    representative_image_path=new_rep_image_path
                )
                
                if not person_id:
                    # Cleanup files if DB add fails
                    if os.path.exists(new_rep_feature_path):
                        os.remove(new_rep_feature_path)
                    if os.path.exists(new_rep_image_path):
                        os.remove(new_rep_image_path)
                    logger.error(f"Failed to add new person {new_person_id} to database")
                    continue

                logger.info(f"Created new person {new_person_id} from detection in image {image_id}")
                confidence = 1.0  # New person, so confidence is 1.0
                is_reliable = True

            # Save detection to database
            detection_id = da.add_detection(
                image_id=image_id,
                person_id=person_id,
                face_crop_path=detection_crop_filepath,
                feature_vector=sqlite3.Binary(feature_vector.tobytes()),
                bbox_coords=bbox,
                recognition_confidence=confidence,
                face_quality_score=overall_quality,
                face_angles=face_angles
            )

            if person_id:
                # Update person's features
                update_person_features(
                    person_id=person_id,
                    new_feature_vector=feature_vector,
                    face_angles=face_angles,
                    quality_score=overall_quality,
                    detection_id=detection_id
                )

            num_detections += 1

        # Update image status
        da.update_class_image_status(
            image_id, 
            "completed",
            f"Processed successfully. Found {num_detections} persons."
        )
        return True

    except Exception as e:
        logger.error(f"Error processing image {image_id}: {e}")
        da.update_class_image_status(image_id, "error", str(e))
        return False


def merge_persons_logic(person_ids_to_merge: list, canonical_person_id: str):
    """
    Merges multiple person records into a single canonical person record.
    - Reassigns Detections.
    - Reassigns PersonFeatures (if used, or deletes features of merged persons).
    - Deletes non-canonical Persons records.
    - Deletes representative files of non-canonical persons.
    - Updates the canonical person's representative data (simplified for now).
    """
    if not person_ids_to_merge or not canonical_person_id:
        print("[ERROR] Both list of IDs to merge and canonical ID must be provided.")
        return False
    if canonical_person_id not in person_ids_to_merge:
        print(f"[ERROR] Canonical ID {canonical_person_id} must be in the list of IDs to merge.")
        return False
    if len(set(person_ids_to_merge)) < 2: # Ensure there's at least one other ID to merge into canonical
        print("[ERROR] At least two unique person IDs are required for a merge operation.")
        return False

    print(f"[INFO] Starting merge operation. Canonical ID: {canonical_person_id}. Merging: {person_ids_to_merge}")

    # Ensure canonical person exists
    canonical_person_data = da.get_person_by_id(canonical_person_id)
    if not canonical_person_data:
        print(f"[ERROR] Canonical person ID {canonical_person_id} not found in database.")
        return False

    success_overall = True
    merged_ids_processed_files = []

    for old_person_id in person_ids_to_merge:
        if old_person_id == canonical_person_id:
            continue

        print(f"[INFO] Processing merge for {old_person_id} into {canonical_person_id}...")
        old_person_data = da.get_person_by_id(old_person_id)
        if not old_person_data:
            print(f"[WARNING] Person ID {old_person_id} not found in database. Skipping.")
            continue

        # 1. Reassign Detections
        detections_of_old_person = da.get_detections_for_person(old_person_id)
        print(f"[DEBUG] Found {len(detections_of_old_person)} detections for {old_person_id} to reassign.")
        for det in detections_of_old_person:
            # original_assigned_person_id should be the old_person_id before this merge correction
            da.update_detection_assignment(
                detection_id=det['detection_id'],
                new_person_id=canonical_person_id,
                is_verified=det['is_verified_by_user'], # Keep existing verification status
                original_assigned_person_id_to_set=old_person_id
            )
        print(f"[INFO] Reassigned detections from {old_person_id} to {canonical_person_id}.")

        # 2. Handle PersonFeatures (if PersonFeatures table is actively used and populated)
        # For now, we assume representative features are mainly managed by Persons.representative_feature_path
        # If PersonFeatures table is used, one might transfer features or delete old ones.
        # Current schema has ON DELETE CASCADE from Persons to PersonFeatures, so deleting person will clear them.
        # If we wanted to merge features before deleting person:
        # features_to_transfer = da.get_features_for_person(old_person_id)
        # for feat_data in features_to_transfer:
        #     da.add_person_feature(canonical_person_id, feat_data['feature_vector'], feat_data['source_detection_id'])
        # da.delete_features_for_person(old_person_id) # Then delete old ones explicitly

        # 3. Delete representative files of the non-canonical person
        old_rep_img_path = old_person_data.get('representative_image_path')
        if old_rep_img_path and os.path.exists(old_rep_img_path):
            try:
                os.remove(old_rep_img_path)
                print(f"[INFO] Deleted old representative image: {old_rep_img_path}")
            except OSError as e:
                print(f"[ERROR] Could not delete old representative image {old_rep_img_path}: {e}")
                success_overall = False
        
        old_rep_feat_path = old_person_data.get('representative_feature_path')
        if old_rep_feat_path and os.path.exists(old_rep_feat_path):
            try:
                os.remove(old_rep_feat_path)
                print(f"[INFO] Deleted old representative feature: {old_rep_feat_path}")
            except OSError as e:
                print(f"[ERROR] Could not delete old representative feature {old_rep_feat_path}: {e}")
                success_overall = False
        
        merged_ids_processed_files.append(old_person_id)

        # 4. Delete the non-canonical Persons record
        # This will also cascade-delete their PersonFeatures due to schema.
        if not da.delete_person(old_person_id):
            print(f"[ERROR] Failed to delete person record for {old_person_id}.")
            success_overall = False
        else:
            print(f"[INFO] Deleted person record for {old_person_id}.")

    # 5. Consolidate/Update canonical person's representative data (Simplified for now)
    # A more advanced strategy would involve:
    # - Collecting all features from all merged persons (from PersonFeatures table or by loading all .npy).
    # - Calculating a new average representative feature.
    # - Saving this new feature and updating Persons.representative_feature_path.
    # - Selecting the "best" representative image from all candidates.
    # For now, we are keeping the canonical person's original representative data.
    # If their feature was updated during identify_or_enroll due to new sightings, that's fine.
    print(f"[INFO] Merge process complete. Canonical person {canonical_person_id} data retained/updated.")
    
    return success_overall

def reassign_detection_to_new_person(detection_id: int, original_person_id_of_detection_on_student_page: str):
    """
    Creates a new Person from a specific detection and reassigns that detection to the new Person.
    This is used when a detection was wrongly assigned to an existing student, and that face
    actually belongs to a new, previously unrecorded student.
    """
    app_log_prefix = "[AttendanceManager-ReassignNew]"
    print(f"{app_log_prefix} Attempting to create new person from detection_id: {detection_id}")

    detection_data = da.get_detection_by_id(detection_id)
    if not detection_data:
        return False, f"Detection ID {detection_id} not found.", None

    # Ensure this detection isn't already unassigned or assigned to the person it's being removed from
    # The original_person_id_of_detection_on_student_page helps confirm context if needed, but main check is detection_data['person_id']
    
    face_crop_path = detection_data.get('face_crop_path')
    feature_vector_blob = detection_data.get('feature_vector')

    if not face_crop_path or not os.path.exists(face_crop_path):
        return False, f"Face crop path for detection {detection_id} is missing or file does not exist.", None
    if not feature_vector_blob:
        return False, f"Feature vector for detection {detection_id} is missing.", None

    try:
        feature_vector_np = np.frombuffer(feature_vector_blob, dtype=np.float32) # Assuming float32, adjust if different
    except Exception as e:
        print(f"{app_log_prefix} Error converting feature vector blob to numpy: {e}")
        return False, "Could not process feature vector for new person.", None

    # 1. Create a new Person ID
    new_person_id = str(uuid.uuid4())
    print(f"{app_log_prefix} Generated new person ID: {new_person_id} for detection {detection_id}")

    # 2. Save the detection's feature as the new person's representative feature
    new_rep_feature_path = _save_representative_feature_to_path(new_person_id, feature_vector_np)
    if not new_rep_feature_path:
        return False, f"Failed to save representative feature for new person {new_person_id}.", None

    # 3. Copy the detection's face crop as the new person's representative image
    new_rep_image_path = _save_representative_image(new_person_id, face_crop_path)
    if not new_rep_image_path:
        # Cleanup already saved feature file for the new person if image saving fails
        if os.path.exists(new_rep_feature_path): os.remove(new_rep_feature_path)
        return False, f"Failed to save representative image for new person {new_person_id}.", None

    # 4. Add the new person to the Persons table
    created_person_id = da.add_person(
        person_id=new_person_id,
        name=None, # User can name them later
        enrollment_date=datetime.now().isoformat(), # Or use detection's date?
        representative_feature_path=new_rep_feature_path,
        representative_image_path=new_rep_image_path
    )
    if not created_person_id:
        # Cleanup representative files if DB add fails
        if os.path.exists(new_rep_feature_path): os.remove(new_rep_feature_path)
        if os.path.exists(new_rep_image_path): os.remove(new_rep_image_path)
        return False, f"Failed to add new person {new_person_id} to database.", None
    
    # 5. Update the original Detection record to point to this new_person_id and mark as verified
    # The original_assigned_person_id should be who it was *before* this operation.
    # This is passed as original_person_id_of_detection_on_student_page
    update_success = da.update_detection_assignment(
        detection_id=detection_id,
        new_person_id=new_person_id,
        is_verified=True, # This action implies verification of the new assignment
        original_assigned_person_id_to_set=detection_data.get('person_id') # Log who it was before this specific correction
    )

    if not update_success:
        # This is tricky: person is created, but detection not updated.
        # For now, log and return partial success. Manual DB correction might be needed.
        print(f"{app_log_prefix} [CRITICAL] New person {new_person_id} created, but FAILED to update detection {detection_id} to this new person.")
        return False, f"New person {new_person_id} created, but failed to update detection {detection_id}.", new_person_id
        
    print(f"{app_log_prefix} Successfully reassigned detection {detection_id} to new person {new_person_id}.")
    return True, f"Detection {detection_id} successfully reassigned to new person {new_person_id}.", new_person_id


def generate_database_merge_suggestions():
    """
    Generates merge suggestions based on similarity of representative features
    stored in .npy files, paths to which are in the Persons table.
    Returns a list of groups (lists of person_ids) suggested for merging.
    """
    print("[INFO] Generating merge suggestions from database representative features...")
    all_persons_db = da.get_all_persons()
    
    persons_with_features = []
    for p_data in all_persons_db:
        feature_path = p_data.get('representative_feature_path')
        if feature_path:
            feature = _load_representative_feature_from_path(feature_path)
            if feature is not None:
                persons_with_features.append({
                    "person_id": p_data['person_id'],
                    "feature_vector": feature.reshape(1, -1) # Ensure 2D for cosine_similarity
                })
            else:
                print(f"[WARNING] Could not load feature for {p_data['person_id']} from {feature_path}")
        # else:
            # print(f"[DEBUG] Person {p_data['person_id']} has no representative feature path for suggestion.")

    if not persons_with_features or len(persons_with_features) < 2:
        print("[INFO] Not enough persons with features to generate suggestions.")
        return []

    print(f"[INFO] Comparing features for {len(persons_with_features)} persons.")
    suggestions = []
    processed_ids_in_suggestion_run = set()

    for i in range(len(persons_with_features)):
        person1_data = persons_with_features[i]
        person1_id = person1_data['person_id']

        if person1_id in processed_ids_in_suggestion_run:
            continue

        current_group = {person1_id}
        person1_feature = person1_data['feature_vector']

        for j in range(i + 1, len(persons_with_features)):
            person2_data = persons_with_features[j]
            person2_id = person2_data['person_id']

            if person2_id in processed_ids_in_suggestion_run:
                continue
            
            person2_feature = person2_data['feature_vector']
            similarity = cosine_similarity(person1_feature, person2_feature)[0][0]

            if similarity >= SIMILARITY_THRESHOLD:
                current_group.add(person2_id)
        
        if len(current_group) > 1:
            # Sort the group for consistent output/handling
            sorted_group = sorted(list(current_group))
            suggestions.append({
                "group_ids": sorted_group,
                "reason": f"High similarity (>{SIMILARITY_THRESHOLD:.2f}) among representative features.",
                "reference_id_for_similarity": sorted_group[0] # Arbitrary reference from the group
            })
            processed_ids_in_suggestion_run.update(current_group)
            print(f"[INFO] Suggested group: {sorted_group}")

    print(f"[INFO] Found {len(suggestions)} potential merge groups.")
    return suggestions

def delete_class_image_and_all_associations(image_id: int):
    """
    Deletes a ClassImage, its Detections, associated physical files (main image, face crops),
    and any persons that were created solely from this image.
    """
    app_log_prefix = "[AttendanceManager-DeleteImage]" # For clarity if logs are aggregated
    print(f"{app_log_prefix} Attempting to delete image_id: {image_id} and its associations.")

    # 1. Get ClassImage details to find the main image file path
    class_image_data = da.get_class_image_by_id(image_id)
    if not class_image_data:
        print(f"{app_log_prefix} ClassImage with ID {image_id} not found. Nothing to delete.")
        return False, "ClassImage not found."

    main_image_filepath = class_image_data.get('filepath_processed')

    # 2. Get all detections for this image to find face crop paths and identify persons to potentially delete
    detections = da.get_detections_for_image(image_id)
    face_crop_paths_to_delete = []
    persons_to_check = set()  # Set of person_ids to check if they should be deleted
    
    if detections:
        for det in detections:
            if det.get('face_crop_path'):
                face_crop_paths_to_delete.append(det['face_crop_path'])
            if det.get('person_id'):
                persons_to_check.add(det['person_id'])
    
    # 3. Delete physical face crop files
    for crop_path in face_crop_paths_to_delete:
        if crop_path and os.path.exists(crop_path):
            try:
                os.remove(crop_path)
                print(f"{app_log_prefix} Deleted face crop file: {crop_path}")
            except OSError as e:
                print(f"{app_log_prefix} [ERROR] Could not delete face crop file {crop_path}: {e}")
                # Continue deleting other files/records even if one file fails

    # 4. For each person detected in this image, check if they have any other detections
    for person_id in persons_to_check:
        all_detections = da.get_detections_for_person(person_id)
        other_detections = [d for d in all_detections if d['class_image_id'] != image_id]
        
        if not other_detections:  # This person only appears in this image
            print(f"{app_log_prefix} Person {person_id} only appears in this image, will be deleted.")
            
            # Delete person's representative files
            person_data = da.get_person_by_id(person_id)
            if person_data:
                rep_image_path = person_data.get('representative_image_path')
                rep_feature_path = person_data.get('representative_feature_path')
                
                if rep_image_path and os.path.exists(rep_image_path):
                    try:
                        os.remove(rep_image_path)
                        print(f"{app_log_prefix} Deleted representative image: {rep_image_path}")
                    except OSError as e:
                        print(f"{app_log_prefix} [ERROR] Could not delete representative image {rep_image_path}: {e}")
                
                if rep_feature_path and os.path.exists(rep_feature_path):
                    try:
                        os.remove(rep_feature_path)
                        print(f"{app_log_prefix} Deleted representative feature: {rep_feature_path}")
                    except OSError as e:
                        print(f"{app_log_prefix} [ERROR] Could not delete representative feature {rep_feature_path}: {e}")
            
            # Delete the person from database (this will cascade delete their features)
            da.delete_person(person_id)
            print(f"{app_log_prefix} Deleted person {person_id} from database")

    # 5. Delete the ClassImages record (this will CASCADE DELETE Detections table entries)
    if da.delete_class_image(image_id):
        print(f"{app_log_prefix} Successfully deleted ClassImage record {image_id} and its Detections from DB.")
        
        # 6. Delete the main physical image file
        if main_image_filepath and os.path.exists(main_image_filepath):
            try:
                os.remove(main_image_filepath)
                print(f"{app_log_prefix} Deleted main image file: {main_image_filepath}")
            except OSError as e:
                print(f"{app_log_prefix} [ERROR] Could not delete main image file {main_image_filepath}: {e}")
                return True, f"DB records deleted, but failed to delete main image file: {main_image_filepath}" # Partial success
        return True, f"Successfully deleted image {image_id} and all associated data."
    else:
        print(f"{app_log_prefix} [ERROR] Failed to delete ClassImage record {image_id} from DB.")
        return False, f"Failed to delete ClassImage record {image_id} from database."


# Placeholder for reporting functions

if __name__ == '__main__':
    print("Testing attendance_manager.py...")
    # This requires database to be setup (run database_setup.py)
    # And data_access.py to be functional.
    # Also needs some dummy .npy files and image files if we fully test.

    # Create a dummy feature and crop path for testing
    dummy_feature = np.random.rand(512).astype(np.float32) # Example ReID feature size
    
    # Create a dummy crop file
    dummy_crop_filename = "dummy_crop_for_am_test.jpg"
    dummy_crop_path = os.path.join(FACE_CROP_DIR, dummy_crop_filename)
    if not os.path.exists(dummy_crop_path):
        try:
            # Create a small black image for the dummy crop
            dummy_img_data = np.zeros((64, 64, 3), dtype=np.uint8)
            cv2.imwrite(dummy_crop_path, dummy_img_data)
            print(f"Created dummy crop file at {dummy_crop_path}")
        except Exception as e:
            print(f"Could not create dummy crop file: {e}")


    if os.path.exists(dummy_crop_path):
        print("\n--- Test 1: Enroll a new person (testing identify_or_enroll_person directly) ---")
        person1_id = identify_or_enroll_person(dummy_feature, dummy_crop_path)
        if person1_id:
            print(f"Enrolled/Identified Person 1 ID: {person1_id}")
            person1_data = da.get_person_by_id(person1_id)
            print(f"Person 1 DB Data: {person1_data}")

            print("\n--- Test 2: Identify the same person (should match) ---")
            # Slightly modified feature to simulate a new detection of the same person
            slightly_different_feature = dummy_feature + np.random.normal(0, 0.01, dummy_feature.shape).astype(np.float32)
            person1_again_id = identify_or_enroll_person(slightly_different_feature, dummy_crop_path)
            if person1_again_id:
                print(f"Second identification for Person 1 ID: {person1_again_id}")
                assert person1_again_id == person1_id, "Should have matched the same person!"
                person1_updated_data = da.get_person_by_id(person1_id)
                print(f"Person 1 DB Data after re-identification: {person1_updated_data}")


            print("\n--- Test 3: Enroll a different new person ---")
            different_feature = np.random.rand(512).astype(np.float32)
            # Ensure it's different enough not to match person1 easily
            while cosine_similarity(different_feature.reshape(1,-1), dummy_feature.reshape(1,-1))[0][0] > SIMILARITY_THRESHOLD - 0.1:
                different_feature = np.random.rand(512).astype(np.float32)

            person2_id = identify_or_enroll_person(different_feature, dummy_crop_path) # Using same crop path for simplicity of test
            if person2_id:
                print(f"Enrolled/Identified Person 2 ID: {person2_id}")
                assert person2_id != person1_id, "Should be a new person!"
                person2_data = da.get_person_by_id(person2_id)
                print(f"Person 2 DB Data: {person2_data}")
        
        # Clean up dummy files and DB entries (optional)
        # if person1_id: da.delete_person(person1_id) # This will also delete features if cascade is set
        # if person2_id: da.delete_person(person2_id)
        # if os.path.exists(dummy_crop_path): os.remove(dummy_crop_path)
        # if person1_id and os.path.exists(os.path.join(REPRESENTATIVE_FEATURE_DIR, f"{person1_id}.npy")):
        #     os.remove(os.path.join(REPRESENTATIVE_FEATURE_DIR, f"{person1_id}.npy"))
        # if person1_id and os.path.exists(os.path.join(REPRESENTATIVE_IMAGE_DIR, f"{person1_id}.jpg")):
        #     os.remove(os.path.join(REPRESENTATIVE_IMAGE_DIR, f"{person1_id}.jpg"))
        # Similar cleanup for person2_id

        # --- Test generate_database_merge_suggestions ---
        # This requires persons with saved .npy features from the identify_or_enroll_person tests.
        print("\n--- Test 4: Generate Merge Suggestions from DB ---")
        db_suggestions = generate_database_merge_suggestions()
        if db_suggestions:
            for idx, sugg in enumerate(db_suggestions):
                print(f"DB Suggestion {idx+1}: Group {sugg['group_ids']}, Reason: {sugg['reason']}")
        else:
            print("No merge suggestions generated from DB (or not enough data).")
        
        # --- Test process_new_class_image ---
        # This requires a valid image in 'pictures' dir and image_processing to be working.
        print("\n--- Test 5: Process a new class image (conceptual test) ---")
        mock_image_filename = "mock_class_image.jpg"
        mock_image_path_in_pictures = os.path.join(da.PROJECT_ROOT, "pictures", mock_image_filename)
        
        if not os.path.exists(mock_image_path_in_pictures):
            try:
                tiny_img = np.zeros((100,100,3), dtype=np.uint8) # Create a small black image
                cv2.imwrite(mock_image_path_in_pictures, tiny_img)
                print(f"Created mock image for testing: {mock_image_path_in_pictures}")
            except Exception as e_mock_img:
                print(f"Could not create mock image for testing process_new_class_image: {e_mock_img}")

        if os.path.exists(mock_image_path_in_pictures):
            if not os.path.exists(da.DB_FILE):
                 print(f"Database file {da.DB_FILE} not found. Run database_setup.py first.")
            else:
                img_entry_id = da.add_class_image(
                    original_filename=mock_image_filename,
                    date_taken=datetime.now().isoformat(),
                    filepath_processed=mock_image_path_in_pictures
                )
                if img_entry_id:
                    print(f"Added mock ClassImage to DB with ID: {img_entry_id} for process_new_class_image test.")
                    success = process_new_class_image(img_entry_id, mock_image_path_in_pictures)
                    print(f"process_new_class_image result for img_id {img_entry_id}: {success}")
                    detections = da.get_detections_for_image(img_entry_id)
                    print(f"Detections found for image {img_entry_id}: {len(detections)}")
                    # Add cleanup for mock image and its detections/persons if desired
                else:
                    print("Failed to add mock ClassImage to DB for testing process_new_class_image.")
        else:
            print(f"Skipping process_new_class_image test as mock image {mock_image_path_in_pictures} could not be created/found.")
    else:
        print(f"Skipping identify_or_enroll_person, suggestions & process_new_class_image tests as dummy crop file {dummy_crop_path} could not be created.")

    print("\nAttendance Manager testing finished.")