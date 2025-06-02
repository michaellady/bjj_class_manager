"""
End-to-end test script for the BJJ attendance system.
Tests the entire pipeline from image upload to face detection and attendance tracking.
"""
import os
import sys
import logging
import unittest
from datetime import datetime
import requests
import json
import time
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# Configure logging - set level based on DEBUG env var
log_level = logging.DEBUG if os.environ.get('DEBUG') == '1' else logging.INFO
logging.basicConfig(level=log_level, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TestEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test environment."""
        # Instagram post URL
        cls.instagram_url = "https://www.instagram.com/p/DKPhEPfRJ6U/?img_index=1"
        
        # Base URL for the Flask application
        cls.base_url = os.environ.get('BASE_URL', 'http://localhost:5001')
        logger.info(f"Using base URL: {cls.base_url}")
        
        # Store test data at class level
        cls.image_id = None
        cls.detections = []
        
        # Create a session with retry logic
        cls.session = requests.Session()
        retries = Retry(
            total=15,  # Increase retries
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )
        cls.session.mount('http://', HTTPAdapter(max_retries=retries))
        cls.session.mount('https://', HTTPAdapter(max_retries=retries))
        
        # Print diagnostic information
        logger.info("------- TEST ENVIRONMENT -------")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Working directory: {os.getcwd()}")
        logger.info(f"Test timeout: {os.environ.get('TEST_TIMEOUT', '120')} seconds")
        logger.info(f"Debug mode: {os.environ.get('DEBUG', '0')}")
        logger.info(f"Base URL: {cls.base_url}")
        
        # Wait for the Flask app to be available
        if not cls._wait_for_flask_app():
            logger.error("Flask app is not available, skipping tests")
            sys.exit(1)
    
    @classmethod
    def _wait_for_flask_app(cls):
        """Wait for Flask app to be available."""
        max_attempts = 30
        for attempt in range(max_attempts):
            try:
                logger.info(f"Checking if Flask app is available (attempt {attempt+1}/{max_attempts})...")
                # Add timeout parameter to avoid hanging indefinitely
                response = cls.session.get(f"{cls.base_url}/health", timeout=5)
                
                # Log the response status and content regardless
                logger.info(f"Health check status code: {response.status_code}")
                try:
                    content = response.text
                    logger.info(f"Health check response content: {content[:200]}...")
                    
                    # Try to parse as JSON
                    try:
                        json_data = response.json()
                        logger.info(f"Health check JSON data: {json.dumps(json_data, indent=2)}")
                    except:
                        logger.warning("Health check response is not valid JSON")
                        
                except Exception as e:
                    logger.warning(f"Could not get response content: {e}")
                
                if response.status_code == 200:
                    logger.info("Flask app is available!")
                    return True
                elif response.status_code == 500:
                    logger.error("Health check returned 500 Internal Server Error")
                    logger.error("This suggests the app container is running but has an error")
                    # Continue retrying - it might resolve
                
            except requests.exceptions.ConnectionError as e:
                logger.info(f"Connection error to Flask app: {e}")
                logger.info("This suggests the app container is not yet reachable")
            except requests.exceptions.RequestException as e:
                logger.info(f"Flask app not yet available: {e}")
            
            time.sleep(1)
        
        logger.warning(f"Flask app not available after {max_attempts} attempts")
        return False

    def test_01_upload_class_photo(self):
        """Test uploading a class photo from Instagram URL."""
        # Set a longer timeout if TEST_TIMEOUT env var is set
        timeout = int(os.environ.get('TEST_TIMEOUT', 180))
        logger.info(f"Using timeout of {timeout} seconds for upload request")
        
        # Upload the image directly from Instagram URL to simulate real user experience
        data = {
            'image_url': self.instagram_url,
            'date': datetime.now().isoformat(),
            'caption': 'Test BJJ Class Photo'
        }
        
        logger.info(f"Uploading image from Instagram URL: {self.instagram_url}")
        logger.info("This tests the real user experience of fetching from Instagram")
        
        try:
            # First, try to hit Instagram directly to check availability
            logger.info("Testing Instagram availability...")
            instagram_response = requests.get("https://www.instagram.com", timeout=10)
            logger.info(f"Instagram response status: {instagram_response.status_code}")
        except Exception as e:
            logger.warning(f"Could not reach Instagram: {e}")
        
        try:
            # Upload using the URL
            logger.info("Starting upload request...")
            start_time = time.time()
            
            # Use a longer timeout for this request
            response = self.session.post(
                f"{self.base_url}/api/images/upload",
                data=data,  # Send as form data
                timeout=timeout
            )
            
            elapsed_time = time.time() - start_time
            logger.info(f"Upload request completed in {elapsed_time:.2f} seconds")
            
            logger.info(f"Upload response status code: {response.status_code}")
            try:
                response_json = response.json()
                logger.info(f"Upload response JSON: {json.dumps(response_json, indent=2)}")
            except Exception as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.info(f"Raw response content: {response.content}")
            
            self.assertEqual(response.status_code, 201)  # Expect 201 Created
            result = response.json()
            self.assertIn('image_id', result)
            TestEndToEnd.image_id = result['image_id']  # Store at class level
            logger.info(f"Uploaded class photo with ID {self.image_id}")
            
        except requests.exceptions.ReadTimeout as e:
            logger.error(f"Request timed out after {timeout} seconds: {e}")
            logger.error("This is likely due to Instagram rate limiting or slow response")
            logger.error("In a production environment, consider implementing a queue system")
            logger.error("or increasing the timeout for Instagram requests")
            raise
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error during upload: {e}")
            logger.error("This could be due to network issues or the server being unreachable")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during upload: {e}")
            raise

    def test_02_check_face_processing(self):
        """Test that face detection and processing completed successfully."""
        self.assertIsNotNone(TestEndToEnd.image_id, "No image ID from previous test")
        
        # Wait for processing to complete (max 60 seconds)
        max_retries = 60
        retry_count = 0
        processing_complete = False
        
        logger.info(f"Checking face processing for image {TestEndToEnd.image_id}")
        
        while retry_count < max_retries and not processing_complete:
            # Get image status
            try:
                logger.info(f"Checking processing status (attempt {retry_count+1}/{max_retries})...")
                response = self.session.get(
                    f"{self.base_url}/api/images/{TestEndToEnd.image_id}/detections",
                    timeout=30  # Increase timeout
                )
                self.assertEqual(response.status_code, 200)
                result = response.json()
                
                # Log processing status
                status = result['image_info']['processing_status']
                logger.info(f"Current processing status: {status}")
                
                # Check if processing is complete
                if status == 'completed':
                    processing_complete = True
                    TestEndToEnd.detections = result['detections']
                    break
                elif status == 'failed':
                    logger.error("Processing failed according to status")
                    self.fail("Image processing failed")
                
            except Exception as e:
                logger.error(f"Error checking processing status: {e}")
            
            # Wait 1 second before retrying
            time.sleep(1)
            retry_count += 1
        
        self.assertTrue(processing_complete, "Face processing did not complete within 60 seconds")
        
        # Check for exactly 18 faces
        logger.info(f"Found {len(TestEndToEnd.detections)} faces in the image")
        self.assertEqual(len(TestEndToEnd.detections), 18, 
                        f"Expected 18 faces but found {len(TestEndToEnd.detections)}. This image should have exactly 18 faces.")
        logger.info(f"Successfully detected all 18 faces in the class photo")

    def test_03_assign_person_names(self):
        """Test assigning names to detected faces."""
        self.assertTrue(len(TestEndToEnd.detections) > 0, "No detections from previous test")
        self.assertEqual(len(TestEndToEnd.detections), 18, "Must have exactly 18 detections to proceed")
        
        # Create new persons and assign test names to each detection
        for i, detection in enumerate(TestEndToEnd.detections):
            # First, create a new person from the detection
            logger.info(f"Creating new person from detection {detection['detection_id']} ({i+1}/18)")
            response = self.session.post(
                f"{self.base_url}/api/detections/{detection['detection_id']}/reassign_to_new_person",
                json={},
                timeout=30  # Increase timeout
            )
            
            self.assertEqual(response.status_code, 200)
            result = response.json()
            self.assertIn('new_person_id', result)
            new_person_id = result['new_person_id']
            
            # Then, update the person's name
            logger.info(f"Updating name for person {new_person_id} to 'Test Person {i}'")
            response = self.session.post(
                f"{self.base_url}/api/persons/{new_person_id}/update",
                json={'name': f'Test Person {i}'},
                timeout=30  # Increase timeout
            )
            
            self.assertEqual(response.status_code, 200)
            logger.info(f"Created and named new person 'Test Person {i}' for detection {detection['detection_id']}")

    def test_04_verify_attendance(self):
        """Test verifying the recorded attendance."""
        self.assertTrue(len(TestEndToEnd.detections) > 0, "No detections from previous test")
        self.assertEqual(len(TestEndToEnd.detections), 18, "Must have exactly 18 detections to verify")
        
        # Get the attendance record for the class
        logger.info(f"Getting attendance record for image {TestEndToEnd.image_id}")
        response = self.session.get(
            f"{self.base_url}/api/images/{TestEndToEnd.image_id}/attendance",
            timeout=30  # Increase timeout
        )
        
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIn('attendees', result)
        attendees = result['attendees']
        
        # Verify all 18 test persons are present
        self.assertEqual(len(attendees), 18, "Attendance record should have exactly 18 people")
        for i in range(18):
            expected_name = f'Test Person {i}'
            self.assertTrue(
                any(a['name'] == expected_name for a in attendees),
                f"Could not find {expected_name} in attendance"
            )
        
        logger.info("Verified attendance record for all 18 people")

if __name__ == '__main__':
    unittest.main(verbosity=2) 