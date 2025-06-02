import os
from flask import Flask, jsonify, request, send_from_directory, render_template, current_app
from flask_cors import CORS
import pandas as pd # For specific error handling if needed
from werkzeug.utils import secure_filename
from datetime import datetime 
import requests 
import shutil 
import uuid 
# from bs4 import BeautifulSoup # No longer primary method for Instagram
import json 
import re 
import instaloader # For Instagram scraping
import sqlite3

# Use relative imports as src is treated as a package
from . import data_access as da
from . import attendance_manager as am
from .utils.technique_extractor import TechniqueExtractor

CURRENT_APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_APP_DIR, '..'))
REPRESENTATIVE_IMAGE_DIR_PATH = am.REPRESENTATIVE_IMAGE_DIR

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app) 

UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'pictures', 'incoming') 
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize Instaloader globally - this can take time on first run if it downloads data
# We are not logging in, so capabilities are limited to public posts.
# To avoid downloading files by default, we can configure it.
L = instaloader.Instaloader(
    download_pictures=False, 
    download_videos=False, 
    download_video_thumbnails=False,
    download_geotags=False, 
    download_comments=False, 
    save_metadata=False,
    compress_json=False # We are not saving metadata, but good to set
)

# Initialize technique extractor
technique_extractor = None

def init_technique_extractor():
    global technique_extractor
    if technique_extractor is None:
        technique_extractor = TechniqueExtractor()

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def _get_image_url_from_instagram_post(post_url: str, req_headers: dict):
    """
    Attempts to fetch the direct image URL and metadata from an Instagram post URL using Instaloader.
    Returns a tuple of (image_url, post_date_iso, caption, shortcode) if successful, otherwise None.
    """
    app.logger.info(f"Attempting to fetch Instagram post via Instaloader: {post_url}")
    try:
        # Extract shortcode from URL (e.g., /p/SHORTCODE/ or /reel/SHORTCODE/)
        match = re.search(r"/(?:p|reel)/([^/]+)", post_url)
        if not match:
            app.logger.warning(f"Could not extract shortcode from Instagram URL: {post_url}")
            return None
        shortcode = match.group(1)
        
        app.logger.info(f"Extracted shortcode: {shortcode}")
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        post_date_iso = post.date_utc.isoformat()
        caption = post.caption if post.caption else ""

        if post.is_video:
            app.logger.warning(f"Instagram post {shortcode} is a video. Thumbnail URL: {post.video_url}. We need an image.")
            return post.url, post_date_iso, caption, shortcode

        target_image_url = None
        
        # Check for img_index in the original URL for carousels
        img_index_match = re.search(r"img_index=(\d+)", post_url)
        target_index = 1 # Default to first image
        if img_index_match:
            try:
                target_index = int(img_index_match.group(1))
                if target_index < 1: target_index = 1 # Ensure 1-based index
                app.logger.info(f"Requested img_index: {target_index} for carousel post {shortcode}")
            except ValueError:
                app.logger.warning(f"Invalid img_index in URL: {post_url}. Defaulting to first image.")
        
        current_index = 0
        if post.typename == 'GraphSidecar': # Indicates a carousel
            app.logger.info(f"Post {shortcode} is a carousel. Iterating nodes...")
            nodes = post.get_sidecar_nodes()
            for i, node in enumerate(nodes):
                current_index = i + 1 # 1-based index for user
                if node.is_video:
                    app.logger.info(f"Carousel item {current_index} is a video. Skipping.")
                    continue
                if current_index == target_index:
                    target_image_url = node.display_url
                    app.logger.info(f"Found image at img_index {target_index}: {target_image_url}")
                    break
            if not target_image_url and target_index == 1 and not nodes[0].is_video: # Fallback if index was out of bounds but first is image
                 target_image_url = nodes[0].display_url 
                 app.logger.info(f"img_index {target_index} not found or was video, falling back to first carousel image: {target_image_url}")

        elif not post.is_video: # Single image post
            target_image_url = post.url
            app.logger.info(f"Post {shortcode} is a single image. URL: {target_image_url}")

        if target_image_url:
            return target_image_url, post_date_iso, caption, shortcode
        else:
            app.logger.warning(f"Instaloader could not find a suitable image URL for {shortcode} (target_index: {target_index}).")
            return None
    
    except instaloader.exceptions.InstaloaderException as e:
        app.logger.error(f"Instaloader error for {post_url} (shortcode: {shortcode if 'shortcode' in locals() else 'N/A'}): {e}")
        if "Private Profile" in str(e) or "login required" in str(e).lower():
             app.logger.warning("Instaloader indicated private profile or login required.")
        elif "404 Not Found" in str(e) or "Post not found" in str(e):
             app.logger.warning("Instaloader indicated post not found.")
        return None
    except Exception as e:
        app.logger.error(f"Unexpected error with Instaloader for {post_url}: {e}")
        return None

