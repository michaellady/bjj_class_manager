import os
import shutil
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# Configuration (can be moved to a config file or app config later)
ATTENDANCE_CSV = "attendance.csv" # Relative to project root
REPRESENTATIVE_IMAGE_DIR = "data/representative_persons" # Relative to project root
REPRESENTATIVE_FEATURE_DIR = "data/representative_features" # Relative to project root
BACKUP_CSV_PATH = "attendance_backup.csv" # Relative to project root
SUGGEST_MERGE_SIMILARITY_THRESHOLD = 0.85

# Ensure paths are relative to the project root, not necessarily src/
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ATTENDANCE_CSV_PATH = os.path.join(PROJECT_ROOT, ATTENDANCE_CSV)
REPRESENTATIVE_IMAGE_DIR_PATH = os.path.join(PROJECT_ROOT, REPRESENTATIVE_IMAGE_DIR)
REPRESENTATIVE_FEATURE_DIR_PATH = os.path.join(PROJECT_ROOT, REPRESENTATIVE_FEATURE_DIR)
BACKUP_CSV_PATH_FULL = os.path.join(PROJECT_ROOT, BACKUP_CSV_PATH)


def get_df():
    if not os.path.exists(ATTENDANCE_CSV_PATH):
        raise FileNotFoundError(f"Attendance CSV not found: {ATTENDANCE_CSV_PATH}")
    return pd.read_csv(ATTENDANCE_CSV_PATH)

def save_df(df):
    # Create backup before saving
    try:
        if os.path.exists(ATTENDANCE_CSV_PATH): # Check if original exists before backup
            shutil.copy(ATTENDANCE_CSV_PATH, BACKUP_CSV_PATH_FULL)
            print(f"Backup of attendance data created at {BACKUP_CSV_PATH_FULL}")
    except Exception as e:
        print(f"Error creating backup: {e}. Save operation will continue but backup failed.")
        # Decide if you want to halt saving if backup fails. For now, it continues.

    df.to_csv(ATTENDANCE_CSV_PATH, index=False)
    print(f"Changes saved to {ATTENDANCE_CSV_PATH}")


def load_representative_features():
    """Loads all representative .npy feature files."""
    features = {}
    if not os.path.exists(REPRESENTATIVE_FEATURE_DIR_PATH):
        print(f"[WARNING] Representative feature directory not found: {REPRESENTATIVE_FEATURE_DIR_PATH}")
        return features
    
    print(f"Loading features from: {REPRESENTATIVE_FEATURE_DIR_PATH}")
    for fname in os.listdir(REPRESENTATIVE_FEATURE_DIR_PATH):
        if fname.endswith(".npy"):
            person_id = fname.replace(".npy", "")
            try:
                features[person_id] = np.load(os.path.join(REPRESENTATIVE_FEATURE_DIR_PATH, fname))
            except Exception as e:
                print(f"Error loading feature for {person_id}: {e}")
    print(f"Loaded {len(features)} representative features.")
    return features

def get_all_unique_person_ids(df=None):
    if df is None:
        df = get_df()
    return sorted(list(df['person_id'].unique()))

def get_person_details(person_id, df=None):
    if df is None:
        df = get_df()
    
    person_records = df[df['person_id'] == person_id]
    if person_records.empty:
        return None
        
    image_filename = f"{person_id}.jpg"
    # Path for web serving should be relative to static folder or an absolute URL if served differently
    # For now, let's assume a /static/representative_persons/ route will be set up
    image_url = f"/static/representative_persons/{image_filename}" 
    
    # Check if actual image file exists
    if not os.path.exists(os.path.join(REPRESENTATIVE_IMAGE_DIR_PATH, image_filename)):
        image_url = None # Or a placeholder image URL

    attendance_dates = sorted(list(person_records['date_attended'].unique()))
    num_attendance_days = len(attendance_dates)
    first_seen = attendance_dates[0] if attendance_dates else None
    last_seen = attendance_dates[-1] if attendance_dates else None

    return {
        "person_id": person_id,
        "image_url": image_url, # This will need to be served by Flask
        "num_attendance_days": num_attendance_days,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "attendance_summary": f"Attended {num_attendance_days} days. First: {first_seen}, Last: {last_seen}."
    }


