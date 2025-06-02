import os
import cv2
import torch
import numpy as np
from ultralytics import YOLO
import torchreid
from torchreid.reid.utils import FeatureExtractor
from torchvision import transforms

# Load the YOLOv8 model globally for efficiency
yolo_model = YOLO('yolo11x.pt') # Using existing model yolo11x.pt

# Load the ReID model (OSNet)
# You might need to specify a weights path if it's not automatically downloaded
# or if you have a specific pre-trained model file.
try:
    reid_extractor = FeatureExtractor(
        model_name='osnet_x1_0', # Using OSNet, a common ReID model
        model_path=None, # Set to path if you have a .pth file, otherwise it will try to download
        device='cuda' if torch.cuda.is_available() else 'cpu'
    )
    print("[INFO] ReID model loaded successfully.")
except Exception as e:
    print(f"[ERROR] Failed to load ReID model: {e}")
    print("[INFO] Attempting to load ReID model on CPU if CUDA failed or not available.")
    try:
        reid_extractor = FeatureExtractor(
            model_name='osnet_x1_0',
            model_path=None,
            device='cpu'
        )
        print("[INFO] ReID model loaded successfully on CPU.")
    except Exception as e_cpu:
        print(f"[ERROR] Failed to load ReID model on CPU: {e_cpu}")
        reid_extractor = None

def extract_person_features(image_path):
    print(f"[DEBUG] Processing image for feature extraction: {image_path}")
    if not reid_extractor:
        print("[ERROR] ReID extractor not available. Cannot extract features.")
        return []

    try:
        img_cv = cv2.imread(image_path)
        if img_cv is None:
            print(f"[ERROR] Could not read image: {image_path}")
            return []
        img_rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
    except Exception as e:
        print(f"[ERROR] Error reading or converting image {image_path}: {e}")
        return []

    # Run YOLOv8 inference
    yolo_results = yolo_model(image_path, imgsz=1280, conf=0.25, augment=True, classes=[0]) # class 0 is 'person'

    detected_persons_features = []

    # Ensure yolo_results[0] and yolo_results[0].boxes are not None
    if yolo_results and len(yolo_results) > 0 and yolo_results[0].boxes is not None:
        person_boxes = [box for box in yolo_results[0].boxes if int(box.cls) == 0 and box.conf > 0.25]
        print(f"[DEBUG] YOLOv8 detected {len(person_boxes)} people in {os.path.basename(image_path)}")

        cropped_images = []
        original_boxes_coords = []

        for box in person_boxes:
            xyxy = box.xyxy[0].cpu().numpy().astype(int)
            x1, y1, x2, y2 = xyxy
            cropped_person = img_rgb[y1:y2, x1:x2]

            if cropped_person.size == 0:
                print(f"[WARNING] Empty crop for box {xyxy} in {os.path.basename(image_path)}. Skipping.")
                continue
            
            # Convert to PIL Image for ReID model preprocessing
            # The reid_extractor expects a list of image paths or numpy arrays.
            # We'll pass numpy arrays.
            cropped_images.append(cropped_person)
            original_boxes_coords.append(xyxy.tolist())

        if cropped_images:
            try:
                # Extract features in batch if possible
                features = reid_extractor(cropped_images) # Expects list of RGB numpy arrays
                for i, feature_vec in enumerate(features):
                    detected_persons_features.append({
                        "embedding": feature_vec.cpu().numpy(),
                        "bbox_xyxy": original_boxes_coords[i],
                        "cropped_image_np": cropped_images[i] # Add the cropped image NumPy array
                    })
            except Exception as e:
                print(f"[ERROR] Could not extract ReID features for {os.path.basename(image_path)}: {e}")
        
        # Optional: Save the image with bounding boxes for debugging
        debug_output_dir = "debug_output_reid"
        os.makedirs(debug_output_dir, exist_ok=True)
        debug_output_path = os.path.join(debug_output_dir, os.path.basename(image_path))
        
        # Create a plot with the original image and bounding boxes
        # yolo_results[0].plot() creates an image with detections.
        # We need to save this plotted image.
        # The plot() method modifies the image in-place and returns it.
        annotated_img = yolo_results[0].plot()
        cv2.imwrite(debug_output_path, annotated_img) # Save using cv2
        print(f"[DEBUG] Saved debug image with detections to {debug_output_path}")

    else:
        print(f"[DEBUG] No detections or boxes found in {os.path.basename(image_path)}")


    print(f"[DEBUG] Extracted {len(detected_persons_features)} person features from {os.path.basename(image_path)}")
    return detected_persons_features