# --- Error Handling ---
@app.errorhandler(FileNotFoundError)
def handle_file_not_found(error):
    app.logger.error(f"File not found error: {error}")
    return jsonify(error=str(error), message="A required data file was not found on the server."), 404

@app.errorhandler(pd.errors.EmptyDataError)
def handle_empty_data(error):
    app.logger.error(f"Empty data error: {error}")
    return jsonify(error=str(error), message="A data file is empty or unreadable."), 500

@app.errorhandler(KeyError)
def handle_key_error(error):
    app.logger.error(f"Key error (e.g., missing column): {error}")
    return jsonify(error=f"Missing expected data key: {str(error)}", message="Data is missing an expected column or key."), 500

@app.errorhandler(ValueError)
def handle_value_error(error): # For merge validation errors etc.
    app.logger.error(f"Value error: {error}")
    return jsonify(error=str(error), message="Invalid input or data for the requested operation."), 400

@app.errorhandler(Exception)
def handle_generic_exception(error):
    app.logger.error(f"Unhandled exception: {error}")
    return jsonify(error=str(error), message="An unexpected error occurred on the server."), 500

# --- API Endpoints ---
# ... (list_persons, get_single_person_details_route, get_merge_suggestions, merge_persons_route, list_class_images remain the same)

@app.route('/api/persons', methods=['GET'])
def list_persons():
    """Lists all unique persons with their details from the database."""
    try:
        persons_from_db = da.get_all_persons() 
        detailed_persons = []
        for p_dict_row in persons_from_db: 
            p_dict = dict(p_dict_row) 
            p_dict['image_url'] = f"/static/representative_persons/{p_dict['person_id']}.jpg" if p_dict.get('representative_image_path') else None
            detailed_persons.append(p_dict)
        return jsonify(detailed_persons)
    except Exception as e:
        app.logger.error(f"Error in /api/persons: {e}")
        raise e


@app.route('/api/persons/<string:person_id>', methods=['GET'])
def get_single_person_details_route(person_id):
    """Gets details for a specific person from the database."""
    try:
        person_data_row = da.get_person_by_id(person_id)
        if person_data_row:
            person_data = dict(person_data_row) 
            person_data['image_url'] = f"/static/representative_persons/{person_data['person_id']}.jpg" if person_data.get('representative_image_path') else None
            return jsonify(person_data)
        else:
            return jsonify(error="Person not found", message=f"No details found for person ID {person_id}."), 404
    except Exception as e:
        app.logger.error(f"Error in /api/persons/{person_id}: {e}")
        raise e