def suggest_potential_merges(df=None, features=None):
    if df is None:
        df = get_df()
    if features is None:
        features = load_representative_features()

    if not features:
        return []

    unique_ids = get_all_unique_person_ids(df)
    suggestions = []
    processed_ids = set()

    for i in range(len(unique_ids)):
        id1 = unique_ids[i]
        if id1 in processed_ids or id1 not in features:
            continue

        feature1 = features[id1].reshape(1, -1)
        current_group = {id1}

        for j in range(i + 1, len(unique_ids)):
            id2 = unique_ids[j]
            if id2 in processed_ids or id2 not in features:
                continue
            
            feature2 = features[id2].reshape(1, -1)
            similarity = cosine_similarity(feature1, feature2)[0][0]

            if similarity >= SUGGEST_MERGE_SIMILARITY_THRESHOLD:
                current_group.add(id2)
        
        if len(current_group) > 1:
            group_list = sorted(list(current_group))
            suggestions.append({
                "group": group_list,
                "similarity_reference_id": id1, # Could add more detailed similarity scores later
                "reason": f"High similarity (>{SUGGEST_MERGE_SIMILARITY_THRESHOLD:.2f}) starting with {id1}"
            })
            processed_ids.update(group_list)
            
    return suggestions


def merge_person_ids_action(ids_to_merge, canonical_id):
    df = get_df()
    
    # Validate inputs
    if not canonical_id in ids_to_merge:
        raise ValueError("Canonical ID must be one of the IDs to merge.")
    if not all(pid in df['person_id'].unique() for pid in ids_to_merge):
        missing_ids = [pid for pid in ids_to_merge if pid not in df['person_id'].unique()]
        raise ValueError(f"Some person IDs not found in current data: {missing_ids}")

    print(f"Merging IDs {ids_to_merge} into {canonical_id}...")
    for old_id in ids_to_merge:
        if old_id != canonical_id:
            df.loc[df['person_id'] == old_id, 'person_id'] = canonical_id
            print(f"Replaced {old_id} with {canonical_id}")
    
    # Re-aggregate attendance
    print("Re-aggregating daily attendance...")
    daily_attendance = {}
    for _, row in df.iterrows():
        person_id_val = row['person_id']
        day_date = str(row['date_attended']).split(' ')[0] 
        current_files = set(f.strip() for f in str(row['source_filenames']).split(','))
        key = (person_id_val, day_date)
        if key not in daily_attendance:
            daily_attendance[key] = set()
        daily_attendance[key].update(current_files)
    
    new_records = []
    for (person_id_val, day_date), filenames in daily_attendance.items():
        new_records.append({
            'person_id': person_id_val,
            'date_attended': day_date,
            'source_filenames': ", ".join(sorted(list(filenames)))
        })
    new_df = pd.DataFrame(new_records)
    new_df = new_df.sort_values(by=['person_id', 'date_attended']).reset_index(drop=True)
    
    save_df(new_df) # This also handles backup

    # Delete merged files
    print("Cleaning up representative images and features for non-canonical IDs...")
    for old_id in ids_to_merge:
        if old_id != canonical_id:
            # Delete image
            img_path = os.path.join(REPRESENTATIVE_IMAGE_DIR_PATH, f"{old_id}.jpg")
            if os.path.exists(img_path):
                try:
                    os.remove(img_path)
                    print(f"Deleted image: {img_path}")
                except Exception as e:
                    print(f"Error deleting image {img_path}: {e}")
            # Delete feature
            feature_path = os.path.join(REPRESENTATIVE_FEATURE_DIR_PATH, f"{old_id}.npy")
            if os.path.exists(feature_path):
                try:
                    os.remove(feature_path)
                    print(f"Deleted feature file: {feature_path}")
                except Exception as e:
                    print(f"Error deleting feature file {feature_path}: {e}")
    
    return {"message": f"Successfully merged IDs into {canonical_id}. Data saved.", "new_person_count": len(new_df['person_id'].unique())}

if __name__ == '__main__':
    # For basic testing of utility functions
    print("Testing merge_utils.py...")
    # test_df = get_df()
    # print(f"Loaded df with {len(test_df)} records.")
    # unique_ids_test = get_all_unique_person_ids(test_df)
    # print(f"Found {len(unique_ids_test)} unique IDs.")
    # if unique_ids_test:
    #     print("Details for first ID:", get_person_details(unique_ids_test[0], test_df))
    
    # features_test = load_representative_features()
    # suggestions_test = suggest_potential_merges(test_df, features_test)
    # print(f"\nFound {len(suggestions_test)} merge suggestions:")
    # for i, sug in enumerate(suggestions_test):
    #     print(f"Suggestion {i+1}: {sug['group']} (Reason: {sug['reason']})")
    pass