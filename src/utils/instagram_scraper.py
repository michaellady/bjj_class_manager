"""
Instagram scraper module for BJJ attendance tracking system.
Uses instaloader to fetch posts and extract images and metadata.
"""
import os
import time
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple
import instaloader
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InstagramScraper:
    def __init__(self, download_dir: str = None):
        """
        Initialize the Instagram scraper.
        
        Args:
            download_dir: Directory where to save downloaded images
        """
        self.loader = instaloader.Instaloader(
            download_pictures=True,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=True,
            post_metadata_txt_pattern=''  # Don't save txt files
        )
        
        # Set download directory
        if download_dir:
            self.download_dir = download_dir
        else:
            # Default to project's pictures/incoming folder
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
            self.download_dir = os.path.join(project_root, 'pictures', 'incoming')
            
        os.makedirs(self.download_dir, exist_ok=True)
        logger.info(f"Instagram scraper initialized with download directory: {self.download_dir}")
        
    def extract_shortcode_from_url(self, url: str) -> Optional[str]:
        """
        Extract shortcode from Instagram post URL.
        
        Args:
            url: Instagram post URL
            
        Returns:
            Shortcode string or None if not found
        """
        if not url or 'instagram.com' not in url:
            return None
            
        # Handle different URL formats
        if '/p/' in url:
            # Standard post URL: https://www.instagram.com/p/ABC123/
            parts = url.split('/p/')
            if len(parts) > 1:
                shortcode = parts[1].split('/')[0].split('?')[0]
                return shortcode
                
        return None
        
    def fetch_post(self, url: str) -> Dict:
        """
        Fetch an Instagram post from URL.
        
        Args:
            url: Instagram post URL
            
        Returns:
            Dictionary with post data:
                - success: bool
                - image_path: str, path to downloaded image
                - shortcode: str, post shortcode
                - caption: str, post caption
                - date: datetime, post date
                - username: str, poster's username
                - error: str, error message if any
        """
        start_time = time.time()
        result = {
            "success": False,
            "image_path": None,
            "shortcode": None,
            "caption": None,
            "date": None,
            "username": None,
            "error": None
        }
        
        try:
            shortcode = self.extract_shortcode_from_url(url)
            if not shortcode:
                result["error"] = f"Could not extract shortcode from URL: {url}"
                return result
                
            result["shortcode"] = shortcode
            logger.info(f"Extracted shortcode: {shortcode} from URL: {url}")
            
            # Create temporary download directory specific to this post
            temp_dir = os.path.join(self.download_dir, f"temp_{shortcode}")
            os.makedirs(temp_dir, exist_ok=True)
            
            # Download the post
            logger.info(f"Downloading Instagram post with shortcode: {shortcode}")
            post = instaloader.Post.from_shortcode(self.loader.context, shortcode)
            
            # Save post information
            result["caption"] = post.caption if post.caption else ""
            result["date"] = post.date
            result["username"] = post.owner_username
            
            # Download only the first image (for carousel posts)
            logger.info(f"Downloading media from post {shortcode}")
            
            # Set download directory for this specific download
            self.loader.dirname_pattern = temp_dir
            
            # Download the post
            self.loader.download_post(post, target=shortcode)
            
            # Find the downloaded image file
            downloaded_files = [f for f in os.listdir(temp_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]
            if not downloaded_files:
                result["error"] = "No image files found after download"
                return result
                
            # Sort files to get the first image in case of carousel
            downloaded_files.sort()
            
            # Move the first image to the main download directory
            source_path = os.path.join(temp_dir, downloaded_files[0])
            destination_filename = f"instagram_{shortcode}.jpg"
            destination_path = os.path.join(self.download_dir, destination_filename)
            
            # Copy the file to destination
            import shutil
            shutil.copy2(source_path, destination_path)
            
            # Clean up temporary directory
            shutil.rmtree(temp_dir)
            
            result["image_path"] = destination_path
            result["success"] = True
            logger.info(f"Successfully downloaded Instagram post to {destination_path}")
            logger.info(f"Process took {time.time() - start_time:.2f} seconds")
            
            return result
            
        except instaloader.exceptions.InstaloaderException as e:
            error_msg = f"Instaloader error: {str(e)}"
            logger.error(error_msg)
            result["error"] = error_msg
            return result
            
        except Exception as e:
            error_msg = f"Error fetching Instagram post: {str(e)}"
            logger.error(error_msg)
            result["error"] = error_msg
            return result 