@app.route('/api/persons/<string:person_id>/attendance_details', methods=['GET'])
def get_person_attendance_details(person_id):
    """
    Retrieves all detection records for a specific person,
    which includes details about the class images they were detected in.
    """
    try:
        person_info = da.get_person_by_id(person_id)
        if not person_info:
            return jsonify(error="Person not found"), 404

        # get_detections_for_person already joins with ClassImages and gets relevant info
        attendance_records_rows = da.get_detections_for_person(person_id)
        
        attendance_records_serializable = []
        for row in attendance_records_rows:
            record_dict = dict(row)
            # Remove or encode feature_vector before sending to frontend
            if 'feature_vector' in record_dict:
                del record_dict['feature_vector'] # Option 1: Omit
                # Option 2: Encode (example, if needed later)
                # import base64
                # record_dict['feature_vector'] = base64.b64encode(record_dict['feature_vector']).decode('utf-8')
            
            if record_dict.get('face_crop_path'):
                record_dict['face_crop_url'] = f"/static_crops/{os.path.basename(record_dict['face_crop_path'])}"
            
            filepath = record_dict.get('filepath_processed')
            original_filename = record_dict.get('original_filename')

            if filepath and isinstance(filepath, str):
                record_dict['main_class_image_url'] = f"/static/incoming_pictures/{os.path.basename(filepath)}"
            elif original_filename and isinstance(original_filename, str):
                record_dict['main_class_image_url'] = f"/static/incoming_pictures/{os.path.basename(original_filename)}"
            else:
                record_dict['main_class_image_url'] = None
                app.logger.warning(f"Could not determine main_class_image_url for detection record: {record_dict.get('detection_id')}, image_id: {record_dict.get('class_image_id')}")
            attendance_records_serializable.append(record_dict)
                
        return jsonify({
            "person_info": dict(person_info), # person_info is already a dict from get_person_by_id
            "attendance_details": attendance_records_serializable
        })
    except Exception as e:
        app.logger.error(f"Error fetching attendance details for person {person_id}: {e}")
        raise e

@app.route('/api/suggestions', methods=['GET'])
def get_merge_suggestions():
    """
    Gets potential merge suggestions.
    """
    try:
        app.logger.info("Attempting to generate merge suggestions from database...")
        raw_suggestion_groups = am.generate_database_merge_suggestions()
        
        detailed_suggestions_for_frontend = []
        if not raw_suggestion_groups:
            app.logger.info("No merge suggestions generated by attendance_manager.")
            return jsonify([])

        for sugg_group_obj in raw_suggestion_groups:
            group_ids = sugg_group_obj.get("group_ids", [])
            group_members_details = []
            for person_id_sugg in group_ids: 
                person_detail_row = da.get_person_by_id(person_id_sugg) 
                if person_detail_row:
                    person_detail_dict = dict(person_detail_row)
                    person_detail_dict['image_url'] = f"/static/representative_persons/{person_id_sugg}.jpg" if person_detail_dict.get('representative_image_path') else None
                    person_detail_dict['attendance_summary'] = f"Enrolled: {person_detail_dict.get('enrollment_date', 'N/A')}"
                    group_members_details.append(person_detail_dict)
            
            if group_members_details and len(group_members_details) > 1: 
                detailed_suggestions_for_frontend.append({
                    "group_members": group_members_details,
                    "reason": sugg_group_obj.get("reason", "High Similarity"),
                })
        
        app.logger.info(f"Returning {len(detailed_suggestions_for_frontend)} detailed merge suggestions to frontend.")
        return jsonify(detailed_suggestions_for_frontend)
    except Exception as e:
        app.logger.error(f"Error in /api/suggestions: {e}")
        raise e

@app.route('/api/merge', methods=['POST'])
def merge_persons_route():
    """Performs a merge operation."""
    data = request.get_json()
    if not data:
        return jsonify(error="Missing data", message="Request body must be JSON."), 400

    ids_to_merge = data.get('ids_to_merge')
    canonical_id = data.get('canonical_id')

    if not ids_to_merge or not isinstance(ids_to_merge, list) or len(ids_to_merge) < 2:
        return jsonify(error="Invalid input", message="'ids_to_merge' must be a list of at least two IDs."), 400
    if not canonical_id or not isinstance(canonical_id, str):
        return jsonify(error="Invalid input", message="'canonical_id' must be a string."), 400
    if canonical_id not in ids_to_merge:
        return jsonify(error="Invalid input", message="'canonical_id' must be one of the 'ids_to_merge'."), 400

    try:
        merge_successful = am.merge_persons_logic(ids_to_merge, canonical_id)
        if merge_successful:
            return jsonify(message=f"Successfully merged IDs into {canonical_id}. Data saved.")
        else:
            return jsonify(error="Merge failed", message="The merge operation failed. Check server logs."), 500
            
    except ValueError as ve: 
        app.logger.warning(f"Validation error during merge: {ve}")
        return jsonify(error=str(ve), message="Merge operation failed due to invalid data or state."), 400
    except Exception as e:
        app.logger.error(f"Error in /api/merge: {e}")
        raise e

