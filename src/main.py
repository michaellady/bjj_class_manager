import os
import csv
import uuid
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import cv2 # For saving representative images
import concurrent.futures
import time

# --- Configuration ---
SIMILARITY_THRESHOLD = 0.85  # Adjust this threshold based on ReID model performance and dataset
REPRESENTATIVE_IMAGE_DIR = "data/representative_persons"
REPRESENTATIVE_FEATURE_DIR = "data/representative_features"
# How to update known person's features: 'average' or 'replace' (with latest)
KNOWN_PERSON_FEATURE_UPDATE_STRATEGY = 'average' 
MAX_FEATURES_PER_PERSON = 5 # Max features to store per person for averaging

# Configure the number of worker processes for parallelism
# os.cpu_count() is a good default. Adjust based on your hardware and workload.
# For GPU-bound tasks, you might want fewer workers than CPU cores.
NUM_WORKERS = max(1, os.cpu_count() - 1 if os.cpu_count() else 1) # Leave one core for system if possible

# --- Utility Functions (largely unchanged) ---
def get_image_date(image_path):
    try:
        image = Image.open(image_path)
        exif_data = image._getexif()
        if exif_data:
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == 'DateTimeOriginal':
                    return datetime.strptime(value, '%Y:%m:%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
        timestamp = os.path.getmtime(image_path)
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        # print(f"[WARNING] Could not read EXIF date for {os.path.basename(image_path)}, falling back to mtime: {e}")
        try:
            timestamp = os.path.getmtime(image_path)
            return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e_mtime:
            print(f"[ERROR] Could not get any date for {os.path.basename(image_path)}: {e_mtime}")
            return ""

def save_representative_feature(person_id, feature_embedding):
    """Saves a representative feature embedding to a .npy file."""
    try:
        feature_path = os.path.join(REPRESENTATIVE_FEATURE_DIR, f"{person_id}.npy")
        np.save(feature_path, feature_embedding)
        # print(f"[DEBUG] Representative feature saved/updated for {person_id} to {feature_path}")
    except Exception as e_save_feat:
        print(f"[ERROR] Could not save representative feature for {person_id}: {e_save_feat}")

def update_person_feature(person_data, new_feature_embedding):
    """Updates a known person's feature embeddings and saves the representative feature."""
    # person_data is an entry from known_persons list
    person_id = person_data['id']
    if KNOWN_PERSON_FEATURE_UPDATE_STRATEGY == 'average':
        person_data['features'].append(new_feature_embedding)
        if len(person_data['features']) > MAX_FEATURES_PER_PERSON:
            person_data['features'].pop(0) 
        person_data['representative_feature'] = np.mean(person_data['features'], axis=0)
    else: # Default to 'replace'
        person_data['features'] = [new_feature_embedding]
        person_data['representative_feature'] = new_feature_embedding
    
    save_representative_feature(person_id, person_data['representative_feature'])


# --- Worker Function for Parallel Processing ---
def process_image_file(filename, pictures_dir_abs_path, utils_module_path):
    """
    Processes a single image file: gets date and extracts person features.
    This function is designed to be run in a separate process.
    It re-imports utils.image_processing to ensure models are loaded in the new process.
    """
    # Dynamically import image_processing in the worker process
    # This is important for multiprocessing to ensure models are loaded correctly in each process
    # and to handle potential GPU context issues.
    import sys
    # Add the directory of utils_module_path to sys.path if it's not already there
    # to ensure the import works correctly.
    module_dir = os.path.dirname(utils_module_path)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir) # Insert at the beginning for priority
    
    # The actual import name will be 'utils.image_processing' if utils_module_path is 'src/utils/image_processing.py'
    # and 'src' is the parent directory from where python src/main.py is run.
    # For simplicity, assuming 'utils.image_processing' can be found if 'src' is in PYTHONPATH
    # or if the script is run from the project root.
    # A more robust way would be to pass the project root and construct the import path.
    # For now, let's assume 'from utils.image_processing import extract_person_features' works
    # if the worker inherits the necessary path, or we adjust it.
    
    # Simpler: Assume utils.image_processing is in a package 'utils' relative to where this worker might be "seen" from.
    # This often works if the main script is in a directory like 'src/' and utils is 'src/utils/'.
    try:
        # This import needs to happen *inside* the worker function for multiprocessing
        from utils.image_processing import extract_person_features
    except ImportError as e:
        return filename, None, None, f"Failed to import extract_person_features in worker: {e}. Check PYTHONPATH and module structure."
    except Exception as e_import: # Catch any other import-related errors
        return filename, None, None, f"Unexpected error importing in worker: {e_import}"


    image_path = os.path.join(pictures_dir_abs_path, filename)
    # print(f"[Worker-{os.getpid()}] Processing {filename}")
    date_str = None
    detected_features = None
    error_msg = None
    try:
        date_str = get_image_date(image_path) # get_image_date is simple, can be called directly
        if not date_str:
            # print(f"[Worker-{os.getpid()}] No date for {filename}")
            return filename, None, None, "No date found" # Return error if no date

        detected_features = extract_person_features(image_path)
        # print(f"[Worker-{os.getpid()}] Features for {filename}: {len(detected_features) if detected_features else 0}")

    except Exception as e:
        error_msg = f"Error processing {filename} in worker: {e}"
        print(f"[ERROR] {error_msg}")
    
    return filename, date_str, detected_features, error_msg

