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

# Configure logging
logging.basicConfig(level=logging.INFO)
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

    def test_01_upload_class_photo(self):
        """Test uploading a class photo from Instagram URL."""
        # Upload the image directly from Instagram URL
        data = {
            'image_url': self.instagram_url,
            'date': datetime.now().isoformat(),
            'caption': 'Test BJJ Class Photo'
        }
        
        # Upload using the URL
        response = requests.post(
            f"{self.base_url}/api/images/upload",
            data=data  # Send as form data
        )
        
        self.assertEqual(response.status_code, 201)  # Expect 201 Created
        result = response.json()
        self.assertIn('image_id', result)
        TestEndToEnd.image_id = result['image_id']  # Store at class level
        logger.info(f"Uploaded class photo with ID {self.image_id}")

    def test_02_check_face_processing(self):
        """Test that face detection and processing completed successfully."""
        self.assertIsNotNone(TestEndToEnd.image_id, "No image ID from previous test")
        
        # Wait for processing to complete (max 30 seconds)
        max_retries = 30
        retry_count = 0
        processing_complete = False
        
        while retry_count < max_retries and not processing_complete:
            # Get image status
            response = requests.get(f"{self.base_url}/api/images/{TestEndToEnd.image_id}/detections")
            self.assertEqual(response.status_code, 200)
            result = response.json()
            
            # Check if processing is complete
            if result['image_info']['processing_status'] == 'completed':
                processing_complete = True
                TestEndToEnd.detections = result['detections']
                break
            
            # Wait 1 second before retrying
            time.sleep(1)
            retry_count += 1
        
        self.assertTrue(processing_complete, "Face processing did not complete within 30 seconds")
        
        # Check for exactly 18 faces
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
            response = requests.post(
                f"{self.base_url}/api/detections/{detection['detection_id']}/reassign_to_new_person",
                json={}
            )
            
            self.assertEqual(response.status_code, 200)
            result = response.json()
            self.assertIn('new_person_id', result)
            new_person_id = result['new_person_id']
            
            # Then, update the person's name
            response = requests.post(
                f"{self.base_url}/api/persons/{new_person_id}/update",
                json={'name': f'Test Person {i}'}
            )
            
            self.assertEqual(response.status_code, 200)
            logger.info(f"Created and named new person 'Test Person {i}' for detection {detection['detection_id']}")

    def test_04_verify_attendance(self):
        """Test verifying the recorded attendance."""
        self.assertTrue(len(TestEndToEnd.detections) > 0, "No detections from previous test")
        self.assertEqual(len(TestEndToEnd.detections), 18, "Must have exactly 18 detections to verify")
        
        # Get the attendance record for the class
        response = requests.get(
            f"{self.base_url}/api/images/{TestEndToEnd.image_id}/attendance"
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