@app.route('/api/classimages', methods=['GET'])
def list_class_images():
    """Lists all processed class images, possibly with pagination later."""
    try:
        images_rows = da.get_all_class_images(status='completed') 
        images = [dict(row) for row in images_rows] 
        return jsonify(images)
    except Exception as e:
        app.logger.error(f"Error in /api/classimages: {e}")
        raise e

@app.route('/api/classimages/<image_id>', methods=['DELETE'])
def delete_single_class_image(image_id):
    """Deletes a class image and all its associated data (detections, files)."""
    try:
        # Validate image_id
        try:
            image_id = int(image_id)
        except (TypeError, ValueError):
            return jsonify(error=f"Invalid image ID format: {image_id}"), 400
            
        success, message = am.delete_class_image_and_all_associations(image_id)
        if success:
            return jsonify(message=message), 200
        else:
            if "not found" in message.lower(): # Check if the message indicates "not found"
                return jsonify(error=message), 404
            return jsonify(error=message), 500
    except Exception as e:
        app.logger.error(f"Error deleting class image {image_id}: {e}")
        return jsonify(error=str(e), message="An unexpected error occurred while deleting class image."), 500

@app.route('/api/images/upload', methods=['POST'])
def upload_class_image():
    file = request.files.get('file')
    image_url = request.form.get('image_url')
    saved_image_path = None
    original_filename_for_db = None
    instagram_shortcode = None
    instagram_caption = None
    techniques_data = {"techniques": [], "positions": [], "confidence": 0.0}
    date_taken_to_use = datetime.now().isoformat()  # Default value
    
    app.logger.info(f"Upload attempt: file='{file.filename if file else None}', url='{image_url}'")

    if file and file.filename: 
        if allowed_file(file.filename):
            original_filename_for_db = secure_filename(file.filename)
            saved_image_path = os.path.join(app.config['UPLOAD_FOLDER'], original_filename_for_db)
            try:
                file.save(saved_image_path)
                app.logger.info(f"Image saved from file upload to {saved_image_path}")
            except Exception as e:
                app.logger.error(f"Error saving uploaded file: {e}")
                return jsonify(error=f"Could not save uploaded file: {str(e)}"), 500
        else:
            return jsonify(error="File type not allowed for uploaded file."), 400
    elif image_url:
        download_url_to_try = image_url
        is_instagram_url = "instagram.com/p/" in image_url.lower() or "instagram.com/reel/" in image_url.lower()
        req_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        scraped_date_str = None

        if is_instagram_url:
            app.logger.info(f"Detected Instagram URL: {image_url}. Attempting Instaloader.")
            result = _get_image_url_from_instagram_post(image_url, req_headers)
            if result:
                scraped_img_url, scraped_date_str, caption, instagram_shortcode = result
                download_url_to_try = scraped_img_url
                instagram_caption = caption
                
                # Extract techniques using GPT
                init_technique_extractor()
                if caption and technique_extractor:
                    techniques_data = technique_extractor.extract_techniques(caption)
                    app.logger.info(f"Extracted techniques: {techniques_data}")
                
                app.logger.info(f"Instaloader provided direct image URL: {download_url_to_try}, date: {scraped_date_str}")
            else:
                app.logger.warning(f"Instaloader could not extract direct image from Instagram URL: {image_url}.")
                return jsonify(error=f"Failed to extract image from Instagram URL: {image_url}. Post might be private, video-only, or an unsupported format."), 400
        
        # Proceed to download from download_url_to_try
        try:
            app.logger.info(f"Attempting to download image from final URL: {download_url_to_try}")
            response = requests.get(download_url_to_try, stream=True, timeout=15, headers=req_headers)
            response.raise_for_status() 

            content_type = response.headers.get('content-type')
            if not content_type or not content_type.startswith('image/'):
                app.logger.warning(f"URL content-type not image: {content_type} for URL {download_url_to_try} (original input: {image_url})")
                error_message = "URL does not appear to point to a direct image or content type is not image."
                if is_instagram_url : # If it was an IG url, the message from instaloader failure is more relevant
                     error_message = f"The URL (possibly from Instagram: {download_url_to_try}) did not provide a direct image content type."
                return jsonify(error=error_message, received_content_type=content_type, attempted_url=download_url_to_try), 400

            url_path_part = requests.utils.urlparse(download_url_to_try).path
            base_name = os.path.basename(url_path_part)
            
            filename_stem = f"downloaded_image_{uuid.uuid4().hex[:8]}" 
            file_ext_to_use = 'jpg' 

            if base_name and '.' in base_name:
                 temp_stem, temp_ext = base_name.rsplit('.', 1)
                 temp_ext = temp_ext.lower()
                 if temp_ext in ALLOWED_EXTENSIONS:
                     filename_stem = temp_stem
                     file_ext_to_use = temp_ext
            
            if file_ext_to_use not in ALLOWED_EXTENSIONS:
                guessed_ext_from_content = content_type.split('/')[-1].lower()
                if guessed_ext_from_content in ['jpeg', 'jpg', 'png']:
                    file_ext_to_use = guessed_ext_from_content
            
            original_filename_for_db = secure_filename(f"{filename_stem}.{file_ext_to_use}")
            if not original_filename_for_db: 
                 original_filename_for_db = f"downloaded_image_{uuid.uuid4().hex[:8]}.{file_ext_to_use}"

            saved_image_path = os.path.join(app.config['UPLOAD_FOLDER'], original_filename_for_db)
            with open(saved_image_path, 'wb') as f:
                shutil.copyfileobj(response.raw, f)
            app.logger.info(f"Image saved from URL to {saved_image_path}")
            del response
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Error downloading image from URL {download_url_to_try}: {e}")
            return jsonify(error=f"Could not download image from URL: {str(e)}"), 400
        except Exception as e:
            app.logger.error(f"Generic error processing URL {download_url_to_try}: {e}")
            return jsonify(error=f"An error occurred processing the URL: {str(e)}"), 500
    else:
        return jsonify(error="No file or image URL provided in the request."), 400

    if not saved_image_path or not original_filename_for_db:
         return jsonify(error="Image could not be saved or filename could not be determined."), 500

    # Determine date_taken_to_use
    if is_instagram_url and scraped_date_str:
        try:
            # Validate/reformat if necessary
            datetime.fromisoformat(scraped_date_str.replace('Z', '+00:00'))
            date_taken_to_use = scraped_date_str
            app.logger.info(f"Using Instagram post date: {date_taken_to_use}")
        except ValueError:
            app.logger.warning(f"Scraped Instagram date '{scraped_date_str}' not valid ISO, falling back to current time.")
            date_taken_to_use = datetime.now().isoformat()

    try:
        # First, add the image to the database to get the image_id
        image_id = da.add_class_image(
            original_filename=original_filename_for_db,
            date_taken=date_taken_to_use,
            filepath_processed=saved_image_path,
            processing_status='pending',
            instagram_shortcode=instagram_shortcode,
            instagram_caption=instagram_caption,
            instagram_post_url=image_url if is_instagram_url else None
        )

        if not image_id:
            if os.path.exists(saved_image_path): os.remove(saved_image_path)
            return jsonify(error="Failed to record image in database"), 500

        # Now store techniques and positions
        conn = sqlite3.connect(da.DB_FILE)
        cursor = conn.cursor()
        
        # Store techniques
        for technique in techniques_data.get('techniques', []):
            formatted_technique = technique_extractor.format_technique_name(technique) if technique_extractor else technique
            # Insert technique if it doesn't exist
            cursor.execute("""
            INSERT OR IGNORE INTO Techniques (name, category, last_updated)
            VALUES (?, 'technique', CURRENT_TIMESTAMP)
            """, (formatted_technique,))
            
            # Get technique_id
            cursor.execute("SELECT technique_id FROM Techniques WHERE name = ?", (formatted_technique,))
            technique_id = cursor.fetchone()[0]
            
            # Link technique to image with confidence
            cursor.execute("""
            INSERT INTO ClassTechniques (class_image_id, technique_id, confidence, extraction_method)
            VALUES (?, ?, ?, 'gpt')
            """, (image_id, technique_id, techniques_data.get('confidence', 0.9)))

        # Store positions
        for position in techniques_data.get('positions', []):
            formatted_position = technique_extractor.format_technique_name(position) if technique_extractor else position
            # Insert position if it doesn't exist
            cursor.execute("""
            INSERT OR IGNORE INTO Techniques (name, category, last_updated)
            VALUES (?, 'position', CURRENT_TIMESTAMP)
            """, (formatted_position,))
            
            # Get position_id
            cursor.execute("SELECT technique_id FROM Techniques WHERE name = ?", (formatted_position,))
            position_id = cursor.fetchone()[0]
            
            # Link position to image with confidence
            cursor.execute("""
            INSERT INTO ClassTechniques (class_image_id, technique_id, confidence, extraction_method)
            VALUES (?, ?, ?, 'gpt')
            """, (image_id, position_id, techniques_data.get('confidence', 0.9)))

        conn.commit()
        conn.close()

        # Trigger image processing
        app.logger.info(f"Triggering processing for image_id: {image_id}, path: {saved_image_path}")
        processing_success = am.process_new_class_image(image_id, saved_image_path, date_taken_to_use)
        
        if not processing_success:
            return jsonify(error="Image acquired but processing failed. Check server logs.", image_id=image_id), 500

        return jsonify(
            message="Image acquired and processing initiated.",
            image_id=image_id,
            filename=original_filename_for_db,
            techniques=techniques_data.get('techniques', []),
            positions=techniques_data.get('positions', []),
            confidence=techniques_data.get('confidence', 0.0)
        ), 201

    except Exception as e:
        app.logger.error(f"Error during DB logging or processing trigger: {e}")
        if saved_image_path and os.path.exists(saved_image_path): os.remove(saved_image_path)
        return jsonify(error=f"An error occurred: {str(e)}"), 500