# --- Main Application Logic ---
def main():
    start_time = time.time()

    project_root = os.getcwd() # Assuming script is run from project root
    pictures_dir = os.path.join(project_root, "pictures")
    utils_module_abs_path = os.path.join(project_root, "src", "utils", "image_processing.py") # Path for worker import
    
    attendance_csv_path = os.path.join(project_root, "attendance.csv")
    os.makedirs(REPRESENTATIVE_IMAGE_DIR, exist_ok=True) 
    os.makedirs(REPRESENTATIVE_FEATURE_DIR, exist_ok=True)

    if not os.path.exists(pictures_dir):
        print(f"[ERROR] Pictures directory not found: {pictures_dir}")
        return

    image_files = sorted([
        f for f in os.listdir(pictures_dir)
        if f.lower().endswith(('.jpg', '.jpeg', '.png'))
    ])
    print(f"[INFO] Found {len(image_files)} images in {pictures_dir}. Processing with {NUM_WORKERS} workers.")

    known_persons = [] 
    attendance_records = []
    
    processed_image_data = [] # To store results from parallel processing

    # Parallel processing of images
    with concurrent.futures.ProcessPoolExecutor(max_workers=NUM_WORKERS) as executor:
        # Pass the absolute path to pictures_dir and the utils module for robust path handling in workers
        futures = {executor.submit(process_image_file, filename, pictures_dir, utils_module_abs_path): filename for filename in image_files}
        
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            original_filename = futures[future]
            try:
                filename_res, date_str_res, features_res, error_res = future.result()
                if error_res:
                    print(f"[ERROR] Skipping {filename_res} due to worker error: {error_res}")
                    continue
                if not date_str_res:
                    print(f"[WARNING] Skipping {filename_res} due to missing date from worker.")
                    continue
                if features_res is None: # Can happen if extract_person_features returns None or empty
                     print(f"[INFO] No persons detected or features extracted in {filename_res} by worker.")
                     continue
                processed_image_data.append((filename_res, date_str_res, features_res))
                print(f"[INFO] Parallel processing complete for {filename_res} ({i+1}/{len(image_files)})")
            except Exception as e:
                print(f"[ERROR] Main process error retrieving result for {original_filename}: {e}")

    print(f"\n[INFO] Parallel feature extraction complete. {len(processed_image_data)} images successfully processed for features.")
    print("[INFO] Starting sequential ID assignment and attendance logging...")

    # Sequential processing for ID assignment and state updates
    for filename, date_str, detected_persons_features in processed_image_data:
        print(f"\n[INFO] Sequentially processing features for {filename}...")
        if not detected_persons_features: # Should have been caught earlier, but double check
            print(f"[INFO] No features for {filename} during sequential step.")
            continue
        
        print(f"[DEBUG] Seq: Extracted {len(detected_persons_features)} features from {filename}.")

        for detected_person in detected_persons_features:
            current_embedding = detected_person['embedding'].reshape(1, -1)
            best_match_id = None
            max_similarity = -1

            for i, person_data in enumerate(known_persons):
                similarity = cosine_similarity(current_embedding, person_data['representative_feature'].reshape(1, -1))[0][0]
                if similarity > max_similarity:
                    max_similarity = similarity
                    if similarity > SIMILARITY_THRESHOLD:
                        best_match_id = person_data['id']
            
            person_id_for_record = None
            if best_match_id:
                person_id_for_record = best_match_id
                # Find the person_data in known_persons to update
                person_to_update_idx = next((idx for idx, p_data in enumerate(known_persons) if p_data['id'] == best_match_id), None)
                if person_to_update_idx is not None:
                    update_person_feature(known_persons[person_to_update_idx], detected_person['embedding'])
                print(f"[DEBUG] Seq: Matched existing ID: {person_id_for_record} in {filename} (Sim: {max_similarity:.2f})")
            else:
                new_person_id = str(uuid.uuid4())
                person_id_for_record = new_person_id
                new_person_data_entry = {
                    'id': new_person_id,
                    'features': [detected_person['embedding']],
                    'representative_feature': detected_person['embedding']
                }
                known_persons.append(new_person_data_entry)
                print(f"[DEBUG] Seq: New person ID: {person_id_for_record} in {filename} (Max sim: {max_similarity:.2f})")

                # Save representative image
                try:
                    cropped_img_np = detected_person.get('cropped_image_np')
                    if cropped_img_np is not None:
                        rep_img_bgr = cv2.cvtColor(cropped_img_np, cv2.COLOR_RGB2BGR)
                        rep_img_path = os.path.join(REPRESENTATIVE_IMAGE_DIR, f"{new_person_id}.jpg")
                        cv2.imwrite(rep_img_path, rep_img_bgr)
                        # print(f"[DEBUG] Seq: Saved rep image for {new_person_id}")
                    # else: print(f"[WARNING] Seq: Cropped image not found for new person {new_person_id}")
                except Exception as e_save_img:
                    print(f"[ERROR] Seq: Could not save rep image for {new_person_id}: {e_save_img}")
                
                # Save initial representative feature
                save_representative_feature(new_person_id, new_person_data_entry['representative_feature'])
            
            attendance_records.append({
                'person_id': person_id_for_record,
                'date': date_str,
                'filename': filename
            })

    # Deduplicate and write CSV (unchanged)
    daily_attendance = {}
    for record in attendance_records:
        day_date = record['date'].split(' ')[0]
        key = (record['person_id'], day_date)
        if key not in daily_attendance:
            daily_attendance[key] = set()
        daily_attendance[key].add(record['filename'])

    print(f"\n[INFO] Writing attendance data to {attendance_csv_path}")
    with open(attendance_csv_path, mode='w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["person_id", "date_attended", "source_filenames"])
        sorted_daily_attendance = sorted(daily_attendance.items(), key=lambda item: (item[0][0], item[0][1]))
        for (person_id, day_date), filenames in sorted_daily_attendance:
            writer.writerow([person_id, day_date, ", ".join(sorted(list(filenames)))])
            # print(f"[DEBUG] Wrote to CSV: {person_id}, {day_date}, {len(filenames)} files")

    end_time = time.time()
    print(f"\n[INFO] Processing complete. Attendance data saved to {attendance_csv_path}")
    print(f"[INFO] Total unique persons identified: {len(known_persons)}")
    print(f"[INFO] Total daily attendance records: {len(daily_attendance)}")
    print(f"[INFO] Total execution time: {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    # This is crucial for multiprocessing on some platforms (like Windows)
    # and good practice for others.
    # It ensures that child processes don't re-execute the main script's top-level code.
    # The ProcessPoolExecutor handles this internally for its workers, but
    # if you were using multiprocessing.Process directly, this would be essential.
    # For concurrent.futures, it's generally managed, but explicit `if __name__ == "__main__":`
    # is always a good safeguard for scripts intended to be runnable and importable.
    main()