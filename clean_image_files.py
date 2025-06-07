#!/usr/bin/env python
"""
Script to clean up all image files in the data directories.
This will delete all images in the following directories:
- pictures/incoming
- pictures/processed
- data/face_crops
- data/representative_persons
- data/representative_features
"""
import os
import shutil
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("clean_image_files")

# Project directories
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DIRECTORIES_TO_CLEAN = [
    os.path.join(CURRENT_DIR, 'pictures', 'incoming'),
    os.path.join(CURRENT_DIR, 'pictures', 'processed'),
    os.path.join(CURRENT_DIR, 'data', 'face_crops'),
    os.path.join(CURRENT_DIR, 'data', 'representative_persons'),
    os.path.join(CURRENT_DIR, 'data', 'representative_features'),
]

def clean_directories():
    """Clear all files in the specified directories but keep the directories themselves."""
    total_files_removed = 0
    
    for directory in DIRECTORIES_TO_CLEAN:
        if not os.path.exists(directory):
            logger.warning(f"Directory does not exist: {directory}")
            continue
            
        logger.info(f"Cleaning directory: {directory}")
        
        files_removed = 0
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            
            # Skip directories and .gitkeep files
            if os.path.isdir(file_path) or filename == '.gitkeep' or filename == '.DS_Store':
                continue
                
            try:
                os.remove(file_path)
                files_removed += 1
            except Exception as e:
                logger.error(f"Error removing file {file_path}: {e}")
        
        logger.info(f"Removed {files_removed} files from {directory}")
        total_files_removed += files_removed
    
    logger.info(f"Total files removed: {total_files_removed}")
    return total_files_removed

if __name__ == "__main__":
    logger.info("Starting cleanup of image files")
    total_removed = clean_directories()
    logger.info(f"Cleanup completed. Removed {total_removed} files.") 