@app.route('/api/images/<int:image_id>/detections', methods=['GET'])
def get_image_detections(image_id):
    """Gets all detections for a specific class image."""
    try:
        image_info_row = da.get_class_image_by_id(image_id)
        if not image_info_row:
            return jsonify(error="Image not found"), 404
        image_info = dict(image_info_row)
        
        detections_rows = da.get_detections_for_image(image_id)
        detections = []
        for row in detections_rows:
            det = dict(row)
            # Remove binary feature vector from response
            if 'feature_vector' in det:
                del det['feature_vector']
            if det.get('face_crop_path'):
                crop_filename = os.path.basename(det['face_crop_path'])
                det['face_crop_url'] = f"/static_crops/{crop_filename}"
            detections.append(det)

        return jsonify({
            "image_info": image_info, 
            "detections": detections
        })
    except Exception as e:
        app.logger.error(f"Error fetching detections for image {image_id}: {e}")
        return jsonify(error=str(e), message="An unexpected error occurred on the server."), 500

@app.route('/api/images/<int:image_id>/attendance', methods=['GET'])
def get_class_attendance(image_id):
    """Gets attendance record for a specific class image."""
    try:
        image_info = da.get_class_image_by_id(image_id)
        if not image_info:
            return jsonify(error="Image not found", message=f"No image found with ID {image_id}."), 404

        # Get all detections for this image
        detections = da.get_detections_for_image(image_id)
        
        # Get person details for each detection
        attendees = []
        for detection in detections:
            if detection.get('person_id'):
                person = da.get_person_by_id(detection['person_id'])
                if person:
                    attendee = dict(person)
                    # Remove binary data
                    if 'feature_vector' in attendee:
                        del attendee['feature_vector']
                    attendees.append(attendee)

        return jsonify({
            'image_info': dict(image_info),
            'attendees': attendees
        })
    except Exception as e:
        app.logger.error(f"Error getting attendance for image {image_id}: {e}")
        return jsonify(error=str(e), message="An unexpected error occurred on the server."), 500

# --- API Endpoints for Verification and Correction ---

@app.route('/api/detections/<int:detection_id>/verify', methods=['POST']) # Or PUT
def verify_detection(detection_id):
    """Marks a detection as verified by the user."""
    current_detection_row = da.get_detection_by_id(detection_id)
    if not current_detection_row:
        return jsonify(error="Detection not found"), 404
    current_detection = dict(current_detection_row)

    try:
        success = da.update_detection_assignment(
            detection_id=detection_id,
            new_person_id=current_detection['person_id'], 
            is_verified=True
        )
        if success:
            updated_detection_row = da.get_detection_by_id(detection_id)
            return jsonify(message="Detection verified successfully.", detection=dict(updated_detection_row) if updated_detection_row else None)
        else:
            return jsonify(error="Failed to verify detection."), 500
    except Exception as e:
        app.logger.error(f"Error verifying detection {detection_id}: {e}")
        return jsonify(error=str(e), message="An error occurred during verification."), 500

@app.route('/api/detections/<int:detection_id>/correct', methods=['POST']) # Or PUT
def correct_detection_assignment(detection_id):
    """Corrects the person_id assigned to a detection."""
    data = request.get_json()
    if not data or 'new_person_id' not in data:
        return jsonify(error="Missing new_person_id in request body"), 400
    
    new_person_id = data.get('new_person_id') 
    if new_person_id == "NONE_OR_UNKNOWN": 
        new_person_id = None

    current_detection_row = da.get_detection_by_id(detection_id)
    if not current_detection_row:
        return jsonify(error="Detection not found"), 404
    current_detection = dict(current_detection_row)

    if new_person_id and not da.get_person_by_id(new_person_id):
        app.logger.warning(f"Attempting to correct detection {detection_id} to non-existent person_id {new_person_id}. This assumes person will be created or ID is valid.")

    try:
        success = da.update_detection_assignment(
            detection_id=detection_id,
            new_person_id=new_person_id,
            is_verified=True, 
            original_assigned_person_id_to_set=current_detection['person_id'] 
        )
        if success:
            updated_detection_row = da.get_detection_by_id(detection_id)
            return jsonify(message="Detection assignment corrected successfully.", detection=dict(updated_detection_row) if updated_detection_row else None)
        else:
            return jsonify(error="Failed to correct detection assignment."), 500
    except Exception as e:
        app.logger.error(f"Error correcting detection {detection_id}: {e}")
        return jsonify(error=str(e), message="An error occurred during correction."), 500

@app.route('/api/detections/<int:detection_id>/reassign_to_new_person', methods=['POST'])
def reassign_detection_to_new_person_route(detection_id):
    """
    Creates a new Person from the specified detection and reassigns the detection to this new Person.
    The request body can optionally include 'original_person_id_of_detection' for logging/context.
    """
    data = request.get_json()
    original_person_id_on_page = data.get('original_person_id_of_detection') if data else None
    
    app.logger.info(f"Attempting to reassign detection {detection_id} to a new person. Original person context from student page: {original_person_id_on_page}")

    try:
        success, message, new_person_id_or_none = am.reassign_detection_to_new_person(detection_id, original_person_id_on_page)
        if success:
            # Fetch the updated detection to include in the response, similar to /correct endpoint
            updated_detection_data = {}
            if new_person_id_or_none: # If a new person was created and detection reassigned
                updated_detection_row = da.get_detection_by_id(detection_id)
                if updated_detection_row:
                    updated_detection_data = dict(updated_detection_row)
                    if 'feature_vector' in updated_detection_data:
                        del updated_detection_data['feature_vector'] # Remove bytes before jsonify
                    
                    # Add face_crop_url if needed by frontend for immediate update
                    if updated_detection_data.get('face_crop_path'):
                        updated_detection_data['face_crop_url'] = f"/static_crops/{os.path.basename(updated_detection_data['face_crop_path'])}"

            return jsonify(message=message, detection_id=detection_id, new_person_id=new_person_id_or_none, updated_detection=updated_detection_data), 200
        else:
            if "not found" in message.lower():
                 return jsonify(error=message, detection_id=detection_id), 404
            return jsonify(error=message, detection_id=detection_id), 500
    except Exception as e:
        app.logger.error(f"Unexpected error reassigning detection {detection_id} to new person: {e}")
        return jsonify(error=str(e), message="An unexpected server error occurred."), 500

# --- Static File Serving ---

# Serve representative images from data/representative_persons
@app.route('/static/representative_persons/<path:filename>')
def serve_representative_image(filename):
    return send_from_directory(REPRESENTATIVE_IMAGE_DIR_PATH, filename)

# Serve face crops from data/face_crops
@app.route('/static_crops/<path:filename>')
def serve_face_crop_image(filename):
    FACE_CROP_DIR_PATH = am.FACE_CROP_DIR 
    return send_from_directory(FACE_CROP_DIR_PATH, filename)

# Serve uploaded class images from pictures/incoming (or wherever they are stored post-upload)
@app.route('/static/incoming_pictures/<path:filename>')
def serve_uploaded_class_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

# --- Instagram and Technique Analysis Endpoints ---

@app.route('/api/instagram/fetch_image', methods=['POST'])
def fetch_instagram_image():
    """Fetch a single Instagram post's image and metadata."""
    try:
        data = request.get_json()
        post_url = data.get('post_url')
        if not post_url:
            return jsonify(error="Missing post_url parameter"), 400

        # Get image URL, date, caption, and shortcode from the post
        result = _get_image_url_from_instagram_post(post_url, {})
        if not result:
            return jsonify(error="Could not fetch data from Instagram post"), 404
            
        image_url, post_date, caption, shortcode = result

        # Initialize technique extractor if needed
        init_technique_extractor()

        # Extract techniques using GPT
        techniques_data = {"techniques": [], "positions": [], "confidence": 0.0}
        if caption and technique_extractor:
            techniques_data = technique_extractor.extract_techniques(caption)

        # Return all the data
        return jsonify({
            'image_url': image_url,
            'post_date': post_date,
            'caption': caption,
            'shortcode': shortcode,
            'techniques': techniques_data.get('techniques', []),
            'positions': techniques_data.get('positions', []),
            'confidence': techniques_data.get('confidence', 0.0)
        })

    except Exception as e:
        app.logger.error(f"Error fetching Instagram data: {e}")
        return jsonify(error=str(e)), 500

@app.route('/api/persons/<string:person_id>/update', methods=['POST'])
def update_person_details(person_id):
    """Updates details for a specific person."""
    data = request.get_json()
    if not data:
        return jsonify(error="Missing data", message="Request body must be JSON."), 400

    try:
        person = da.get_person_by_id(person_id)
        if not person:
            return jsonify(error="Person not found", message=f"No person found with ID {person_id}."), 404

        # Update name if provided
        if 'name' in data:
            success = da.update_person_name(person_id, data['name'])
            if not success:
                return jsonify(error="Update failed", message="Failed to update person name."), 500

        return jsonify(message=f"Successfully updated person {person_id}.")
    except Exception as e:
        app.logger.error(f"Error updating person {person_id}: {e}")
        return jsonify(error=str(e), message="An unexpected error occurred on the server."), 500

if __name__ == '__main__':
    # Make sure to create the 'data/representative_persons' and 'data/representative_features'
    # directories and populate them with some test data if running standalone.
    # Also, ensure 'bjj_attendance.db' exists (run database_setup.py first).
    
    # For development, it's often better to run Flask with `flask run` command
    # after setting FLASK_APP=src.app and FLASK_DEBUG=1 (or FLASK_ENV=development)
    # This provides hot reloading.
    
    # Example:
    # export FLASK_APP=src.app
    # export FLASK_DEBUG=1
    # python -m flask run --port=5001 
    # (Using port 5001 to avoid conflict if other apps use 5000)
    
    app.run(debug=True, port=5001)